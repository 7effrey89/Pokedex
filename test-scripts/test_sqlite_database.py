"""Focused tests for SQLite schema initialization and readiness checks."""

import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import SCHEMA_VERSION, SqliteDatabase  # noqa: E402
from src.services.cache_service import CacheService  # noqa: E402


class SqliteDatabaseTests(unittest.TestCase):
    def test_initialize_creates_valid_unhydrated_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = SqliteDatabase(Path(temp_dir) / "pokedex.sqlite3")
            database.initialize()

            status = database.status()

            self.assertEqual(status.schema_version, SCHEMA_VERSION)
            self.assertEqual(status.pokemon_count, 0)
            self.assertFalse(status.available)
            self.assertIn("needs Pokemon data", status.reason)

    def test_missing_database_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status = SqliteDatabase(Path(temp_dir) / "missing.sqlite3").status()

            self.assertFalse(status.available)
            self.assertIsNone(status.schema_version)
            self.assertEqual(status.reason, "Database has not been built")

    def test_schema_enforces_foreign_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = SqliteDatabase(Path(temp_dir) / "pokedex.sqlite3")
            database.initialize()

            with closing(database.connect()) as connection:
                with self.assertRaises(Exception):
                    connection.execute(
                        "INSERT INTO pokemon (id, species_id, name, display_order) VALUES (1, 999, 'test', 1)"
                    )

    def test_data_source_mode_is_persisted_and_validated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CacheService(temp_dir)
            self.assertEqual(service.get_data_source_mode(), "json")

            service.set_data_source_mode("sqlite")
            self.assertEqual(CacheService(temp_dir).get_data_source_mode(), "sqlite")

            with self.assertRaises(ValueError):
                service.set_data_source_mode("remote")


if __name__ == "__main__":
    unittest.main()