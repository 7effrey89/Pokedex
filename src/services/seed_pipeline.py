"""Prepare portable seed data without modifying the running application's storage."""

import os
import sqlite3
import logging
import tempfile
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from src.config import PROJECT_ROOT, get_storage_paths
from src.config.paths import StoragePaths
from src.db.importer import SqliteImporter
from src.services.backup_service import BackupService, COMPONENT_LABELS
from src.services.catalog_merge import merge_catalog
from src.services.seed_assets import download_seed_media, manifest_path, read_seed_manifest

DEFAULT_SEED_ROOT = PROJECT_ROOT / "seeds" / "prepared"
DEFAULT_BUNDLE_DIR = PROJECT_ROOT / "seeds" / "backup-bundles"
SEED_COMPONENTS = {key: label for key, label in COMPONENT_LABELS.items() if key != "catalog_database"}
DEFAULT_COMPONENTS = tuple(key for key in SEED_COMPONENTS if key != "users_database")
logger = logging.getLogger(__name__)


def seed_paths(root: Path) -> StoragePaths:
    paths = StoragePaths(root.resolve())
    if paths.data_root == get_storage_paths().data_root.resolve():
        raise ValueError("Seed preparation must not target the live application data root")
    return paths


def import_seed_catalog(pokeapi: Path, tcg: Path, target: StoragePaths, *,
                        apply: bool = False, allow_network: bool = False) -> dict:
    source_roots = [pokeapi.resolve(), tcg.resolve(), PROJECT_ROOT / "seeds"]
    if pokeapi.resolve().parent == tcg.resolve().parent:
        source_roots.append(pokeapi.resolve().parent)
    if any(target.catalog_database.resolve().is_relative_to(root) for root in source_roots):
        raise ValueError("The runtime catalog target must be outside the seed workspace")
    with tempfile.TemporaryDirectory(prefix="pokedex-seed-import-") as directory:
        temporary = StoragePaths(Path(directory))
        importer = SqliteImporter(
            temporary.data_root, temporary.catalog_database, pokeapi, tcg,
            temporary.data_root / "data" / "assets", allow_network=allow_network,
            download_artwork=False, require_artwork=False, require_card_images=False,
            progress=lambda message: print(message, flush=True),
        )
        summary = importer.build()
        report = merge_catalog(temporary.catalog_database, target) if apply else None
    return {"catalog": asdict(summary), "applied": apply, "catalog_merge": report}


def download_seed_assets(root: Path, components: list[str], limit: int = 0, *,
                         pokeapi: Path | None = None, tcg: Path | None = None) -> dict:
    paths = seed_paths(root)
    return download_seed_media(paths, pokeapi or PROJECT_ROOT / "seeds" / "pokeapi",
                               tcg or PROJECT_ROOT / "seeds" / "tcg", components, limit)


def _snapshot_users(source: Path, target: Path) -> None:
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"User accounts database does not exist: {source}")
    if source == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".sqlite3.snapshot")
    try:
        with closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as original:
            if original.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("User accounts source database failed its integrity check")
            with closing(sqlite3.connect(temporary)) as snapshot:
                original.backup(snapshot)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def create_seed_bundles(
    root: Path, output: Path, components: list[str], *, users_database: Path | None = None,
) -> list[Path]:
    paths = seed_paths(root)
    if not components:
        raise ValueError("Select at least one seed backup category")
    if "catalog_database" in components:
        raise ValueError("Catalog databases are derived, not seed items; use script 03 to import raw seeds")
    unknown = set(components) - set(SEED_COMPONENTS)
    if unknown:
        raise ValueError(f"Unknown components: {', '.join(sorted(unknown))}")
    if "users_database" in components:
        if users_database is None:
            raise ValueError("User accounts require an explicit --users-database source; no seed users are generated")
    service = BackupService(paths)
    media = set(components) & {"pokemon_images", "pokemon_cries", "tcg_images"}
    if media and not manifest_path(paths).is_file():
        raise ValueError("Download seed media with script 04 to create its asset manifest before packaging")
    records = read_seed_manifest(paths) if media else []
    available = {item["key"] for item in service.available_components() if item["available"]}
    missing = set(components) - available - {"users_database"}
    if missing:
        raise ValueError(f"Prepare these categories before packaging: {', '.join(sorted(missing))}")
    bundles = []
    for key in dict.fromkeys(components):
        if key == "users_database":
            with tempfile.TemporaryDirectory(prefix="pokedex-accounts-export-") as directory:
                temporary = StoragePaths(Path(directory))
                _snapshot_users(users_database, temporary.users_database)
                bundles.append(BackupService(temporary).create_backup([key], output_dir=output))
        else:
            bundles.append(service.create_backup([key], output_dir=output, asset_records=records))
    return bundles


def select_seed_bundles(directory: Path, components: list[str]) -> list[Path]:
    latest = {}
    service = BackupService()
    for path in sorted(directory.glob("*.pokedex-backup.zip")):
        manifest = service.inspect_backup(path)
        if len(manifest["components"]) != 1:
            logger.info("Combined backup %s requires an explicit ZIP path, not automatic category selection", path.name)
            continue
        for key in set(manifest["components"]) & set(components):
            candidate = (manifest["created_at"], path)
            if key not in latest or candidate[0] > latest[key][0]:
                latest[key] = candidate
    missing = set(components) - set(latest)
    if missing:
        raise ValueError(f"No seed ZIP found for: {', '.join(sorted(missing))}. Pass combined admin ZIPs explicitly.")
    return list(dict.fromkeys(latest[key][1] for key in components))


def restore_seed_bundles(bundles: list[Path], target: StoragePaths) -> list[dict]:
    if not bundles:
        raise ValueError("Select at least one seed backup ZIP")
    service = BackupService(target)
    manifests = [(path, service.verify_backup(path)) for path in bundles]
    seen = set()
    for _, manifest in manifests:
        duplicate = seen & set(manifest["components"])
        if duplicate:
            raise ValueError(f"Multiple bundles would import the same categories: {', '.join(sorted(duplicate))}")
        seen.update(manifest["components"])
    manifests.sort(key=lambda item: "catalog_database" not in item[1]["components"])
    return [service.restore_backup(path) for path, _ in manifests]
