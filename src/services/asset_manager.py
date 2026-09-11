"""Selective local asset hydration for the SQLite catalog.

Downloads only assets the catalog knows about but has not stored locally, so
production never re-fetches an asset it already owns.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from PIL import Image, UnidentifiedImageError

from src.config import get_storage_paths
from src.db.database import SqliteDatabase

logger = logging.getLogger(__name__)

USER_AGENT = "Pokedex-Asset-Manager/1.0"
DOWNLOAD_TIMEOUT_SECONDS = 30

COMPONENTS = {
    "pokemon_images": {
        "label": "Pokemon artwork",
        "table": "pokemon_asset",
        "kinds": ("official_artwork",),
        "media": "image",
    },
    "pokemon_cries": {
        "label": "Pokemon cries",
        "table": "pokemon_asset",
        "kinds": ("cry_latest", "cry_legacy"),
        "media": "audio",
    },
    "tcg_images": {
        "label": "TCG card images",
        "table": "card_asset",
        "kinds": ("large",),
        "media": "image",
    },
}


@dataclass
class AssetJob:
    """Progress for one selective download run."""

    components: List[str]
    total: int = 0
    completed: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    status: str = "running"
    message: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        percent = round(self.completed / self.total * 100, 1) if self.total else 100.0
        return {
            "components": self.components, "total": self.total, "completed": self.completed,
            "downloaded": self.downloaded, "skipped": self.skipped, "failed": self.failed,
            "status": self.status, "message": self.message, "percent": percent,
            "errors": self.errors[-20:],
        }


class AssetManager:
    """Inventories and downloads catalog-registered assets."""

    def __init__(self, database: SqliteDatabase | None = None):
        self.paths = get_storage_paths()
        self.database = database or SqliteDatabase(self.paths.catalog_database)
        self._lock = threading.Lock()
        self._job: Optional[AssetJob] = None
        self._thread: Optional[threading.Thread] = None

    def inventory(self) -> Dict[str, Any]:
        if not self.database.path.is_file():
            return {"available": False, "components": [], "reason": "Catalog database has not been built"}

        connection = self.database.connect(read_only=True)
        try:
            components = [
                self._component_inventory(connection, key, spec)
                for key, spec in COMPONENTS.items()
            ]
        except sqlite3.Error as exc:
            return {"available": False, "components": [], "reason": str(exc)}
        finally:
            connection.close()

        return {
            "available": True,
            "data_root": str(self.paths.data_root),
            "components": components,
            "total_missing": sum(item["missing"] for item in components),
        }

    def _component_inventory(self, connection, key: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        placeholders = ",".join("?" for _ in spec["kinds"])
        row = connection.execute(
            f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN local_path IS NOT NULL AND local_path != '' THEN 1 ELSE 0 END) AS stored,
                   SUM(CASE WHEN (local_path IS NULL OR local_path = '')
                             AND source_url IS NOT NULL AND source_url != '' THEN 1 ELSE 0 END) AS missing
            FROM {spec['table']}
            WHERE asset_kind IN ({placeholders})
            """,
            spec["kinds"],
        ).fetchone()
        directory = self.paths.asset_directories().get(key)
        return {
            "key": key,
            "label": spec["label"],
            "total": int(row["total"] or 0),
            "stored": int(row["stored"] or 0),
            "missing": int(row["missing"] or 0),
            "disk_bytes": None if directory and directory.is_dir() else 0,
        }

    def job_status(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._job.to_dict() if self._job else None

    def start_download(self, components: Iterable[str], limit: int = 0) -> Dict[str, Any]:
        selected = [key for key in components if key in COMPONENTS]
        if not selected:
            raise ValueError("Select at least one valid asset component")

        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("An asset download is already running")
            self._job = AssetJob(components=selected, message="Preparing download")
            self._thread = threading.Thread(
                target=self._run_download, args=(selected, limit), daemon=True
            )
            self._thread.start()
            return self._job.to_dict()

    def _run_download(self, components: List[str], limit: int) -> None:
        job = self._job
        assert job is not None
        try:
            pending = self._pending_assets(components, limit)
            with self._lock:
                job.total = len(pending)
                job.message = f"Downloading {len(pending):,} assets"
            for asset in pending:
                self._download_asset(asset, job)
            with self._lock:
                job.status = "completed"
                job.message = (
                    f"Downloaded {job.downloaded:,} assets"
                    + (f", {job.failed:,} failed" if job.failed else "")
                )
        except Exception as exc:  # surface unexpected failures to the admin UI
            logger.exception("Asset download failed")
            with self._lock:
                job.status = "failed"
                job.message = str(exc)

    def _pending_assets(self, components: List[str], limit: int) -> List[Dict[str, Any]]:
        pending: List[Dict[str, Any]] = []
        connection = self.database.connect(read_only=True)
        try:
            for key in components:
                spec = COMPONENTS[key]
                placeholders = ",".join("?" for _ in spec["kinds"])
                rows = connection.execute(
                    f"""
                    SELECT id, asset_kind, source_url,
                           {'pokemon_id' if spec['table'] == 'pokemon_asset' else 'card_id'} AS owner_id
                    FROM {spec['table']}
                    WHERE asset_kind IN ({placeholders})
                      AND (local_path IS NULL OR local_path = '')
                      AND source_url IS NOT NULL AND source_url != ''
                    ORDER BY owner_id
                    """,
                    spec["kinds"],
                ).fetchall()
                for row in rows:
                    pending.append({
                        "component": key, "table": spec["table"], "media": spec["media"],
                        "id": row["id"], "asset_kind": row["asset_kind"],
                        "source_url": row["source_url"], "owner_id": row["owner_id"],
                    })
        finally:
            connection.close()
        if limit > 0:
            pending = pending[:limit]
        return pending

    def _download_asset(self, asset: Dict[str, Any], job: AssetJob) -> None:
        destination = self._destination(asset)
        try:
            metadata = self._store(asset["source_url"], destination, asset["media"])
        except Exception as exc:
            metadata = None
            logger.warning("Asset download failed for %s: %s", asset["source_url"], exc)

        with self._lock:
            job.completed += 1
            if metadata is None:
                job.failed += 1
                job.errors.append(f"{asset['owner_id']}: {asset['source_url']}")
                return
            job.downloaded += 1

        sha256, media_type, width, height = metadata
        connection = self.database.connect()
        try:
            if asset["table"] == "pokemon_asset":
                connection.execute(
                    """
                    UPDATE pokemon_asset
                    SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ?
                    WHERE id = ?
                    """,
                    (self.paths.relative_to_root(destination), media_type, sha256,
                     width, height, asset["id"]),
                )
            else:
                connection.execute(
                    """
                    UPDATE card_asset
                    SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ?
                    WHERE id = ?
                    """,
                    (self.paths.relative_to_root(destination), media_type, sha256,
                     width, height, asset["id"]),
                )
            connection.commit()
        finally:
            connection.close()

    def _destination(self, asset: Dict[str, Any]) -> Path:
        component = asset["component"]
        owner = str(asset["owner_id"])
        suffix = hashlib.sha1(f"{owner}:{asset['asset_kind']}".encode("utf-8")).hexdigest()[:8]
        if component == "tcg_images":
            safe = "".join(character if character.isalnum() or character in "._-" else "-"
                           for character in owner)
            return self.paths.tcg_images / f"{safe}-{suffix}.img"
        directory = self.paths.cry_assets if component == "pokemon_cries" else self.paths.pokemon_assets
        return directory / f"{owner}-{asset['asset_kind']}-{suffix}.bin"

    def _store(self, url: str, destination: Path, media: str):
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
                temporary.write_bytes(response.read())
            if media == "image":
                metadata = _image_metadata(temporary)
                if metadata is None:
                    return None
            else:
                payload = temporary.read_bytes()
                if not payload:
                    return None
                metadata = (hashlib.sha256(payload).hexdigest(), "audio/ogg", None, None)
            os.replace(temporary, destination)
            return metadata
        finally:
            temporary.unlink(missing_ok=True)


def _image_metadata(path: Path):
    try:
        with Image.open(path) as image:
            width, height = image.size
            media_type = Image.MIME.get(image.format)
            image.verify()
        return hashlib.sha256(path.read_bytes()).hexdigest(), media_type, width, height
    except (OSError, UnidentifiedImageError, ValueError):
        return None


_ASSET_MANAGER: Optional[AssetManager] = None


def get_asset_manager() -> AssetManager:
    global _ASSET_MANAGER
    if _ASSET_MANAGER is None:
        _ASSET_MANAGER = AssetManager()
    return _ASSET_MANAGER
