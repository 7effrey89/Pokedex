"""Discover and add catalog content that does not exist locally yet.

CatalogScanService performs read-only diffs against the live PokeAPI and TCG
API so the admin panel can answer "what's new that we don't have yet?"
without rebuilding the whole catalog. CatalogIngestService then inserts only
the missing rows, reusing the same card/set normalization the full importer
uses so newly added content matches the existing schema exactly.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests

from src.api.pokemon_tcg_api import PokemonTCGTools
from src.config import get_storage_paths
from src.db.database import SqliteDatabase
from src.db.importer import SqliteImporter, resource_id, resource_name
from src.services.catalog_refresh import CatalogRefreshService

logger = logging.getLogger(__name__)

POKEAPI_ROOT = "https://pokeapi.co/api/v2"
TCG_API_BASE_URL = "https://api.pokemontcg.io/v2"
USER_AGENT = "Pokedex-Catalog-Scan/1.0"
TCG_SET_PAGE_SIZE = 250
MAX_LISTED_ITEMS = 200
TCG_SCAN_TIMEOUT_SECONDS = 8
TCG_SCAN_MAX_ATTEMPTS = 3
TCG_SCAN_RETRY_DELAY_SECONDS = 1.5


@dataclass
class IngestJob:
    """Progress for one batch of species or TCG set additions."""

    kind: str
    items: list[str]
    total: int = 0
    completed: int = 0
    sub_completed: int = 0
    sub_total: int = 0
    current_label: str = ""
    status: str = "running"
    message: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        percent = round(self.completed / self.total * 100, 1) if self.total else 100.0
        sub_percent = round(self.sub_completed / self.sub_total * 100, 1) if self.sub_total else 0.0
        return {
            "kind": self.kind, "total": self.total, "completed": self.completed, "percent": percent,
            "current_label": self.current_label, "sub_completed": self.sub_completed,
            "sub_total": self.sub_total, "sub_percent": sub_percent,
            "status": self.status, "message": self.message, "errors": self.errors[-20:],
        }


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _fetch_tcg_sets_page(page: int) -> dict[str, Any] | None:
    """Fetch one page of TCG sets with a short timeout and a couple of quick retries.

    The upstream TCG API occasionally returns a transient 5xx; retrying twice
    with a brief pause absorbs that without making scans slow when the API is
    genuinely down (worst case is bounded, unlike the shared PokemonTCGTools
    client which is tuned for reliability over speed).
    """
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("POKEMON_TCG_API_KEY", "").strip()
    if api_key:
        headers["X-Api-Key"] = api_key
    params = {"page": page, "pageSize": TCG_SET_PAGE_SIZE, "orderBy": "-releaseDate"}

    last_error: requests.RequestException | None = None
    for attempt in range(TCG_SCAN_MAX_ATTEMPTS):
        try:
            response = requests.get(
                f"{TCG_API_BASE_URL}/sets", params=params, headers=headers, timeout=TCG_SCAN_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 < TCG_SCAN_MAX_ATTEMPTS:
                time.sleep(TCG_SCAN_RETRY_DELAY_SECONDS)
    raise last_error


class CatalogScanService:
    """Read-only diff between the live upstream APIs and the local catalog."""

    def __init__(self, database: SqliteDatabase | None = None):
        paths = get_storage_paths()
        self.database = database or SqliteDatabase(paths.catalog_database)

    def scan_pokemon(self) -> dict[str, Any]:
        if not self.database.path.is_file():
            return {"available": False, "reason": "Catalog database has not been built"}

        remote = self._fetch_species_index()
        connection = self.database.connect(read_only=True)
        try:
            local_ids = {row["id"] for row in connection.execute("SELECT id FROM pokemon_species")}
        finally:
            connection.close()

        missing = sorted(
            (
                {"id": species_id, "name": name}
                for species_id, name in remote.items()
                if species_id not in local_ids
            ),
            key=lambda item: item["id"],
        )
        return {
            "available": True,
            "checked": len(remote),
            "missing_count": len(missing),
            "missing": missing[:MAX_LISTED_ITEMS],
        }

    def scan_tcg(self) -> dict[str, Any]:
        if not self.database.path.is_file():
            return {"available": False, "reason": "Catalog database has not been built"}

        remote_sets = self._fetch_all_sets()
        connection = self.database.connect(read_only=True)
        try:
            local_card_counts = {
                row["id"]: row["card_count"]
                for row in connection.execute(
                    """
                    SELECT s.id, COUNT(c.id) AS card_count
                    FROM tcg_set AS s
                    LEFT JOIN tcg_card AS c ON c.set_id = s.id
                    GROUP BY s.id
                    """
                )
            }
        finally:
            connection.close()

        new_sets = []
        sets_with_new_cards = []
        for remote_set in remote_sets:
            set_id = remote_set.get("id")
            if not set_id:
                continue
            remote_total = int(remote_set.get("total") or 0)
            if set_id not in local_card_counts:
                new_sets.append({"id": set_id, "name": remote_set.get("name"), "total": remote_total})
                continue
            local_count = local_card_counts[set_id]
            if remote_total > local_count:
                sets_with_new_cards.append({
                    "id": set_id, "name": remote_set.get("name"),
                    "local_count": local_count, "remote_total": remote_total,
                })

        return {
            "available": True,
            "checked": len(remote_sets),
            "new_sets_count": len(new_sets),
            "new_sets": new_sets[:MAX_LISTED_ITEMS],
            "sets_with_new_cards_count": len(sets_with_new_cards),
            "sets_with_new_cards": sets_with_new_cards[:MAX_LISTED_ITEMS],
        }

    def _fetch_species_index(self) -> dict[int, str]:
        payload = _fetch_json(f"{POKEAPI_ROOT}/pokemon-species?limit=100000")
        index: dict[int, str] = {}
        for entry in payload.get("results", []):
            species_id = resource_id(entry)
            if species_id is not None:
                index[species_id] = entry.get("name")
        return index

    def _fetch_all_sets(self) -> list[dict[str, Any]]:
        sets: list[dict[str, Any]] = []
        page = 1
        while True:
            try:
                response = _fetch_tcg_sets_page(page)
            except requests.RequestException as exc:
                if page == 1:
                    raise RuntimeError(f"TCG API is unavailable: {exc}") from exc
                break
            if not response or not response.get("data"):
                break
            sets.extend(response["data"])
            total_count = response.get("totalCount", 0)
            if page * TCG_SET_PAGE_SIZE >= total_count:
                break
            page += 1
        return sets


class _StorageAwareTcgImporter(SqliteImporter):
    """Reuses SqliteImporter's set/card normalization, writing assets under
    the environment-aware storage root instead of the fixed project root."""

    def __init__(self, database_path: Path):
        paths = get_storage_paths()
        super().__init__(
            project_root=paths.data_root,
            database_path=database_path,
            pokeapi_dir=paths.data_root / "cache",
            tcg_dir=paths.data_root / "tcg-cache",
            asset_dir=paths.data_root / "data" / "assets",
            allow_network=True,
            download_artwork=True,
            require_artwork=False,
            require_card_images=False,
            progress=lambda message: logger.info(message),
        )
        self._storage_paths = paths

    def _tcg_image_path(self, card_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", card_id).strip("-")
        import hashlib

        suffix = hashlib.sha1(card_id.encode("utf-8")).hexdigest()[:8]
        return self._storage_paths.tcg_images / f"{safe_id}-{suffix}.img"


class CatalogIngestService:
    """Insert brand-new Pokemon species/forms and TCG sets/cards into the catalog."""

    def __init__(self, database: SqliteDatabase | None = None):
        paths = get_storage_paths()
        self.database = database or SqliteDatabase(paths.catalog_database)
        self.refresh = CatalogRefreshService(self.database)
        self._lock = threading.Lock()
        self._job: IngestJob | None = None
        self._thread: threading.Thread | None = None

    def start_batch(self, kind: str, ids: list) -> dict[str, Any]:
        if kind not in {"pokemon_species", "tcg_set"}:
            raise ValueError(f"Unknown ingest kind: {kind}")
        if not ids:
            raise ValueError("Select at least one item to add")

        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("An ingest job is already running")
            self._job = IngestJob(kind=kind, items=[str(item) for item in ids], total=len(ids))
            self._thread = threading.Thread(target=self._run_batch, args=(kind, ids), daemon=True)
            self._thread.start()
            return self._job.to_dict()

    def job_status(self) -> dict[str, Any] | None:
        with self._lock:
            return self._job.to_dict() if self._job else None

    def _run_batch(self, kind: str, ids: list) -> None:
        job = self._job
        assert job is not None

        def on_progress(sub_completed: int, sub_total: int, label: str | None = None) -> None:
            with self._lock:
                job.sub_completed = sub_completed
                job.sub_total = sub_total
                if label:
                    job.current_label = label

        for index, item_id in enumerate(ids):
            with self._lock:
                job.current_label = str(item_id)
                job.sub_completed = 0
                job.sub_total = 0
                job.message = f"Adding {item_id}"
            try:
                if kind == "pokemon_species":
                    self.add_species(int(item_id), progress=on_progress)
                else:
                    self.add_tcg_set(str(item_id), progress=on_progress)
            except Exception as exc:
                logger.exception("Failed to add %s %s", kind, item_id)
                with self._lock:
                    job.errors.append(f"{item_id}: {exc}")
            with self._lock:
                job.completed = index + 1

        with self._lock:
            job.status = "completed"
            job.message = (
                f"Added {job.completed - len(job.errors):,}/{job.total:,}"
                + (f", {len(job.errors):,} failed" if job.errors else "")
            )

    def add_species(self, species_id: int, progress: Callable[[int, int, str | None], None] | None = None) -> dict[str, Any]:
        connection = self.database.connect()
        try:
            if connection.execute("SELECT 1 FROM pokemon_species WHERE id = ?", (species_id,)).fetchone():
                return {"species_id": species_id, "added": False, "reason": "Species already present"}

            species_payload = _fetch_json(f"{POKEAPI_ROOT}/pokemon-species/{species_id}")
            self.refresh._store_raw("pokeapi", "species", species_id, species_payload)
            varieties = species_payload.get("varieties", [])
            if progress:
                progress(0, len(varieties), species_payload.get("name"))

            chain_id = resource_id(species_payload.get("evolution_chain"))
            if chain_id is not None:
                connection.execute("INSERT OR IGNORE INTO evolution_chain (id) VALUES (?)", (chain_id,))
            connection.execute(
                """
                INSERT INTO pokemon_species (
                    id, name, generation_name, evolution_chain_id, color_name, shape_name,
                    habitat_name, growth_rate_name, capture_rate, base_happiness, gender_rate,
                    hatch_counter, is_baby, is_legendary, is_mythical
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    species_payload["id"], species_payload["name"],
                    resource_name(species_payload.get("generation")), chain_id,
                    resource_name(species_payload.get("color")), resource_name(species_payload.get("shape")),
                    resource_name(species_payload.get("habitat")), resource_name(species_payload.get("growth_rate")),
                    species_payload.get("capture_rate"), species_payload.get("base_happiness"),
                    species_payload.get("gender_rate"), species_payload.get("hatch_counter"),
                    bool(species_payload.get("is_baby")), bool(species_payload.get("is_legendary")),
                    bool(species_payload.get("is_mythical")),
                ),
            )
            self.refresh._insert_species_text(connection, species_id, species_payload)

            added_pokemon: list[int] = []
            for variety_index, variety in enumerate(species_payload.get("varieties", []), start=1):
                pokemon_ref = variety.get("pokemon", {})
                pokemon_id = resource_id(pokemon_ref)
                if pokemon_id is None:
                    continue
                pokemon_payload = _fetch_json(pokemon_ref.get("url") or f"{POKEAPI_ROOT}/pokemon/{pokemon_id}")
                self.refresh._store_raw("pokeapi", "pokemon", pokemon_id, pokemon_payload)
                connection.execute(
                    """
                    INSERT INTO pokemon (id, species_id, name, display_order, is_default, base_experience,
                                         height_decimetres, weight_hectograms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pokemon_id, species_id, pokemon_payload["name"],
                        pokemon_payload.get("order", pokemon_id), bool(pokemon_payload.get("is_default")),
                        pokemon_payload.get("base_experience"), pokemon_payload.get("height"),
                        pokemon_payload.get("weight"),
                    ),
                )
                self.refresh._replace_relations(connection, pokemon_id, pokemon_payload)
                self.refresh._upsert_assets(connection, pokemon_id, pokemon_payload)
                added_pokemon.append(pokemon_id)
                if progress:
                    progress(variety_index, len(species_payload.get("varieties", [])), species_payload.get("name"))

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"species_id": species_id, "added": True, "pokemon_ids": added_pokemon}

    def add_tcg_set(self, set_id: str, progress: Callable[[int, int, str | None], None] | None = None) -> dict[str, Any]:
        cards = self._fetch_all_cards_for_set(set_id)
        if not cards:
            return {"set_id": set_id, "added": False, "reason": "No cards returned from TCG API"}

        set_name = cards[0].get("set", {}).get("name") or set_id
        if progress:
            progress(0, len(cards), set_name)

        self.refresh._store_raw("tcg", "sets", set_id, {"set_id": set_id, "cards": cards})

        importer = _StorageAwareTcgImporter(self.database.path)
        connection = self.database.connect()
        try:
            existing_ids = {
                row["id"] for row in connection.execute(
                    "SELECT id FROM tcg_card WHERE set_id = ?", (set_id,)
                )
            }
            species_by_name = {
                row["name"].casefold(): row["id"]
                for row in connection.execute("SELECT id, name FROM pokemon_species")
            }
            importer._import_set(connection, cards[0].get("set", {}))
            added = 0
            for card_index, card in enumerate(cards, start=1):
                if card.get("id") not in existing_ids:
                    importer._import_card(connection, card, species_by_name)
                    added += 1
                if progress:
                    progress(card_index, len(cards), set_name)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"set_id": set_id, "added": True, "card_count": len(cards), "new_card_count": added}

    def _fetch_all_cards_for_set(self, set_id: str) -> list[dict[str, Any]]:
        client = PokemonTCGTools()
        cards: list[dict[str, Any]] = []
        page = 1
        while True:
            response = client.search_cards_by_set(set_id, page=page, page_size=TCG_SET_PAGE_SIZE)
            if not response or not response.get("data"):
                break
            cards.extend(response["data"])
            total_count = response.get("totalCount", 0)
            if page * TCG_SET_PAGE_SIZE >= total_count:
                break
            page += 1
        return cards


_SCAN_SERVICE: CatalogScanService | None = None
_INGEST_SERVICE: CatalogIngestService | None = None


def get_catalog_scan_service() -> CatalogScanService:
    global _SCAN_SERVICE
    if _SCAN_SERVICE is None:
        _SCAN_SERVICE = CatalogScanService()
    return _SCAN_SERVICE


def get_catalog_ingest_service() -> CatalogIngestService:
    global _INGEST_SERVICE
    if _INGEST_SERVICE is None:
        _INGEST_SERVICE = CatalogIngestService()
    return _INGEST_SERVICE
