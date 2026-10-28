import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "seed_snapshot", PROJECT_ROOT / "scripts" / "08-create_snapshot.py",
)
assert SPEC is not None and SPEC.loader is not None
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


class SeedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.seeds = self.root / "seeds"
        self.output = self.root / "snapshots"
        for relative, content in (
            ("pokeapi/pokemon.json", b'{"id": 25}'),
            ("tcg/cards.json", b'{"data": []}'),
            ("pokemon_list.json", b"[]"),
            ("prepared/data/assets/tcg/card.img", b"image bytes"),
            ("prepared/data/index/vectors.npy", b"embedding bytes"),
            ("prepared/asset-manifest.json", b'{"asset_records": []}'),
            ("prepared/data/seed-preparation-catalog.sqlite3", b"catalog bytes"),
            ("prepared/data/seed-preparation-catalog.sqlite3-wal", b"catalog sidecar"),
            ("prepared/data/pokedex.sqlite3", b"legacy catalog bytes"),
            ("prepared/data/seed-preparation-catalog.sqlite3.building-wal", b"failed build sidecar"),
            ("prepared/data/users.sqlite3-wal", b"private accounts sidecar"),
            ("prepared/data/users.sqlite3", b"private accounts"),
            ("backup-bundles/catalog.zip", b"redundant category bundle"),
        ):
            target = self.seeds / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    def test_compressed_snapshot_includes_seed_inputs_and_prepared_assets_but_not_bundles_or_accounts(self):
        target = snapshot.create_snapshot(self.seeds, self.output, compress=True)
        with tarfile.open(target, "r:gz") as archive:
            names = set(archive.getnames())
            self.assertIn("pokeapi/pokemon.json", names)
            self.assertIn("tcg/cards.json", names)
            self.assertIn("pokemon_list.json", names)
            self.assertIn("prepared/data/assets/tcg/card.img", names)
            self.assertIn("prepared/data/index/vectors.npy", names)
            self.assertIn("prepared/asset-manifest.json", names)
            self.assertFalse(any(".sqlite" in name for name in names))
            self.assertNotIn("prepared/data/users.sqlite3", names)
            self.assertFalse(any(name.startswith("backup-bundles/") for name in names))
            manifest = json.load(archive.extractfile("snapshot-manifest.json"))
            self.assertEqual(manifest["snapshot_version"], 2)
            self.assertFalse(manifest["includes_users_database"])
            self.assertEqual(len(manifest["files"]), 6)
            image_entry = next(item for item in manifest["files"]
                               if item["path"] == "prepared/data/assets/tcg/card.img")
            self.assertEqual(image_entry["sha256"], snapshot.file_hash(self.seeds / image_entry["path"]))

    def test_directory_snapshot_can_explicitly_include_private_accounts(self):
        target = snapshot.create_snapshot(self.seeds, self.output, include_users=True)
        self.assertEqual((target / "prepared/data/users.sqlite3").read_bytes(), b"private accounts")
        self.assertFalse((target / "backup-bundles/catalog.zip").exists())
        manifest = json.loads((target / "snapshot-manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["includes_users_database"])
        self.assertEqual(len(manifest["files"]), 7)

    def test_snapshot_output_inside_seed_root_is_not_absorbed_into_itself(self):
        target = snapshot.create_snapshot(self.seeds, self.seeds / "snapshots", compress=True)
        with tarfile.open(target, "r:gz") as archive:
            self.assertFalse(any(name.startswith("snapshots/") for name in archive.getnames()))


if __name__ == "__main__":
    unittest.main()
