#!/usr/bin/env python3
"""Preload PokeAPI cache files via the CacheService descriptors.

This utility walks the national dex, fetches the requested PokéAPI resources,
and writes them into `cache/` using the exact schema emitted by
`CacheService`. It is the fast way to warm every `pokeapi-*` entry so the
frontend never has to touch the public API at runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "pokemon_list.json"
DEFAULT_LIMIT = 1025
RESOURCES = ("pokemon", "species", "evolution", "types")

sys.path.insert(0, str(PROJECT_ROOT))
from src.services.cache_service import get_cache_service  # noqa: E402

POKEAPI_BASE_URL = os.environ.get("POKEMON_API_URL", "https://pokeapi.co/api/v2")
cache_service = get_cache_service()


def parse_resource_arg(raw: str) -> List[str]:
    value = (raw or "").strip().lower()
    if value in {"", "all"}:
        return list(RESOURCES)
    seen: List[str] = []
    for part in value.split(','):
        slug = part.strip().lower()
        if not slug:
            continue
        if slug not in RESOURCES:
            raise argparse.ArgumentTypeError(
                f"Unknown resource '{slug}'. Choose from: {', '.join(RESOURCES)}"
            )
        if slug not in seen:
            seen.append(slug)
    return seen or list(RESOURCES)


def setup_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def load_pokemon_list(session: requests.Session, needed: int) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if DATA_FILE.exists():
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
    if len(entries) >= needed:
        return entries
    fetched = fetch_remote_pokemon_list(session, max(needed, DEFAULT_LIMIT))
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(fetched, handle, indent=2, ensure_ascii=False)
    return fetched


def fetch_remote_pokemon_list(session: requests.Session, limit: int) -> List[Dict[str, Any]]:
    url = f"{POKEAPI_BASE_URL.rstrip('/')}/pokemon?limit={limit}&offset=0"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    pokemon_list: List[Dict[str, Any]] = []
    for idx, entry in enumerate(payload.get("results", []), start=1):
        pokemon_list.append({"number": idx, "name": entry.get("name", f"pokemon-{idx}")})
    return pokemon_list


def fetch_json(session: requests.Session, resource_path: str) -> Dict[str, Any]:
    url = f"{POKEAPI_BASE_URL.rstrip('/')}/{resource_path.lstrip('/')}"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def ensure_cached(
    session: requests.Session,
    endpoint: str,
    params: Dict[str, Any],
    resource_path: str,
    refresh: bool,
) -> Tuple[str, Dict[str, Any]]:
    if not refresh:
        cached = cache_service.get(endpoint, params)
        if cached is not None:
            return "cached", cached
    data = fetch_json(session, resource_path)
    cache_service.set(endpoint, params, data)
    return "fetched", data


def extract_chain_id(species_data: Optional[Dict[str, Any]]) -> Optional[str]:
    if not species_data:
        return None
    chain_info = species_data.get("evolution_chain")
    if not isinstance(chain_info, dict):
        return None
    url = chain_info.get("url")
    if not isinstance(url, str):
        return None
    trimmed = url.rstrip('/').split('/')
    return trimmed[-1] if trimmed else None


def preload_pokemon_entry(
    session: requests.Session,
    pokemon: Dict[str, Any],
    resources: Iterable[str],
    refresh: bool,
) -> Dict[str, str]:
    number = pokemon.get("number")
    name = str(pokemon.get("name", "")).strip() or f"pokemon-{number}"
    statuses: Dict[str, str] = {}
    species_data: Optional[Dict[str, Any]] = None

    if "pokemon" in resources:
        state, _ = ensure_cached(
            session,
            "pokeapi_pokemon",
            {"pokemon": str(number)},
            f"pokemon/{number}",
            refresh,
        )
        statuses["pokemon"] = state

    if "species" in resources or "evolution" in resources:
        state, species_data = ensure_cached(
            session,
            "pokeapi_species",
            {"species": str(number)},
            f"pokemon-species/{number}",
            refresh,
        )
        statuses["species"] = state

    if "evolution" in resources:
        chain_id = extract_chain_id(species_data)
        if chain_id:
            state, _ = ensure_cached(
                session,
                "pokeapi_evolution_chain",
                {"chain": str(chain_id)},
                f"evolution-chain/{chain_id}",
                refresh,
            )
            statuses["evolution"] = state
        else:
            statuses["evolution"] = "skipped"

    return statuses


def preload_types(session: requests.Session, refresh: bool) -> Counter:
    url = f"{POKEAPI_BASE_URL.rstrip('/')}/type"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    stats: Counter = Counter()
    for entry in payload.get("results", []):
        name = entry.get("name")
        if not name:
            continue
        state, _ = ensure_cached(
            session,
            "pokeapi_type",
            {"type": name.lower()},
            f"type/{name}",
            refresh,
        )
        stats[state] += 1
    return stats


def format_status(statuses: Dict[str, str], order: Iterable[str]) -> str:
    parts = []
    for item in order:
        if item in statuses:
            parts.append(f"{item}:{statuses[item]}")
    return ", ".join(parts) if parts else "no-op"


def main() -> None:
    parser = argparse.ArgumentParser(description="Warm the PokéAPI cache via CacheService")
    parser.add_argument("--start", type=int, default=1, help="First dex number to process")
    parser.add_argument("--end", type=int, default=DEFAULT_LIMIT, help="Last dex number to process")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on how many entries to visit")
    parser.add_argument(
        "--resources",
        default="pokemon,species",
        help="Comma-separated list of resources (pokemon,species,evolution,types,all)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh even when cache entries already exist",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Sleep between Pokémon (seconds). Ignored for type-only runs.",
    )
    args = parser.parse_args()
    resources = parse_resource_arg(args.resources)

    if args.start < 1:
        parser.error("--start must be >= 1")
    if args.end < args.start:
        parser.error("--end must be >= --start")

    session = setup_session()
    pokemon_list = load_pokemon_list(session, args.end)

    start_index = args.start - 1
    end_index = min(args.end, len(pokemon_list))
    subset = pokemon_list[start_index:end_index]
    if args.limit is not None:
        subset = subset[: args.limit]

    print(
        f"Preloading resources {resources} for {len(subset)} Pokemon (#{args.start}-#{args.start + len(subset) - 1})"
    )
    if args.refresh:
        print("Refresh mode: existing cache entries will be overwritten")

    stats: Dict[str, Counter] = {res: Counter() for res in resources if res != "types"}
    error_count = 0

    for idx, pokemon in enumerate(subset, start=1):
        try:
            statuses = preload_pokemon_entry(session, pokemon, resources, args.refresh)
            for resource, state in statuses.items():
                if resource in stats:
                    stats[resource][state] += 1
            label = f"#{int(pokemon.get('number', idx)):04d} {str(pokemon.get('name', 'unknown')).title()}"
            print(f"[{idx}/{len(subset)}] {label} -> {format_status(statuses, resources)}")
        except requests.RequestException as exc:
            error_count += 1
            label = f"#{int(pokemon.get('number', idx)):04d}"
            print(f"[{idx}/{len(subset)}] {label} -> ERROR: {exc}")
        if args.delay and idx < len(subset):
            time.sleep(args.delay)

    type_stats: Optional[Counter] = None
    if "types" in resources:
        print("\nPreloading type metadata...")
        try:
            type_stats = preload_types(session, args.refresh)
            print(
                "Type cache -> "
                + ", ".join(f"{key}:{count}" for key, count in sorted(type_stats.items()))
                if type_stats
                else "Type cache -> no-op"
            )
        except requests.RequestException as exc:
            error_count += 1
            print(f"Type preload failed: {exc}")

    print("\nSummary")
    for resource, counter in stats.items():
        if not counter:
            continue
        details = ", ".join(f"{state}:{count}" for state, count in sorted(counter.items()))
        print(f"  {resource}: {details}")
    if type_stats:
        details = ", ".join(f"{state}:{count}" for state, count in sorted(type_stats.items()))
        print(f"  types: {details}")
    if error_count:
        print(f"Errors encountered: {error_count}")
    else:
        print("All requests completed without transport errors.")


if __name__ == "__main__":
    main()
