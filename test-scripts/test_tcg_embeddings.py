import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

import numpy as np
from flask import Flask
from PIL import Image

from src.config.paths import StoragePaths
from src.db.database import SqliteDatabase
from src.services.tcg_embedding_service import TcgEmbeddingService
from src.services.tcg_image_index import ENCODER_VERSION, TcgImageIndex, _read_index, encode_card_image
from src.services.backup_service import BackupService
from src.utils.file_lock import exclusive_file_lock


class TcgEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.paths = StoragePaths(Path(self.temporary.name).resolve())
        self.paths.ensure_directories()
        self.database = SqliteDatabase(self.paths.catalog_database)
        self.database.initialize()
        with closing(self.database.connect()) as connection, connection:
            connection.execute("INSERT INTO tcg_set(id, name, total) VALUES ('test', 'Test', 4)")
        self.service = TcgEmbeddingService(self.paths)

    def card(self, card_id, *, image=True, corrupt=False, kind="large"):
        path = self.paths.tcg_images / f"{card_id}.img"
        if image:
            if corrupt:
                path.write_bytes(b"corrupt")
            else:
                Image.new("RGB", (63, 88), (30, 210, 40)).save(path, format="PNG")
        with closing(self.database.connect()) as connection, connection:
            connection.execute(
                "INSERT INTO tcg_card(id, set_id, name, number, hp) VALUES (?, 'test', ?, '3', 70)",
                (card_id, f"Card {card_id}"),
            )
            connection.execute(
                "INSERT INTO card_asset(card_id, asset_kind, local_path, source_url) VALUES (?, ?, ?, ?)",
                (card_id, kind, self.paths.relative_to_root(path) if image else None,
                 f"https://example.test/{card_id}.png"),
            )
        return path

    def run_job(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("Embedding must be offline")), \
             mock.patch("requests.get", side_effect=AssertionError("Embedding must be offline")):
            self.service.start()
            self.service._thread.join(timeout=10)
            self.assertFalse(self.service._thread.is_alive())
        return self.service.job_status()

    def test_builds_only_missing_cards_and_preserves_existing_vectors_and_metadata(self):
        self.card("old")
        self.card("new", kind="small")
        self.card("waiting", image=False)
        image = Image.new("RGB", (63, 88), (220, 20, 20))
        original = encode_card_image(image)
        original_card = {"id": "old", "name": "Preserve metadata", "attacks": [{"name": "Original"}]}
        self.service._append([original_card], [original])
        index = TcgImageIndex(self.paths.tcg_index)
        self.assertEqual(index.search(image)[0]["id"], "old")
        inventory = self.service.inventory()
        self.assertEqual((inventory["total"], inventory["indexed"], inventory["ready"], inventory["waiting_for_images"]),
                         (3, 1, 1, 1))
        result = self.run_job()
        self.assertEqual((result["status"], result["added"], result["failed"]), ("completed", 1, 0))
        vectors, cards = _read_index(self.paths.tcg_index)
        np.testing.assert_array_equal(original, vectors[0])
        self.assertEqual(original_card, cards[0])
        self.assertEqual(("new", "Card new", 70), (cards[1]["id"], cards[1]["name"], cards[1]["hp"]))
        self.assertEqual(2, len(index.search(image)))
        before = {name: (self.paths.tcg_index / name).read_bytes()
                  for name in ("vectors.npy", "cards.json", "manifest.json")}
        with self.assertRaisesRegex(ValueError, "No missing embeddings"):
            self.service.start()
        for name, payload in before.items():
            self.assertEqual(payload, (self.paths.tcg_index / name).read_bytes())
        self.assertEqual(1, self.service.inventory()["waiting_for_images"])

    def test_bootstraps_index_from_catalog_and_restores_with_shared_backup(self):
        self.card("new")
        self.assertFalse(self.service.inventory()["index_ready"])
        self.assertEqual(1, self.run_job()["added"])
        backup = BackupService(self.paths).create_backup(["catalog_database", "tcg_images", "tcg_embeddings"])
        target = StoragePaths(self.paths.data_root / "restored")
        restored = BackupService(target).restore_backup(backup)
        self.assertIn("tcg_embeddings", restored["restored_components"])
        self.assertEqual(1, TcgEmbeddingService(target).inventory()["indexed"])
        self.assertEqual("new", TcgImageIndex(target.tcg_index).search(Image.new("RGB", (63, 88), "green"))[0]["id"])

    def test_invalid_images_are_reported_and_valid_cards_are_still_published(self):
        self.card("valid")
        self.card("bad", corrupt=True)
        result = self.run_job()
        self.assertEqual("completed_with_errors", result["status"])
        self.assertEqual((1, 1, 2, 100), (result["added"], result["failed"], result["completed"], result["percent"]))
        self.assertTrue(any("bad:" in error for error in result["errors"]))
        self.assertEqual(["valid"], [card["id"] for card in _read_index(self.paths.tcg_index)[1]])

    def test_all_invalid_images_do_not_create_success_shaped_index(self):
        self.card("bad", corrupt=True)
        result = self.run_job()
        self.assertEqual("completed_with_errors", result["status"])
        self.assertEqual(0, result["added"])
        self.assertFalse((self.paths.tcg_index / "manifest.json").exists())

    def test_rejects_incompatible_or_partial_existing_index_without_replacing_it(self):
        self.card("old")
        self.run_job()
        self.card("new")
        path = self.paths.tcg_index / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["encoder_version"] = "wrong-encoder"
        path.write_text(json.dumps(manifest))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "encoder version"):
            self.service.start()
        self.assertFalse(self.service.inventory()["available"])
        self.assertEqual(before, path.read_bytes())
        path.unlink()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.service.start()

    def test_failed_publication_rolls_back_all_index_files(self):
        self.card("old")
        self.run_job()
        before = {name: (self.paths.tcg_index / name).read_bytes()
                  for name in ("vectors.npy", "cards.json", "manifest.json")}
        original_replace = __import__("os").replace

        def replace(source, target):
            if Path(source).name == "cards.json" and Path(source).parent.name != "previous":
                raise OSError("Simulated write failure")
            original_replace(source, target)

        with mock.patch("src.services.tcg_embedding_service.os.replace", side_effect=replace):
            with self.assertRaisesRegex(OSError, "Simulated"):
                self.service._append([{"id": "new"}], [encode_card_image(Image.new("RGB", (63, 88), "blue"))])
        for name, payload in before.items():
            self.assertEqual(payload, (self.paths.tcg_index / name).read_bytes())

    def test_overlapping_jobs_are_rejected_and_progress_is_shared_between_workers(self):
        self.card("new")
        other = TcgEmbeddingService(self.paths)
        with exclusive_file_lock(self.service._job_lock, blocking=False):
            job = {"status": "running", "message": "Processing", "completed": 1, "total": 2}
            self.service._write_job(job)
            self.assertEqual(job, other.job_status())
            with self.assertRaisesRegex(RuntimeError, "already running"):
                other.start()
        self.assertEqual("failed", other.job_status()["status"])

    def test_progress_updates_do_not_replace_an_open_legacy_json_file(self):
        previous = {"status": "completed", "completed": 4}
        updated = {"status": "completed", "completed": 5}
        self.service._job_file.write_text(json.dumps(previous), encoding="utf-8")
        with self.service._job_file.open(encoding="utf-8") as reader, \
             mock.patch("src.services.tcg_embedding_service.os.replace",
                        side_effect=PermissionError("WinError 5: open destination cannot be replaced")) as replace:
            self.service._write_job(updated)
            replace.assert_not_called()
            self.assertEqual(previous, json.load(reader))
        self.assertEqual(updated, self.service.job_status())

    def test_legacy_status_remains_readable_until_a_new_job_writes_sqlite(self):
        legacy = {"status": "failed", "message": "Previous Windows replacement error", "completed": 1230}
        self.service._job_file.write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(legacy, self.service.job_status())
        updated = {"status": "completed", "message": "New job completed", "completed": 4065}
        self.service._write_job(updated)
        self.assertEqual(updated, TcgEmbeddingService(self.paths).job_status())
        self.assertEqual(legacy, json.loads(self.service._job_file.read_text(encoding="utf-8")))
        with closing(self.service._job_database.connect(read_only=True)) as connection:
            self.assertEqual(updated, json.loads(connection.execute("SELECT payload FROM embedding_job").fetchone()[0]))

    def test_all_4065_progress_updates_survive_cross_process_polling(self):
        job = {"status": "running", "total": 4065, "completed": 0, "message": "Processed 0"}
        code = (
            "import json,sys,time; from pathlib import Path; "
            "from src.config.paths import StoragePaths; "
            "from src.services.tcg_embedding_service import TcgEmbeddingService; "
            "s=TcgEmbeddingService(StoragePaths(Path(sys.argv[1]))); "
            "print('READY',flush=True); polls=0; deadline=time.monotonic()+180\n"
            "while time.monotonic()<deadline:\n"
            " j=s.job_status(); assert j['message']==f\"Processed {j['completed']}\"; polls+=1\n"
            " if j['status']!='running': break\n"
            " time.sleep(0.01)\n"
            "assert j['status']=='completed' and j['completed']==4065, j\n"
            "print(json.dumps({'polls':polls,'completed':j['completed']}),flush=True)\n"
        )
        with exclusive_file_lock(self.service._job_lock, blocking=False):
            self.service._write_job(job)
            with subprocess.Popen(
                [sys.executable, "-c", code, str(self.paths.data_root)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            ) as process:
                self.assertEqual("READY", process.stdout.readline().strip())
                for completed in range(1, 4066):
                    job["completed"] = completed
                    job["message"] = f"Processed {completed}"
                    if completed == 4065:
                        job["status"] = "completed"
                    self.service._write_job(job)
                output, error = process.communicate(timeout=185)
                self.assertEqual(0, process.returncode, error)
                self.assertGreater(json.loads(output)["polls"], 1)
        self.assertEqual(job, self.service.job_status())

    def test_embedding_generation_completes_while_another_service_polls_progress(self):
        for number in range(20):
            self.card(f"new-{number}")
        reader = TcgEmbeddingService(self.paths)
        statuses = []
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("Embedding must be offline")):
            self.service.start()
            deadline = time.monotonic() + 20
            while self.service._thread.is_alive() and time.monotonic() < deadline:
                statuses.append(reader.job_status())
                time.sleep(0.005)
            self.service._thread.join(timeout=5)
        self.assertFalse(self.service._thread.is_alive())
        self.assertTrue(statuses)
        self.assertTrue(all(status["total"] == 20 for status in statuses))
        final = reader.job_status()
        self.assertEqual(("completed", 20, 20, 0), (
            final["status"], final["completed"], final["added"], final["failed"],
        ))
        self.assertEqual(20, len(_read_index(self.paths.tcg_index)[1]))

    def test_loaded_index_reloads_when_another_worker_publishes(self):
        self.card("old")
        self.run_job()
        index = TcgImageIndex(self.paths.tcg_index)
        image = Image.new("RGB", (63, 88), "green")
        self.assertEqual(1, len(index.search(image)))
        code = (
            "import sys; from pathlib import Path; from PIL import Image; "
            "from src.config.paths import StoragePaths; "
            "from src.services.tcg_embedding_service import TcgEmbeddingService; "
            "from src.services.tcg_image_index import encode_card_image; "
            "s=TcgEmbeddingService(StoragePaths(Path(sys.argv[1]))); "
            "s._append([{'id':'new','name':'New'}],[encode_card_image(Image.new('RGB',(63,88),'green'))])"
        )
        process = subprocess.run(
            [sys.executable, "-c", code, str(self.paths.data_root)], capture_output=True,
            text=True, timeout=20, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual(2, len(index.search(image)))

    def test_generate_endpoint_requires_admin_and_returns_progress(self):
        from src.routes.admin_routes import admin_bp
        self.card("new")
        app = Flask(__name__)
        app.register_blueprint(admin_bp)
        with app.test_client() as client, \
             mock.patch("src.routes.embedding_routes.get_tcg_embedding_service", return_value=self.service):
            with mock.patch("src.routes.embedding_routes.require_admin", return_value=({"error": "denied"}, 403)):
                self.assertEqual(403, client.post("/api/admin/embeddings/generate").status_code)
            with mock.patch("src.routes.embedding_routes.require_admin", return_value=None):
                self.assertEqual(1, client.get("/api/admin/embeddings").get_json()["embeddings"]["ready"])
                response = client.post("/api/admin/embeddings/generate")
                self.assertEqual(202, response.status_code, response.get_json())
                self.service._thread.join(timeout=10)
                self.assertEqual("completed", client.get("/api/admin/embeddings/job").get_json()["job"]["status"])
                self.assertEqual(1, client.get("/api/admin/embeddings").get_json()["embeddings"]["indexed"])
                self.assertEqual(400, client.post("/api/admin/embeddings/generate").status_code)


if __name__ == "__main__":
    unittest.main()
