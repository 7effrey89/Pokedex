"""Fetch complete TCG refreshes and atomically normalize them into SQLite."""

import logging
import sqlite3
from typing import Any, Callable

from src.config import get_storage_paths
from src.config.paths import StoragePaths
from src.db.database import SqliteDatabase
from src.db.importer import SqliteImporter
from src.services.catalog_refresh import CatalogRefreshService, utc_now
from src.services.asset_manager import _image_metadata

logger = logging.getLogger(__name__)


def import_tcg_set(
    connection: sqlite3.Connection, importer: SqliteImporter,
    paths: StoragePaths, item: dict[str, Any],
) -> None:
    assets = connection.execute("SELECT * FROM set_asset WHERE set_id = ?", (item["id"],)).fetchall()
    importer._import_set(connection, item)
    if item.get("_source") == "tcgdex":
        for asset in assets:
            stored = paths.resolve_stored(asset["local_path"]) if asset["local_path"] else None
            if stored is not None and _image_metadata(stored) is not None:
                connection.execute(
                    "UPDATE set_asset SET local_path = ?, media_type = ?, sha256 = ? "
                    "WHERE set_id = ? AND asset_kind = ?",
                    (asset["local_path"], asset["media_type"], asset["sha256"], item["id"], asset["asset_kind"]),
                )


class TcgRefreshService:
    def __init__(self, client, database: SqliteDatabase | None = None):
        self.client = client
        self.database = database or SqliteDatabase()
        paths = get_storage_paths()
        self.paths = paths
        self.importer = SqliteImporter(
            paths.data_root, self.database.path, paths.data_root / "seeds" / "pokeapi",
            paths.data_root / "seeds" / "tcg", paths.data_root / "data" / "assets",
            allow_network=False, download_artwork=False,
            require_artwork=False, require_card_images=False,
        )
        self.snapshots = CatalogRefreshService(self.database)

    def _fetch_pages(self, fetch: Callable[..., Any]) -> list[dict[str, Any]]:
        items = []
        page = 1
        while True:
            response = fetch(page=page, page_size=250)
            if not isinstance(response, dict) or not isinstance(response.get("data"), list):
                raise RuntimeError(f"TCG API refresh failed on page {page}")
            batch = response["data"]
            if any(not isinstance(item, dict) or not item.get("id") for item in batch):
                raise ValueError(f"Invalid TCG API payload on page {page}")
            items.extend(batch)
            total = response.get("totalCount")
            if total is not None:
                if len(items) >= int(total):
                    return items
                if not batch:
                    raise RuntimeError("TCG API pagination ended before all records were received")
            elif len(batch) < 250:
                return items
            page += 1

    def refresh_search(self, **filters) -> None:
        cards = self._fetch_pages(lambda **page: self.client.search_cards_advanced(**filters, **page))
        self._persist(cards=cards)

    def refresh_set(self, set_id: str) -> None:
        cards = self._fetch_pages(
            lambda **page: self.client.search_cards_by_set(set_id, **page)
        )
        self._persist(cards=cards)

    def refresh_sets(self) -> None:
        self._persist(sets=self._fetch_pages(self.client.get_sets))

    def refresh_card(self, card_id: str) -> None:
        response = self.client.get_card(card_id)
        card = response.get("data") if isinstance(response, dict) else None
        if not isinstance(card, dict) or card.get("id") != card_id:
            raise RuntimeError(f"Unable to refresh TCG card {card_id}")
        self._persist(cards=[card])

    def _persist(self, *, cards: list[dict] | None = None, sets: list[dict] | None = None) -> None:
        cards = cards or []
        sets = sets or []
        for card in cards:
            if not isinstance(card.get("set"), dict) or not card["set"].get("id"):
                raise ValueError(f"TCG card {card['id']} has no set")
        self.snapshots._store_raw("tcg", "refresh", "catalog", {"cards": cards, "sets": sets})
        connection = self.database.connect()
        try:
            species = {
                row["name"].casefold(): row["id"]
                for row in connection.execute("SELECT id, name FROM pokemon_species")
            }
            for item in sets:
                import_tcg_set(connection, self.importer, self.paths, item)
                connection.execute(
                    "UPDATE tcg_set SET last_refreshed_at = ? WHERE id = ?", (utc_now(), item["id"])
                )
            for card in cards:
                import_tcg_set(connection, self.importer, self.paths, card["set"])
                assets = connection.execute(
                    "SELECT * FROM card_asset WHERE card_id = ?", (card["id"],)
                ).fetchall()
                preserved_prices = []
                if card.get("_source") == "tcgdex":
                    for listing in connection.execute(
                        "SELECT * FROM card_market_listing WHERE card_id = ?", (card["id"],),
                    ):
                        if not card.get(listing["provider"], {}).get("prices"):
                            prices = connection.execute(
                                "SELECT * FROM card_price WHERE listing_id = ?", (listing["id"],),
                            ).fetchall()
                            if prices:
                                preserved_prices.append((listing, prices))
                                logger.warning("TCGdex has no %s prices for %s; preserving stored observations",
                                               listing["provider"], card["id"])
                connection.execute("DELETE FROM tcg_card WHERE id = ?", (card["id"],))
                self.importer._import_card(connection, card, species)
                for listing, prices in preserved_prices:
                    connection.execute(
                        "DELETE FROM card_market_listing WHERE card_id = ? AND provider = ?",
                        (card["id"], listing["provider"]),
                    )
                    cursor = connection.execute(
                        "INSERT INTO card_market_listing (card_id, provider, listing_url, source_updated_at) "
                        "VALUES (?, ?, ?, ?)",
                        (card["id"], listing["provider"], listing["listing_url"], listing["source_updated_at"]),
                    )
                    connection.executemany("INSERT INTO card_price VALUES (?, ?, ?, ?, ?)", [
                        (cursor.lastrowid, price["variant"], price["metric"], price["amount"], price["currency"])
                        for price in prices
                    ])
                for asset in assets:
                    preserve_migrated = card.get("_source") == "tcgdex" and self._valid_local_image(asset)
                    if preserve_migrated:
                        connection.execute(
                            "INSERT OR IGNORE INTO card_asset (card_id, asset_kind, source_url) VALUES (?, ?, ?)",
                            (card["id"], asset["asset_kind"], asset["source_url"]),
                        )
                    connection.execute(
                        "UPDATE card_asset SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ? "
                        "WHERE card_id = ? AND asset_kind = ? AND (source_url = ? OR ?)",
                        (
                            asset["local_path"], asset["media_type"], asset["sha256"],
                            asset["width"], asset["height"], card["id"], asset["asset_kind"], asset["source_url"],
                            preserve_migrated,
                        ),
                    )
                connection.execute(
                    "UPDATE tcg_card SET last_refreshed_at = ? WHERE id = ?", (utc_now(), card["id"])
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _valid_local_image(self, asset: sqlite3.Row) -> bool:
        stored = self.paths.resolve_stored(asset["local_path"]) if asset["local_path"] else None
        return stored is not None and _image_metadata(stored) is not None
