import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from src.db.database import SqliteDatabase, apply_catalog_schema
from src.services import catalog_ingest
from src.services.catalog_ingest import CatalogIngestService, CatalogScanService


def _seed_pikachu(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    apply_catalog_schema(connection)
    connection.execute("INSERT INTO pokemon_species (id, name) VALUES (25, 'pikachu')")
    connection.execute(
        "INSERT INTO pokemon (id, species_id, name, display_order) VALUES (25, 25, 'pikachu', 25)"
    )
    connection.execute("INSERT INTO tcg_set (id, name, total) VALUES ('base1', 'Base', 2)")
    connection.execute("INSERT INTO tcg_card (id, set_id, name, number) VALUES ('base1-1', 'base1', 'Alakazam', '1')")
    connection.commit()
    connection.close()


class CatalogScanTests(unittest.TestCase):
    def test_scan_pokemon_reports_missing_species(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "catalog.sqlite3"
            _seed_pikachu(database_path)
            service = CatalogScanService(SqliteDatabase(database_path))
            service._fetch_species_index = lambda: {25: "pikachu", 26: "raichu"}

            result = service.scan_pokemon()

            self.assertTrue(result["available"])
            self.assertEqual(1, result["missing_count"])
            self.assertEqual([{"id": 26, "name": "raichu"}], result["missing"])

    def test_scan_tcg_reports_new_sets_and_growing_sets(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "catalog.sqlite3"
            _seed_pikachu(database_path)
            service = CatalogScanService(SqliteDatabase(database_path))
            service._fetch_all_sets = lambda: [
                {"id": "base1", "name": "Base", "total": 3},
                {"id": "jungle", "name": "Jungle", "total": 64},
            ]

            result = service.scan_tcg()

            self.assertTrue(result["available"])
            self.assertEqual(1, result["new_sets_count"])
            self.assertEqual("jungle", result["new_sets"][0]["id"])
            self.assertEqual(1, result["sets_with_new_cards_count"])
            self.assertEqual("base1", result["sets_with_new_cards"][0]["id"])
            self.assertEqual(1, result["sets_with_new_cards"][0]["local_count"])


class CatalogIngestTests(unittest.TestCase):
    def test_add_species_inserts_new_species_and_forms(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "catalog.sqlite3"
            _seed_pikachu(database_path)
            database = SqliteDatabase(database_path)
            service = CatalogIngestService(database)
            service.refresh.snapshots_root = Path(temporary) / "snapshots"

            species_payload = {
                "id": 133, "name": "eevee", "evolution_chain": {"url": f"{catalog_ingest.POKEAPI_ROOT}/evolution-chain/67/"},
                "generation": {"name": "generation-i"}, "names": [], "genera": [], "flavor_text_entries": [],
                "varieties": [{"pokemon": {"name": "eevee", "url": f"{catalog_ingest.POKEAPI_ROOT}/pokemon/133/"}}],
            }
            pokemon_payload = {
                "id": 133, "name": "eevee", "order": 133, "is_default": True, "base_experience": 65,
                "height": 3, "weight": 65, "species": {"name": "eevee"}, "types": [], "abilities": [], "stats": [],
                "sprites": {}, "cries": {},
            }

            def fake_fetch_json(url):
                return species_payload if "pokemon-species" in url else pokemon_payload

            with mock.patch.object(catalog_ingest, "_fetch_json", side_effect=fake_fetch_json):
                result = service.add_species(133)

            self.assertTrue(result["added"])
            self.assertEqual([133], result["pokemon_ids"])
            connection = database.connect(read_only=True)
            self.assertIsNotNone(connection.execute("SELECT 1 FROM pokemon_species WHERE id = 133").fetchone())
            self.assertIsNotNone(connection.execute("SELECT 1 FROM pokemon WHERE id = 133").fetchone())
            connection.close()

    def test_add_tcg_set_inserts_new_cards_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "catalog.sqlite3"
            _seed_pikachu(database_path)
            database = SqliteDatabase(database_path)
            service = CatalogIngestService(database)
            service.refresh.snapshots_root = Path(temporary) / "snapshots"

            cards = [
                {
                    "id": "base1-1", "name": "Alakazam", "number": "1", "supertype": "Pokémon",
                    "set": {"id": "base1", "name": "Base", "total": 2}, "images": {},
                },
                {
                    "id": "base1-2", "name": "Blastoise", "number": "2", "supertype": "Pokémon",
                    "set": {"id": "base1", "name": "Base", "total": 2}, "images": {},
                },
            ]
            service._fetch_all_cards_for_set = lambda set_id: cards

            result = service.add_tcg_set("base1")

            self.assertTrue(result["added"])
            self.assertEqual(2, result["card_count"])
            self.assertEqual(1, result["new_card_count"])
            connection = database.connect(read_only=True)
            count = connection.execute("SELECT COUNT(*) FROM tcg_card WHERE set_id = 'base1'").fetchone()[0]
            self.assertEqual(2, count)
            connection.close()

    def test_start_batch_reports_progress_and_completes(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "catalog.sqlite3"
            _seed_pikachu(database_path)
            database = SqliteDatabase(database_path)
            service = CatalogIngestService(database)
            service.refresh.snapshots_root = Path(temporary) / "snapshots"

            cards = [
                {
                    "id": "jungle-1", "name": "Clefable", "number": "1", "supertype": "Pokémon",
                    "set": {"id": "jungle", "name": "Jungle", "total": 1}, "images": {},
                },
            ]
            service._fetch_all_cards_for_set = lambda set_id: cards

            job = service.start_batch("tcg_set", ["jungle"])
            self.assertEqual("running", job["status"])
            self.assertEqual(1, job["total"])

            deadline = time.monotonic() + 5
            final_job = service.job_status()
            while final_job["status"] == "running" and time.monotonic() < deadline:
                time.sleep(0.05)
                final_job = service.job_status()

            self.assertEqual("completed", final_job["status"])
            self.assertEqual(1, final_job["completed"])
            self.assertEqual([], final_job["errors"])
            connection = database.connect(read_only=True)
            self.assertIsNotNone(connection.execute("SELECT 1 FROM tcg_set WHERE id = 'jungle'").fetchone())
            connection.close()


if __name__ == "__main__":
    unittest.main()
