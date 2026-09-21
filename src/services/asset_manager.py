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
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from PIL import Image, UnidentifiedImageError

from src.config import get_storage_paths
from src.db.database import SqliteDatabase

logger = logging.getLogger(__name__)

USER_AGENT = "Pokedex-Asset-Manager/1.0"
DOWNLOAD_TIMEOUT_SECONDS = 30

POKEMON_SPRITE_STYLES = {
    "official-artwork": ("official_artwork", "other/official-artwork/{id}.png", "image/png"),
    "home": ("home_artwork", "other/home/{id}.png", "image/png"),
    "dream-world": ("dream_world", "other/dream-world/{id}.svg", "image/svg+xml"),
    "showdown": ("showdown", "other/showdown/{id}.gif", "image/gif"),
    "default": ("default_sprite", "{id}.png", "image/png"),
}
POKEMON_SPRITE_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

COMPONENTS = {
    "pokemon_images": {
        "label": "Pokemon artwork and sprites",
        "table": "pokemon_asset",
        "kinds": tuple(spec[0] for spec in POKEMON_SPRITE_STYLES.values()),
        "media": "image",
    },
    "pokemon_cries": {
        "label": "Pokemon cries",
        "table": "pokemon_asset",
        "kinds": ("cry_latest", "cry_legacy"),
        "media": "audio",
    },
    "tcg_images": {
        "label": "TCG card and set images",
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
        if key == "tcg_images":
            row = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN local_path IS NOT NULL AND local_path != '' THEN 1 ELSE 0 END) AS stored,
                       SUM(CASE WHEN (local_path IS NULL OR local_path = '')
                                 AND source_url IS NOT NULL AND source_url != '' THEN 1 ELSE 0 END) AS missing
                FROM (
                    SELECT local_path, source_url FROM card_asset WHERE asset_kind = 'large'
                    UNION ALL
                    SELECT local_path, source_url FROM set_asset WHERE asset_kind IN ('logo', 'symbol')
                )
                """
            ).fetchone()
        else:
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

    def materialize_pokemon_cry(self, pokemon_id: int) -> tuple[Path, str] | None:
        """Return a local cry, downloading and cataloging it on first playback."""
        connection = self.database.connect(read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT id, pokemon_id, asset_kind, source_url, local_path, media_type
                FROM pokemon_asset
                WHERE pokemon_id = ? AND asset_kind IN ('cry_latest', 'cry_legacy')
                ORDER BY CASE asset_kind WHEN 'cry_latest' THEN 0 ELSE 1 END
                """,
                (pokemon_id,),
            ).fetchall()
        finally:
            connection.close()

        for row in rows:
            if row["local_path"]:
                stored = self.paths.resolve_stored(row["local_path"])
                if stored is not None:
                    return stored, row["media_type"] or "audio/ogg"
            if not row["source_url"]:
                continue

            asset = {
                "component": "pokemon_cries",
                "table": "pokemon_asset",
                "media": "audio",
                "id": row["id"],
                "asset_kind": row["asset_kind"],
                "source_url": row["source_url"],
                "owner_id": row["pokemon_id"],
            }
            destination = self._destination(asset)
            metadata = self._store(row["source_url"], destination, "audio")
            if metadata is None:
                continue

            sha256, media_type, width, height = metadata
            connection = self.database.connect()
            try:
                connection.execute(
                    """
                    UPDATE pokemon_asset
                    SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ?
                    WHERE id = ?
                    """,
                    (self.paths.relative_to_root(destination), media_type, sha256,
                     width, height, row["id"]),
                )
                connection.commit()
            finally:
                connection.close()
            return destination, media_type
        return None

    def materialize_pokemon_sprite(self, pokemon_id: int, style: str) -> tuple[Path, str] | None:
        """Register and persist a selected Pokemon sprite on first use."""
        requested = POKEMON_SPRITE_STYLES.get(style)
        if requested is None:
            raise ValueError("Unsupported Pokemon sprite style")

        connection = self.database.connect()
        try:
            if connection.execute("SELECT 1 FROM pokemon WHERE id = ?", (pokemon_id,)).fetchone() is None:
                return None
            asset_kind, source_path, media_type = requested
            source_url = f"{POKEMON_SPRITE_BASE_URL}/{source_path.format(id=pokemon_id)}"
            connection.execute(
                """
                INSERT INTO pokemon_asset (pokemon_id, asset_kind, source_url, media_type)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(pokemon_id, asset_kind) DO UPDATE SET
                    source_url = excluded.source_url,
                    media_type = excluded.media_type,
                    local_path = CASE
                        WHEN pokemon_asset.source_url = excluded.source_url THEN pokemon_asset.local_path
                        ELSE NULL
                    END
                """,
                (pokemon_id, asset_kind, source_url, media_type),
            )
            connection.commit()
            row = connection.execute(
                """
                SELECT id, pokemon_id, asset_kind, source_url, local_path, media_type
                FROM pokemon_asset WHERE pokemon_id = ? AND asset_kind = ?
                """,
                (pokemon_id, asset_kind),
            ).fetchone()
        finally:
            connection.close()

        if row["local_path"]:
            stored = self.paths.resolve_stored(row["local_path"])
            if stored is not None:
                return stored, row["media_type"] or media_type

        asset = {
            "component": "pokemon_images",
            "table": "pokemon_asset",
            "media": "svg" if media_type == "image/svg+xml" else "image",
            "id": row["id"],
            "asset_kind": row["asset_kind"],
            "source_url": row["source_url"],
            "owner_id": row["pokemon_id"],
        }
        destination = self._destination(asset)
        metadata = self._store(row["source_url"], destination, asset["media"])
        if metadata is None:
            return None

        sha256, stored_media_type, width, height = metadata
        connection = self.database.connect()
        try:
            connection.execute(
                """
                UPDATE pokemon_asset
                SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ?
                WHERE id = ?
                """,
                (self.paths.relative_to_root(destination), stored_media_type, sha256,
                 width, height, row["id"]),
            )
            connection.commit()
        finally:
            connection.close()
        return destination, stored_media_type

    def materialize_tcg_card_image(self, card_id: str, asset_kind: str) -> tuple[Path, str] | None:
        """Return a persistent TCG card image, preferring the requested size."""
        if asset_kind not in {"small", "large"}:
            raise ValueError("Unsupported TCG card image kind")
        connection = self.database.connect(read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT id, card_id, asset_kind, source_url, local_path, media_type
                FROM card_asset
                WHERE card_id = ? AND asset_kind IN ('small', 'large')
                ORDER BY CASE asset_kind WHEN ? THEN 0 ELSE 1 END
                """,
                (card_id, asset_kind),
            ).fetchall()
        finally:
            connection.close()
        return self._materialize_tcg_rows(rows, "card_asset", "card_id")

    def materialize_tcg_set_image(self, set_id: str, asset_kind: str) -> tuple[Path, str] | None:
        """Return a persistent TCG set logo or symbol."""
        if asset_kind not in {"logo", "symbol"}:
            raise ValueError("Unsupported TCG set image kind")
        connection = self.database.connect(read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT id, set_id, asset_kind, source_url, local_path, media_type
                FROM set_asset WHERE set_id = ? AND asset_kind = ?
                """,
                (set_id, asset_kind),
            ).fetchall()
        finally:
            connection.close()
        return self._materialize_tcg_rows(rows, "set_asset", "set_id")

    def _materialize_tcg_rows(self, rows, table: str, owner_column: str) -> tuple[Path, str] | None:
        for row in rows:
            if row["local_path"]:
                stored = self.paths.resolve_stored(row["local_path"])
                if stored is not None:
                    metadata = _image_metadata(stored)
                    if metadata is not None:
                        return stored, metadata[1] or row["media_type"] or "image/png"
            if not row["source_url"]:
                continue
            asset = {
                "component": "tcg_images", "table": table, "media": "image",
                "id": row["id"], "asset_kind": row["asset_kind"],
                "source_url": row["source_url"], "owner_id": row[owner_column],
            }
            destination = self._destination(asset)
            metadata = self._store(row["source_url"], destination, "image")
            if metadata is None:
                continue
            sha256, media_type, width, height = metadata
            connection = self.database.connect()
            try:
                if table == "set_asset":
                    connection.execute(
                        """
                        UPDATE set_asset
                        SET local_path = ?, media_type = ?, sha256 = ?
                        WHERE id = ?
                        """,
                        (self.paths.relative_to_root(destination), media_type, sha256, row["id"]),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE card_asset
                        SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ?
                        WHERE id = ?
                        """,
                        (self.paths.relative_to_root(destination), media_type, sha256,
                         width, height, row["id"]),
                    )
                connection.commit()
            finally:
                connection.close()
            return destination, media_type
        return None

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
                          SELECT id, asset_kind, source_url, media_type,
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
                    media = spec["media"]
                    if row["media_type"] == "image/svg+xml":
                        media = "svg"
                    pending.append({
                        "component": key, "table": spec["table"], "media": media,
                        "id": row["id"], "asset_kind": row["asset_kind"],
                        "source_url": row["source_url"], "owner_id": row["owner_id"],
                    })
                if key == "tcg_images":
                    set_rows = connection.execute(
                        """
                        SELECT id, asset_kind, source_url, media_type, set_id AS owner_id
                        FROM set_asset
                        WHERE asset_kind IN ('logo', 'symbol')
                          AND (local_path IS NULL OR local_path = '')
                          AND source_url IS NOT NULL AND source_url != ''
                        ORDER BY set_id, asset_kind
                        """
                    ).fetchall()
                    for row in set_rows:
                        pending.append({
                            "component": key, "table": "set_asset", "media": "image",
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
            elif asset["table"] == "card_asset":
                connection.execute(
                    """
                    UPDATE card_asset
                    SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ?
                    WHERE id = ?
                    """,
                    (self.paths.relative_to_root(destination), media_type, sha256,
                     width, height, asset["id"]),
                )
            else:
                # set_asset has no width/height columns (logos/symbols aren't card-sized assets).
                connection.execute(
                    """
                    UPDATE set_asset
                    SET local_path = ?, media_type = ?, sha256 = ?
                    WHERE id = ?
                    """,
                    (self.paths.relative_to_root(destination), media_type, sha256,
                     asset["id"]),
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
            elif media == "svg":
                metadata = _svg_metadata(temporary)
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


def _svg_metadata(path: Path):
    try:
        payload = path.read_bytes()
        root = ElementTree.fromstring(payload)
        if root.tag.split("}")[-1].lower() != "svg":
            return None
        return hashlib.sha256(payload).hexdigest(), "image/svg+xml", None, None
    except (OSError, ElementTree.ParseError):
        return None


_ASSET_MANAGER: Optional[AssetManager] = None


def get_asset_manager() -> AssetManager:
    global _ASSET_MANAGER
    if _ASSET_MANAGER is None:
        _ASSET_MANAGER = AssetManager()
    return _ASSET_MANAGER
