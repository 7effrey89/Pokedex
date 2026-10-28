# Seed Preparation, Backup Bundles, and Restore

Preparation writes only under `seeds/`. Downloaded source data is not installed
into the running application. Script 07, or **Settings > Backup and Restore**,
is the explicit installation boundary.

| Order | Script | Purpose and default output |
| --- | --- | --- |
| 01 | `01-download_raw_pokemontcgapi_to_seed.py` | Raw TCG responses in `seeds/tcg/`; shared dex input in `seeds/pokemon_list.json`. |
| 02 | `02-download_raw_pokeapi_to_seed.py` | Raw Pokemon, species, evolution, and type responses in `seeds/pokeapi/`. |
| 03 | `03-build_seed_catalog.py` | Normalized catalog at `seeds/prepared/data/pokedex.sqlite3`, without image downloads. |
| 04 | `04-download_raw_pokeapi_and_pokemontcgapi_assets_to_seed.py` | Validated Pokemon artwork/sprites, cries, and TCG card/set images under `seeds/prepared/data/assets/`, registered in the prepared catalog. |
| 05 | `05-build_tcg_image_embeddings.py` | Offline NumPy embeddings, card mapping, manifest, and failure report under `seeds/prepared/data/index/`. |
| 06 | `06-create_seed_backup_bundles.py` | One admin-compatible ZIP per category under `seeds/backup-bundles/`. |
| 07 | `07-import_seed_backup_bundles.py` | Verify ZIPs, then optionally restore them using the admin panel's `BackupService`. |
| 08 | `08-create_snapshot.py` | Optional checksummed snapshot of the seed workspace, including prepared assets and catalog. |

Scripts 01 and 02 are independent. If the raw seeds are already complete, skip
them. Embeddings are optional for ordinary catalog browsing. Other categories
can also be selected individually; not every script must run every time.

## 01–02: Acquire raw API inputs

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe .\scripts\01-download_raw_pokemontcgapi_to_seed.py
.\.venv\Scripts\python.exe .\scripts\02-download_raw_pokeapi_to_seed.py --resources all
```

TCG acquisition accepts `--start`, `--end`, `--limit`, `--parallel`, and
`--max-retries`. Existing seeds are skipped by default; `--no-skip-existing`
redownloads them. `POKEMON_TCG_API_KEY` provides higher upstream rate limits.

PokeAPI acquisition accepts dex ranges, `--resources`, `--delay`, and `--refresh`.
The raw seeds contain metadata and URLs, not downloaded image/audio bytes.

## 03: Build the seed catalog

```powershell
.\.venv\Scripts\python.exe .\scripts\03-build_seed_catalog.py
```

The importer normalizes species, forms, evolution chains, type relations, TCG
sets/cards/prices, and asset references. Missing forms or metadata can be fetched
upstream during preparation. `--no-network` requires a complete raw archive;
it fails rather than silently omitting required forms.

The staged catalog is validated before replacement. Rebuilding retains compatible
registrations for downloaded seed assets and catalog refresh settings.
`--resume` validates a retained failed `.building` catalog. Neither build nor
resume replaces the live catalog or accounts database.

## 04: Download selected seed assets

```powershell
# All three asset categories
.\.venv\Scripts\python.exe .\scripts\04-download_raw_pokeapi_and_pokemontcgapi_assets_to_seed.py

# A small trial run, or just one category
.\.venv\Scripts\python.exe .\scripts\04-download_raw_pokeapi_and_pokemontcgapi_assets_to_seed.py --components tcg_images --limit 25
```

Categories are `pokemon_images`, `pokemon_cries`, and `tcg_images`. The last
includes card faces, set logos, and set symbols. This uses the same asset manager
as the admin download controls, but with seed-only storage paths. Validated files,
hashes, media types, and portable paths are recorded in the prepared catalog.
Existing registered files are reused; failed downloads make the command fail.
Bulk downloads can involve tens of thousands of files.

## 05: Build TCG image embeddings

```powershell
.\.venv\Scripts\python.exe .\scripts\05-build_tcg_image_embeddings.py
```

This step makes no network requests. It reads TCG seed records and images
registered in the prepared catalog, applies the application's shared encoder,
and produces the aligned `vectors.npy`, `cards.json`, and `manifest.json`.
Missing/corrupt card images fail the build by default. `--allow-partial` explicitly
permits omissions, recorded in `failures.json`; `--limit` is useful for tests.
The admin panel and scanner call this category **TCG image embeddings**.

## 06: Create admin-compatible category ZIPs

```powershell
# Catalog, three asset categories, and embeddings
.\.venv\Scripts\python.exe .\scripts\06-create_seed_backup_bundles.py

