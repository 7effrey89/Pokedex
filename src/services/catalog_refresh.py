"""Persist explicit upstream refreshes as raw snapshots and normalized catalog rows."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import get_storage_paths
from src.db.database import SqliteDatabase


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resource_id(resource: Any) -> int | None:
    if not isinstance(resource, dict):
        return None
    if isinstance(resource.get("id"), int):
        return resource["id"]
    match = re.search(r"/(\d+)/?$", str(resource.get("url", "")))
    return int(match.group(1)) if match else None


class CatalogRefreshService:
    """Write fresh PokeAPI and TCG payloads without rebuilding the whole catalog."""

    def __init__(self, database: SqliteDatabase | None = None, snapshots_root: Path | None = None):
        paths = get_storage_paths()
        self.database = database or SqliteDatabase(paths.catalog_database)
        self.snapshots_root = snapshots_root or paths.snapshots

    def refresh_pokemon(self, payload: dict[str, Any]) -> Path:
        pokemon_id = int(payload["id"])
        raw_path = self._store_raw("pokeapi", "pokemon", pokemon_id, payload)
        refreshed_at = utc_now()
        connection = self.database.connect()
        try:
            existing = connection.execute(
                "SELECT species_id FROM pokemon WHERE id = ?", (pokemon_id,)
            ).fetchone()
            species_id = resource_id(payload.get("species"))
            if existing is None:
                raise ValueError(f"Pokemon {pokemon_id} is not present in the catalog")
            if species_id is None:
                species_id = int(existing["species_id"])
            species_exists = connection.execute(
                "SELECT 1 FROM pokemon_species WHERE id = ?", (species_id,)
            ).fetchone()
            if species_exists is None:
                raise ValueError(f"Pokemon {pokemon_id} references unknown species {species_id}")

            connection.execute(
                """
                UPDATE pokemon
                SET species_id = ?, name = ?, display_order = ?, is_default = ?,
                    base_experience = ?, height_decimetres = ?, weight_hectograms = ?,
                    last_refreshed_at = ?
                WHERE id = ?
                """,
                (
                    species_id, payload["name"], payload.get("order", pokemon_id),
                    bool(payload.get("is_default")), payload.get("base_experience"),
                    payload.get("height"), payload.get("weight"), refreshed_at, pokemon_id,
                ),
            )
            self._replace_relations(connection, pokemon_id, payload)
            self._upsert_assets(connection, pokemon_id, payload)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return raw_path

    def refresh_species(self, payload: dict[str, Any]) -> Path:
        species_id = int(payload["id"])
        raw_path = self._store_raw("pokeapi", "species", species_id, payload)
        chain_id = resource_id(payload.get("evolution_chain"))
        connection = self.database.connect()
        try:
            if connection.execute(
                "SELECT 1 FROM pokemon_species WHERE id = ?", (species_id,)
            ).fetchone() is None:
                raise ValueError(f"Pokemon species {species_id} is not present in the catalog")
            if chain_id is not None:
                connection.execute("INSERT OR IGNORE INTO evolution_chain (id) VALUES (?)", (chain_id,))
            connection.execute(
                """
                UPDATE pokemon_species
                SET name = ?, generation_name = ?, evolution_chain_id = ?, color_name = ?,
                    shape_name = ?, habitat_name = ?, growth_rate_name = ?, capture_rate = ?,
                    base_happiness = ?, gender_rate = ?, hatch_counter = ?, is_baby = ?,
                    is_legendary = ?, is_mythical = ?, last_refreshed_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"], self._resource_name(payload.get("generation")), chain_id,
                    self._resource_name(payload.get("color")), self._resource_name(payload.get("shape")),
                    self._resource_name(payload.get("habitat")), self._resource_name(payload.get("growth_rate")),
                    payload.get("capture_rate"), payload.get("base_happiness"), payload.get("gender_rate"),
                    payload.get("hatch_counter"), bool(payload.get("is_baby")),
                    bool(payload.get("is_legendary")), bool(payload.get("is_mythical")), utc_now(), species_id,
                ),
            )
            connection.execute("DELETE FROM species_text WHERE species_id = ?", (species_id,))
            self._insert_species_text(connection, species_id, payload)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return raw_path

    def _store_raw(self, domain: str, resource_kind: str, identifier: Any, payload: dict[str, Any]) -> Path:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()[:12]
        destination = self.snapshots_root / domain / resource_kind / f"{identifier}-{digest}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, destination)
        return destination

    def _lookup(self, connection, table: str, resource: dict[str, Any]) -> int:
        name = str(resource.get("name", ""))
        identifier = resource_id(resource)
        row = connection.execute(
            f"SELECT id FROM {table} WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if row:
            return int(row["id"])
        if identifier is None:
            identifier = int(connection.execute(
                f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}"
            ).fetchone()[0])
        connection.execute(f"INSERT INTO {table} (id, name) VALUES (?, ?)", (identifier, name))
        return identifier

    @staticmethod
    def _resource_name(resource: Any) -> str | None:
        return resource.get("name") if isinstance(resource, dict) else None

    def _insert_species_text(self, connection, species_id: int, payload: dict[str, Any]) -> None:
        rows = []
        for item in payload.get("names", []):
            rows.append((species_id, self._resource_name(item.get("language")) or "", "", "name", item.get("name", "")))
        for item in payload.get("genera", []):
            rows.append((species_id, self._resource_name(item.get("language")) or "", "", "genus", item.get("genus", "")))
        for item in payload.get("flavor_text_entries", []):
            text = str(item.get("flavor_text", "")).replace("\n", " ").replace("\f", " ")
            rows.append((
                species_id, self._resource_name(item.get("language")) or "",
                self._resource_name(item.get("version")) or "", "flavor_text", text,
            ))
        connection.executemany(
            "INSERT OR IGNORE INTO species_text (species_id, language, version_name, text_kind, text) VALUES (?, ?, ?, ?, ?)",
            [row for row in rows if row[-1]],
        )

    def _replace_relations(self, connection, pokemon_id: int, payload: dict[str, Any]) -> None:
        connection.execute("DELETE FROM pokemon_type WHERE pokemon_id = ?", (pokemon_id,))
        connection.execute("DELETE FROM pokemon_ability WHERE pokemon_id = ?", (pokemon_id,))
        connection.execute("DELETE FROM pokemon_stat WHERE pokemon_id = ?", (pokemon_id,))
        for item in payload.get("types", []):
            type_id = self._lookup(connection, "type", item["type"])
            connection.execute(
                "INSERT INTO pokemon_type (pokemon_id, type_id, slot) VALUES (?, ?, ?)",
                (pokemon_id, type_id, item["slot"]),
            )
        for item in payload.get("abilities", []):
            ability_id = self._lookup(connection, "ability", item["ability"])
            connection.execute(
                "INSERT INTO pokemon_ability (pokemon_id, ability_id, slot, is_hidden) VALUES (?, ?, ?, ?)",
                (pokemon_id, ability_id, item["slot"], bool(item.get("is_hidden"))),
            )
        for item in payload.get("stats", []):
            stat_id = self._lookup(connection, "stat", item["stat"])
            connection.execute(
                "INSERT INTO pokemon_stat (pokemon_id, stat_id, base_stat, effort) VALUES (?, ?, ?, ?)",
                (pokemon_id, stat_id, item["base_stat"], item.get("effort", 0)),
            )

    def _upsert_assets(self, connection, pokemon_id: int, payload: dict[str, Any]) -> None:
        sprites = payload.get("sprites") if isinstance(payload.get("sprites"), dict) else {}
        other = sprites.get("other") if isinstance(sprites.get("other"), dict) else {}
        official = other.get("official-artwork") if isinstance(other.get("official-artwork"), dict) else {}
        assets = {
            "official_artwork": (official.get("front_default"), "image/png"),
            "cry_latest": ((payload.get("cries") or {}).get("latest"), "audio/ogg"),
            "cry_legacy": ((payload.get("cries") or {}).get("legacy"), "audio/ogg"),
        }
        for kind, (source_url, media_type) in assets.items():
            if not source_url:
                continue
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
                    END,
                    sha256 = CASE WHEN pokemon_asset.source_url = excluded.source_url THEN pokemon_asset.sha256 ELSE NULL END,
                    width = CASE WHEN pokemon_asset.source_url = excluded.source_url THEN pokemon_asset.width ELSE NULL END,
                    height = CASE WHEN pokemon_asset.source_url = excluded.source_url THEN pokemon_asset.height ELSE NULL END
                """,
                (pokemon_id, kind, source_url, media_type),
            )
