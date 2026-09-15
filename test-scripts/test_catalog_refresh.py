import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.db.database import SqliteDatabase, apply_catalog_schema
from src.services.catalog_refresh import CatalogRefreshService


class CatalogRefreshTests(unittest.TestCase):
    def test_refresh_pokemon_updates_catalog_and_retains_raw_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = SqliteDatabase(root / "catalog.sqlite3")
            connection = sqlite3.connect(database.path)
            connection.row_factory = sqlite3.Row
            apply_catalog_schema(connection)
            connection.execute("INSERT INTO pokemon_species (id, name) VALUES (25, 'pikachu')")
            connection.execute(
                "INSERT INTO pokemon (id, species_id, name, display_order) VALUES (25, 25, 'pikachu', 25)"
            )
            connection.commit()
            connection.close()

            payload = {
                "id": 25,
                "name": "pikachu",
                "order": 35,
                "is_default": True,
                "base_experience": 112,
                "height": 4,
                "weight": 60,
                "species": {"name": "pikachu", "url": "https://pokeapi.co/api/v2/pokemon-species/25/"},
                "types": [{"slot": 1, "type": {"name": "electric", "url": "https://pokeapi.co/api/v2/type/13/"}}],
                "abilities": [{"slot": 1, "is_hidden": False, "ability": {"name": "static", "url": "https://pokeapi.co/api/v2/ability/9/"}}],
                "stats": [{"base_stat": 90, "effort": 2, "stat": {"name": "speed", "url": "https://pokeapi.co/api/v2/stat/6/"}}],
                "sprites": {"other": {"official-artwork": {"front_default": "https://example.test/pikachu.png"}}},
                "cries": {"latest": "https://example.test/pikachu.ogg"},
            }

            snapshots = root / "snapshots"
            raw_path = CatalogRefreshService(database, snapshots).refresh_pokemon(payload)

            self.assertTrue(raw_path.is_file())
            self.assertEqual(payload, json.loads(raw_path.read_text(encoding="utf-8")))
            connection = database.connect(read_only=True)
            pokemon = connection.execute("SELECT * FROM pokemon WHERE id = 25").fetchone()
            self.assertEqual(112, pokemon["base_experience"])
            self.assertEqual(35, pokemon["display_order"])
            self.assertIsNotNone(pokemon["last_refreshed_at"])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM pokemon_type WHERE pokemon_id = 25").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM pokemon_ability WHERE pokemon_id = 25").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM pokemon_stat WHERE pokemon_id = 25").fetchone()[0])
            artwork = connection.execute(
                "SELECT source_url FROM pokemon_asset WHERE pokemon_id = 25 AND asset_kind = 'official_artwork'"
            ).fetchone()
            self.assertEqual("https://example.test/pikachu.png", artwork["source_url"])
            connection.close()


if __name__ == "__main__":
    unittest.main()