# Package only the catalog and artwork
.\.venv\Scripts\python.exe .\scripts\06-create_seed_backup_bundles.py --components catalog_database pokemon_images

# Explicitly add real accounts/collections from an existing database
.\.venv\Scripts\python.exe .\scripts\06-create_seed_backup_bundles.py --users-database .\data\users.sqlite3
```

The last command takes an online SQLite snapshot into seed preparation storage;
it does not modify the source database. No accounts are invented, and the live
accounts database is never selected implicitly. Missing selected categories fail
packaging rather than producing empty backups.

| Admin panel category | Component key | ZIP filename prefix |
| --- | --- | --- |
| Catalog database | `catalog_database` | `catalog-database--` |
| User accounts and collections | `users_database` | `user-accounts-and-collections--` |
| Pokemon artwork | `pokemon_images` | `pokemon-artwork--` |
| Pokemon cries | `pokemon_cries` | `pokemon-cries--` |
| TCG card images | `tcg_images` | `tcg-card-images--` |
| TCG image embeddings | `tcg_embeddings` | `tcg-image-embeddings--` |

Every filename ends with a UTC timestamp and `.pokedex-backup.zip`. For example:
`tcg-image-embeddings--20261028T120000000000Z.pokedex-backup.zip`.

The CLI and admin export use the exact same ZIP writer: same bundle/schema
versions, component keys, manifest, paths, file sizes, and SHA-256 checksums.
Timestamps naturally differ between separate exports. Asset registrations travel
with asset bundles so restoring artwork updates SQLite as well as copying files.
Older version-1 bundles without registrations remain readable.

Prepared data and generated ZIPs are ignored by Git. Account bundles contain
sensitive personal/account data: protect them and do not commit or publish them.

## 07: Verify or install seed ZIPs

```powershell
# Verification only: newest single-category ZIP for each non-user category
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py

# Select only categories being installed
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py --components catalog_database tcg_images

# After stopping the target Flask/Gunicorn server, actually restore
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py --apply --server-stopped
```

Automatic category selection excludes accounts unless `--components
users_database` is explicit. Combined admin-exported ZIPs are supported by
passing their paths explicitly:

```powershell
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py .\seeds\backup-bundles\my-admin-export.pokedex-backup.zip
```

Add `--apply --server-stopped` only when ready to replace the categories printed
by verification. `--target-root` selects another local/persistent data root.
Every ZIP is verified before a batch changes any target files; catalog bundles
are restored before asset bundles. Duplicate categories in explicit ZIPs are
rejected. Filesystem failures during installation are surfaced; a multi-ZIP batch
is not one cross-file transaction.

Alternatively, upload any generated ZIP through **Settings > Restore From File**.
Restore imports the categories declared in the uploaded ZIP, not the categories
currently available for export. Embeddings are validated as an aligned unit;
active scanner mappings are released and reloaded after an admin restore.

After a CLI restore, restart the server and refresh the browser. Seed preparation
and ZIP verification alone do not require stopping/restarting the server.

## 08: Optional seed-workspace snapshot

```powershell
.\.venv\Scripts\python.exe .\scripts\08-create_snapshot.py --compress
```

This snapshots the full contents of `seeds/` except the generated
`seeds/backup-bundles/` ZIPs, which are already transferable admin backups. It
archives the `pokeapi/`, `tcg/`, and (when present) `prepared/` folders, plus
root-level seed files such as `pokemon_list.json`. It therefore includes raw API
JSON, the prepared catalog, downloaded assets, and embeddings. Files are listed
with sizes and SHA-256 checksums in `snapshot-manifest.json`. By default, staged
`users.sqlite3` is excluded because it contains private account data;
`--include-users` opts in explicitly.

The output defaults to the configured data root's `snapshots/` directory, not
inside `seeds/`. To repopulate an empty `seeds/` directory, extract the archive
at the `seeds/` root (for example,
`tar -xzf <snapshot-file> -C .\seeds`) so the archived folders and root-level
files return to their expected paths. A snapshot is an archival copy, not an
admin restore ZIP; there is no automatic snapshot-restore command. Alternatively,
use script 06/07 for app-compatible category restore.
