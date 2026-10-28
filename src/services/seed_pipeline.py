"""Prepare portable seed data without modifying the running application's storage."""

import os
import sqlite3
import logging
from contextlib import closing
from pathlib import Path

from src.config import PROJECT_ROOT, get_storage_paths
from src.config.paths import StoragePaths
from src.db.importer import SqliteImporter
from src.services.asset_manager import AssetManager
from src.services.backup_assets import ASSET_TABLES, collect_asset_records, restore_asset_records
from src.services.backup_service import BackupService, COMPONENT_LABELS

DEFAULT_SEED_ROOT = PROJECT_ROOT / "seeds" / "prepared"
DEFAULT_BUNDLE_DIR = PROJECT_ROOT / "seeds" / "backup-bundles"
DEFAULT_COMPONENTS = tuple(key for key in COMPONENT_LABELS if key != "users_database")
logger = logging.getLogger(__name__)


def seed_paths(root: Path) -> StoragePaths:
    paths = StoragePaths(root.resolve())
    if paths.catalog_database == get_storage_paths().catalog_database.resolve():
        raise ValueError("Seed preparation must not target the live application data root")
    return paths


def build_seed_catalog(root: Path, pokeapi: Path, tcg: Path, *, allow_network: bool = True, resume: bool = False):
    paths = seed_paths(root)
    files = [
        {"path": f"{key}/{item.relative_to(directory).as_posix()}"}
        for key, directory in paths.asset_directories().items() if key in ASSET_TABLES
        for item in directory.rglob("*") if item.is_file()
    ]
    records = collect_asset_records(paths, list(ASSET_TABLES), files)
    importer = SqliteImporter(
        paths.data_root, paths.catalog_database, pokeapi, tcg, paths.data_root / "data" / "assets",
        allow_network=allow_network, download_artwork=False, require_artwork=False, require_card_images=False,
        progress=lambda message: print(message, flush=True),
    )
    summary = importer.resume() if resume else importer.build()
    restore_asset_records(paths, {"asset_records": records}, set(ASSET_TABLES))
    return summary


def download_seed_assets(root: Path, components: list[str], limit: int = 0) -> dict:
    paths = seed_paths(root)
    if not paths.catalog_database.is_file():
        raise ValueError("Build the seed catalog with script 03 before downloading seed assets")
    restore_asset_records(paths, {"asset_records": []}, {"catalog_database"})
    return AssetManager(paths=paths).download(components, limit)


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
    unknown = set(components) - set(COMPONENT_LABELS)
    if unknown:
        raise ValueError(f"Unknown components: {', '.join(sorted(unknown))}")
    if "users_database" in components:
        if users_database is None:
            raise ValueError("User accounts require an explicit --users-database source; no seed users are generated")
        _snapshot_users(users_database, paths.users_database)
    service = BackupService(paths)
    available = {item["key"] for item in service.available_components() if item["available"]}
    missing = set(components) - available
    if missing:
        raise ValueError(f"Prepare these categories before packaging: {', '.join(sorted(missing))}")
    return [service.create_backup([key], output_dir=output) for key in dict.fromkeys(components)]


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
            raise ValueError(f"Multiple bundles would replace the same categories: {', '.join(sorted(duplicate))}")
        seen.update(manifest["components"])
    manifests.sort(key=lambda item: "catalog_database" not in item[1]["components"])
    return [service.restore_backup(path) for path, _ in manifests]
