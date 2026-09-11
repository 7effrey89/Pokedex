"""Read-only Pokemon TCG queries backed by the normalized SQLite database."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.db.database import SqliteDatabase


class SqliteTcgRepository:
    """Build the existing TCG handler response shapes from SQLite rows."""

    def __init__(self, database: SqliteDatabase | None = None):
        self.database = database or SqliteDatabase()

    def get_sets(self) -> dict[str, Any]:
        connection = self.database.connect(read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT s.id, s.name, s.series, s.release_date, s.total,
                       logo.source_url AS logo_url, symbol.source_url AS symbol_url
                FROM tcg_set AS s
                LEFT JOIN set_asset AS logo
                  ON logo.set_id = s.id AND logo.asset_kind = 'logo'
                LEFT JOIN set_asset AS symbol
                  ON symbol.set_id = s.id AND symbol.asset_kind = 'symbol'
                ORDER BY s.release_date DESC, s.name COLLATE NOCASE
                """
            ).fetchall()
            sets = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "series": row["series"],
                    "releaseDate": row["release_date"],
                    "total": row["total"] or 0,
                    "images": {"logo": row["logo_url"], "symbol": row["symbol_url"]},
                }
                for row in rows
            ]
            return {"sets": sets, "total_count": len(sets)}
        finally:
            connection.close()

    def get_cards_by_set(self, set_id: str, *, slim: bool = False, limit: int = 0) -> dict[str, Any]:
        connection = self.database.connect(read_only=True)
        try:
            set_row = connection.execute(
                "SELECT id, name, release_date FROM tcg_set WHERE id = ?",
                (set_id,),
            ).fetchone()
            if set_row is None:
                return {"error": f"No cards found for set: {set_id}"}

            total_count = int(
                connection.execute("SELECT COUNT(*) FROM tcg_card WHERE set_id = ?", (set_id,)).fetchone()[0]
            )
            sql = """
                SELECT c.id, c.name, c.number, c.supertype, c.rarity,
                       c.hp, c.level, c.evolves_from, c.converted_retreat_cost,
                       c.artist, c.flavor_text, c.regulation_mark, c.rules_text
                FROM tcg_card AS c
                WHERE c.set_id = ?
                ORDER BY
                    CASE WHEN c.number GLOB '[0-9]*' THEN CAST(c.number AS INTEGER) END,
                    c.number COLLATE NOCASE, c.name COLLATE NOCASE
            """
            parameters: list[Any] = [set_id]
            if limit > 0:
                sql += " LIMIT ?"
                parameters.append(limit)
            card_rows = connection.execute(sql, parameters).fetchall()
            cards = self._hydrate_cards(connection, card_rows, set_row, slim=slim)
            return {
                "cards": cards,
                "total_count": total_count,
                "search_query": set_row["name"],
                "set_id": set_id,
            }
        finally:
            connection.close()

    def get_card(self, card_id: str) -> dict[str, Any]:
        connection = self.database.connect(read_only=True)
        try:
            row = connection.execute(
                """
                SELECT c.*, s.name AS set_name, s.release_date
                FROM tcg_card AS c
                JOIN tcg_set AS s ON s.id = c.set_id
                WHERE c.id = ?
                """,
                (card_id,),
            ).fetchone()
            if row is None:
                return {"error": f"Card not found: {card_id}"}
            set_row = {"id": row["set_id"], "name": row["set_name"], "release_date": row["release_date"]}
            return self._hydrate_cards(connection, [row], set_row, slim=False)[0]
        finally:
            connection.close()

    def _hydrate_cards(self, connection, rows, set_row, *, slim: bool) -> list[dict[str, Any]]:
        if not rows:
            return []
        card_ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in card_ids)

        def grouped(query: str) -> dict[str, list[Any]]:
            values: dict[str, list[Any]] = defaultdict(list)
            for result in connection.execute(query, card_ids):
                values[result["card_id"]].append(result)
            return values

        subtypes = grouped(
            f"SELECT card_id, subtype AS value FROM card_subtype WHERE card_id IN ({placeholders}) ORDER BY slot"
        )
        types = grouped(
            f"""SELECT ct.card_id, t.name AS value FROM card_type AS ct
                JOIN type AS t ON t.id = ct.type_id
                WHERE ct.card_id IN ({placeholders}) ORDER BY ct.slot"""
        )
        species = grouped(
            f"""SELECT cp.card_id, ps.id AS value FROM card_pokemon AS cp
                JOIN pokemon_species AS ps ON ps.id = cp.species_id
                WHERE cp.card_id IN ({placeholders}) ORDER BY ps.id"""
        )
        prices = grouped(
            f"""SELECT l.card_id, p.variant, p.metric, p.amount FROM card_market_listing AS l
                JOIN card_price AS p ON p.listing_id = l.id
                WHERE l.provider = 'tcgplayer' AND l.card_id IN ({placeholders})"""
        )

        cards = []
        for row in rows:
            card_id = row["id"]
            card_prices: dict[str, dict[str, float]] = defaultdict(dict)
            for price in prices[card_id]:
                if price["metric"] in {"market", "mid"}:
                    card_prices[price["variant"]][price["metric"]] = price["amount"]
            card = {
                "id": card_id,
                "name": row["name"],
                "number": row["number"],
                "supertype": row["supertype"],
                "subtypes": [value["value"] for value in subtypes[card_id]],
                "types": [value["value"].title() for value in types[card_id]],
                "rarity": row["rarity"],
                "nationalPokedexNumbers": [value["value"] for value in species[card_id]],
                "images": {
                    "small": f"/api/tcg/card-image/{card_id}/large",
                    "large": f"/api/tcg/card-image/{card_id}/large",
                },
                "set": {
                    "id": set_row["id"],
                    "name": set_row["name"],
                    "releaseDate": set_row["release_date"],
                },
                "tcgplayer": {"prices": dict(card_prices)} if card_prices else {},
            }
            if not slim:
                card.update({
                    "hp": row["hp"],
                    "level": row["level"],
                    "evolvesFrom": row["evolves_from"],
                    "convertedRetreatCost": row["converted_retreat_cost"],
                    "artist": row["artist"],
                    "flavorText": row["flavor_text"],
                    "regulationMark": row["regulation_mark"],
                    "rules": [row["rules_text"]] if row["rules_text"] else [],
                })
            cards.append(card)
        return cards

    def get_image_path(self, card_id: str, asset_kind: str) -> str | None:
        if asset_kind not in {"small", "large"}:
            return None
        connection = self.database.connect(read_only=True)
        try:
            row = connection.execute(
                """
                SELECT COALESCE(requested.local_path, fallback.local_path) AS local_path
                FROM tcg_card AS c
                LEFT JOIN card_asset AS requested
                  ON requested.card_id = c.id AND requested.asset_kind = ?
                LEFT JOIN card_asset AS fallback
                  ON fallback.card_id = c.id AND fallback.asset_kind = 'large'
                WHERE c.id = ?
                """,
                (asset_kind, card_id),
            ).fetchone()
            return row["local_path"] if row else None
        finally:
            connection.close()
