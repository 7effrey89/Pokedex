"""Focused tests for wrapped-seed import, deduplication, and atomic replacement."""

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.importer import SqliteImporter, unwrap_payload  # noqa: E402


class SqliteImporterTests(unittest.TestCase):
    def test_unwrap_payload_accepts_wrapped_and_raw_values(self):
        self.assertEqual(unwrap_payload({"response": {"id": 25}}), {"id": 25})
        self.assertEqual(unwrap_payload({"id": 25}), {"id": 25})

    def test_build_deduplicates_cards_and_atomically_replaces_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pokeapi_dir = root / "cache"
            tcg_dir = root / "tcg-cache"
            pokeapi_dir.mkdir()
            tcg_dir.mkdir()
            database_path = root / "data" / "pokedex.sqlite3"
            database_path.parent.mkdir()
            database_path.write_text("old database", encoding="utf-8")

            self._write(pokeapi_dir / "pokeapi-species-0025-pikachu.json", {
                "response": {
                    "id": 25, "name": "pikachu", "is_baby": False, "is_legendary": False,
                    "is_mythical": False, "evolution_chain": {"url": "https://pokeapi.co/api/v2/evolution-chain/10/"},
                    "varieties": [{"is_default": True, "pokemon": {"name": "pikachu", "url": "https://pokeapi.co/api/v2/pokemon/25/"}}],
                    "names": [{"language": {"name": "en"}, "name": "Pikachu"}],
                    "genera": [], "flavor_text_entries": [],
                }
            })
            self._write(pokeapi_dir / "pokeapi-0025-pikachu.json", {
                "response": {
                    "id": 25, "name": "pikachu", "order": 35, "is_default": True,
                    "species": {"name": "pikachu", "url": "https://pokeapi.co/api/v2/pokemon-species/25/"},
                    "abilities": [], "types": [{"slot": 1, "type": {"name": "electric", "url": "https://pokeapi.co/api/v2/type/13/"}}],
                    "stats": [], "sprites": {"other": {"official-artwork": {"front_default": "https://example.test/25.png"}}},
                    "cries": {"latest": "https://example.test/25.ogg"},
                }
            })
            card = {
                "id": "base-1", "name": "Pikachu", "number": "1", "types": ["Lightning"],
                "nationalPokedexNumbers": [25], "set": {"id": "base", "name": "Base", "legalities": {}},
                "subtypes": ["Basic"], "attacks": [], "legalities": {}, "images": {},
                "cardmarket": {"url": "https://example.test/card", "updatedAt": "2025/01/01", "prices": {"trendPrice": 10.5}},
            }
            self._write(tcg_dir / "tcg-a.json", {"response": {"data": [card]}, "cached_at": 1})
            self._write(tcg_dir / "tcg-b.json", {"response": {"data": [card]}, "cached_at": 2})

            progress_messages = []
            summary = SqliteImporter(
                root, database_path, pokeapi_dir, tcg_dir, root / "assets",
                allow_network=False, download_artwork=False, require_artwork=False, require_card_images=False,
                progress=progress_messages.append,
            ).build()

            self.assertEqual(summary.pokemon_count, 1)
            self.assertEqual(summary.card_count, 1)
            self.assertTrue(any("Phase 1/5" in message for message in progress_messages))
            self.assertTrue(any("TCG cards: 1/1 (100%)" in message for message in progress_messages))
            self.assertTrue(any("Validation passed" in message for message in progress_messages))
            self.assertFalse(database_path.with_suffix(".sqlite3.building").exists())
            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM tcg_card").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT amount FROM card_price").fetchone()[0], 10.5)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_failed_build_preserves_existing_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pokeapi_dir = root / "cache"
            tcg_dir = root / "tcg-cache"
            pokeapi_dir.mkdir()
            tcg_dir.mkdir()
            database_path = root / "data" / "pokedex.sqlite3"
            database_path.parent.mkdir()
            database_path.write_bytes(b"existing database")
            self._write(pokeapi_dir / "pokeapi-species-0001-test.json", {
                "response": {"id": 1, "name": "test", "is_baby": False, "is_legendary": False, "is_mythical": False}
            })

            with self.assertRaisesRegex(RuntimeError, "No Pokemon seeds"):
                SqliteImporter(
                    root, database_path, pokeapi_dir, tcg_dir, root / "assets",
                    allow_network=False, download_artwork=False, require_artwork=False, require_card_images=False,
                ).build()

            self.assertEqual(database_path.read_bytes(), b"existing database")

    @staticmethod
    def _write(path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()