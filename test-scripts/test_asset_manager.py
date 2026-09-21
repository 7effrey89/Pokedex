import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import SqliteDatabase
from src.services.asset_manager import AssetManager


class AssetManagerTests(unittest.TestCase):
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