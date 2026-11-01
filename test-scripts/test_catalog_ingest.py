import sqlite3
import io
import hashlib
import logging
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src.config.paths import StoragePaths
from src.db.database import SqliteDatabase, apply_catalog_schema
from src.services import catalog_ingest
from src.services.catalog_ingest import CatalogIngestService, CatalogScanService
from src.services.asset_manager import AssetManager
from src.utils.catalog_logging import configure_catalog_logging


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
    def test_new_card_download_uses_shared_destination_and_reports_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = StoragePaths(Path(temporary).resolve())
            paths.ensure_directories()
            _seed_pikachu(paths.catalog_database)
            service = CatalogIngestService(SqliteDatabase(paths.catalog_database))
            service.refresh.snapshots_root = paths.snapshots
            card = {
                "id": "base1-2", "name": "Blastoise", "number": "2",
                "set": {"id": "base1", "name": "Base", "total": 2},
                "images": {"large": "https://example.test/card.png"},
            }
            service._fetch_all_cards_for_set = lambda _id: [card]
            destination = AssetManager(paths=paths)._destination({
                "component": "tcg_images", "owner_id": "base1-2", "asset_kind": "large",
            })
            payload = io.BytesIO()
            Image.new("RGB", (2, 2), "blue").save(payload, format="PNG")
            with mock.patch.object(catalog_ingest, "get_storage_paths", return_value=paths), \
                 mock.patch("urllib.request.urlopen", return_value=io.BytesIO(payload.getvalue())) as download, \
                 self.assertLogs(catalog_ingest.logger, level="INFO") as logs:
                result = service.add_tcg_set("base1")
                repeated = service.add_tcg_set("base1")
            download.assert_called_once()
            self.assertEqual(1, result["new_card_count"])
            self.assertEqual(0, repeated["new_card_count"])
            self.assertEqual(payload.getvalue(), destination.read_bytes())
            self.assertTrue(any(
                "Downloading missing TCG image for base1-2 (Blastoise)" in line
                and "https://example.test/card.png -> " + str(destination) in line
                for line in logs.output
            ))

    def test_ingest_reuses_both_image_conventions_and_skips_existing_cards(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                paths = StoragePaths(root)
                paths.ensure_directories()
                _seed_pikachu(paths.catalog_database)
                database = SqliteDatabase(paths.catalog_database)
                service = CatalogIngestService(database)
                service.refresh.snapshots_root = paths.snapshots
                card = {
                    "id": "base1-2", "name": "Blastoise", "number": "2",
                    "set": {"id": "base1", "name": "Base", "total": 2},
                    "images": {"large": "https://example.test/large.png"},
                }
                manager = AssetManager(database, paths=paths)
                if legacy:
                    digest = hashlib.sha1(b"base1-2").hexdigest()[:8]
                    destination = paths.tcg_images / f"base1-2-{digest}.img"
                else:
                    destination = manager._destination({
                        "component": "tcg_images", "owner_id": "base1-2", "asset_kind": "large",
                    })
                Image.new("RGB", (2, 2), "red").save(destination, format="PNG")
                original = destination.read_bytes()
                modified = destination.stat().st_mtime_ns
                service._fetch_all_cards_for_set = lambda _id: [
                    {"id": "base1-1", "set": card["set"], "images": card["images"]}, card,
                ]
                with mock.patch.object(catalog_ingest, "get_storage_paths", return_value=paths), \
                     mock.patch("urllib.request.urlopen") as download, \
                     self.assertLogs(catalog_ingest.logger, level="INFO") as logs:
                    result = service.add_tcg_set("base1")
                    repeated = service.add_tcg_set("base1")
                download.assert_not_called()
                self.assertEqual(1, result["new_card_count"])
                self.assertEqual(0, repeated["new_card_count"])
                self.assertEqual(original, destination.read_bytes())
                self.assertEqual(modified, destination.stat().st_mtime_ns)
                self.assertEqual(1, len(list(paths.tcg_images.glob("*.img"))))
                self.assertTrue(any("Reusing existing TCG image" in line and str(destination) in line for line in logs.output))
                self.assertTrue(any("1 new cards added, 1 existing cards skipped" in line for line in logs.output))
                connection = database.connect(read_only=True)
                try:
                    row = connection.execute(
                        "SELECT local_path FROM card_asset WHERE card_id = 'base1-2' AND asset_kind = 'large'"
                    ).fetchone()
                    self.assertEqual(paths.relative_to_root(destination), row["local_path"])
                    self.assertEqual("Alakazam", connection.execute(
                        "SELECT name FROM tcg_card WHERE id = 'base1-1'"
                    ).fetchone()["name"])
                finally:
                    connection.close()

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


class CatalogLoggingTests(unittest.TestCase):
    def test_activity_log_is_bounded_idempotent_and_excludes_chat(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            names = ("src.services.catalog_ingest", "src.services.catalog_refresh", "src.services.asset_manager")
            log_path = configure_catalog_logging(directory)
            handlers = [handler for handler in logging.getLogger(names[0]).handlers
                        if getattr(handler, "baseFilename", None) == str(log_path.resolve())]
            try:
                self.assertEqual(log_path, configure_catalog_logging(directory))
                self.assertEqual(1, len(handlers))
                handler = handlers[0]
                self.assertEqual(5 * 1024 * 1024, handler.maxBytes)
                self.assertEqual(3, handler.backupCount)
                for name in names:
                    logging.getLogger(name).warning("test activity: %s", name)
                with mock.patch.object(logging.getLogger("src.routes.chat_routes"), "propagate", False):
                    null_handler = logging.NullHandler()
                    logging.getLogger("src.routes.chat_routes").addHandler(null_handler)
                    try:
                        logging.getLogger("src.routes.chat_routes").warning("private conversation")
                    finally:
                        logging.getLogger("src.routes.chat_routes").removeHandler(null_handler)
                handler.flush()
                content = log_path.read_text(encoding="utf-8")
                for name in names:
                    self.assertIn(name, content)
                self.assertNotIn("private conversation", content)
            finally:
                for name in names:
                    for handler in handlers:
                        logging.getLogger(name).removeHandler(handler)
                for handler in handlers:
                    handler.close()


if __name__ == "__main__":
    unittest.main()
