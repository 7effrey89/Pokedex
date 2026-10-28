import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import SqliteDatabase
from src.config.paths import StoragePaths
from src.services.asset_manager import AssetManager


class AssetManagerTests(unittest.TestCase):
    def test_inventory_counts_catalog_assets_independently_of_local_downloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = SqliteDatabase(root / "catalog.sqlite3")
            database.initialize()
            with closing(database.connect()) as connection:
                connection.execute("INSERT INTO pokemon_species (id, name) VALUES (1, 'bulbasaur')")
                connection.execute(
                    "INSERT INTO pokemon (id, species_id, name, display_order) "
                    "VALUES (1, 1, 'bulbasaur', 1)"
                )
                connection.executemany(
                    "INSERT INTO pokemon_asset (pokemon_id, asset_kind, source_url, local_path) VALUES (1, ?, ?, ?)",
                    [
                        ("official_artwork", "https://example.test/1.png", None),
                        ("default_sprite", None, "sprite.png"),
                        ("home_artwork", "https://example.test/home.png", "home.png"),
                        ("dream_world", None, None),
                        ("showdown", "", ""),
                    ],
                )
                connection.execute("INSERT INTO tcg_set (id, name) VALUES ('base1', 'Base')")
                connection.execute(
                    "INSERT INTO tcg_card (id, set_id, name, number) "
                    "VALUES ('base1-1', 'base1', 'Bulbasaur', '1')"
                )
                connection.executemany(
                    "INSERT INTO card_asset (card_id, asset_kind, source_url, local_path) "
                    "VALUES ('base1-1', ?, ?, ?)",
                    [
                        ("large", "https://example.test/card.png", None),
                        ("small", "https://example.test/small.png", None),
                    ],
                )
                connection.executemany(
                    "INSERT INTO set_asset (set_id, asset_kind, source_url, local_path) VALUES ('base1', ?, ?, ?)",
                    [("logo", None, "logo.png"), ("symbol", None, None)],
                )
                connection.commit()
            manager = AssetManager(database)
            manager.paths = StoragePaths(root)

            inventory = {item["key"]: item for item in manager.inventory()["components"]}
            images = inventory["pokemon_images"]
            self.assertEqual(images["total"], 5)
            self.assertEqual(images["available_count"], 3)
            self.assertEqual(images["stored"], 2)
            self.assertEqual(images["missing"], 1)
            self.assertEqual(inventory["pokemon_cries"]["available_count"], 0)
            self.assertEqual(inventory["tcg_images"]["available_count"], 2)

            with closing(database.connect()) as connection:
                connection.execute(
                    "UPDATE pokemon_asset SET local_path = 'downloaded.png' WHERE asset_kind = 'official_artwork'"
                )
                connection.commit()
            images = manager.inventory()["components"][0]
            self.assertEqual(images["available_count"], 3)
            self.assertEqual(images["stored"], 3)
            self.assertEqual(images["missing"], 0)

    def test_tcg_image_falls_back_when_preferred_file_is_corrupt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = SqliteDatabase(root / "catalog.sqlite3")
            connection = sqlite3.connect(database.path)
            connection.execute(
                """
                CREATE TABLE card_asset (
                    id INTEGER PRIMARY KEY,
                    card_id TEXT NOT NULL,
                    asset_kind TEXT NOT NULL,
                    source_url TEXT,
                    local_path TEXT,
                    media_type TEXT
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO card_asset (card_id, asset_kind, local_path, media_type)
                VALUES ('test-1', ?, ?, 'image/png')
                """,
                (("large", "large.img"), ("small", "small.img")),
            )
            connection.commit()
            connection.close()

            (root / "large.img").touch()
            valid_image = root / "small.img"
            Image.new("RGB", (2, 2), "red").save(valid_image, format="PNG")

            class TestPaths:
                def resolve_stored(self, relative_path):
                    candidate = root / relative_path
                    return candidate if candidate.is_file() else None

            manager = AssetManager.__new__(AssetManager)
            manager.paths = TestPaths()
            manager.database = database
            manager._store = lambda *_args, **_kwargs: self.fail("unexpected download")

            image_path, media_type = manager.materialize_tcg_card_image("test-1", "large")

            self.assertEqual(valid_image, image_path)
            self.assertEqual("image/png", media_type)


if __name__ == "__main__":
    unittest.main()