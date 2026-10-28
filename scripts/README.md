# Seed Preparation, Backup Bundles, and Restore

Raw responses, media, the asset manifest, and embeddings live under `seeds/`;
no database seed is needed. Downloaded data is not installed automatically.
Script 03's apply mode installs catalog rows. Script 07, or
**Settings > Backup and Restore**, installs category ZIPs.

| Order | Script | Purpose and default output |
| --- | --- | --- |
| 01 | `01-download_raw_pokemontcgapi_to_seed.py` | Raw TCG responses in `seeds/tcg/`; shared dex input in `seeds/pokemon_list.json`. |
| 02 | `02-download_raw_pokeapi_to_seed.py` | Raw Pokemon, species, evolution, and type responses in `seeds/pokeapi/`. |
| 03 | `03-import_seed_catalog.py` | Validate raw metadata in disposable storage; optionally SQL-merge into the runtime catalog. No seed database. |
| 04 | `04-download_raw_pokeapi_and_pokemontcgapi_assets_to_seed.py` | Raw JSON to validated media under `seeds/prepared/data/assets/` plus portable `seeds/prepared/asset-manifest.json`; no database. |
| 05 | `05-build_tcg_image_embeddings.py` | Offline NumPy embeddings, card mapping, manifest, and failure report under `seeds/prepared/data/index/`. |
| 06 | `06-create_seed_backup_bundles.py` | One admin-compatible ZIP per category under `seeds/backup-bundles/`. |
| 07 | `07-import_seed_backup_bundles.py` | Verify ZIPs, then optionally restore them using the admin panel's `BackupService`. |
| 08 | `08-create_snapshot.py` | Checksummed seed workspace snapshot, including media, manifests, and embeddings, excluding derived SQLite artifacts. |

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
The `pokemon` resource also saves species-listed alternate forms so the catalog
can be regenerated offline. Rerun script 02 for older archives missing these
form files; existing raw responses are reused unless `--refresh` is supplied.
The raw seeds contain metadata and URLs, not downloaded image/audio bytes.

## 03: Validate and import the runtime catalog

```powershell
.\.venv\Scripts\python.exe .\scripts\03-import_seed_catalog.py
# After stopping the target server:
.\.venv\Scripts\python.exe .\scripts\03-import_seed_catalog.py --apply --server-stopped
```

The importer normalizes species, forms, evolution chains, type relations, TCG
sets/cards/prices, and asset references in disposable storage outside seeds.
It matches form references by name or stable PokeAPI ID, so a renamed form
does not require another download when its response is already present.
Default behavior validates only and does not create/change the runtime target.
Applying uses transactional SQL inserts/updates, retaining destination-only data,
settings, valid local assets, and accounts. No catalog ZIP is produced.

The default is offline: incomplete raw archives fail explicitly.
`--allow-network` permits fetching missing form/evolution metadata for that run.
`--target-root` selects runtime storage; `--pokeapi-dir` and `--tcg-dir` select
raw inputs. Temporary normalization is cleaned up even after failure. Script 03
is not a prerequisite for scripts 04–06, but import the runtime catalog before
installing media so portable registrations have matching target rows.

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
hashes, media types, owner IDs, kinds, source URLs, and portable paths are recorded
in `seeds/prepared/asset-manifest.json`, not SQLite. `--pokeapi-dir` and
`--tcg-dir` override the raw input directories.
Existing registered files are reused; failed downloads make the command fail.
Bulk downloads can involve tens of thousands of files.

## 05: Build TCG image embeddings

```powershell
.\.venv\Scripts\python.exe .\scripts\05-build_tcg_image_embeddings.py
```

This step makes no network requests. It reads TCG seed records and images
registered in the asset manifest, verifies hashes, applies the shared encoder,
and produces the aligned `vectors.npy`, `cards.json`, and `manifest.json`.
Missing/corrupt card images fail the build by default. `--allow-partial` explicitly
permits omissions, recorded in `failures.json`; `--limit` is useful for tests.
The admin panel and scanner call this category **TCG image embeddings**.

## 06: Create admin-compatible category ZIPs

```powershell
# Three asset categories and embeddings; no catalog database
.\.venv\Scripts\python.exe .\scripts\06-create_seed_backup_bundles.py

# Package only artwork
.\.venv\Scripts\python.exe .\scripts\06-create_seed_backup_bundles.py --components pokemon_images

# Explicitly add real accounts/collections from an existing database
.\.venv\Scripts\python.exe .\scripts\06-create_seed_backup_bundles.py --users-database .\data\users.sqlite3
```

The last command takes an online SQLite snapshot in disposable storage;
it does not modify the source database. No accounts are invented, and the live
accounts database is never selected implicitly. Missing selected categories fail
packaging rather than producing empty backups.

| Admin panel category | Component key | ZIP filename prefix |
| --- | --- | --- |
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
Catalog database exports remain available in the admin panel; they are not seed
items and script 06 rejects that category. Use script 03 to recreate the catalog.

Prepared data and generated ZIPs are ignored by Git. Account bundles contain
sensitive personal/account data: protect them and do not commit or publish them.

## 07: Verify or install seed ZIPs

```powershell
# Verification only: newest ZIP for media and embeddings, not databases
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py

# Select only categories being installed
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py --components tcg_images

# After stopping the target Flask/Gunicorn server, actually restore
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py --apply --server-stopped
```

Default category selection excludes both databases. Explicit admin/older catalog
ZIP imports remain supported and SQL-merged. Accounts require explicit selection.
Combined admin-exported ZIPs are supported by
passing their paths explicitly:

```powershell
.\.venv\Scripts\python.exe .\scripts\07-import_seed_backup_bundles.py .\seeds\backup-bundles\my-admin-export.pokedex-backup.zip
```

Add `--apply --server-stopped` only when ready to import the categories printed
by verification. `--target-root` selects another local/persistent data root.
Every ZIP is verified before a batch changes any target files; catalog bundles
are restored before asset bundles. Duplicate categories in explicit ZIPs are
rejected. Filesystem failures during installation are surfaced; a multi-ZIP batch
is not one cross-file transaction.

Catalog imports use transactional SQL inserts/updates, never replacement of the
destination database file. Destination-only records and relationships are not
deleted. Matching metadata uses its refresh timestamp (the API update timestamp
for sets); prices use the provider's source update date. Newer values win; ties
or unknown dates preserve existing values while filling missing rows when the
source is not older. Existing catalog settings and valid local asset
registrations/files are retained. Generated row IDs are remapped by their
logical identities, so attacks, prices, evolution links, and other relations
cannot attach to unrelated destination rows. A failed SQL merge rolls back.
An absent catalog is initialized and populated through the same SQL path.

An embeddings-only import replaces the index files without opening either
database. **Accounts are different:** explicitly importing `users_database`
still replaces the separate accounts database; accounts/collections are not
merged.

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

This snapshots `seeds/` except derived SQLite artifacts and generated
`seeds/backup-bundles/` ZIPs, which are already transferable admin backups. It
archives the `pokeapi/`, `tcg/`, and (when present) `prepared/` folders, plus
root-level seed files such as `pokemon_list.json`. It therefore includes raw API
JSON, the asset manifest, downloaded assets, and embeddings. Derived SQLite
databases and sidecars are excluded. Files are listed
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
