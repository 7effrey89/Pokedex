"""Versioned backup and restore for the catalog, user data, and local assets.

Backups are ZIP bundles with a manifest describing every file and its SHA-256.
Restores validate the manifest before anything is swapped into place.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.config import get_storage_paths
from src.db.database import SCHEMA_VERSION

logger = logging.getLogger(__name__)

BUNDLE_VERSION = 1
MAX_RESTORE_BYTES = 40 * 1024 * 1024 * 1024

DATABASE_COMPONENTS = {"catalog_database": "catalog_database", "users_database": "users_database"}
DIRECTORY_COMPONENTS = ("pokemon_images", "pokemon_cries", "tcg_images")
COMPONENT_LABELS = {
    "catalog_database": "Catalog database",
    "users_database": "User accounts and collections",
    "pokemon_images": "Pokemon artwork",
    "pokemon_cries": "Pokemon cries",
    "tcg_images": "TCG card images",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackupService:
    """Creates and restores selective backup bundles."""

    def __init__(self):
        self.paths = get_storage_paths()
        self._job_lock = threading.Lock()
        self._job: Dict[str, Any] | None = None
        self._job_thread: threading.Thread | None = None

    def job_status(self) -> Dict[str, Any] | None:
        with self._job_lock:
            return dict(self._job) if self._job else None

    def start_backup(self, components: Iterable[str]) -> Dict[str, Any]:
        selected = [key for key in components if key in COMPONENT_LABELS]
        if not selected:
            raise ValueError("Select at least one component to back up")
        with self._job_lock:
            if self._job_thread and self._job_thread.is_alive():
                raise RuntimeError("A backup is already running")
            self._job = {
                "status": "running", "message": "Preparing backup", "total": 0,
                "completed": 0, "percent": 0, "name": None, "size_bytes": 0,
                "download_url": None, "error": None,
            }
            self._job_thread = threading.Thread(
                target=self._run_backup, args=(selected,), daemon=True
            )
            self._job_thread.start()
            return dict(self._job)

    def _run_backup(self, components: List[str]) -> None:
        try:
            total = self._count_files(components)
            with self._job_lock:
                self._job["total"] = total
                self._job["message"] = f"Backing up {total:,} files"
            bundle = self.create_backup(components, progress=self._update_job)
            with self._job_lock:
                self._job.update({
                    "status": "completed", "message": "Backup ready",
                    "percent": 100, "name": bundle.name,
                    "size_bytes": bundle.stat().st_size,
                    "download_url": f"/api/admin/backup/download/{bundle.name}",
                })
        except Exception as exc:
            logger.exception("Background backup failed")
            with self._job_lock:
                self._job.update({"status": "failed", "message": str(exc), "error": str(exc)})

    def _update_job(self, completed: int) -> None:
        with self._job_lock:
            if self._job:
                total = self._job["total"]
                self._job["completed"] = completed
                self._job["percent"] = round(completed / total * 100, 1) if total else 100

    def _count_files(self, components: Iterable[str]) -> int:
        count = 0
        for key in components:
            if key in DATABASE_COMPONENTS:
                count += 1 if getattr(self.paths, key).is_file() else 0
            else:
                directory = self.paths.asset_directories()[key]
                count += sum(1 for item in directory.rglob("*") if item.is_file()) if directory.is_dir() else 0
        return count

    def available_components(self) -> List[Dict[str, Any]]:
        components = []
        for key in ("catalog_database", "users_database"):
            path = getattr(self.paths, key)
            components.append({
                "key": key, "label": COMPONENT_LABELS[key],
                "available": path.is_file(),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            })
        for key in DIRECTORY_COMPONENTS:
            directory = self.paths.asset_directories()[key]
            available = directory.is_dir() and any(directory.iterdir())
            size_bytes = self._directory_size(directory) if available else 0
            components.append({
                "key": key, "label": COMPONENT_LABELS[key],
                "available": available,
                "size_bytes": size_bytes,
                "size_estimated": True,
            })
        return components

    @staticmethod
    def _directory_size(directory: Path) -> int:
        try:
            return sum(item.stat().st_size for item in directory.rglob("*") if item.is_file())
        except OSError:
            return 0

    def create_backup(self, components: Iterable[str], progress=None) -> Path:
        selected = [key for key in components if key in COMPONENT_LABELS]
        if not selected:
            raise ValueError("Select at least one component to back up")

        self.paths.backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bundle_path = self.paths.backups / f"{stamp}.pokedex-backup.zip"
        manifest: Dict[str, Any] = {
            "bundle_version": BUNDLE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "created_at": utc_now(),
            "components": selected,
            "files": [],
        }

        staging = Path(tempfile.mkdtemp(prefix="pokedex-backup-"))
        try:
            with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for key in selected:
                    if key in DATABASE_COMPONENTS:
                        self._add_database(archive, manifest, key, staging)
                        if progress:
                            progress(len(manifest["files"]))
                    else:
                        self._add_directory(archive, manifest, key, progress)
                archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        except Exception:
            bundle_path.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return bundle_path

    def _add_database(self, archive: zipfile.ZipFile, manifest: Dict[str, Any],
                      key: str, staging: Path) -> None:
        source = getattr(self.paths, key)
        if not source.is_file():
            return
        snapshot = staging / f"{key}.sqlite3"
        source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        target_connection = sqlite3.connect(snapshot)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        entry = f"{key}/{source.name}"
        archive.write(snapshot, entry)
        manifest["files"].append({
            "component": key, "path": entry, "size_bytes": snapshot.stat().st_size,
            "sha256": _file_hash(snapshot),
        })

    def _add_directory(self, archive: zipfile.ZipFile, manifest: Dict[str, Any], key: str, progress=None) -> None:
        directory = self.paths.asset_directories()[key]
        if not directory.is_dir():
            return
        for item in sorted(directory.rglob("*")):
            if not item.is_file():
                continue
            entry = f"{key}/{item.relative_to(directory).as_posix()}"
            archive.write(item, entry)
            manifest["files"].append({
                "component": key, "path": entry, "size_bytes": item.stat().st_size,
                "sha256": _file_hash(item),
            })
            if progress:
                progress(len(manifest["files"]))

    def restore_backup(self, bundle_path: Path, components: Iterable[str] | None = None) -> Dict[str, Any]:
        with zipfile.ZipFile(bundle_path) as archive:
            manifest = self._read_manifest(archive)
            requested = set(components or manifest["components"])
            unknown = requested - set(COMPONENT_LABELS)
            if unknown:
                raise ValueError(f"Unknown components: {', '.join(sorted(unknown))}")

            total_bytes = sum(entry["size_bytes"] for entry in manifest["files"]
                              if entry["component"] in requested)
            if total_bytes > MAX_RESTORE_BYTES:
                raise ValueError("Backup exceeds the maximum restore size")

            staging = Path(tempfile.mkdtemp(prefix="pokedex-restore-"))
            try:
                restored = self._extract_and_verify(archive, manifest, requested, staging)
                self._promote(restored, requested, staging)
            finally:
                shutil.rmtree(staging, ignore_errors=True)

        return {
            "restored_components": sorted(requested),
            "file_count": len([entry for entry in manifest["files"]
                               if entry["component"] in requested]),
            "created_at": manifest.get("created_at"),
        }

    def _read_manifest(self, archive: zipfile.ZipFile) -> Dict[str, Any]:
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except KeyError as exc:
            raise ValueError("Backup is missing manifest.json") from exc
        if manifest.get("bundle_version") != BUNDLE_VERSION:
            raise ValueError(f"Unsupported bundle version {manifest.get('bundle_version')}")
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"Backup schema version {manifest.get('schema_version')} "
                f"does not match supported version {SCHEMA_VERSION}"
            )
        return manifest

    def _extract_and_verify(self, archive: zipfile.ZipFile, manifest: Dict[str, Any],
                            requested: set, staging: Path) -> List[Dict[str, Any]]:
        restored = []
        for entry in manifest["files"]:
            if entry["component"] not in requested:
                continue
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Rejected unsafe path in backup: {entry['path']}")
            destination = (staging / relative).resolve()
            destination.relative_to(staging.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry["path"]) as source, open(destination, "wb") as target:
                shutil.copyfileobj(source, target)
            if _file_hash(destination) != entry["sha256"]:
                raise ValueError(f"Checksum mismatch for {entry['path']}")
            restored.append(entry)
        return restored

    def _promote(self, restored: List[Dict[str, Any]], requested: set, staging: Path) -> None:
        self.paths.ensure_directories()
        for key in requested:
            if key in DATABASE_COMPONENTS:
                staged = next((staging / entry["path"] for entry in restored
                               if entry["component"] == key), None)
                if staged and staged.is_file():
                    target = getattr(self.paths, key)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(staged, target)
                continue

            directory = self.paths.asset_directories()[key]
            directory.mkdir(parents=True, exist_ok=True)
            for entry in restored:
                if entry["component"] != key:
                    continue
                staged = staging / entry["path"]
                relative = Path(entry["path"]).relative_to(key)
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)

    def list_backups(self) -> List[Dict[str, Any]]:
        if not self.paths.backups.is_dir():
            return []
        bundles = []
        for item in sorted(self.paths.backups.glob("*.pokedex-backup.zip"), reverse=True):
            bundles.append({
                "name": item.name,
                "size_bytes": item.stat().st_size,
                "created_at": datetime.fromtimestamp(item.stat().st_mtime, timezone.utc).isoformat(),
            })
        return bundles


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_BACKUP_SERVICE: BackupService | None = None


def get_backup_service() -> BackupService:
    global _BACKUP_SERVICE
    if _BACKUP_SERVICE is None:
        _BACKUP_SERVICE = BackupService()
    return _BACKUP_SERVICE
