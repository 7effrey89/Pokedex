#!/usr/bin/env python3
"""
Test script to verify TCG cache download functionality
This validates the cache file structure without making real API calls
"""

import json
import sys
import os
import hashlib
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.download_tcg_cache import get_cache_key, save_tcg_cache


def test_cache_key_generation():
    """Test that cache key generation works correctly"""
    print("Testing cache key generation...")
    
    endpoint = "https://api.pokemontcg.io/v2/cards"
    params = {"q": "name:pikachu"}
    
    cache_key = get_cache_key(endpoint, params)
    
    # Verify it's a 32-character MD5 hash
    assert len(cache_key) == 32, f"Expected 32-char hash, got {len(cache_key)}"
    assert cache_key.isalnum(), "Cache key should be alphanumeric"
    
    # Verify consistent results
    cache_key2 = get_cache_key(endpoint, params)
    assert cache_key == cache_key2, "Cache key should be consistent"
    
    print(f"  ✓ Cache key: {cache_key}")
    print("  ✓ Cache key generation works correctly")


def test_cache_file_structure():
    """Test that cache files have correct structure"""
    print("\nTesting cache file structure...")
    
    # Create test cache directory
    test_cache_dir = Path("test-tcg-cache")
    test_cache_dir.mkdir(exist_ok=True)
    
    # Mock response data
    mock_response = {
        "data": [
            {
                "id": "base1-58",
                "name": "Pikachu",
                "types": ["Lightning"],
                "hp": "60"
            }
        ],
        "page": 1,
        "pageSize": 250,
        "count": 1,
        "totalCount": 1
    }
    
    # Test parameters
    endpoint = "https://api.pokemontcg.io/v2/cards"
    params = {"q": "name:pikachu"}
    pokemon_number = 25
    pokemon_name = "pikachu"
    
    # Temporarily change TCG_CACHE_DIR for testing
    import scripts.download_tcg_cache as script_module
    original_cache_dir = script_module.TCG_CACHE_DIR
    script_module.TCG_CACHE_DIR = test_cache_dir
    
    try:
        # Save test cache file
        filepath = save_tcg_cache(
            pokemon_number, pokemon_name,
            mock_response, endpoint, params
        )
        
        print(f"  ✓ Created test file: {filepath.name}")
        
        # Verify file exists
        assert filepath.exists(), "Cache file should exist"
        
        # Load and verify structure
        with open(filepath, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Verify required fields
        required_fields = ["endpoint", "params", "cache_key", "cached_at", "response"]
        for field in required_fields:
            assert field in cache_data, f"Missing required field: {field}"
        
        print(f"  ✓ All required fields present: {required_fields}")
        
        # Verify field types and values
        assert cache_data["endpoint"] == endpoint, "Endpoint mismatch"
        assert cache_data["params"] == params, "Params mismatch"
        assert isinstance(cache_data["cache_key"], str), "cache_key should be string"
        assert len(cache_data["cache_key"]) == 32, "cache_key should be MD5 hash"
        assert isinstance(cache_data["cached_at"], (int, float)), "cached_at should be numeric"
        assert cache_data["cached_at"] > 0, "cached_at should be positive timestamp"
        assert cache_data["response"] == mock_response, "Response data mismatch"
        
        print("  ✓ Field types and values correct")
        
        # Verify filename format
        expected_pattern = f"tcg-{pokemon_number:03d}-{pokemon_name}-"
        assert filepath.name.startswith(expected_pattern), f"Filename should start with {expected_pattern}"
        assert filepath.name.endswith(".json"), "Filename should end with .json"
        
        print(f"  ✓ Filename format correct: {filepath.name}")
        
        # Verify cache_key matches CacheService algorithm
        expected_key = get_cache_key(endpoint, params)
        assert cache_data["cache_key"] == expected_key, "cache_key should match algorithm"
        
        print(f"  ✓ cache_key matches CacheService algorithm")
        
    finally:
        # Restore original cache dir
        script_module.TCG_CACHE_DIR = original_cache_dir
        
        # Cleanup test files
        for f in test_cache_dir.glob("*.json"):
            f.unlink()
        test_cache_dir.rmdir()
        print("  ✓ Cleaned up test files")


def test_pokemon_list_format():
    """Test that pokemon_list.json has correct format"""
    print("\nTesting Pokemon list format...")
    
    pokemon_list_file = Path("data/pokemon_list.json")
    assert pokemon_list_file.exists(), "pokemon_list.json should exist"
    
    with open(pokemon_list_file, 'r', encoding='utf-8') as f:
        pokemon_list = json.load(f)
    
    # Verify it's a list
    assert isinstance(pokemon_list, list), "Pokemon list should be a list"
    
    # Verify length
    assert len(pokemon_list) == 1025, f"Expected 1025 Pokemon, got {len(pokemon_list)}"
    
    # Verify first entry format
    first_pokemon = pokemon_list[0]
    assert "number" in first_pokemon, "Pokemon should have 'number' field"
    assert "name" in first_pokemon, "Pokemon should have 'name' field"
    assert first_pokemon["number"] == 1, "First Pokemon should be #1"
    assert first_pokemon["name"] == "bulbasaur", "First Pokemon should be Bulbasaur"
    
    # Verify last entry
    last_pokemon = pokemon_list[-1]
    assert last_pokemon["number"] == 1025, "Last Pokemon should be #1025"
    
    print(f"  ✓ Pokemon list has {len(pokemon_list)} entries")
    print(f"  ✓ First: #{first_pokemon['number']} {first_pokemon['name']}")
    print(f"  ✓ Last: #{last_pokemon['number']} {last_pokemon['name']}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("TCG Cache Download Script - Test Suite")
    print("=" * 60)
    
    try:
        test_cache_key_generation()
        test_cache_file_structure()
        test_pokemon_list_format()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
