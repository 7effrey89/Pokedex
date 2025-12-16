# Pokemon TCG Cache Pipeline

Two scripts keep offline TCG data in sync with the format this app expects:

| Step | Script | Purpose | Output |
| --- | --- | --- | --- |
| 01 | `scripts/01-download_tcg_cache.py` | Bulk download every Pokémon’s raw TCG response directly from the public API. | Raw JSON snapshots in `tcg-cache/` plus `data/pokemon_list.json`. |
| 02 | `scripts/02-normalize_tcg_cache.py` | Reformat those raw files so they exactly match the CacheService schema. | Canonical files in `cache/` (or in-place when requested). |

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

`scripts/02-normalize_tcg_cache.py` consumes any raw file (legacy, downloader, download-manager, etc.) and emits the exact structure the app’s CacheService expects.

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

Outputs land in `cache/` (unless `--in-place`), so the app can immediately pick them up via `CacheService` while your raw archive remains safely stored in `tcg-cache/`.

## FAQ

- **Do I need both steps every time?** Only when you want fresh data. Run Step 01 to pull new cards; Step 02 whenever you need normalized copies in `cache/`.
- **Where do I set the TCG API key?** Add `POKEMON_TCG_API_KEY=...` to `.env` or export it in your shell before running Step 01.
- **Can I normalize third-party files?** Yes—pass any path(s) to Step 02; it detects names, rebuilds params, and outputs the canonical schema.

That’s it: archive everything in `tcg-cache/`, feed the app via `cache/`, and rerun either script whenever you need updated data.
