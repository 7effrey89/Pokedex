"""Focused tests for SQLite schema initialization and readiness checks."""

import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import SCHEMA_VERSION, SqliteDatabase, UsersDatabase  # noqa: E402
from src.services.catalog_settings import CatalogSettings  # noqa: E402


class SqliteDatabaseTests(unittest.TestCase):
    def test_initialize_creates_valid_unhydrated_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = SqliteDatabase(Path(temp_dir) / "pokedex.sqlite3")
            database.initialize()

            status = database.status()

            self.assertEqual(status.schema_version, SCHEMA_VERSION)
            self.assertEqual(status.pokemon_count, 0)
            self.assertEqual(status.species_count, 0)
            self.assertEqual(status.set_count, 0)
            self.assertFalse(status.available)
            self.assertIn("needs Pokemon data", status.reason)

    def test_missing_database_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status = SqliteDatabase(Path(temp_dir) / "missing.sqlite3").status()

            self.assertFalse(status.available)
            self.assertIsNone(status.schema_version)
            self.assertEqual(status.reason, "Database has not been built")

    def test_catalog_counts_do_not_require_downloaded_artwork(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = SqliteDatabase(Path(temp_dir) / "pokedex.sqlite3")
            database.initialize()
            with closing(database.connect()) as connection:
                connection.execute("INSERT INTO pokemon_species (id, name) VALUES (1, 'bulbasaur')")
                connection.execute(
                    "INSERT INTO pokemon (id, species_id, name, display_order, is_default) "
                    "VALUES (1, 1, 'bulbasaur', 1, 1), (10001, 1, 'bulbasaur-form', 2, 0)"
                )
                connection.execute("INSERT INTO tcg_set (id, name) VALUES ('base1', 'Base')")
                connection.execute(
                    "INSERT INTO tcg_card (id, set_id, name, number) "
                    "VALUES ('base1-1', 'base1', 'Bulbasaur', '1')"
                )
                connection.commit()

            status = database.status()

            self.assertEqual(status.species_count, 1)
            self.assertEqual(status.pokemon_count, 2)
            self.assertEqual(status.card_count, 1)
            self.assertEqual(status.set_count, 1)
            self.assertEqual(status.to_dict()["species_count"], 1)
            self.assertFalse(status.available)
            self.assertEqual(status.missing_asset_count, 1)

    def test_schema_enforces_foreign_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = SqliteDatabase(Path(temp_dir) / "pokedex.sqlite3")
            database.initialize()

            with closing(database.connect()) as connection:
                with self.assertRaises(Exception):
                    connection.execute(
                        "INSERT INTO pokemon (id, species_id, name, display_order) VALUES (1, 999, 'test', 1)"
                    )

    def test_azure_uses_rollback_journals_for_network_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            "os.environ", {"WEBSITE_SITE_NAME": "app-pokedex-test"}
        ):
            catalog = SqliteDatabase(Path(temp_dir) / "pokedex.sqlite3")
            users = UsersDatabase(Path(temp_dir) / "users.sqlite3")

            catalog.initialize()
            users.initialize()

            with closing(catalog.connect()) as connection:
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            with closing(users.connect()) as connection:
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_refresh_policy_is_persisted_and_validated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = SqliteDatabase(Path(temp_dir) / "catalog.sqlite3")
            service = CatalogSettings(database, Path(temp_dir) / "missing.json")
            service.set_tcg_price_expiry_seconds(300)
            self.assertEqual(CatalogSettings(database).get_config()["tcg_price_expiry_seconds"], 300)

            with self.assertRaises(ValueError):
                service.set_tcg_price_expiry_seconds(123)


if __name__ == "__main__":
    unittest.main()