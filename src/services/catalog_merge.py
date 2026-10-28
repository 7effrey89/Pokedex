"""Merge normalized catalog snapshots without replacing or deleting destination data."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import StoragePaths
from src.db.database import SCHEMA_VERSION, SqliteDatabase
from src.services.backup_assets import local_asset_path


@dataclass(frozen=True)
class Table:
    keys: tuple[str, ...]
    references: dict[str, str] = field(default_factory=dict)
    parent: tuple[str, str] | None = None
    timestamps: tuple[str, ...] = ()
    generated_id: bool = False


# Source-generated row IDs must never be treated as identities across databases.
TABLES = {
    "schema_metadata": Table(("key",)),
    "catalog_setting": Table(("key",)),
    "import_run": Table(("started_at", "importer_version", "schema_version"), generated_id=True),
    "import_file": Table(("import_run_id", "relative_path"), {"import_run_id": "import_run"}, generated_id=True),
    "type": Table(("name",), generated_id=True),
    "ability": Table(("name",), generated_id=True),
    "stat": Table(("name",), generated_id=True),
    "evolution_chain": Table(("id",)),
    "pokemon_species": Table(("id",), {"evolution_chain_id": "evolution_chain"}, timestamps=("last_refreshed_at",)),
    "pokemon": Table(("id",), {"species_id": "pokemon_species"}, timestamps=("last_refreshed_at",)),
    "tcg_set": Table(("id",), timestamps=("api_updated_at", "last_refreshed_at")),
    "tcg_card": Table(("id",), {"set_id": "tcg_set"}, timestamps=("last_refreshed_at",)),
    "species_text": Table(("species_id", "language", "version_name", "text_kind", "text"),
                          {"species_id": "pokemon_species"}, ("pokemon_species", "species_id"), generated_id=True),
    "evolution_node": Table(("chain_id", "species_id", "parent_node_id", "sort_order"),
                            {"chain_id": "evolution_chain", "species_id": "pokemon_species",
                             "parent_node_id": "evolution_node"}, generated_id=True),
    "evolution_condition": Table((), {"node_id": "evolution_node"}, generated_id=True),
    "pokemon_type": Table(("pokemon_id", "slot"), {"pokemon_id": "pokemon", "type_id": "type"},
                          ("pokemon", "pokemon_id")),
    "pokemon_ability": Table(("pokemon_id", "slot"), {"pokemon_id": "pokemon", "ability_id": "ability"},
                             ("pokemon", "pokemon_id")),
    "pokemon_stat": Table(("pokemon_id", "stat_id"), {"pokemon_id": "pokemon", "stat_id": "stat"},
                          ("pokemon", "pokemon_id")),
    "type_damage_relation": Table(("type_id", "related_type_id", "relation_kind"),
                                  {"type_id": "type", "related_type_id": "type"}),
    "pokemon_asset": Table(("pokemon_id", "asset_kind"), {"pokemon_id": "pokemon"}, ("pokemon", "pokemon_id"),
                           generated_id=True),
    "card_pokemon": Table(("card_id", "species_id"), {"card_id": "tcg_card", "species_id": "pokemon_species"},
                          ("tcg_card", "card_id")),
    "card_type": Table(("card_id", "slot"), {"card_id": "tcg_card", "type_id": "type"}, ("tcg_card", "card_id")),
    "card_subtype": Table(("card_id", "slot"), {"card_id": "tcg_card"}, ("tcg_card", "card_id")),
    "card_ability": Table(("card_id", "sort_order"), {"card_id": "tcg_card"}, ("tcg_card", "card_id"), generated_id=True),
    "card_attack": Table(("card_id", "sort_order"), {"card_id": "tcg_card"}, ("tcg_card", "card_id"), generated_id=True),
    "card_attack_cost": Table(("attack_id", "slot"), {"attack_id": "card_attack"}, ("card_attack", "attack_id")),
    "card_effectiveness": Table(("card_id", "effect_kind", "sort_order"), {"card_id": "tcg_card"},
                                ("tcg_card", "card_id"), generated_id=True),
    "card_retreat_cost": Table(("card_id", "slot"), {"card_id": "tcg_card"}, ("tcg_card", "card_id")),
    "card_legality": Table(("card_id", "format_name"), {"card_id": "tcg_card"}, ("tcg_card", "card_id")),
    "set_legality": Table(("set_id", "format_name"), {"set_id": "tcg_set"}, ("tcg_set", "set_id")),
    "card_asset": Table(("card_id", "asset_kind"), {"card_id": "tcg_card"}, ("tcg_card", "card_id"), generated_id=True),
    "set_asset": Table(("set_id", "asset_kind"), {"set_id": "tcg_set"}, ("tcg_set", "set_id"), generated_id=True),
    "card_market_listing": Table(("card_id", "provider"), {"card_id": "tcg_card"},
                                 timestamps=("source_updated_at",), generated_id=True),
    "card_price": Table(("listing_id", "variant", "metric"), {"listing_id": "card_market_listing"},
                        ("card_market_listing", "listing_id")),
}
ASSET_COMPONENTS = {"card_asset": "tcg_images", "set_asset": "tcg_images"}
LOOKUPS = {"type", "ability", "stat"}
SLOT_UNIQUES = {
    "pokemon_type": ("pokemon_id", "type_id"),
    "card_type": ("card_id", "type_id"),
    "card_subtype": ("card_id", "subtype"),
}


def _freshness(source: dict, existing: dict, columns: tuple[str, ...]) -> int:
    def timestamp(row):
        for column in columns:
            value = row[column]
            if value:
                try:
                    parsed = datetime.fromisoformat(value.replace("/", "-"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid catalog timestamp in {column}: {value!r}") from exc
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        return None

    incoming, current = timestamp(source), timestamp(existing)
    if incoming is None:
        return 0 if current is None else -1
    if current is None:
        return 1
    return (incoming > current) - (incoming < current)


class CatalogMerger:
    def __init__(self, source: sqlite3.Connection, target: sqlite3.Connection, paths: StoragePaths):
        self.source, self.target, self.paths = source, target, paths
        self.ids: dict[str, dict] = {}
        self.accepted: dict[str, set] = {}
        self.eligible: dict[str, set] = {}
        self.counts = {"inserted": 0, "updated": 0, "preserved": 0}

    def merge(self) -> dict[str, int]:
        for table, spec in TABLES.items():
            self._merge_table(table, spec)
        if self.target.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Merged catalog failed its foreign key check")
        return self.counts

    def _rows(self, table: str) -> list[dict]:
        rows = [dict(row) for row in self.source.execute(f'SELECT * FROM "{table}"')]
        if table != "evolution_node":
            return rows
        ordered, seen = [], set()
        while rows:
            ready = [row for row in rows if row["parent_node_id"] is None or row["parent_node_id"] in seen]
            if not ready:
                raise ValueError("Evolution nodes contain a cyclic or missing parent")
            ordered.extend(ready)
            seen.update(row["id"] for row in ready)
            rows = [row for row in rows if row["id"] not in seen]
        return ordered

    def _merge_table(self, table: str, spec: Table) -> None:
        info = self.target.execute(f'PRAGMA table_info("{table}")').fetchall()
        columns = [row["name"] for row in info]
        source_columns = [row["name"] for row in self.source.execute(f'PRAGMA table_info("{table}")')]
        if not columns or set(columns) != set(source_columns):
            raise ValueError(f"Catalog schema does not match for table {table}")
        primary = [row["name"] for row in sorted(info, key=lambda row: row["pk"]) if row["pk"]]
        keys = spec.keys or tuple(column for column in columns if column != "id")
        mutable = [name for name in columns if name not in keys and name != "id"]
        if table in SLOT_UNIQUES:
            mutable.append("slot")

        def identity(row):
            return tuple(row[key].lower() if table in LOOKUPS and isinstance(row[key], str) else row[key]
                         for key in keys)

        existing = {}
        for item in self.target.execute(f'SELECT * FROM "{table}"'):
            row = dict(item)
            key = identity(row)
            if key in existing:
                if any(row[name] != existing[key][name] for name in columns if name != "id"):
                    raise ValueError(f"Ambiguous catalog identity in {table}: {key}")
                continue
            existing[key] = row
        originals = self._rows(table)
        matches = existing
        if table in SLOT_UNIQUES:
            # Match retained values first so type/subtype slot swaps do not collide with unique keys.
            owner, value = SLOT_UNIQUES[table]

            def unique(row):
                item = row[value]
                return row[owner], item.lower() if isinstance(item, str) else item

            incoming = [self._remap(row, spec) for row in originals]
            required = {unique(row) for row in incoming}
            by_unique = {unique(row): row for row in existing.values()}
            reusable = {key: row for key, row in existing.items() if unique(row) not in required}
            matches = {}
            seen = set()
            for row in incoming:
                key = identity(row)
                if key in seen:
                    raise ValueError(f"Ambiguous source slot in {table}: {key}")
                seen.add(key)
                previous = by_unique.get(unique(row))
                if previous is None:
                    candidates = [old for old in reusable.values() if old[owner] == row[owner]]
                    if candidates:
                        previous = min(candidates, key=lambda old: (old["slot"] != row["slot"], old["slot"]))
                        reusable.pop(identity(previous))
                if previous is not None:
                    matches[key] = previous

        self.ids[table], self.accepted[table], self.eligible[table] = {}, set(), set()
        for original in originals:
            parent_allowed = spec.parent is None or original[spec.parent[1]] in self.accepted[spec.parent[0]]
            parent_eligible = spec.parent is None or original[spec.parent[1]] in self.eligible[spec.parent[0]]
            if not parent_eligible:
                self.counts["preserved"] += 1
                continue
            row = self._remap(original, spec)
            key = identity(row)
            previous = matches.get(key)
            freshness = _freshness(row, previous, spec.timestamps) if previous and spec.timestamps else 0
            update = bool(mutable) and previous is not None and (
                freshness > 0 if spec.timestamps else spec.parent is not None and parent_allowed
            )
            if table in ("pokemon_asset", "card_asset", "set_asset"):
                if previous and self._local_asset(table, previous):
                    update = False
                elif not self._local_asset(table, row):
                    row["local_path"] = None
            if previous is None:
                names = [name for name in columns if not (spec.generated_id and name == "id")]
                cursor = self.target.execute(
                    f'INSERT INTO "{table}" ({", ".join(names)}) VALUES ({", ".join("?" for _ in names)})',
                    [row[name] for name in names],
                )
                if spec.generated_id:
                    row["id"] = cursor.lastrowid
                self.counts["inserted"] += 1
                accepted = True
            elif update:
                if "id" in row:
                    row["id"] = previous["id"]
                names = mutable
                self.target.execute(
                    f'UPDATE "{table}" SET {", ".join(f"{name} = ?" for name in names)} '
                    f'WHERE {" AND ".join(f"{name} IS ?" for name in primary)}',
                    [row[name] for name in names] + [previous[name] for name in primary],
                )
                self.counts["updated"] += 1
                accepted = True
            else:
                row = previous
                self.counts["preserved"] += 1
                accepted = False
            existing[key] = row
            if "id" in original:
                self.ids[table][original["id"]] = row["id"]
                if accepted:
                    self.accepted[table].add(original["id"])
                if freshness >= 0:
                    self.eligible[table].add(original["id"])

    def _remap(self, original: dict, spec: Table) -> dict:
        row = dict(original)
        for column, referenced in spec.references.items():
            if row[column] is not None:
                row[column] = self.ids[referenced][row[column]]
        return row

    def _local_asset(self, table: str, row: dict) -> bool:
        if not row.get("local_path"):
            return False
        component = ASSET_COMPONENTS.get(table)
        if component is None:
            component = "pokemon_cries" if row["asset_kind"].startswith("cry_") else "pokemon_images"
        return local_asset_path(self.paths, component, row["local_path"], row.get("sha256")) is not None


def merge_catalog(source_path: Path, paths: StoragePaths) -> dict[str, int]:
    database = SqliteDatabase(paths.catalog_database)
    if not database.path.exists():
        database.initialize()
    with closing(sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        with closing(database.connect()) as target:
            if target.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise ValueError("Destination catalog schema is unsupported; migrate it before importing")
            with target:
                target.execute("BEGIN IMMEDIATE")
                return CatalogMerger(source, target, paths).merge()
