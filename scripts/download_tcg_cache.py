#!/usr/bin/env python3
"""
Download Pokemon TCG API responses for all Pokemon (001-1025)

This script fetches TCG card data for each Pokemon and stores the responses
in the tcg-cache directory. Each response is saved with the same structure
used by CacheService to enable easy migration or import.

The script supports resume functionality - if interrupted, you can restart it
and it will skip Pokemon that have already been cached (unless --no-skip-existing
is specified).

Parallel downloads are supported for faster processing using multiple threads.

Usage:
    python scripts/download_tcg_cache.py [--start NUM] [--end NUM] [--limit NUM]

Options:
    --start NUM             Start from Pokemon number NUM (default: 1)
    --end NUM               End at Pokemon number NUM (default: 1025)
    --limit NUM             Limit to NUM Pokemon (useful for testing)
    --delay SEC             Delay between requests in seconds (default: 1)
    --skip-existing         Skip already-cached Pokemon (default, enables resume)
    --no-skip-existing      Re-download all Pokemon even if cached
    --parallel N            Number of parallel download threads (default: 1, max: 10)
"""

import json
import os
import sys
import time
import hashlib
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Base directories
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TCG_CACHE_DIR = PROJECT_DIR / "tcg-cache"
DATA_DIR = PROJECT_DIR / "data"

# API Configuration
POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"
TCG_API_BASE_URL = "https://api.pokemontcg.io/v2"
TCG_API_ENDPOINT = f"{TCG_API_BASE_URL}/cards"


def get_cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    """
    Generate cache key using the same algorithm as CacheService
    
    Args:
        endpoint: API endpoint URL
        params: Request parameters dict
        
    Returns:
        MD5 hash as cache key
    """
    # Remove None values to normalize cache keys (same as CacheService)
    normalized_params = {k: v for k, v in params.items() if v is not None}
    
    # Create stable string representation (same as CacheService)
    key_data = f"{endpoint}:{json.dumps(normalized_params, sort_keys=True)}"
    
    # Hash it for clean filename
    return hashlib.md5(key_data.encode()).hexdigest()


def setup_session() -> requests.Session:
    """
    Create requests session with retry logic
    
    Returns:
        Configured requests Session
    """
    session = requests.Session()
    
    # Retry strategy for failed requests
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session


def fetch_pokemon_list(session: requests.Session, limit: int = 1025) -> list:
    """
    Fetch Pokemon list from PokeAPI
    
    This function attempts to fetch the complete Pokemon list from PokeAPI.
    On first run with internet access, it will download all 1025 Pokemon names
    and save them to data/pokemon_list.json, replacing any placeholder names.
    
    Args:
        session: Requests session
        limit: Number of Pokemon to fetch (default: 1025)
        
    Returns:
        List of dicts with 'number' and 'name' keys
    """
    print(f"Fetching Pokemon list (1-{limit}) from PokeAPI...")
    
    try:
        url = f"{POKEAPI_BASE_URL}/pokemon?limit={limit}&offset=0"
        response = session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Build list with numbers
        pokemon_list = []
        for idx, pokemon in enumerate(data['results'], start=1):
            pokemon_list.append({
                "number": idx,
                "name": pokemon['name']
            })
        
        print(f"✓ Fetched {len(pokemon_list)} Pokemon")
        return pokemon_list
        
    except Exception as e:
        print(f"✗ Error fetching Pokemon list: {e}")
        # Try to load from cached file
        pokemon_list_file = DATA_DIR / "pokemon_list.json"
        if pokemon_list_file.exists():
            print(f"  Loading from cached file: {pokemon_list_file}")
            with open(pokemon_list_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print("  No cached Pokemon list found. Cannot continue.")
            sys.exit(1)


def save_pokemon_list(pokemon_list: list):
    """
    Save Pokemon list to data directory for future use
    
    Args:
        pokemon_list: List of Pokemon dicts
    """
    DATA_DIR.mkdir(exist_ok=True)
    output_file = DATA_DIR / "pokemon_list.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(pokemon_list, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved Pokemon list to: {output_file}")


