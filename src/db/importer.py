"""Build the normalized Pokedex database from reproducible JSON seed files."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from src.db.database import SCHEMA_VERSION, apply_catalog_schema


IMPORTER_VERSION = "1"
POKEAPI_ROOT = "https://pokeapi.co/api/v2"
USER_AGENT = "Pokedex-SQLite-Importer/1.0"
TCG_TYPE_NAMES = {
    "colorless": "normal",
    "darkness": "dark",
    "lightning": "electric",
    "metal": "steel",
}


@dataclass(frozen=True)
class ImportSummary:
    pokemon_count: int
    species_count: int
    card_count: int
    set_count: int
    imported_file_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def unwrap_payload(value: Any) -> Any:
    if isinstance(value, dict) and "response" in value:
        return value["response"]
    return value


def resource_id(resource: Any) -> int | None:
    if not isinstance(resource, dict):
        return None
    if isinstance(resource.get("id"), int):
        return resource["id"]
    match = re.search(r"/(\d+)/?$", str(resource.get("url", "")))
    return int(match.group(1)) if match else None


def resource_name(resource: Any) -> str | None:
    return resource.get("name") if isinstance(resource, dict) else None


def parse_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


class SqliteImporter:
    """Hydrate a new database and replace the active file only after validation."""

    def __init__(
        self,
        project_root: Path,
        database_path: Path,
        pokeapi_dir: Path,
        tcg_dir: Path,
        asset_dir: Path,
        *,
        allow_network: bool = True,
        download_artwork: bool = True,
        require_artwork: bool = True,
        require_card_images: bool = True,
        progress: Callable[[str], None] | None = None,
    ):
        self.project_root = project_root.resolve()
        self.database_path = database_path.resolve()
        self.pokeapi_dir = pokeapi_dir.resolve()
        self.tcg_dir = tcg_dir.resolve()
        self.asset_dir = asset_dir.resolve()
        self.allow_network = allow_network
        self.download_artwork = download_artwork
        self.require_artwork = require_artwork
        self.require_card_images = require_card_images
        self.progress = progress or (lambda _message: None)
        self.imported_files: list[tuple[str, str, Path, str | None, int]] = []
        self._network_payloads: dict[str, dict[str, Any]] = {}
        self._species_payloads: list[dict[str, Any]] = []

    def build(self) -> ImportSummary:
        temporary_path = self.database_path.with_suffix(self.database_path.suffix + ".building")
        self.progress(f"Preparing temporary database: {temporary_path}")
        temporary_path.unlink(missing_ok=True)
        temporary_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(temporary_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        run_id = 0
        try:
            apply_catalog_schema(connection)
            cursor = connection.execute(
                "INSERT INTO import_run (started_at, status, importer_version, schema_version) VALUES (?, 'running', ?, ?)",
                (utc_now(), IMPORTER_VERSION, SCHEMA_VERSION),
            )
            run_id = int(cursor.lastrowid)
            self.progress("Phase 1/5: importing Pokemon species")
            species_by_name = self._import_species(connection)
            self.progress("Phase 2/5: importing Pokemon forms and artwork")
            self._import_pokemon(connection, species_by_name)
            self.progress("Phase 3/5: importing and deduplicating TCG cards")
            self._import_tcg(connection, species_by_name)
            self.progress("Phase 4/5: recording import provenance")
            self._record_import_files(connection, run_id)
            connection.execute(
                "UPDATE import_run SET status = 'completed', completed_at = ? WHERE id = ?",
                (utc_now(), run_id),
            )
            connection.commit()
            self.progress("Phase 5/5: validating database integrity and required assets")
            summary = self._validate(connection)
        except Exception as exc:
            connection.rollback()
            if run_id:
                connection.execute(
                    "UPDATE import_run SET status = 'failed', completed_at = ?, error_message = ? WHERE id = ?",
                    (utc_now(), str(exc)[:1000], run_id),
                )
                connection.commit()
            raise
        finally:
            connection.close()

        self.progress(f"Validation passed. Replacing active database: {self.database_path}")
        os.replace(temporary_path, self.database_path)
        return summary

    def resume(self) -> ImportSummary:
        temporary_path = self.database_path.with_suffix(self.database_path.suffix + ".building")
        if not temporary_path.is_file():
            raise RuntimeError(f"No resumable database found: {temporary_path}")
        self.progress(f"Resuming validation-failed database: {temporary_path}")
        connection = sqlite3.connect(temporary_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            run = connection.execute(
                "SELECT id, status FROM import_run ORDER BY id DESC LIMIT 1"
            ).fetchone()
            pokemon_count = int(connection.execute("SELECT COUNT(*) FROM pokemon").fetchone()[0])
            if schema_version != SCHEMA_VERSION or run is None or run["status"] != "failed" or pokemon_count == 0:
                raise RuntimeError("Temporary database is not a complete validation-failed import")
            run_id = int(run["id"])
            connection.execute(
                "UPDATE import_run SET status = 'running', completed_at = NULL, error_message = NULL WHERE id = ?",
                (run_id,),
            )
            self._hydrate_missing_card_images(connection)
            self.progress("Validating repaired database integrity and required assets")
            summary = self._validate(connection)
            connection.execute(
                "UPDATE import_run SET status = 'completed', completed_at = ? WHERE id = ?",
                (utc_now(), run_id),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            if "run_id" in locals():
                connection.execute(
                    "UPDATE import_run SET status = 'failed', completed_at = ?, error_message = ? WHERE id = ?",
                    (utc_now(), str(exc)[:1000], run_id),
                )
                connection.commit()
            raise
        finally:
            connection.close()

        self.progress(f"Validation passed. Replacing active database: {self.database_path}")
        os.replace(temporary_path, self.database_path)
        return summary

    def _hydrate_missing_card_images(self, connection: sqlite3.Connection) -> None:
        missing_assets = connection.execute(
            """
            SELECT a.id, a.card_id, c.name, c.set_id, c.number, a.source_url,
                   (SELECT fallback.source_url
                    FROM card_asset AS fallback
                    WHERE fallback.card_id = a.card_id AND fallback.asset_kind = 'small') AS fallback_url
            FROM card_asset AS a
            JOIN tcg_card AS c ON c.id = a.card_id
            WHERE a.asset_kind = 'large'
              AND (a.local_path IS NULL OR a.local_path = '')
              AND a.source_url IS NOT NULL
            ORDER BY a.card_id
            """
        ).fetchall()
        self.progress(f"Downloading {len(missing_assets):,} missing TCG card images")
        for position, asset in enumerate(missing_assets, start=1):
            destination = self._tcg_image_path(str(asset["card_id"]))
            metadata = self._image_metadata(destination) or self._download_image(asset["source_url"], destination)
            if metadata is None and asset["fallback_url"]:
                self.progress(f"  Falling back to small TCG image for {asset['card_id']}")
                metadata = self._download_image(asset["fallback_url"], destination)
            if metadata is None:
                self.progress(f"  Creating unavailable-image card for {asset['card_id']}")
                metadata = self._create_unavailable_card_image(
                    destination, asset["name"], asset["set_id"], asset["number"]
                )
            if metadata is not None:
                sha256, media_type, width, height = metadata
                connection.execute(
                    """
                    UPDATE card_asset
                    SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ?
                    WHERE id = ?
                    """,
                    (
                        destination.relative_to(self.project_root).as_posix(), media_type,
                        sha256, width, height, asset["id"],
                    ),
                )
            self._report_count("missing TCG images", position, len(missing_assets), every=1)

    def _read_seed(self, path: Path, source_kind: str, resource_kind: str) -> Any:
        raw = path.read_bytes()
        wrapper = json.loads(raw.decode("utf-8"))
        cached_at = wrapper.get("cached_at") if isinstance(wrapper, dict) else None
        value = unwrap_payload(wrapper)
        count = len(value) if isinstance(value, list) else 1
        self.imported_files.append(
            (source_kind, resource_kind, path, str(cached_at) if cached_at is not None else None, count)
        )
        return value

    def _fetch_json(self, url: str) -> dict[str, Any]:
        if not self.allow_network:
            raise RuntimeError(f"Missing seed requires network hydration: {url}")
        if url not in self._network_payloads:
            self.progress(f"  Fetching {url}")
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                self._network_payloads[url] = json.load(response)
        return self._network_payloads[url]

    def _import_species(self, connection: sqlite3.Connection) -> dict[str, int]:
        species_payloads: list[tuple[Path, dict[str, Any]]] = []
        species_paths = sorted(self.pokeapi_dir.glob("pokeapi-species-*.json"))
        self.progress(f"  Found {len(species_paths):,} species seed files")
        for position, path in enumerate(species_paths, start=1):
            payload = self._read_seed(path, "pokeapi", "species")
            if isinstance(payload, dict) and isinstance(payload.get("id"), int):
                species_payloads.append((path, payload))
            self._report_count("species files", position, len(species_paths), every=25)
        if not species_payloads:
            raise RuntimeError(f"No Pokemon species seeds found in {self.pokeapi_dir}")
        self._species_payloads = [payload for _, payload in species_payloads]

        for _, species in species_payloads:
            chain_id = resource_id(species.get("evolution_chain"))
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
                    species["id"], species["name"], resource_name(species.get("generation")), chain_id,
                    resource_name(species.get("color")), resource_name(species.get("shape")),
                    resource_name(species.get("habitat")), resource_name(species.get("growth_rate")),
                    species.get("capture_rate"), species.get("base_happiness"), species.get("gender_rate"),
                    species.get("hatch_counter"), bool(species.get("is_baby")),
                    bool(species.get("is_legendary")), bool(species.get("is_mythical")),
                ),
            )
            self._import_species_text(connection, species)

        species_by_name = {
            row["name"].casefold(): row["id"]
            for row in connection.execute("SELECT id, name FROM pokemon_species")
        }
        self._import_evolution_chains(connection, species_payloads, species_by_name)
        return species_by_name

    def _import_species_text(self, connection: sqlite3.Connection, species: dict[str, Any]) -> None:
        rows: list[tuple[int, str, str, str, str]] = []
        for item in species.get("names", []):
            rows.append((species["id"], resource_name(item.get("language")) or "", "", "name", item.get("name", "")))
        for item in species.get("genera", []):
            rows.append((species["id"], resource_name(item.get("language")) or "", "", "genus", item.get("genus", "")))
        for item in species.get("flavor_text_entries", []):
            text = str(item.get("flavor_text", "")).replace("\n", " ").replace("\f", " ")
            rows.append((
                species["id"], resource_name(item.get("language")) or "",
                resource_name(item.get("version")) or "", "flavor_text", text,
            ))
        connection.executemany(
            "INSERT OR IGNORE INTO species_text (species_id, language, version_name, text_kind, text) VALUES (?, ?, ?, ?, ?)",
            [row for row in rows if row[-1]],
        )

    def _import_evolution_chains(
        self,
        connection: sqlite3.Connection,
        species_payloads: Iterable[tuple[Path, dict[str, Any]]],
        species_by_name: dict[str, int],
    ) -> None:
        chain_urls = {
            resource_id(species.get("evolution_chain")): species["evolution_chain"]["url"]
            for _, species in species_payloads
            if resource_id(species.get("evolution_chain")) is not None
        }
        total_chains = len(chain_urls)
        self.progress(f"  Hydrating {total_chains:,} evolution chains")
        for position, (chain_id, url) in enumerate(sorted(chain_urls.items()), start=1):
            seed_path = self.pokeapi_dir / f"pokeapi-evolution-chain-{chain_id:04d}.json"
            if seed_path.exists():
                payload = self._read_seed(seed_path, "pokeapi", "evolution")
            elif self.allow_network:
                payload = self._fetch_json(url)
            else:
                self._report_count("evolution chains", position, total_chains, every=25)
                continue
            connection.execute(
                "UPDATE evolution_chain SET baby_trigger_item_name = ? WHERE id = ?",
                (resource_name(payload.get("baby_trigger_item")), chain_id),
            )
            self._import_evolution_node(connection, chain_id, payload.get("chain"), None, 0, species_by_name)
            self._report_count("evolution chains", position, total_chains, every=25)

    def _import_evolution_node(
        self,
        connection: sqlite3.Connection,
        chain_id: int,
        node: Any,
        parent_node_id: int | None,
        sort_order: int,
        species_by_name: dict[str, int],
    ) -> None:
        if not isinstance(node, dict):
            return
        species_name = resource_name(node.get("species"))
        species_id = species_by_name.get((species_name or "").casefold())
        if species_id is None:
            return
        cursor = connection.execute(
            "INSERT INTO evolution_node (chain_id, species_id, parent_node_id, sort_order) VALUES (?, ?, ?, ?)",
            (chain_id, species_id, parent_node_id, sort_order),
        )
        node_id = int(cursor.lastrowid)
        for detail in node.get("evolution_details", []):
            connection.execute(
                """
                INSERT INTO evolution_condition (
                    node_id, trigger_name, item_name, held_item_name, known_move_name,
                    known_move_type_name, location_name, min_level, min_happiness, min_beauty,
                    min_affection, time_of_day, gender, needs_overworld_rain, turn_upside_down,
                    relative_physical_stats
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id, resource_name(detail.get("trigger")), resource_name(detail.get("item")),
                    resource_name(detail.get("held_item")), resource_name(detail.get("known_move")),
                    resource_name(detail.get("known_move_type")), resource_name(detail.get("location")),
                    detail.get("min_level"), detail.get("min_happiness"), detail.get("min_beauty"),
                    detail.get("min_affection"), detail.get("time_of_day"), detail.get("gender"),
                    bool(detail.get("needs_overworld_rain")), bool(detail.get("turn_upside_down")),
                    detail.get("relative_physical_stats"),
                ),
            )
        for child_order, child in enumerate(node.get("evolves_to", [])):
            self._import_evolution_node(connection, chain_id, child, node_id, child_order, species_by_name)

    def _import_pokemon(self, connection: sqlite3.Connection, species_by_name: dict[str, int]) -> None:
        payloads: dict[str, dict[str, Any]] = {}
        pokemon_paths = sorted(self.pokeapi_dir.glob("pokeapi-[0-9]*.json"))
        self.progress(f"  Found {len(pokemon_paths):,} Pokemon seed files")
        for position, path in enumerate(pokemon_paths, start=1):
            payload = self._read_seed(path, "pokeapi", "pokemon")
            if isinstance(payload, dict) and payload.get("name"):
                payloads[str(payload["name"]).casefold()] = payload
            self._report_count("Pokemon seed files", position, len(pokemon_paths), every=25)

        varieties = []
        for species in self._species_payloads:
            varieties.extend(species.get("varieties", []))
        missing_varieties = []
        for variety in varieties:
            pokemon_ref = variety.get("pokemon", {})
            name = str(pokemon_ref.get("name", "")).casefold()
            if name and name not in payloads:
                missing_varieties.append((name, pokemon_ref.get("url") or f"{POKEAPI_ROOT}/pokemon/{name}"))
        self.progress(f"  Fetching {len(missing_varieties):,} forms missing from seed files")
        for position, (name, url) in enumerate(missing_varieties, start=1):
            payloads[name] = self._fetch_json(url)
            self._report_count("missing forms", position, len(missing_varieties), every=10)

        if not payloads:
            raise RuntimeError(f"No Pokemon seeds found in {self.pokeapi_dir}")
        sorted_payloads = sorted(payloads.values(), key=lambda item: int(item["id"]))
        self.progress(f"  Writing {len(sorted_payloads):,} Pokemon forms")
        for position, pokemon in enumerate(sorted_payloads, start=1):
            species_name = resource_name(pokemon.get("species")) or pokemon.get("name")
            species_id = resource_id(pokemon.get("species")) or species_by_name.get(str(species_name).casefold())
            if species_id not in species_by_name.values():
                raise RuntimeError(f"Pokemon {pokemon.get('name')} references missing species {species_id}")
            connection.execute(
                """
                INSERT INTO pokemon (id, species_id, name, display_order, is_default, base_experience,
                                     height_decimetres, weight_hectograms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pokemon["id"], species_id, pokemon["name"], pokemon.get("order", pokemon["id"]),
                    bool(pokemon.get("is_default")), pokemon.get("base_experience"),
                    pokemon.get("height"), pokemon.get("weight"),
                ),
            )
            self._import_pokemon_relations(connection, pokemon)
            self._import_pokemon_assets(connection, pokemon)
            self._report_count("Pokemon forms", position, len(sorted_payloads), every=25)

    def _lookup(self, connection: sqlite3.Connection, table: str, resource: dict[str, Any]) -> int:
        name = str(resource.get("name", ""))
        identifier = resource_id(resource)
        row = connection.execute(f"SELECT id FROM {table} WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        if row:
            return int(row[0])
        if identifier is None:
            identifier = int(connection.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}").fetchone()[0])
        connection.execute(f"INSERT INTO {table} (id, name) VALUES (?, ?)", (identifier, name))
        return identifier

    def _import_pokemon_relations(self, connection: sqlite3.Connection, pokemon: dict[str, Any]) -> None:
        pokemon_id = pokemon["id"]
        for item in pokemon.get("types", []):
            type_id = self._lookup(connection, "type", item["type"])
            connection.execute("INSERT INTO pokemon_type VALUES (?, ?, ?)", (pokemon_id, type_id, item["slot"]))
        for item in pokemon.get("abilities", []):
            ability_id = self._lookup(connection, "ability", item["ability"])
            connection.execute(
                "INSERT INTO pokemon_ability VALUES (?, ?, ?, ?)",
                (pokemon_id, ability_id, item["slot"], bool(item.get("is_hidden"))),
            )
        for item in pokemon.get("stats", []):
            stat_id = self._lookup(connection, "stat", item["stat"])
            connection.execute(
                "INSERT INTO pokemon_stat VALUES (?, ?, ?, ?)",
                (pokemon_id, stat_id, item["base_stat"], item.get("effort", 0)),
            )

    def _import_pokemon_assets(self, connection: sqlite3.Connection, pokemon: dict[str, Any]) -> None:
        sprites = pokemon.get("sprites") if isinstance(pokemon.get("sprites"), dict) else {}
        other = sprites.get("other") if isinstance(sprites.get("other"), dict) else {}
        official = other.get("official-artwork") if isinstance(other.get("official-artwork"), dict) else {}
        artwork_url = official.get("front_default")
        local_path = None
        sha256 = None
        width = None
        height = None
        if artwork_url and self.download_artwork:
            destination = self.asset_dir / "pokemon" / "official-artwork" / f"{pokemon['id']}.png"
            metadata = self._image_metadata(destination)
            if metadata is None:
                if not self.allow_network:
                    raise RuntimeError(f"Official artwork is missing for {pokemon['name']}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                self.progress(f"  Downloading artwork for #{pokemon['id']} {pokemon['name']}")
                request = urllib.request.Request(artwork_url, headers={"User-Agent": USER_AGENT})
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        temporary.write_bytes(response.read())
                    metadata = self._image_metadata(temporary)
                    if metadata is None:
                        raise RuntimeError(f"Downloaded artwork is invalid for {pokemon['name']}")
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            local_path = destination.relative_to(self.project_root).as_posix()
            sha256, _, width, height = metadata
        connection.execute(
            """
            INSERT INTO pokemon_asset
                (pokemon_id, asset_kind, local_path, source_url, media_type, sha256, width, height)
            VALUES (?, 'official_artwork', ?, ?, 'image/png', ?, ?, ?)
            """,
            (pokemon["id"], local_path, artwork_url, sha256, width, height),
        )
        for kind, url in (("cry_latest", pokemon.get("cries", {}).get("latest")), ("cry_legacy", pokemon.get("cries", {}).get("legacy"))):
            if url:
                connection.execute(
                    "INSERT INTO pokemon_asset (pokemon_id, asset_kind, source_url, media_type) VALUES (?, ?, ?, 'audio/ogg')",
                    (pokemon["id"], kind, url),
                )

    def _import_tcg(self, connection: sqlite3.Connection, species_by_name: dict[str, int]) -> None:
        cards_by_id: dict[str, dict[str, Any]] = {}
        tcg_paths = sorted(self.tcg_dir.glob("*.json"))
        self.progress(f"  Reading {len(tcg_paths):,} TCG seed files")
        for position, path in enumerate(tcg_paths, start=1):
            response = self._read_seed(path, "tcg", "card_search")
            cards = response.get("data") or response.get("cards") or [] if isinstance(response, dict) else []
            accepted = 0
            for card in cards:
                if isinstance(card, dict) and card.get("id"):
                    cards_by_id.setdefault(str(card["id"]), card)
                    accepted += 1
            source_kind, resource_kind, file_path, cached_at, _ = self.imported_files[-1]
            self.imported_files[-1] = (source_kind, resource_kind, file_path, cached_at, accepted)
            self._report_count("TCG seed files", position, len(tcg_paths), every=25)

        self.progress(f"  Found {len(cards_by_id):,} unique TCG cards")
        for card in cards_by_id.values():
            self._import_set(connection, card.get("set", {}))
        sorted_cards = sorted(cards_by_id.values(), key=lambda item: str(item["id"]))
        for position, card in enumerate(sorted_cards, start=1):
            self._import_card(connection, card, species_by_name)
            self._report_count("TCG cards", position, len(sorted_cards), every=250)

    def _report_count(self, label: str, current: int, total: int, *, every: int) -> None:
        if total and (current % every == 0 or current == total):
            percent = current * 100 / total
            self.progress(f"  {label}: {current:,}/{total:,} ({percent:.0f}%)")

    def _import_set(self, connection: sqlite3.Connection, value: dict[str, Any]) -> None:
        if not value.get("id"):
            return
        connection.execute(
            """
            INSERT OR IGNORE INTO tcg_set
                (id, name, series, printed_total, total, ptcgo_code, release_date, api_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                value["id"], value.get("name", value["id"]), value.get("series"), value.get("printedTotal"),
                value.get("total"), value.get("ptcgoCode"), str(value.get("releaseDate", "")).replace("/", "-") or None,
                value.get("updatedAt"),
            ),
        )
        for name, status in value.get("legalities", {}).items():
            connection.execute("INSERT OR IGNORE INTO set_legality VALUES (?, ?, ?)", (value["id"], name, status))
        for kind, url in value.get("images", {}).items():
            if kind in {"logo", "symbol"}:
                connection.execute(
                    "INSERT OR IGNORE INTO set_asset (set_id, asset_kind, source_url) VALUES (?, ?, ?)",
                    (value["id"], kind, url),
                )

    def _import_card(
        self,
        connection: sqlite3.Connection,
        card: dict[str, Any],
        species_by_name: dict[str, int],
    ) -> None:
        set_id = card.get("set", {}).get("id")
        if not set_id:
            return
        connection.execute(
            """
            INSERT INTO tcg_card (
                id, set_id, name, number, supertype, level, hp, evolves_from, converted_retreat_cost,
                rarity, artist, flavor_text, regulation_mark, rules_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card["id"], set_id, card.get("name", card["id"]), str(card.get("number", "")),
                card.get("supertype"), card.get("level"), parse_int(card.get("hp")), card.get("evolvesFrom"),
                card.get("convertedRetreatCost"), card.get("rarity"), card.get("artist"),
                card.get("flavorText"), card.get("regulationMark"), "\n".join(card.get("rules", [])) or None,
            ),
        )
        card_id = str(card["id"])
        for species_id in card.get("nationalPokedexNumbers", []):
            if species_id in species_by_name.values():
                connection.execute("INSERT OR IGNORE INTO card_pokemon VALUES (?, ?)", (card_id, species_id))
        for slot, name in enumerate(card.get("types", []), start=1):
            normalized_name = TCG_TYPE_NAMES.get(str(name).casefold(), str(name).casefold())
            type_id = self._lookup(connection, "type", {"name": normalized_name})
            connection.execute("INSERT OR IGNORE INTO card_type VALUES (?, ?, ?)", (card_id, type_id, slot))
        for slot, subtype in enumerate(card.get("subtypes", []), start=1):
            connection.execute("INSERT INTO card_subtype VALUES (?, ?, ?)", (card_id, subtype, slot))
        for order, ability in enumerate(card.get("abilities", [])):
            connection.execute(
                "INSERT INTO card_ability (card_id, name, ability_type, text, sort_order) VALUES (?, ?, ?, ?, ?)",
                (card_id, ability.get("name", ""), ability.get("type"), ability.get("text"), order),
            )
        for order, attack in enumerate(card.get("attacks", [])):
            cursor = connection.execute(
                """
                INSERT INTO card_attack (card_id, name, damage, text, converted_energy_cost, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (card_id, attack.get("name", ""), attack.get("damage"), attack.get("text"), attack.get("convertedEnergyCost"), order),
            )
            for slot, energy_type in enumerate(attack.get("cost", []), start=1):
                connection.execute("INSERT INTO card_attack_cost VALUES (?, ?, ?)", (cursor.lastrowid, energy_type, slot))
        for effect_kind, source_key in (("weakness", "weaknesses"), ("resistance", "resistances")):
            for order, effect in enumerate(card.get(source_key, [])):
                connection.execute(
                    "INSERT INTO card_effectiveness (card_id, effect_kind, type_name, value, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (card_id, effect_kind, effect.get("type", ""), effect.get("value"), order),
                )
        for slot, energy_type in enumerate(card.get("retreatCost", []), start=1):
            connection.execute("INSERT INTO card_retreat_cost VALUES (?, ?, ?)", (card_id, energy_type, slot))
        for name, status in card.get("legalities", {}).items():
            connection.execute("INSERT INTO card_legality VALUES (?, ?, ?)", (card_id, name, status))
        self._import_card_assets(connection, card)
        self._import_prices(connection, card)

    def _import_card_assets(self, connection: sqlite3.Connection, card: dict[str, Any]) -> None:
        cached_path = self._tcg_image_path(str(card["id"]))
        metadata = self._image_metadata(cached_path)
        images = card.get("images", {})
        large_url = images.get("large") if isinstance(images, dict) else None
        if metadata is None and large_url and self.allow_network:
            self.progress(f"  Downloading missing TCG image for {card['id']} ({card.get('name', 'unknown')})")
            metadata = self._download_image(large_url, cached_path)
            small_url = images.get("small")
            if metadata is None and small_url:
                self.progress(f"  Falling back to small TCG image for {card['id']}")
                metadata = self._download_image(small_url, cached_path)
            if metadata is None:
                self.progress(f"  Creating unavailable-image card for {card['id']}")
                metadata = self._create_unavailable_card_image(
                    cached_path, card.get("name", "Unknown card"),
                    card.get("set", {}).get("id", "Unknown set"), card.get("number", "?"),
                )
        for kind, url in images.items():
            if kind not in {"small", "large"}:
                continue
            has_local_image = kind == "large" and metadata is not None
            local_path = cached_path.relative_to(self.project_root).as_posix() if has_local_image else None
            sha256, detected_media_type, width, height = metadata if has_local_image else (None, None, None, None)
            media_type = detected_media_type or mimetypes.guess_type(str(url))[0]
            connection.execute(
                """
                INSERT INTO card_asset
                    (card_id, asset_kind, local_path, source_url, media_type, sha256, width, height)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (card["id"], kind, local_path, url, media_type, sha256, width, height),
            )

    def _tcg_image_path(self, card_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", card_id).strip("-")
        suffix = hashlib.sha1(card_id.encode("utf-8")).hexdigest()[:8]
        return self.project_root / "data" / "assets" / "tcg" / f"{safe_id}-{suffix}.img"

    def _download_image(self, url: str, destination: Path) -> tuple[str, str | None, int, int] | None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                temporary.write_bytes(response.read())
            metadata = self._image_metadata(temporary)
            if metadata is None:
                self.progress(f"  Warning: downloaded image was invalid: {url}")
                return None
            os.replace(temporary, destination)
            return metadata
        except (OSError, ValueError) as exc:
            self.progress(f"  Warning: image download failed for {url}: {exc}")
            return None
        finally:
            temporary.unlink(missing_ok=True)

    def _create_unavailable_card_image(
        self, destination: Path, name: str, set_id: str, number: str
    ) -> tuple[str, str | None, int, int]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        image = Image.new("RGB", (488, 680), "#f3f0e7")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=24)
        small_font = ImageFont.load_default(size=18)
        draw.rounded_rectangle((24, 24, 464, 656), radius=16, outline="#27313b", width=4)
        draw.text((56, 250), name, fill="#182028", font=font)
        draw.text((56, 300), "IMAGE UNAVAILABLE", fill="#a43b32", font=small_font)
        draw.text((56, 340), f"Set {set_id}  |  Card {number}", fill="#58636d", font=small_font)
        try:
            image.save(temporary, format="PNG", optimize=True)
            os.replace(temporary, destination)
        finally:
            image.close()
            temporary.unlink(missing_ok=True)
        metadata = self._image_metadata(destination)
        if metadata is None:
            raise RuntimeError(f"Unable to create fallback image for {name}")
        return metadata

    @staticmethod
    def _image_metadata(path: Path) -> tuple[str, str | None, int, int] | None:
        if not path.is_file():
            return None
        try:
            with Image.open(path) as image:
                width, height = image.size
                media_type = Image.MIME.get(image.format)
                image.verify()
            return hashlib.sha256(path.read_bytes()).hexdigest(), media_type, width, height
        except (OSError, UnidentifiedImageError, ValueError):
            return None

    def _import_prices(self, connection: sqlite3.Connection, card: dict[str, Any]) -> None:
        for provider, currency in (("tcgplayer", "USD"), ("cardmarket", "EUR")):
            listing = card.get(provider)
            if not isinstance(listing, dict):
                continue
            cursor = connection.execute(
                "INSERT INTO card_market_listing (card_id, provider, listing_url, source_updated_at) VALUES (?, ?, ?, ?)",
                (card["id"], provider, listing.get("url"), listing.get("updatedAt")),
            )
            prices = listing.get("prices", {})
            if provider == "tcgplayer":
                observations = (
                    (variant, metric, amount)
                    for variant, metrics in prices.items() if isinstance(metrics, dict)
                    for metric, amount in metrics.items()
                )
            else:
                observations = (("default", metric, amount) for metric, amount in prices.items())
            for variant, metric, amount in observations:
                if isinstance(amount, (int, float)):
                    connection.execute(
                        "INSERT INTO card_price VALUES (?, ?, ?, ?, ?)",
                        (cursor.lastrowid, variant, metric, amount, currency),
                    )

    def _record_import_files(self, connection: sqlite3.Connection, run_id: int) -> None:
        for source_kind, resource_kind, path, cached_at, record_count in self.imported_files:
            relative_path = path.relative_to(self.project_root).as_posix()
            connection.execute(
                """
                INSERT INTO import_file (
                    import_run_id, source_kind, resource_kind, relative_path, sha256,
                    source_cached_at, imported_at, record_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, source_kind, resource_kind, relative_path,
                    hashlib.sha256(path.read_bytes()).hexdigest(), cached_at, utc_now(), record_count,
                ),
            )

    def _validate(self, connection: sqlite3.Connection) -> ImportSummary:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise RuntimeError(f"Database validation failed: integrity={integrity}, foreign_keys={len(foreign_keys)}")
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("pokemon", "pokemon_species", "tcg_card", "tcg_set", "import_file")
        }
        if counts["pokemon"] == 0 or counts["pokemon_species"] == 0:
            raise RuntimeError("Database validation failed: Pokemon data is empty")
        if self.require_artwork:
            missing_artwork = connection.execute(
                """
                SELECT COUNT(*) FROM pokemon AS p
                LEFT JOIN pokemon_asset AS a ON a.pokemon_id = p.id AND a.asset_kind = 'official_artwork'
                WHERE p.is_default = 1 AND (a.local_path IS NULL OR a.local_path = '')
                """
            ).fetchone()[0]
            if missing_artwork:
                raise RuntimeError(f"Database validation failed: {missing_artwork} default Pokemon lack artwork")
        if self.require_card_images:
            missing_card_images = connection.execute(
                """
                SELECT COUNT(*) FROM tcg_card AS c
                LEFT JOIN card_asset AS a ON a.card_id = c.id AND a.asset_kind = 'large'
                WHERE a.local_path IS NULL OR a.local_path = ''
                """
            ).fetchone()[0]
            if missing_card_images:
                raise RuntimeError(f"Database validation failed: {missing_card_images} TCG cards lack local images")
        return ImportSummary(
            counts["pokemon"], counts["pokemon_species"], counts["tcg_card"],
            counts["tcg_set"], counts["import_file"],
        )