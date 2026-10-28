"""Seed ZIPs and administrator backups must use one portable, verifiable contract."""

import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from PIL import Image

from src.config.paths import PROJECT_ROOT, StoragePaths
from src.db.database import SqliteDatabase, UsersDatabase
from src.routes.admin_routes import admin_bp
from src.services.asset_manager import AssetManager
from src.services.backup_service import BackupService, COMPONENT_LABELS
from src.services.seed_pipeline import (
    import_seed_catalog, create_seed_bundles, download_seed_assets, restore_seed_bundles, seed_paths,
    select_seed_bundles, SEED_COMPONENTS,
)
from src.services.seed_assets import read_seed_manifest, save_seed_manifest
from src.services.tcg_image_index import TcgImageIndex, suspend_indexes


class SeedPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = seed_paths(self.root / "seeds" / "prepared")
        self.target = StoragePaths(self.root / "target")
        self.raw_pokemon = self.root / "seeds" / "pokeapi"
        self.raw_tcg = self.root / "seeds" / "tcg"
        self.output = self.root / "seeds" / "backup-bundles"
        self.raw_pokemon.mkdir(parents=True)
        self.raw_tcg.mkdir(parents=True)
        self.live = StoragePaths(self.root / "live")
        self.live.catalog_database.parent.mkdir(parents=True)
        self.live.catalog_database.write_bytes(b"untouched live catalog")
        patcher = patch("src.services.seed_pipeline.get_storage_paths", return_value=self.live)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.species = {"id": 25, "name": "pikachu"}
        self.pokemon = {
            "id": 25, "name": "pikachu", "is_default": True,
            "species": {"name": "pikachu", "url": "https://pokeapi.co/api/v2/pokemon-species/25/"},
            "sprites": {"front_default": "https://example.test/sprite.png",
                        "other": {"official-artwork": {"front_default": "https://example.test/artwork.png"}}},
            "cries": {"latest": "https://example.test/cry.ogg"},
        }
        self.card = {
            "id": "test1-1", "name": "Pikachu", "number": "1",
            "images": {"large": "https://example.test/card.png"},
            "set": {"id": "test1", "name": "Test", "images": {
                "logo": "https://example.test/logo.png", "symbol": "https://example.test/symbol.png",
            }},
        }
        for path, payload in (
            (self.raw_pokemon / "pokeapi-species-0025-pikachu.json", self.species),
            (self.raw_pokemon / "pokeapi-0025-pikachu.json", self.pokemon),
            (self.raw_tcg / "cards.json", {"data": [self.card]}),
        ):
            path.write_text(json.dumps({"response": payload}), encoding="utf-8")
        self.source = StoragePaths(self.root / "source-app")
        with redirect_stdout(io.StringIO()):
            import_seed_catalog(self.raw_pokemon, self.raw_tcg, self.source, apply=True)
        spec = importlib.util.spec_from_file_location(
            "seed_embeddings_builder", PROJECT_ROOT / "scripts" / "05-build_tcg_image_embeddings.py",
        )
        assert spec is not None and spec.loader is not None
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    @staticmethod
    def store_asset(_manager, _url, destination, media):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if media == "audio":
            destination.write_bytes(b"OggS-seed-test")
            return hashlib.sha256(destination.read_bytes()).hexdigest(), "audio/ogg", None, None
        Image.new("RGB", (63, 88), (250, 230, 20)).save(destination, format="PNG")
        return hashlib.sha256(destination.read_bytes()).hexdigest(), "image/png", 63, 88

    def prepare_assets(self):
        with patch.object(AssetManager, "_store", self.store_asset):
            job = download_seed_assets(
                self.paths.data_root, ["pokemon_images", "pokemon_cries", "tcg_images"],
                pokeapi=self.raw_pokemon, tcg=self.raw_tcg,
            )
        self.assertEqual(job["downloaded"], 6)
        self.builder.build_embeddings(self.paths.data_root, self.raw_tcg)

    def prepare_all(self):
        self.prepare_assets()
        source = self.root / "private" / "accounts.sqlite3"
        source.parent.mkdir()
        UsersDatabase(source).initialize()
        with closing(sqlite3.connect(source)) as connection:
            connection.execute("CREATE TABLE fixture_marker (value TEXT)")
            connection.execute("INSERT INTO fixture_marker VALUES ('original user account')")
            connection.commit()
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        bundles = create_seed_bundles(
            self.paths.data_root, self.output, list(SEED_COMPONENTS), users_database=source,
        )
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), checksum)
        self.assertFalse(self.paths.users_database.exists())
        restore_seed_bundles(bundles, self.source)
        catalog = BackupService(self.source).create_backup(["catalog_database"], output_dir=self.output)
        return [catalog, *bundles]

    def assert_target_assets(self, target):
        with closing(sqlite3.connect(target.catalog_database)) as connection:
            for table, count in (("pokemon_asset", 3), ("card_asset", 1), ("set_asset", 2)):
                stored = connection.execute(
                    f"SELECT local_path FROM {table} WHERE local_path IS NOT NULL"
                ).fetchall()
                self.assertEqual(len(stored), count)
                for (relative,) in stored:
                    self.assertFalse(Path(relative).is_absolute())
                    self.assertTrue((target.data_root / relative).is_file(), relative)
        with closing(sqlite3.connect(target.users_database)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM fixture_marker").fetchone()[0],
                             "original user account")
        index = TcgImageIndex(target.tcg_index)
        try:
            self.assertEqual(index.search(Image.new("RGB", (63, 88), (250, 230, 20)))[0]["id"], "test1-1")
        finally:
            with suspend_indexes(target.tcg_index):
                pass

    def admin_app(self, paths):
        app = Flask(__name__)
        app.register_blueprint(admin_bp)
        service = BackupService(paths)
        for target, value in (
            ("src.routes.admin_routes.require_admin", None),
            ("src.routes.admin_routes.get_storage_paths", paths),
            ("src.services.backup_service.get_backup_service", service),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return app, service

    def test_seed_zips_restore_through_real_admin_route_for_every_category(self):
        bundles = self.prepare_all()
        self.assertEqual(len(bundles), 6)
        self.assertFalse(self.paths.backups.exists())
        self.assertEqual(self.live.catalog_database.read_bytes(), b"untouched live catalog")
        app, service = self.admin_app(self.target)
        with app.test_client() as client:
            for bundle in bundles:
                manifest = service.inspect_backup(bundle)
                key = manifest["components"][0]
                slug = COMPONENT_LABELS[key].lower().replace(" ", "-")
                self.assertTrue(bundle.name.startswith(slug + "--"), bundle.name)
                response = client.post("/api/admin/restore", data={
                    "bundle": (io.BytesIO(bundle.read_bytes()), bundle.name),
                }, content_type="multipart/form-data")
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(response.get_json()["restored_components"], [key])
        self.assert_target_assets(self.target)
        self.assertIn("tcg_embeddings", {item["key"] for item in service.available_components() if item["available"]})

    def test_admin_export_restores_through_cli_using_the_same_manifest(self):
        self.prepare_all()
        app, service = self.admin_app(self.source)
        with app.test_client() as client:
            response = client.post("/api/admin/backup", json={"components": list(COMPONENT_LABELS)})
            self.assertEqual(response.status_code, 202)
            service._job_thread.join(timeout=10)
            job = service.job_status()
            self.assertEqual(job["status"], "completed", job)
            download = client.get(job["download_url"])
            self.assertEqual(download.status_code, 200)
            exported = self.output / "admin-export.pokedex-backup.zip"
            exported.write_bytes(download.data)
            download.close()
        environment = {**os.environ, "PYTHON_DOTENV_DISABLED": "1", "PYTHONIOENCODING": "utf-8"}
        command = [
            sys.executable, str(PROJECT_ROOT / "scripts" / "07-import_seed_backup_bundles.py"),
            str(exported), "--target-root", str(self.target.data_root),
        ]
        preview = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse(self.target.catalog_database.exists())
        SqliteDatabase(self.target.catalog_database).initialize()
        with closing(sqlite3.connect(self.target.catalog_database)) as connection, connection:
            connection.execute("CREATE TABLE local_marker (value TEXT)")
            connection.execute("INSERT INTO local_marker VALUES ('keep existing CLI catalog')")
        applied = subprocess.run(
            [*command, "--apply", "--server-stopped"], env=environment, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assert_target_assets(self.target)
        with closing(sqlite3.connect(self.target.catalog_database)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM local_marker").fetchone()[0],
                             "keep existing CLI catalog")

    def test_asset_only_restore_updates_existing_catalog_registration(self):
        bundles = self.prepare_all()
        service = BackupService(self.target)
        catalog = next(path for path in bundles if path.name.startswith("catalog-database--"))
        artwork = next(path for path in bundles if path.name.startswith("pokemon-artwork--"))
        service.restore_backup(catalog)
        with closing(sqlite3.connect(self.target.catalog_database)) as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM pokemon_asset WHERE local_path IS NOT NULL"
            ).fetchone()[0], 0)
        result = service.restore_backup(artwork)
        self.assertEqual(result["asset_records_updated"], 2)

    def test_loaded_embeddings_are_released_and_reloaded_after_restore(self):
        self.prepare_assets()
        target = BackupService(self.target)
        source = BackupService(self.paths)
        original = source.create_backup(["tcg_embeddings"], output_dir=self.output)
        target.restore_backup(original)
        index = TcgImageIndex(self.target.tcg_index)
        image = Image.new("RGB", (63, 88), (250, 230, 20))
        self.assertEqual(index.search(image)[0]["id"], "test1-1")
        cards = self.paths.tcg_index / "cards.json"
        replacement = json.loads(cards.read_text())
        replacement[0]["id"] = "replacement-card"
        cards.write_text(json.dumps(replacement), encoding="utf-8")
        updated = source.create_backup(["tcg_embeddings"], output_dir=self.output)
        target.restore_backup(updated)
        try:
            self.assertEqual(index.search(image)[0]["id"], "replacement-card")
        finally:
            with suspend_indexes(self.target.tcg_index):
                pass

    def test_embeddings_only_admin_import_does_not_open_or_change_catalog_or_accounts(self):
        self.prepare_assets()
        SqliteDatabase(self.target.catalog_database).initialize()
        UsersDatabase(self.target.users_database).initialize()
        before = {path: path.read_bytes() for path in (self.target.catalog_database, self.target.users_database)}
        bundle = BackupService(self.paths).create_backup(["tcg_embeddings"], output_dir=self.output)
        app, _ = self.admin_app(self.target)
        with app.test_client() as client, patch(
            "src.services.backup_assets.sqlite3.connect", side_effect=AssertionError("Must not open a database")
        ):
            response = client.post("/api/admin/restore", data={
                "bundle": (io.BytesIO(bundle.read_bytes()), bundle.name),
            }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIsNone(response.get_json()["catalog_merge"])
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_batch_verifies_every_zip_before_replacing_any_target_data(self):
        bundles = self.prepare_all()
        corrupt = self.output / "corrupt.pokedex-backup.zip"
        source = next(path for path in bundles if path.name.startswith("pokemon-artwork--"))
        with zipfile.ZipFile(source) as archive, zipfile.ZipFile(corrupt, "w") as target:
            for entry in archive.infolist():
                target.writestr(entry.filename, archive.read(entry.filename) if entry.filename == "manifest.json" else b"bad")
        catalog = next(path for path in bundles if path.name.startswith("catalog-database--"))
        with self.assertRaises(ValueError):
            restore_seed_bundles([catalog, corrupt], self.target)
        self.assertFalse(self.target.catalog_database.exists())

    def test_seed_media_embeddings_and_bundles_need_no_database(self):
        with patch("sqlite3.connect", side_effect=AssertionError("Seed media must not open SQLite")):
            self.prepare_assets()
            bundles = create_seed_bundles(
                self.paths.data_root, self.output, list(SEED_COMPONENTS.keys() - {"users_database"}),
            )
            self.assertEqual(len(bundles), 4)
            for bundle in bundles:
                BackupService(self.paths).verify_backup(bundle)
            with patch.object(AssetManager, "_store", side_effect=AssertionError("Must reuse downloaded files")):
                job = download_seed_assets(self.paths.data_root, ["tcg_images"],
                                           pokeapi=self.raw_pokemon, tcg=self.raw_tcg)
            self.assertEqual(job["downloaded"], 0)
            self.assertEqual(job["skipped"], 3)
        self.assertFalse(list((self.root / "seeds").rglob("*.sqlite3*")))
        self.assertEqual(len(read_seed_manifest(self.paths)), 6)
        with self.assertRaisesRegex(ValueError, "derived"):
            create_seed_bundles(self.paths.data_root, self.output, ["catalog_database"])
        with self.assertRaises(ValueError):
            seed_paths(self.live.data_root)
        self.assertEqual(self.live.catalog_database.read_bytes(), b"untouched live catalog")

    def test_direct_catalog_cli_preview_confirmation_and_upsert(self):
        command = [
            sys.executable, str(PROJECT_ROOT / "scripts" / "03-import_seed_catalog.py"),
            "--pokeapi-dir", str(self.raw_pokemon), "--tcg-dir", str(self.raw_tcg),
            "--target-root", str(self.target.data_root),
        ]
        environment = {**os.environ, "PYTHON_DOTENV_DISABLED": "1", "PYTHONIOENCODING": "utf-8"}
        preview = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse(self.target.data_root.exists())
        rejected = subprocess.run([*command, "--apply"], env=environment, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("--server-stopped", rejected.stderr)
        SqliteDatabase(self.target.catalog_database).initialize()
        with closing(sqlite3.connect(self.target.catalog_database)) as connection, connection:
            connection.execute("CREATE TABLE local_marker (value TEXT)")
            connection.execute("INSERT INTO local_marker VALUES ('keep')")
        for _ in range(2):
            applied = subprocess.run([*command, "--apply", "--server-stopped"], env=environment,
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(applied.returncode, 0, applied.stderr)
        with closing(sqlite3.connect(self.target.catalog_database)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM local_marker").fetchone()[0], "keep")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tcg_card").fetchone()[0], 1)
        self.assertFalse(list((self.root / "seeds").rglob("*.sqlite3*")))

    def test_accounts_require_an_explicit_source_and_newest_category_zip_is_selected(self):
        with self.assertRaisesRegex(ValueError, "explicit"):
            create_seed_bundles(self.paths.data_root, self.output, ["users_database"])
        self.assertFalse(self.paths.users_database.exists())
        self.prepare_assets()
        first = create_seed_bundles(self.paths.data_root, self.output, ["tcg_embeddings"])[0]
        second = create_seed_bundles(self.paths.data_root, self.output, ["tcg_embeddings"])[0]
        self.assertNotEqual(first, second)
        self.assertEqual(select_seed_bundles(self.output, ["tcg_embeddings"]), [second])
        with self.assertRaisesRegex(ValueError, "No seed ZIP"):
            select_seed_bundles(self.output, ["users_database"])

    def test_incomplete_embeddings_and_failed_downloads_are_not_reported_as_success(self):
        with self.assertRaisesRegex(ValueError, "seed card images"):
            self.builder.build_embeddings(self.paths.data_root, self.raw_tcg)
        self.assertFalse(self.paths.tcg_index.exists())
        with patch.object(AssetManager, "_store", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                download_seed_assets(self.paths.data_root, ["pokemon_images"], limit=1,
                                     pokeapi=self.raw_pokemon, tcg=self.raw_tcg)
        self.paths.tcg_index.mkdir(parents=True)
        (self.paths.tcg_index / "manifest.json").write_text("{}")
        with self.assertRaises(ValueError):
            BackupService(self.paths).create_backup(["tcg_embeddings"], output_dir=self.output)

    def test_partial_embeddings_require_opt_in_and_keep_the_old_index_on_failure(self):
        self.prepare_assets()
        original = (self.paths.tcg_index / "vectors.npy").read_bytes()
        missing = {**self.card, "id": "test1-2"}
        (self.raw_tcg / "more-cards.json").write_text(json.dumps({"data": [missing]}))
        with self.assertRaises(ValueError):
            self.builder.build_embeddings(self.paths.data_root, self.raw_tcg)
        self.assertEqual((self.paths.tcg_index / "vectors.npy").read_bytes(), original)
        result = self.builder.build_embeddings(self.paths.data_root, self.raw_tcg, allow_partial=True)
        self.assertEqual(result["card_count"], 1)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(json.loads((self.paths.tcg_index / "failures.json").read_text()), ["test1-2"])

    def test_raw_downloader_saves_alternate_forms_for_offline_regeneration(self):
        spec = importlib.util.spec_from_file_location(
            "seed_pokeapi_downloader", PROJECT_ROOT / "scripts" / "02-download_raw_pokeapi_to_seed.py",
        )
        assert spec is not None and spec.loader is not None
        downloader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(downloader)
        species = {**self.species, "varieties": [
            {"is_default": True, "pokemon": {"name": "pikachu", "url": "https://pokeapi.co/api/v2/pokemon/25/"}},
            {"is_default": False, "pokemon": {"name": "pikachu-rock-star",
                                            "url": "https://pokeapi.co/api/v2/pokemon/10080/"}},
        ]}
        calls = []

        def cached(_session, endpoint, params, resource, refresh):
            calls.append(resource)
            return "cached", species if endpoint == "pokeapi_species" else self.pokemon

        with patch.object(downloader, "ensure_cached", side_effect=cached), redirect_stdout(io.StringIO()):
            downloader.preload_pokemon_entry(None, {"number": 25, "name": "pikachu"}, ["pokemon"], False)
        self.assertEqual(calls, ["pokemon/25", "pokemon-species/25", "pokemon/10080"])

    def test_card_seeds_can_have_incomplete_set_metadata_and_do_not_confuse_standalone_sets(self):
        extra = {**self.card, "id": "test1-2", "set": {"name": "Test"}}
        (self.raw_tcg / "extra.json").write_text(json.dumps({"data": [
            extra, {"id": "standalone", "name": "Set", "series": "Test",
                    "images": {"logo": "https://example.test/standalone.png"}},
        ]}))
        self.assertEqual([card["id"] for card in self.builder.load_unique_cards(self.raw_tcg)],
                         ["test1-1", "test1-2"])
        with patch.object(AssetManager, "_store", self.store_asset):
            job = download_seed_assets(self.paths.data_root, ["tcg_images"],
                                       pokeapi=self.raw_pokemon, tcg=self.raw_tcg)
        self.assertEqual(job["downloaded"], 5)

    def test_limit_counts_pending_assets_and_progress_survives_download_failure(self):
        stored = []

        def sometimes_fails(manager, url, destination, media):
            if stored:
                raise OSError("Temporary upstream failure")
            stored.append(url)
            return self.store_asset(manager, url, destination, media)

        with patch.object(AssetManager, "_store", sometimes_fails):
            with self.assertRaisesRegex(RuntimeError, "2 failed"):
                download_seed_assets(self.paths.data_root, ["tcg_images"],
                                     pokeapi=self.raw_pokemon, tcg=self.raw_tcg)
        self.assertEqual(len(read_seed_manifest(self.paths)), 1)
        with patch.object(AssetManager, "_store", self.store_asset):
            resumed = download_seed_assets(self.paths.data_root, ["tcg_images"], limit=1,
                                           pokeapi=self.raw_pokemon, tcg=self.raw_tcg)
        self.assertEqual(resumed["skipped"], 1)
        self.assertEqual(resumed["downloaded"], 1)
        self.assertEqual(len(read_seed_manifest(self.paths)), 2)

    def test_automatic_selection_cannot_restore_accounts_from_a_combined_admin_zip(self):
        self.prepare_all()
        combined = BackupService(self.source).create_backup(
            ["catalog_database", "users_database"], output_dir=self.root / "combined",
        )
        self.assertTrue(combined.is_file())
        with self.assertRaisesRegex(ValueError, "Pass combined admin ZIPs explicitly"):
            select_seed_bundles(combined.parent, ["catalog_database"])

    def test_cli_requires_confirmation_and_old_manifest_without_asset_records_is_supported(self):
        self.prepare_assets()
        bundle = BackupService(self.paths).create_backup(["pokemon_images"], output_dir=self.output)
        legacy = self.output / "legacy.pokedex-backup.zip"
        with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(legacy, "w") as target:
            for entry in source.infolist():
                payload = source.read(entry.filename)
                if entry.filename == "manifest.json":
                    manifest = json.loads(payload)
                    del manifest["asset_records"]
                    payload = json.dumps(manifest).encode()
                target.writestr(entry.filename, payload)
        result = BackupService(self.target).restore_backup(legacy)
        self.assertEqual(result["asset_records_updated"], 0)
        self.assertEqual(len(list(self.target.pokemon_assets.glob("*"))), 2)
        completed = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "07-import_seed_backup_bundles.py"),
             str(bundle), "--target-root", str(self.target.data_root), "--apply"],
            env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"}, capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--server-stopped", completed.stderr)

    @staticmethod
    def replace_bundle_file(bundle, output, filename, replacement):
        with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(output, "w") as target:
            manifest = json.loads(source.read("manifest.json"))
            for entry in manifest["files"]:
                if entry["path"] == filename:
                    entry["size_bytes"] = len(replacement)
                    entry["sha256"] = hashlib.sha256(replacement).hexdigest()
            for entry in source.infolist():
                if entry.filename == "manifest.json":
                    payload = json.dumps(manifest).encode()
                else:
                    payload = replacement if entry.filename == filename else source.read(entry.filename)
                target.writestr(entry.filename, payload)

    def test_correct_checksums_do_not_allow_invalid_databases_or_misaligned_embeddings(self):
        self.prepare_assets()
        target = BackupService(self.target)
        for component, filename, replacement in (
            ("catalog_database", f"catalog_database/{self.source.catalog_database.name}", b"not a SQLite database"),
            ("tcg_embeddings", "tcg_embeddings/cards.json", b"[]"),
        ):
            with self.subTest(component=component):
                source = BackupService(self.source if component == "catalog_database" else self.paths)
                bundle = source.create_backup([component], output_dir=self.output)
                target.restore_backup(bundle)
                path = (self.target.catalog_database if component == "catalog_database"
                        else self.target.tcg_index / "cards.json")
                original = path.read_bytes()
                invalid = self.output / f"invalid-{component}.zip"
                self.replace_bundle_file(bundle, invalid, filename, replacement)
                with self.assertRaises(ValueError):
                    target.verify_backup(invalid)
                with self.assertRaises(ValueError):
                    target.restore_backup(invalid)
                self.assertEqual(path.read_bytes(), original)

    def test_export_rejects_stale_asset_hashes_instead_of_creating_an_unrestorable_zip(self):
        self.prepare_assets()
        records = read_seed_manifest(self.paths)
        records[0]["sha256"] = "stale"
        save_seed_manifest(self.paths, records)
        with self.assertRaisesRegex(ValueError, "registration does not match"):
            create_seed_bundles(self.paths.data_root, self.output, ["pokemon_images"])
        self.assertEqual(list(self.output.glob("*.zip")), [])


if __name__ == "__main__":
    unittest.main()
