# Pokemon and TCG Data Pipeline

Six numbered scripts support raw data acquisition, legacy cache conversion,
SQLite catalog builds, and immutable snapshots. SQLite and persistent assets are
the runtime sources; `cache/` is not a catalog source.

| Step | Script | Purpose | Output |
| --- | --- | --- | --- |
| 01 | `scripts/01-download_tcg_cache.py` | Bulk download every Pokémon’s raw TCG response directly from the public API. | Raw JSON snapshots in `tcg-cache/` plus `data/pokemon_list.json`. |
| 02 | `scripts/02-normalize_tcg_cache.py` | Convert historical TCG payloads to the legacy CacheService envelope for diagnostics or migration. | Legacy files in `cache/` or an explicit destination. |
| 03 | `scripts/03-preload_pokeapi_cache.py` | Legacy utility for warming API-response cache files; not required by normal SQLite-backed detail routes. | Disposable `pokeapi-*` files in `cache/`. |
| 04 | `scripts/04-cache_tcg_images.py` | Cache every unique official card image and build the exact NumPy cosine index. | Images in `tcg-image-cache/images/` and runtime artifacts in `tcg-image-cache/index/`. |
| 05 | `scripts/05-import_sqlite.py` | Normalize raw Pokemon/TCG seeds, type effectiveness, and asset metadata into the runtime catalog. | `data/pokedex.sqlite3` and registered assets. |
| 06 | `scripts/06-create_snapshot.py` | Archive immutable raw seed inputs and their checksums. | Versioned snapshot under the configured data root. |

## Step 01 – Download raw caches

`scripts/01-download_tcg_cache.py` pulls API responses and stores them verbatim under `tcg-cache/` using deterministic filenames (`tcg-<dex>-<slug>.json`). Highlights:

- Resumable by default (`--skip-existing` is on) so reruns only fetch missing Pokémon.
- Supports ranges (`--start`, `--end`, `--limit`), parallelism (`--parallel 1-10`), and multi-pass retries (`--max-retries`).
- Accepts `POKEMON_TCG_API_KEY` via `.env` or environment variable for higher rate limits.

Quick commands:

```bash
# Full dataset (1-1025) with resume mode
python scripts/01-download_tcg_cache.py

# First 10 Pokémon only (useful for testing)
python scripts/01-download_tcg_cache.py --limit 10

# Parallelized Kanto run with aggressive retry budget
python scripts/01-download_tcg_cache.py --start 1 --end 151 --parallel 5 --max-retries 8
```

Outputs:

1. `tcg-cache/` containing raw API payloads (cached forever so you keep an archive).
2. `data/pokemon_list.json` with the full dex listing (auto-fetched the first time).

## Step 02 – Normalize for the app

`scripts/02-normalize_tcg_cache.py` consumes historical raw files and emits the
legacy CacheService envelope. Current TCG catalog handlers do not read these
files; use this utility only for migration, diagnostics, or compatibility work.

- Default behavior: write normalized copies into `cache/` while leaving `tcg-cache/` untouched.
- Use `--in-place` if you truly want to rewrite the originals.
- Automatically renames files to `tcg-<dex>-<slug>.json` when the dex number is known (disable with `--no-rename`).
- Works on individual files, folders, or the entire `tcg-cache/` directory; `--dry-run` + `--verbose` shows the plan.

Quick commands:

```bash
# Preview the normalization plan for the entire archive
python scripts/02-normalize_tcg_cache.py tcg-cache --dry-run --verbose

# Normalize everything and copy into cache/
python scripts/02-normalize_tcg_cache.py tcg-cache --verbose

# Normalize a single file but keep it in tcg-cache/
python scripts/02-normalize_tcg_cache.py tcg-cache/tcg-002-ivysaur.json --in-place --verbose
```

Outputs land in `cache/` unless overridden. They do not replace the SQLite import
performed by Step 05.

## Step 03 – Preload PokeAPI caches

`scripts/03-preload_pokeapi_cache.py` is retained for legacy response-cache
testing. Normal Pokemon, species, evolution, and type routes now read SQLite, so
preloading those JSON files is not part of application startup or deployment.

Highlights:

- Honors cache hits unless `--refresh` is supplied, making it safe to rerun.
- Supports dex windows (`--start`, `--end`, `--limit`) so you can warm only the regions you care about.
- Lets you pick resources (`--resources pokemon,species,evolution`) and adds a global type sweep when `types` is included.
- Reuses the same descriptor logic as the Flask proxy, producing files like `pokeapi-0001-bulbasaur.json` automatically.

Quick commands:

```bash
# Hydrate pokemon + species caches for the entire dex
python scripts/03-preload_pokeapi_cache.py

# Refresh the first 151 entries, including evolution chains
python scripts/03-preload_pokeapi_cache.py --end 151 --resources pokemon,species,evolution --refresh

# Warm type metadata only
python scripts/03-preload_pokeapi_cache.py --resources types
```

## Step 04 – Cache card images and build the NumPy index

`scripts/04-cache_tcg_images.py` reads the Step 01 JSON archive, deduplicates cards by ID, downloads each official card image once, and encodes every valid image with the same shared Pillow/NumPy encoder used by the Flask scanner endpoint.

- Resumes by validating and skipping existing images unless `--refresh` is supplied.
- Retries failed downloads and records cards that could not be indexed in `tcg-image-cache/index/failures.json`.
- Writes normalized `float32` vectors in row-for-row alignment with `cards.json`.
- Writes an encoder version and source fingerprint to `manifest.json` so stale or incompatible indexes fail clearly.
- Supports separate download and rebuild passes with `--download-only` and `--index-only`.

Quick commands:

```bash
# Cache every unique card and build the production index
python scripts/04-cache_tcg_images.py

# Validate the pipeline with a small subset
python scripts/04-cache_tcg_images.py --limit 25 --parallel 4

# Rebuild vectors after an encoder change without downloading again
python scripts/04-cache_tcg_images.py --index-only
```

The downloaded `images/` directory is a rebuildable local cache and is ignored by Git. The smaller `vectors.npy`, `cards.json`, and `manifest.json` files under `index/` are the runtime artifacts used by the **NumPy full catalog** scanner mode.

## Step 05 – Build the SQLite catalog

`scripts/05-import_sqlite.py` reads `seeds/pokeapi/` and `seeds/tcg/`, normalizes
Pokemon, species, evolution chains, all six type-damage relation groups, TCG
sets/cards/latest prices, and asset metadata, then atomically promotes a validated
`data/pokedex.sqlite3`.

```bash
python scripts/05-import_sqlite.py
```

## Step 06 – Snapshot raw seeds

`scripts/06-create_snapshot.py` archives the reproducible raw seed inputs. It
deliberately excludes derived runtime response caches.

```bash
python scripts/06-create_snapshot.py --compress
```

## FAQ

- **Do I need every step every time?** No. Use Steps 01 and the PokeAPI seed tooling to refresh raw inputs, Step 04 when scanner images/indexes change, Step 05 to rebuild SQLite, and Step 06 to preserve source snapshots. Steps 02 and 03 are legacy utilities.
- **Where do I set the TCG API key?** Add `POKEMON_TCG_API_KEY=...` to `.env` or export it in your shell before running Step 01.
- **Can I normalize third-party files?** Yes—pass any path(s) to Step 02; it detects names, rebuilds params, and outputs the canonical schema.

Runtime reads come from SQLite and persistent asset directories. Raw archives
remain rebuild inputs; `cache/` remains disposable API-response acceleration.
