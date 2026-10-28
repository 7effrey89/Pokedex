"""Fetch complete TCG refreshes and atomically normalize them into SQLite."""

from typing import Any, Callable

from src.config import get_storage_paths
from src.db.database import SqliteDatabase
from src.db.importer import SqliteImporter
from src.services.catalog_refresh import CatalogRefreshService, utc_now


class TcgRefreshService:
    def __init__(self, client, database: SqliteDatabase | None = None):
        self.client = client
        self.database = database or SqliteDatabase()
        paths = get_storage_paths()
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
                self.importer._import_set(connection, item)
                connection.execute(
                    "UPDATE tcg_set SET last_refreshed_at = ? WHERE id = ?", (utc_now(), item["id"])
                )
            for card in cards:
                self.importer._import_set(connection, card["set"])
                assets = connection.execute(
                    "SELECT * FROM card_asset WHERE card_id = ?", (card["id"],)
                ).fetchall()
                connection.execute("DELETE FROM tcg_card WHERE id = ?", (card["id"],))
                self.importer._import_card(connection, card, species)
                for asset in assets:
                    connection.execute(
                        "UPDATE card_asset SET local_path = ?, media_type = ?, sha256 = ?, width = ?, height = ? "
                        "WHERE card_id = ? AND asset_kind = ? AND source_url = ?",
                        (
                            asset["local_path"], asset["media_type"], asset["sha256"],
                            asset["width"], asset["height"], card["id"], asset["asset_kind"], asset["source_url"],
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
