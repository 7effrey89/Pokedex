"""Portable catalog registrations accompanying asset ZIP components."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from src.config.paths import StoragePaths
from src.services.asset_manager import COMPONENTS

logger = logging.getLogger(__name__)
ASSET_TABLES = {
    "pokemon_images": (("pokemon_asset", "pokemon_id", COMPONENTS["pokemon_images"]["kinds"]),),
    "pokemon_cries": (("pokemon_asset", "pokemon_id", COMPONENTS["pokemon_cries"]["kinds"]),),
    "tcg_images": (("card_asset", "card_id", ("large", "small")), ("set_asset", "set_id", ("logo", "symbol"))),
}


def collect_asset_records(paths: StoragePaths, components: list[str], files: list[dict]) -> list[dict]:
    if not paths.catalog_database.is_file():
        return []
    archived = {entry["path"] for entry in files}
    records = []
    with closing(sqlite3.connect(f"{paths.catalog_database.as_uri()}?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        for component in components:
            for table, owner, kinds in ASSET_TABLES.get(component, ()):
                placeholders = ",".join("?" for _ in kinds)
                for row in connection.execute(
                    f"SELECT * FROM {table} WHERE asset_kind IN ({placeholders}) AND local_path IS NOT NULL", kinds
                ):
                    source = (paths.data_root / row["local_path"]).resolve()
                    try:
                        relative = source.relative_to(paths.asset_directories()[component].resolve())
                    except ValueError:
                        logger.warning("Omitting asset registration outside %s: %s", component, row["local_path"])
                        continue
                    entry = f"{component}/{relative.as_posix()}"
                    if entry not in archived:
                        continue
                    records.append({
                        "component": component, "table": table, "owner_id": row[owner],
                        "asset_kind": row["asset_kind"], "source_url": row["source_url"], "path": entry,
                        **{key: row[key] for key in ("media_type", "sha256", "width", "height") if key in row.keys()},
                    })
    return records


def validate_asset_records(manifest: dict, requested: set[str]) -> None:
    files = {entry["path"]: entry for entry in manifest["files"]}
    records = manifest.get("asset_records", [])
    if not isinstance(records, list):
        raise ValueError("Invalid asset registrations in backup")
    for record in records:
        component = record["component"]
        if component not in requested:
            continue
        tables = {table: kinds for table, _, kinds in ASSET_TABLES.get(component, ())}
        entry = files.get(record["path"])
        if (
            record["table"] not in tables or record["asset_kind"] not in tables[record["table"]]
            or entry is None or entry["component"] != component
            or (record.get("sha256") is not None and record["sha256"] != entry["sha256"])
        ):
            raise ValueError("Asset registration does not match an archived asset")


def restore_asset_records(paths: StoragePaths, manifest: dict, requested: set[str]) -> int:
    if not paths.catalog_database.is_file():
        if any(record["component"] in requested for record in manifest.get("asset_records", [])):
            logger.warning("Asset files restored without a catalog; import the catalog database to register them")
        return 0
    with closing(sqlite3.connect(paths.catalog_database)) as connection:
        if "catalog_database" in requested:
            for table in ("pokemon_asset", "card_asset", "set_asset"):
                for asset_id, local_path in connection.execute(
                    f"SELECT id, local_path FROM {table} WHERE local_path IS NOT NULL AND local_path != ''"
                ).fetchall():
                    candidate = (paths.data_root / local_path).resolve()
                    if not candidate.is_relative_to(paths.data_root.resolve()) or not candidate.is_file():
                        connection.execute(f"UPDATE {table} SET local_path = NULL WHERE id = ?", (asset_id,))
        restored = 0
        for record in manifest.get("asset_records", []):
            component = record["component"]
            if component not in requested:
                continue
            table = record["table"]
            owner = next(owner for name, owner, _ in ASSET_TABLES[component] if name == table)
            relative = Path(record["path"]).relative_to(component)
            target = paths.asset_directories()[component] / relative
            columns = ["local_path", "media_type", "sha256"]
            values = [target.relative_to(paths.data_root).as_posix(), record.get("media_type"), record.get("sha256")]
            if table != "set_asset":
                columns.extend(("width", "height"))
                values.extend((record.get("width"), record.get("height")))
            cursor = connection.execute(
                f"UPDATE {table} SET {', '.join(f'{column} = ?' for column in columns)} "
                f"WHERE {owner} = ? AND asset_kind = ? AND source_url IS ?",
                (*values, record["owner_id"], record["asset_kind"], record["source_url"]),
            )
            restored += cursor.rowcount
            if cursor.rowcount == 0:
                logger.warning("No matching catalog registration for restored asset %s", record["path"])
        connection.commit()
        return restored
