# Pokemon TCG Cache Download Script

This script downloads Pokemon TCG API responses for all Pokemon (001-1025) and stores them in a format compatible with the CacheService.

## Features

- Fetches TCG card data for each Pokemon from the Pokemon TCG API
- Uses the same cache key algorithm as CacheService (MD5 hash of endpoint + params)
- Stores responses in CacheService-compatible JSON format
- Includes retry logic for failed requests
- Supports optional API key for higher rate limits
- Allows downloading specific ranges or limiting the number of Pokemon
- Maintains a Pokemon list resource for easy extension

## Usage

### Basic Usage

Download TCG data for all Pokemon (1-1025):

```bash
python scripts/download_tcg_cache.py
```

### Test with Limited Pokemon

Download TCG data for only the first 5 Pokemon:

```bash
python scripts/download_tcg_cache.py --limit 5
```

### Download Specific Range

Download TCG data for Pokemon 1-151 (Generation 1):

```bash
python scripts/download_tcg_cache.py --start 1 --end 151
```

Download TCG data for Pokemon 152-251 (Generation 2):

```bash
python scripts/download_tcg_cache.py --start 152 --end 251
```

### Custom Delay

Add a 2-second delay between requests (be nice to the API):

```bash
python scripts/download_tcg_cache.py --delay 2.0
```

## Options

- `--start NUM` - Start from Pokemon number NUM (default: 1)
- `--end NUM` - End at Pokemon number NUM (default: 1025)
- `--limit NUM` - Limit to NUM Pokemon (useful for testing)
- `--delay SEC` - Delay between requests in seconds (default: 1.0)

## API Key (Optional)

For higher rate limits, you can set the `POKEMON_TCG_API_KEY` environment variable:

```bash
export POKEMON_TCG_API_KEY="your-api-key-here"
python scripts/download_tcg_cache.py
```

Get a free API key at: https://pokemontcg.io/

## Output

The script creates:

1. **tcg-cache/** directory containing cache files
2. **data/pokemon_list.json** - List of all Pokemon with numbers and names

### Cache File Format

Each cache file is named: `tcg-{number}-{name}-{timestamp}.json`

Example: `tcg-025-pikachu-202412160045.json`

### Cache File Structure

Each file contains:

```json
{
  "endpoint": "https://api.pokemontcg.io/v2/cards",
  "params": {
    "q": "name:pikachu"
  },
  "cache_key": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "cached_at": 1702684800.123456,
  "response": {
    "data": [...],
    "page": 1,
    "pageSize": 250,
    "count": 123,
    "totalCount": 123
  }
}
```

This structure matches CacheService's format and can be imported into the main cache directory if needed.

## Pokemon List

The script maintains a `data/pokemon_list.json` file containing all Pokemon with their numbers and names. This file is:

- **Automatically fetched from PokeAPI on first run** - The script will download the complete, accurate list of all 1025 Pokemon names from PokeAPI
- **Cached locally for subsequent runs** - After the first successful fetch, the list is saved and reused
- **Includes placeholder names for Pokemon 152+** in the initial version - These will be replaced with actual names (like "chikorita", "cyndaquil", etc.) when the script runs with internet access
- **Easily extensible** for future Pokemon additions

**Important:** The initial `pokemon_list.json` contains accurate names for Pokemon 1-151 (Generation 1) and placeholders for 152-1025. When you run the script for the first time with internet access, it will automatically fetch and save the complete list with all real Pokemon names from PokeAPI, ensuring TCG searches work correctly.

## Integration with CacheService

The cache files are designed to be compatible with CacheService. To import them:

1. The `cache_key` field matches CacheService's MD5 hash algorithm
2. The file structure includes all required fields: `endpoint`, `params`, `cached_at`, `response`
3. Files can be renamed to `{cache_key}.json` and moved to the `cache/` directory if needed

## Examples

### Download first 10 Pokemon for testing:

```bash
python scripts/download_tcg_cache.py --limit 10
```

Output:
```
ℹ No API key set (using lower rate limits)
  Set POKEMON_TCG_API_KEY environment variable for higher limits

Fetching Pokemon list (1-1025) from PokeAPI...
✓ Fetched 1025 Pokemon
✓ Saved Pokemon list to: data/pokemon_list.json

Processing 10 Pokemon (#1 to #10)
Output directory: tcg-cache

[1/10] #001 Bulbasaur ... ✓ 85 cards - saved to tcg-001-bulbasaur-202412160045.json
[2/10] #002 Ivysaur ... ✓ 32 cards - saved to tcg-002-ivysaur-202412160046.json
...
```

## Notes

- The script is rate-limit friendly with a default 1-second delay between requests
- Failed requests are retried automatically (up to 3 times with exponential backoff)
- The Pokemon list is cached locally to avoid repeated PokeAPI calls
- Each run creates new timestamped files (no overwriting)
