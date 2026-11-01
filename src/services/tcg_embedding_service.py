"""Incrementally embed locally stored catalog cards without network requests."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.config import get_storage_paths
from src.config.paths import StoragePaths
from src.db.database import SqliteDatabase
from src.db.tcg_repository import SqliteTcgRepository
from src.services.backup_assets import local_asset_path
from src.services.tcg_image_index import (
    ENCODER_VERSION, VECTOR_SIZE, _read_index, encode_card_image,
    index_access, suspend_indexes, validate_index,
)
from src.utils.file_lock import exclusive_file_lock

logger = logging.getLogger(__name__)
INDEX_FILES = ("vectors.npy", "cards.json", "manifest.json")


class TcgEmbeddingService:
    def __init__(self, paths: StoragePaths | None = None):
        self.paths = paths or get_storage_paths()
        self.database = SqliteDatabase(self.paths.catalog_database)
        self.repository = SqliteTcgRepository(self.database)
        self._thread: threading.Thread | None = None
        self._job_file = self.paths.tcg_index.parent / ".tcg-embedding-job.json"
        self._job_database = SqliteDatabase(self.paths.tcg_index.parent / ".tcg-embedding-job.sqlite3")
        self._job_lock = self.paths.tcg_index.parent / ".tcg-embedding-job.lock"

    def _snapshot(self) -> tuple[np.ndarray, list[dict]]:
        with index_access(self.paths.tcg_index):
            if not any((self.paths.tcg_index / name).exists() for name in INDEX_FILES):
                return np.empty((0, VECTOR_SIZE), dtype=np.float32), []
            vectors, cards = _read_index(self.paths.tcg_index)
            if not np.isfinite(vectors).all():
                raise ValueError("TCG image embeddings contain non-finite values")
            return vectors, cards

    def _catalog_assets(self) -> dict[str, list[dict]]:
        with closing(self.database.connect(read_only=True)) as connection:
            cards = {row["id"]: [] for row in connection.execute("SELECT id FROM tcg_card ORDER BY id")}
            for row in connection.execute(
                "SELECT card_id, asset_kind, local_path, sha256 FROM card_asset "
                "WHERE asset_kind IN ('large', 'small') AND local_path IS NOT NULL "
                "ORDER BY asset_kind = 'large' DESC"
            ):
                cards[row["card_id"]].append(dict(row))
        return cards

    def _local_image(self, assets: list[dict], *, verify_hash: bool = False) -> Path | None:
        for asset in assets:
            path = local_asset_path(
                self.paths, "tcg_images", asset["local_path"],
                asset["sha256"] if verify_hash else None,
            )
            if path is not None:
                return path
        return None

    def inventory(self) -> dict[str, Any]:
        try:
            _, indexed_cards = self._snapshot()
            assets = self._catalog_assets()
            indexed_ids = {card["id"] for card in indexed_cards}
            missing = set(assets) - indexed_ids
            ready = sum(self._local_image(assets[card_id]) is not None for card_id in missing)
            return {
                "available": True, "total": len(assets),
                "indexed": len(set(assets) & indexed_ids), "index_card_count": len(indexed_ids),
                "missing": len(missing), "ready": ready, "waiting_for_images": len(missing) - ready,
                "orphaned": len(indexed_ids - set(assets)), "index_ready": bool(indexed_ids),
            }
        except (OSError, ValueError, sqlite3.Error) as exc:
            logger.exception("TCG embedding inventory unavailable")
            return {"available": False, "reason": str(exc)}

    def _write_job(self, job: dict) -> None:
        with closing(self._job_database.connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS embedding_job "
                "(id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO embedding_job (id, payload) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
                (json.dumps(job),),
            )

    def job_status(self) -> dict | None:
        if self._job_database.path.is_file():
            with closing(self._job_database.connect(read_only=True)) as connection:
                if connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'embedding_job'"
                ).fetchone():
                    row = connection.execute("SELECT payload FROM embedding_job WHERE id = 1").fetchone()
                else:
                    row = None
            if row is None:
                return None
            job = json.loads(row["payload"])
        elif self._job_file.is_file():
            job = json.loads(self._job_file.read_text(encoding="utf-8"))
        else:
            return None
        if job["status"] == "running":
            try:
                with exclusive_file_lock(self._job_lock, blocking=False):
                    job["status"] = "failed"
                    job["message"] = "Embedding job was interrupted; run Generate Missing Embeddings again."
            except (BlockingIOError, PermissionError):
                pass
        return job

    def start(self) -> dict:
        guard = exclusive_file_lock(self._job_lock, blocking=False)
        try:
            guard.__enter__()
        except (BlockingIOError, PermissionError) as exc:
            raise RuntimeError("A TCG embedding job is already running") from exc
        try:
            inventory = self.inventory()
            if not inventory["available"]:
                raise ValueError(inventory["reason"])
            if not inventory["ready"]:
                raise ValueError("No missing embeddings have local images. Download TCG card images in Step 2 first.")
            job = {
                "status": "running", "total": inventory["ready"], "completed": 0, "percent": 0,
                "added": 0, "failed": 0, "errors": [], "message": "Preparing missing TCG embeddings",
            }
            self._write_job(job)
            self._thread = threading.Thread(target=self._run, args=(job, guard), daemon=True)
            self._thread.start()
            return dict(job)
        except Exception:
            guard.__exit__(None, None, None)
            raise

    def _run(self, job: dict, guard) -> None:
        try:
            _, indexed = self._snapshot()
            existing = {card["id"] for card in indexed}
            pending = [(card_id, assets) for card_id, assets in self._catalog_assets().items()
                       if card_id not in existing and self._local_image(assets) is not None]
            job["total"] = len(pending)
            cards, vectors = [], []
            for card_id, assets in pending:
                try:
                    path = self._local_image(assets, verify_hash=True)
                    if path is None:
                        raise ValueError("Local card image is missing or its checksum does not match")
                    with Image.open(path) as image:
                        image.verify()
                    with Image.open(path) as image:
                        vector = encode_card_image(image)
                    card = self.repository.get_card(card_id)
                    if "error" in card:
                        raise ValueError(card["error"])
                    cards.append(card)
                    vectors.append(vector)
                    logger.info("Generated TCG embedding for %s (%s) from %s", card_id, card["name"], path)
                except (OSError, ValueError) as exc:
                    logger.warning("TCG embedding failed for %s: %s", card_id, exc)
                    job["failed"] += 1
                    job["errors"] = (job["errors"] + [f"{card_id}: {exc}"])[-20:]
                job["completed"] += 1
                job["percent"] = round(job["completed"] / job["total"] * 100, 1)
                job["message"] = f"Processing {card_id}"
                self._write_job(job)
            if vectors:
                job["message"] = "Publishing updated scanner index"
                self._write_job(job)
                job["added"] = self._append(cards, vectors)
            job["status"] = "completed" if not job["failed"] else "completed_with_errors"
            job["percent"] = 100
            job["message"] = f"Added {job['added']:,} embeddings; {job['failed']:,} failed."
            logger.info("TCG embedding job complete: %s Index: %s", job["message"], self.paths.tcg_index)
        except Exception as exc:
            logger.exception("TCG embedding job failed")
            job["status"] = "failed"
            job["message"] = str(exc)
        finally:
            try:
                self._write_job(job)
            finally:
                guard.__exit__(None, None, None)

    def _append(self, cards: list[dict], vectors: list[np.ndarray]) -> int:
        directory = self.paths.tcg_index
        with index_access(directory):
            old_vectors, old_cards = self._snapshot()
            existing = {card["id"] for card in old_cards}
            additions = [(card, vector) for card, vector in zip(cards, vectors) if card["id"] not in existing]
            if not additions:
                return 0
            combined_cards = old_cards + [card for card, _ in additions]
            combined_vectors = np.concatenate((old_vectors, np.stack([vector for _, vector in additions])))
            directory.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="tcg-embeddings-", dir=directory.parent) as temporary:
                staging = Path(temporary)
                np.save(staging / "vectors.npy", combined_vectors, allow_pickle=False)
                (staging / "cards.json").write_text(json.dumps(combined_cards), encoding="utf-8")
                manifest = {
                    "encoder_version": ENCODER_VERSION, "vector_size": VECTOR_SIZE, "dtype": "float32",
                    "normalized": True, "card_count": len(combined_cards),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "source_fingerprint": hashlib.sha256(json.dumps(combined_cards, sort_keys=True).encode()).hexdigest(),
                }
                (staging / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                validate_index(staging)
                backup = staging / "previous"
                backup.mkdir()
                directory.mkdir(parents=True, exist_ok=True)
                for name in INDEX_FILES:
                    if (directory / name).is_file():
                        shutil.copy2(directory / name, backup / name)
                with suspend_indexes(directory):
                    installed = []
                    try:
                        for name in INDEX_FILES:
                            os.replace(staging / name, directory / name)
                            installed.append(name)
                    except Exception:
                        for name in installed:
                            if (backup / name).is_file():
                                os.replace(backup / name, directory / name)
                            else:
                                (directory / name).unlink(missing_ok=True)
                        raise
            return len(additions)


_SERVICE: TcgEmbeddingService | None = None


def get_tcg_embedding_service() -> TcgEmbeddingService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = TcgEmbeddingService()
    return _SERVICE
