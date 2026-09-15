import io
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.backup_service import BackupService  # noqa: E402
from src.config.paths import StoragePaths  # noqa: E402
from src.db.database import UsersDatabase  # noqa: E402


class BackupRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.paths = StoragePaths(Path(self.temporary_directory.name))
        self.paths.ensure_directories()
        UsersDatabase(self.paths.users_database).initialize()

        self.service = BackupService()
        self.service.paths = self.paths

        image = self.paths.pokemon_assets / "25-official_artwork.bin"
        image.write_bytes(b"artwork-bytes")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_backup_and_restore_preserves_selected_components(self):
        bundle = self.service.create_backup(["users_database", "pokemon_images"])
        self.assertTrue(bundle.is_file())

        (self.paths.pokemon_assets / "25-official_artwork.bin").unlink()
        self.paths.users_database.unlink()

        result = self.service.restore_backup(bundle, ["users_database", "pokemon_images"])

        self.assertTrue(self.paths.users_database.is_file())
        self.assertEqual(
            (self.paths.pokemon_assets / "25-official_artwork.bin").read_bytes(),
            b"artwork-bytes",
        )
        self.assertEqual(sorted(result["restored_components"]),
                         ["pokemon_images", "users_database"])

    def test_rejects_bundle_with_corrupted_checksum(self):
        import json
        import zipfile

        bundle = self.service.create_backup(["pokemon_images"])
        tampered = bundle.with_name("tampered.zip")

        with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(tampered, "w") as target:
            manifest = json.loads(source.read("manifest.json"))
            for item in source.infolist():
                if item.filename == "manifest.json":
                    target.writestr("manifest.json", json.dumps(manifest))
                else:
                    target.writestr(item.filename, b"different-bytes")

        with self.assertRaises(ValueError):
            self.service.restore_backup(tampered, ["pokemon_images"])

    def test_rejects_unknown_component(self):
        bundle = self.service.create_backup(["pokemon_images"])
        with self.assertRaises(ValueError):
            self.service.restore_backup(bundle, ["not_a_component"])


if __name__ == "__main__":
    unittest.main()
