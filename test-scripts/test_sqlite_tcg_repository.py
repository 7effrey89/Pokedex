import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import SCHEMA_PATH, SqliteDatabase
from src.db.tcg_repository import SqliteTcgRepository


class SqliteTcgRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "pokedex.sqlite3"
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO tcg_set (id, name, series, total, release_date) VALUES (?, ?, ?, ?, ?)",
                ("test1", "Test Set", "Test Series", 1, "2026/01/01"),
            )
            connection.execute(
                "INSERT INTO tcg_card (id, set_id, name, number, supertype, rarity) VALUES (?, ?, ?, ?, ?, ?)",
                ("test1-1", "test1", "Pikachu", "1", "Pokemon", "Rare"),
            )
            connection.execute(
                "INSERT INTO card_asset (card_id, asset_kind, local_path) VALUES (?, ?, ?)",
                ("test1-1", "large", "tcg-image-cache/images/test1-1.img"),
            )
            connection.commit()
        finally:
            connection.close()
        self.repository = SqliteTcgRepository(SqliteDatabase(self.database_path))

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_returns_existing_set_and_slim_card_contract(self):
        sets = self.repository.get_sets()
        cards = self.repository.get_cards_by_set("test1", slim=True, limit=8)

        self.assertEqual(sets["total_count"], 1)
        self.assertEqual(cards["total_count"], 1)
        self.assertEqual(cards["cards"][0]["id"], "test1-1")
        self.assertEqual(cards["cards"][0]["images"]["small"], "/api/tcg/card-image/test1-1/large")

    def test_resolves_small_image_to_registered_large_asset(self):
        self.assertEqual(
            self.repository.get_image_path("test1-1", "small"),
            "tcg-image-cache/images/test1-1.img",
        )


if __name__ == "__main__":
    unittest.main()