def fetch_tcg_data(session: requests.Session, pokemon_name: str, 
                   api_key: Optional[str] = None) -> Optional[Dict]:
    """
    Fetch TCG card data for a Pokemon
    
    Args:
        session: Requests session
        pokemon_name: Name of the Pokemon
        api_key: Optional TCG API key for higher rate limits
        
    Returns:
        API response dict or None if error
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key
    
    params = {"q": f"name:{pokemon_name}"}
    
    try:
        response = session.get(
            TCG_API_ENDPOINT,
            params=params,
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
        
    except requests.RequestException as e:
        print(f"    ✗ Error fetching TCG data: {e}")
        return None


def is_pokemon_cached(pokemon_number: int, pokemon_name: str) -> bool:
    """
    Check if a Pokemon has already been cached
    
    Args:
        pokemon_number: Pokemon national dex number
        pokemon_name: Pokemon name
        
    Returns:
        True if cache file exists for this Pokemon
    """
    if not TCG_CACHE_DIR.exists():
        return False
    
    # Look for any file matching the pattern: tcg-{number}-{name}-*.json
    pattern = f"tcg-{pokemon_number:03d}-{pokemon_name}-*.json"
    matching_files = list(TCG_CACHE_DIR.glob(pattern))
    
    return len(matching_files) > 0


def process_single_pokemon(
    pokemon: Dict[str, Any],
    session: requests.Session,
    api_key: Optional[str],
    skip_existing: bool,
    print_lock: Optional[threading.Lock] = None
) -> Tuple[str, int, int, int]:
    """
    Process a single Pokemon download
    
    Args:
        pokemon: Pokemon dict with 'number' and 'name'
        session: Requests session
        api_key: Optional API key
        skip_existing: Whether to skip already-cached Pokemon
        print_lock: Optional lock for thread-safe printing
        
    Returns:
        Tuple of (status, number, card_count, 0 or 1 for error)
        status: 'success', 'skipped', or 'error'
    """
    number = pokemon['number']
    name = pokemon['name']
    
    # Check if already cached
    if skip_existing and is_pokemon_cached(number, name):
        return ('skipped', number, 0, 0)
    
    # Fetch TCG data
    params = {"q": f"name:{name}"}
    tcg_data = fetch_tcg_data(session, name, api_key)
    
    if tcg_data:
        # Save to cache
        filepath = save_tcg_cache(
            number, name, tcg_data,
            TCG_API_ENDPOINT, params
        )
        
        # Count cards found
        card_count = len(tcg_data.get('data', []))
        
        return ('success', number, card_count, 0)
    else:
        return ('error', number, 0, 1)


def save_tcg_cache(pokemon_number: int, pokemon_name: str, 
                   response_data: Dict, endpoint: str, params: Dict) -> Path:
    """
    Save TCG response to cache file with CacheService-compatible structure
    
    Args:
        pokemon_number: Pokemon national dex number
        pokemon_name: Pokemon name
        response_data: API response data
        endpoint: API endpoint URL
        params: Request parameters
        
    Returns:
        Path to the saved cache file
    """
    # Ensure cache directory exists
    TCG_CACHE_DIR.mkdir(exist_ok=True)
    
    # Generate cache key using CacheService algorithm
    cache_key = get_cache_key(endpoint, params)
    
    # Create timestamp for filename and cached_at field
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y%m%d%H%M")
    cached_at = timestamp.timestamp()
    
    # Build filename: tcg-<number>-<name>-<timestamp>.json
    filename = f"tcg-{pokemon_number:03d}-{pokemon_name}-{timestamp_str}.json"
    filepath = TCG_CACHE_DIR / filename
    
    # Build cache data structure (same as CacheService)
    cache_data = {
        "endpoint": endpoint,
        "params": params,
        "cache_key": cache_key,
        "cached_at": cached_at,
        "response": response_data
    }
    
    # Save to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    return filepath


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Download Pokemon TCG API responses for caching"
    )
    parser.add_argument(
        '--start', type=int, default=1,
        help='Start from Pokemon number (default: 1)'
    )
    parser.add_argument(
        '--end', type=int, default=1025,
        help='End at Pokemon number (default: 1025)'
    )
    parser.add_argument(
        '--limit', type=int, default=None,
        help='Limit to N Pokemon (useful for testing)'
    )
    parser.add_argument(
        '--delay', type=float, default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--skip-existing', dest='skip_existing', action='store_true', default=True,
        help='Skip Pokemon that have already been cached (default: True)'
    )
    parser.add_argument(
        '--no-skip-existing', dest='skip_existing', action='store_false',
        help='Re-download all Pokemon even if already cached'
    )
    parser.add_argument(
        '--parallel', type=int, default=1, metavar='N',
        help='Number of parallel download threads (default: 1, max: 10)'
    )
    
    args = parser.parse_args()
    
    # Validate parallel argument
    if args.parallel < 1:
        args.parallel = 1
    if args.parallel > 10:
        print("⚠ Warning: Limiting parallel threads to 10 to avoid overwhelming the API")
        args.parallel = 10
    
    # Setup
    session = setup_session()
    api_key = os.environ.get("POKEMON_TCG_API_KEY")
    
    if api_key:
        print("✓ Using Pokemon TCG API key")
    else:
        print("ℹ No API key set (using lower rate limits)")
        print("  Set POKEMON_TCG_API_KEY environment variable for higher limits")
    
    print()
    
    # Fetch or load Pokemon list
    pokemon_list = fetch_pokemon_list(session, limit=args.end)
    
    # Save list for future reference
    save_pokemon_list(pokemon_list)
    
    # Filter to requested range
    start_idx = args.start - 1  # Convert to 0-indexed
    end_idx = args.end
    if args.limit:
        end_idx = min(start_idx + args.limit, end_idx)
    
    pokemon_subset = pokemon_list[start_idx:end_idx]
    
    print()
    print(f"Processing {len(pokemon_subset)} Pokemon (#{args.start} to #{min(args.end, start_idx + len(pokemon_subset))})")
    print(f"Output directory: {TCG_CACHE_DIR}")
    if args.skip_existing:
        print(f"Resume mode: Skipping already-cached Pokemon")
    else:
        print(f"Force mode: Re-downloading all Pokemon")
    if args.parallel > 1:
        print(f"Parallel mode: Using {args.parallel} threads")
        print(f"Note: Delay setting is ignored in parallel mode")
    print()
    
    # Statistics
    success_count = 0
    error_count = 0
    skipped_count = 0
    cards_found_count = 0
    
    # Process Pokemon - parallel or sequential
    if args.parallel > 1:
        # Parallel processing with ThreadPoolExecutor
        print_lock = threading.Lock()
        
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            # Submit all tasks
            future_to_pokemon = {
                executor.submit(
                    process_single_pokemon,
                    pokemon,
                    session,
                    api_key,
                    args.skip_existing,
                    print_lock
                ): pokemon for pokemon in pokemon_subset
            }
            
            # Process completed tasks as they finish
            completed = 0
            for future in as_completed(future_to_pokemon):
                pokemon = future_to_pokemon[future]
                completed += 1
                
                try:
                    status, number, card_count, error = future.result()
                    
                    with print_lock:
                        print(f"[{completed}/{len(pokemon_subset)}] #{number:03d} {pokemon['name'].title()}", end=" ... ")
                        
                        if status == 'skipped':
                            print("⊙ Already cached (skipping)")
                            skipped_count += 1
                        elif status == 'success':
                            cards_found_count += card_count
                            print(f"✓ {card_count} cards")
                            success_count += 1
                        else:
                            print("✗ Failed")
                            error_count += 1
                            
                except Exception as e:
                    with print_lock:
                        print(f"[{completed}/{len(pokemon_subset)}] #{pokemon['number']:03d} {pokemon['name'].title()} ... ✗ Exception: {e}")
                        error_count += 1
    else:
        # Sequential processing (original behavior)
        for idx, pokemon in enumerate(pokemon_subset, start=1):
            number = pokemon['number']
            name = pokemon['name']
            
            print(f"[{idx}/{len(pokemon_subset)}] #{number:03d} {name.title()}", end=" ... ")
            
            # Check if already cached
            if args.skip_existing and is_pokemon_cached(number, name):
                print("⊙ Already cached (skipping)")
                skipped_count += 1
                continue
            
            # Fetch TCG data
            params = {"q": f"name:{name}"}
            tcg_data = fetch_tcg_data(session, name, api_key)
            
            if tcg_data:
                # Save to cache
                filepath = save_tcg_cache(
                    number, name, tcg_data,
                    TCG_API_ENDPOINT, params
                )
                
                # Count cards found
                card_count = len(tcg_data.get('data', []))
                cards_found_count += card_count
                
                print(f"✓ {card_count} cards - saved to {filepath.name}")
                success_count += 1
            else:
                print("✗ Failed")
                error_count += 1
            
            # Delay between requests (be nice to the API)
            if idx < len(pokemon_subset):
                time.sleep(args.delay)
    
    # Summary
    print()
    print("=" * 60)
    print(f"Download Complete!")
    print(f"  Success:  {success_count}")
    print(f"  Skipped:  {skipped_count}")
    print(f"  Errors:   {error_count}")
    print(f"  Total cards found: {cards_found_count}")
    print(f"  Cache directory: {TCG_CACHE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
