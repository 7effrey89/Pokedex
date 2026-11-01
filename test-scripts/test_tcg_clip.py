import base64
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import cv2
import numpy as np
from flask import Flask
from PIL import Image, ImageDraw

from src.config.paths import StoragePaths
from src.db.database import SqliteDatabase
from src.services.backup_service import BackupService
from src.services.tcg_card_crop import frame_card, rectify_card
from src.services.tcg_card_ocr import card_name_match_scores, read_card_print_text, read_card_title
from src.services.tcg_clip_encoder import ClipEncoder, VECTOR_SIZE
from src.services.tcg_embedding_service import TcgEmbeddingService
from src.services.tcg_image_index import TcgImageIndex, encode_card_image


def photographed_card():
    card = Image.new("RGB", (315, 440), "white")
    draw = ImageDraw.Draw(card)
    draw.rectangle((8, 8, 306, 431), fill=(30, 180, 40))
    draw.rectangle((30, 80, 280, 235), fill=(20, 40, 180))
    source = np.float32(((0, 0), (314, 0), (314, 439), (0, 439)))
    corners = np.float32(((140, 90), (450, 120), (475, 560), (110, 535)))
    transform = cv2.getPerspectiveTransform(source, corners)
    pixels = cv2.warpPerspective(np.asarray(card), transform, (630, 700), borderValue=(45, 45, 45))
    return card, Image.fromarray(pixels), corners


class CropTests(unittest.TestCase):
    def test_detects_outer_card_and_corrects_perspective_instead_of_artwork_rectangle(self):
        _, photo, corners = photographed_card()
        cropped, metadata = rectify_card(photo)
        self.assertEqual("perspective", metadata["method"])
        self.assertEqual((630, 880), cropped.size)
        np.testing.assert_allclose(metadata["corners"], corners, atol=8)
        self.assertGreater(np.asarray(cropped)[600, 300, 1], 150)

    def test_no_boundary_reports_guide_fallback(self):
        _, metadata = rectify_card(Image.new("RGB", (800, 600), "gray"))
        self.assertFalse(metadata["detected"])
        self.assertIn("No reliable", metadata["warning"])

    def test_interior_landscape_panel_is_not_mistaken_for_a_card(self):
        image = Image.new("RGB", (630, 830), (180, 165, 150))
        draw = ImageDraw.Draw(image)
        draw.rectangle((80, 70, 550, 750), fill=(181, 166, 151))
        draw.rectangle((136, 403, 526, 675), fill=(185, 190, 195), outline=(35, 35, 35), width=4)
        _, metadata = rectify_card(image)
        self.assertFalse(metadata["detected"])
        self.assertEqual("guide_fallback", metadata["method"])

    def test_large_sideways_card_is_still_detected_in_a_portrait_frame(self):
        image = Image.new("RGB", (630, 830), (50, 50, 50))
        ImageDraw.Draw(image).rectangle((45, 210, 585, 610), fill=(230, 230, 230), outline=(0, 0, 0), width=5)
        _, metadata = rectify_card(image)
        self.assertTrue(metadata["detected"])
        self.assertEqual("perspective", metadata["method"])

    def test_color_fallback_orders_corners_before_perspective_warp(self):
        image = Image.new("RGB", (630, 900), (184, 164, 139))
        draw = ImageDraw.Draw(image)
        corners = ((90, 50), (550, 70), (575, 840), (75, 820))
        draw.polygon(corners, fill=(55, 125, 62))
        draw.rectangle((200, 90, 300, 150), fill=(220, 40, 35))
        pixels = np.asarray(image)
        with mock.patch("src.services.tcg_card_crop.cv2.Canny",
                        return_value=np.zeros(pixels.shape[:2], dtype=np.uint8)):
            cropped, metadata = rectify_card(image)
        self.assertEqual("color_segmentation", metadata["method"])
        self.assertTrue(metadata["detected"])
        points = np.asarray(metadata["corners"])
        self.assertLess(points[0, 1], points[3, 1])
        self.assertLess(points[1, 1], points[2, 1])
        top = np.asarray(cropped)[:130]
        self.assertGreater(int(((top[:, :, 0] > 150) & (top[:, :, 0] > top[:, :, 1] * 1.5)).sum()), 100)

    def test_reference_is_not_cropped_to_inner_artwork(self):
        card, _, _ = photographed_card()
        result, metadata = rectify_card(card, reference=True)
        self.assertEqual(card.size, result.size)
        self.assertEqual("catalog_card", metadata["method"])

    def test_square_framing_retains_top_and_bottom_of_card(self):
        card = Image.new("RGB", (630, 880), "green")
        draw = ImageDraw.Draw(card)
        draw.rectangle((0, 20, 630, 150), fill="red")
        draw.rectangle((0, 730, 630, 860), fill="blue")
        framed = np.asarray(frame_card(card))
        self.assertEqual((224, 224, 3), framed.shape)
        self.assertGreater(framed[10, 112, 0], 200)
        self.assertGreater(framed[210, 112, 2], 200)


class CardTitleOcrTests(unittest.TestCase):
    def test_title_reader_uses_only_the_name_region_and_returns_confidence(self):
        engine = mock.Mock(return_value=SimpleNamespace(txts=("Shaymin",), scores=(0.94,)))
        with mock.patch("src.services.tcg_card_ocr._engine", return_value=engine):
            text, confidence = read_card_title(Image.new("RGB", (630, 880), "green"))
        self.assertEqual(("Shaymin", 0.94), (text, confidence))
        self.assertEqual((237, 1134, 3), engine.call_args.args[0].shape)

    def test_title_reader_rejects_non_finite_model_scores(self):
        engine = mock.Mock(return_value=SimpleNamespace(txts=("Shaymin",), scores=(float("nan"),)))
        with mock.patch("src.services.tcg_card_ocr._engine", return_value=engine):
            with self.assertRaises(ValueError):
                read_card_title(Image.new("RGB", (630, 880), "green"))

    def test_title_match_reranks_all_matching_prints_but_ignores_low_confidence_text(self):
        cards = [
            {"id": "shaymin", "name": "Shaymin"},
            {"id": "shaymin-ex", "name": "Shaymin EX"},
            {"id": "pidgey", "name": "Pidgey"},
        ]
        scores = card_name_match_scores(cards, "Shayin", 0.9)
        self.assertGreater(scores["shaymin"], 0.8)
        self.assertGreater(scores["shaymin-ex"], 0.8)
        self.assertNotIn("pidgey", scores)
        self.assertEqual({}, card_name_match_scores(cards, "Shaymin", 0.5))


class CardPrintOcrTests(unittest.TestCase):
    def test_selects_body_and_footer_boxes_and_resets_engine_flags_for_title(self):
        boxes = np.float32([
            [[50, 100], [180, 100], [180, 125], [50, 125]],
            [[35, 510], [160, 510], [160, 525], [35, 525]],
            [[0, 300], [500, 300], [500, 320], [0, 320]],
        ])
        engine = mock.Mock(side_effect=[
            SimpleNamespace(boxes=boxes),
            SimpleNamespace(txts=("Illus. Heisuke Kitazawa",), scores=(0.95,)),
            SimpleNamespace(txts=("Smash Kick",), scores=(0.99,)),
            SimpleNamespace(txts=("Shaymin",), scores=(0.94,)),
        ])
        with mock.patch("src.services.tcg_card_ocr._engine", return_value=engine):
            lines = read_card_print_text(Image.new("RGB", (630, 880), "green"))
            title = read_card_title(Image.new("RGB", (630, 880), "green"))
        self.assertEqual(["footer", "body"], [line["region"] for line in lines])
        self.assertEqual(["Illus. Heisuke Kitazawa", "Smash Kick"], [line["text"] for line in lines])
        self.assertEqual(("Shaymin", 0.94), title)
        self.assertEqual({"use_det": True, "use_cls": False, "use_rec": False}, engine.call_args_list[0].kwargs)
        for call in engine.call_args_list[1:]:
            self.assertEqual({"use_det": False, "use_cls": False, "use_rec": True}, call.kwargs)

    def test_no_detected_text_is_not_an_error(self):
        engine = mock.Mock(return_value=SimpleNamespace(boxes=None))
        with mock.patch("src.services.tcg_card_ocr._engine", return_value=engine):
            self.assertEqual([], read_card_print_text(Image.new("RGB", (630, 880))))

    def test_collector_text_is_checked_with_a_second_preprocessing_pass(self):
        boxes = np.float32([[[35, 510], [160, 510], [160, 525], [35, 525]]])
        engine = mock.Mock(side_effect=[
            SimpleNamespace(boxes=boxes),
            SimpleNamespace(txts=("185/182",), scores=(0.99,)),
            SimpleNamespace(txts=("185/182",), scores=(0.96,)),
        ])
        with mock.patch("src.services.tcg_card_ocr._engine", return_value=engine):
            lines = read_card_print_text(Image.new("RGB", (630, 880), "green"))
        self.assertEqual("185/182", lines[0]["verification_text"])
        self.assertEqual(0.96, lines[0]["verification_confidence"])
        pixels = engine.call_args_list[2].args[0]
        np.testing.assert_array_equal(pixels[:, :, 0], pixels[:, :, 1])
        np.testing.assert_array_equal(pixels[:, :, 1], pixels[:, :, 2])


class ClipTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.paths = StoragePaths(Path(temporary.name).resolve())
        database = SqliteDatabase(self.paths.catalog_database)
        database.initialize()
        image_path = self.paths.tcg_images / "card.png"
        image_path.parent.mkdir(parents=True)
        photographed_card()[0].save(image_path)
        with closing(database.connect()) as connection, connection:
            connection.execute("INSERT INTO tcg_set(id, name) VALUES ('test', 'Test')")
            connection.execute("INSERT INTO tcg_card(id, set_id, name, number) VALUES ('card', 'test', 'Card', '1')")
            connection.execute(
                "INSERT INTO card_asset(card_id, asset_kind, local_path, source_url) VALUES ('card', 'large', ?, ?)",
                (self.paths.relative_to_root(image_path), "https://example.test/card.png"),
            )
        self.service = TcgEmbeddingService(self.paths, encoder="clip")
        self.vector = np.zeros(VECTOR_SIZE, dtype=np.float32)
        self.vector[0] = 1

    def test_local_clip_job_uses_separate_index_and_backup_restores_both_encoders(self):
        legacy = TcgEmbeddingService(self.paths)
        legacy._append([{"id": "card", "name": "Original"}], [encode_card_image(photographed_card()[0])])
        before = (self.paths.tcg_index / "vectors.npy").read_bytes()
        with mock.patch.object(self.service.clip_encoder, "prepare"), \
             mock.patch.object(self.service.clip_encoder, "encode", return_value=self.vector[None, :]):
            self.service.start()
            self.service._thread.join(10)
        job = self.service.job_status()
        self.assertEqual(("completed", 1, 0), (job["status"], job["added"], job["failed"]))
        self.assertEqual(before, (self.paths.tcg_index / "vectors.npy").read_bytes())
        self.assertEqual(1, self.service.inventory()["indexed"])
        self.paths.clip_model.write_bytes(b"test-model")
        with mock.patch.object(ClipEncoder, "_verify_model"):
            bundle = BackupService(self.paths).create_backup([
                "catalog_database", "tcg_images", "tcg_embeddings", "tcg_clip_embeddings",
            ])
            target = StoragePaths(self.paths.data_root / "restored")
            result = BackupService(target).restore_backup(bundle)
        self.assertEqual({"catalog_database", "tcg_images", "tcg_embeddings", "tcg_clip_embeddings"},
                         set(result["restored_components"]))
        self.assertEqual(b"test-model", target.clip_model.read_bytes())
        self.assertEqual(1, TcgEmbeddingService(target, encoder="clip").inventory()["indexed"])
        with mock.patch("src.services.tcg_clip_encoder.get_clip_encoder") as encoder:
            encoder.return_value.encode.return_value = np.stack([self.vector, self.vector])
            index = TcgImageIndex(target.tcg_clip_index, encoder="clip")
            self.assertEqual("card", index.search(photographed_card()[0])[0]["id"])

    def test_model_failure_is_persisted_without_replacing_legacy_index(self):
        with mock.patch.object(self.service.clip_encoder, "prepare", side_effect=ValueError("checksum mismatch")):
            self.service.start()
            self.service._thread.join(10)
        self.assertEqual("failed", self.service.job_status()["status"])
        self.assertIn("checksum mismatch", self.service.job_status()["message"])
        self.assertFalse((self.paths.tcg_clip_index / "manifest.json").exists())

    def test_ocr_reranking_can_promote_a_text_match_and_preserves_cosine_score(self):
        card_a = np.zeros(VECTOR_SIZE, dtype=np.float32)
        card_a[0], card_a[1] = 0.8, 0.6
        card_b = np.zeros(VECTOR_SIZE, dtype=np.float32)
        card_b[0], card_b[1] = 0.85, np.sqrt(1 - 0.85 ** 2)
        self.service._append(
            [{"id": "ocr-match", "name": "Shaymin"}, {"id": "visual-match", "name": "Beautifly"}],
            [card_a, card_b],
        )
        index = TcgImageIndex(self.paths.tcg_clip_index, encoder="clip")
        query = np.zeros(VECTOR_SIZE, dtype=np.float32)
        query[0] = 1
        with mock.patch("src.services.tcg_clip_encoder.get_clip_encoder") as encoder:
            encoder.return_value.encode.return_value = np.stack([query, query])
            results = index.search_with_reranking(
                Image.new("RGB", (630, 880), "green"), 2, {"ocr-match": 0.8},
            )
        self.assertEqual(["ocr-match", "visual-match"], [result["id"] for result in results])
        self.assertEqual(0.8, results[0]["score"])
        self.assertEqual(0.12, results[0]["ocr_rerank_boost"])

    def test_print_evidence_ranks_same_name_variants_without_changing_cosine(self):
        full_art = np.zeros(VECTOR_SIZE, dtype=np.float32)
        full_art[0], full_art[1] = 0.8, 0.6
        standard = np.zeros(VECTOR_SIZE, dtype=np.float32)
        standard[0], standard[1] = 0.86, np.sqrt(1 - 0.86 ** 2)
        self.service._append(
            [{"id": "full-art", "name": "Shaymin"}, {"id": "standard", "name": "Shaymin"}],
            [full_art, standard],
        )
        index = TcgImageIndex(self.paths.tcg_clip_index, encoder="clip")
        query = np.zeros(VECTOR_SIZE, dtype=np.float32)
        query[0] = 1
        with mock.patch("src.services.tcg_clip_encoder.get_clip_encoder") as encoder:
            encoder.return_value.encode.return_value = np.stack([query, query])
            results = index.search_with_reranking(
                Image.new("RGB", (630, 880)), 2, {"full-art": 0.95, "standard": 0.95},
                print_scores={"full-art": 0.9, "standard": 0.225},
            )
        self.assertEqual(["full-art", "standard"], [result["id"] for result in results])
        self.assertEqual(0.8, results[0]["score"])
        self.assertEqual(0.216, results[0]["ocr_print_boost"])
        with self.assertRaises(ValueError):
            index.search_with_reranking(Image.new("RGB", (10, 10)), 2, {}, print_scores={"full-art": float("nan")})

    def test_checkpoint_survives_late_failure_and_retry_encodes_only_remaining_card(self):
        assets = {f"card-{number}": [] for number in range(257)}
        image_path = self.paths.tcg_images / "card.png"
        append = self.service._append
        calls = 0

        def publish(cards, vectors):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("late publication failure")
            return append(cards, vectors)

        with mock.patch.object(self.service, "_catalog_assets", return_value=assets), \
             mock.patch.object(self.service, "_local_image", return_value=image_path), \
             mock.patch.object(self.service.repository, "get_card", side_effect=lambda card_id: {"id": card_id, "name": card_id}), \
             mock.patch.object(self.service.clip_encoder, "prepare"), \
             mock.patch.object(self.service.clip_encoder, "encode", side_effect=lambda images: np.tile(self.vector, (len(images), 1))) as encode:
            with mock.patch.object(self.service, "_append", side_effect=publish):
                self.service.start()
                self.service._thread.join(30)
            self.assertFalse(self.service._thread.is_alive())
            self.assertEqual("failed", self.service.job_status()["status"])
            self.assertEqual(256, self.service.job_status()["added"])
            self.assertEqual(256, len(self.service._snapshot()[1]))
            encode.reset_mock()
            self.service.start()
            self.service._thread.join(10)
            self.assertEqual("completed", self.service.job_status()["status"])
            self.assertEqual(1, self.service.job_status()["added"])
            self.assertEqual(1, len(encode.call_args.args[0]))
            self.assertEqual(257, len(self.service._snapshot()[1]))

    def test_embedding_preprocessing_and_normalization_match_model_contract(self):
        encoder = ClipEncoder(self.paths.clip_model)
        encoder._session = mock.Mock()
        encoder._session.run.return_value = [np.ones((1, VECTOR_SIZE), dtype=np.float32)]
        result = encoder.encode([Image.new("RGB", (630, 880), "green")])
        self.assertEqual((1, VECTOR_SIZE), result.shape)
        self.assertAlmostEqual(1, np.linalg.norm(result), places=6)
        args = encoder._session.run.call_args.args
        self.assertEqual(["image_embeds"], args[0])
        self.assertEqual((1, 3, 224, 224), args[1]["pixel_values"].shape)
        self.assertEqual(np.float32, args[1]["pixel_values"].dtype)

    def test_clip_route_returns_crop_and_same_capture_comparison(self):
        from src.routes import clip_image_routes as routes
        _, photo, _ = photographed_card()
        buffer = io.BytesIO()
        photo.save(buffer, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        app = Flask(__name__)
        app.register_blueprint(routes.tcg_image_bp)
        match = {
            "id": "card", "score": 0.8, "ocr_rerank_boost": 0.12,
            "card": {"id": "card", "name": "Shaymin"},
        }
        print_lines = [{"region": "body", "text": "Leaf Step", "confidence": 0.99}]
        evidence = {"strength": 0.75, "attacks": ["Leaf Step"],
                    "collector_number": None, "artist": None, "set_code": None}
        with app.test_client() as client, mock.patch.object(routes, "_CLIP_INDEX") as index, \
             mock.patch.object(routes, "_NUMPY_INDEX") as legacy, \
             mock.patch.object(routes, "read_card_title", return_value=("Shaymin", 0.9)), \
             mock.patch.object(routes, "read_card_print_text", return_value=print_lines), \
             mock.patch.object(routes, "match_print_text", return_value={"card": evidence}) as match_print:
            index.card_records.return_value = [{"id": "card", "name": "Shaymin"}]
            index.search_with_reranking.return_value = [match]
            index.metadata.return_value = {"vector_size": 512, "card_count": 1}
            legacy.search.return_value = [match]
            result = client.post("/api/tcg/clip-image-match", json={
                "image_data_url": data_url, "compare": True,
            })
            self.assertEqual(200, result.status_code)
            payload = result.get_json()
            self.assertEqual("perspective", payload["crop"]["method"])
            self.assertEqual("Shaymin", payload["ocr"]["recognized_text"])
            self.assertEqual(["Shaymin"], payload["ocr"]["matched_names"])
            self.assertEqual(print_lines, payload["ocr"]["print_lines"])
            self.assertEqual(evidence, payload["matches"][0]["ocr_print_evidence"])
            self.assertEqual({"card": 0.75}, index.search_with_reranking.call_args.kwargs["print_scores"])
            self.assertEqual({"card"}, match_print.call_args.args[1])
            self.assertEqual("cosine_similarity_not_confidence", payload["score_kind"])
            self.assertEqual({"legacy", "legacy_crop"}, set(payload["comparison"]))
            self.assertEqual(2, legacy.search.call_count)
            index.search_with_reranking.side_effect = FileNotFoundError("CLIP embeddings missing")
            self.assertEqual(503, client.post("/api/tcg/clip-image-match", json={
                "image_data_url": data_url,
            }).status_code)

    def test_clip_route_skips_ocr_when_crop_is_unreliable(self):
        from src.routes import clip_image_routes as routes
        photo = Image.new("RGB", (630, 880), "gray")
        buffer = io.BytesIO()
        photo.save(buffer, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        app = Flask(__name__)
        app.register_blueprint(routes.tcg_image_bp)
        with app.test_client() as client, mock.patch.object(routes, "_CLIP_INDEX") as index, \
             mock.patch.object(routes, "read_card_title") as title, \
             mock.patch.object(routes, "read_card_print_text") as print_ocr:
            index.search.return_value = [{"id": "card", "score": 0.8, "card": {"id": "card"}}]
            index.metadata.return_value = {"card_count": 1}
            result = client.post("/api/tcg/clip-image-match", json={"image_data_url": data_url})
            self.assertEqual(200, result.status_code)
            self.assertFalse(result.get_json()["ocr"]["enabled"])
            self.assertIn("boundary", result.get_json()["ocr"]["skipped_reason"])
            title.assert_not_called()
            print_ocr.assert_not_called()
            index.search_with_reranking.assert_not_called()

    def test_upside_down_title_rotates_print_ocr_without_changing_visual_input(self):
        from src.routes import clip_image_routes as routes
        photo = Image.new("RGB", (630, 880), "blue")
        ImageDraw.Draw(photo).rectangle((0, 0, 629, 100), fill="red")
        buffer = io.BytesIO()
        photo.save(buffer, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        app = Flask(__name__)
        app.register_blueprint(routes.tcg_image_bp)
        with app.test_client() as client, mock.patch.object(routes, "_CLIP_INDEX") as index, \
             mock.patch.object(routes, "rectify_card", return_value=(photo, {"detected": True, "method": "test"})), \
             mock.patch.object(routes, "read_card_title", side_effect=[("", 0.0), ("Shaymin", 0.99)]), \
             mock.patch.object(routes, "read_card_print_text", return_value=[]) as print_ocr, \
             mock.patch.object(routes, "match_print_text", return_value={}):
            index.card_records.return_value = [{"id": "card", "name": "Shaymin"}]
            index.search_with_reranking.return_value = [{"id": "card", "score": 0.8, "card": {"id": "card"}}]
            index.metadata.return_value = {"card_count": 1}
            result = client.post("/api/tcg/clip-image-match", json={"image_data_url": data_url})
            self.assertEqual(200, result.status_code)
            self.assertEqual(180, result.get_json()["ocr"]["orientation_degrees"])
            self.assertEqual("Shaymin", result.get_json()["ocr"]["recognized_text"])
            self.assertEqual((0, 0, 255), print_ocr.call_args.args[0].getpixel((0, 0)))
            self.assertIs(photo, index.search_with_reranking.call_args.args[0])

    def test_upside_down_print_text_can_match_without_a_readable_title(self):
        from src.routes import clip_image_routes as routes
        photo = Image.new("RGB", (630, 880), "green")
        buffer = io.BytesIO()
        photo.save(buffer, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        app = Flask(__name__)
        app.register_blueprint(routes.tcg_image_bp)
        evidence = {"strength": 0.6, "attacks": ["Smash Kick"],
                    "collector_number": None, "artist": None, "set_code": None}
        lines = [{"region": "body", "text": "Smash Kick", "confidence": 0.99}]
        with app.test_client() as client, mock.patch.object(routes, "_CLIP_INDEX") as index, \
             mock.patch.object(routes, "rectify_card", return_value=(photo, {"detected": True, "method": "test"})), \
             mock.patch.object(routes, "read_card_title", return_value=("", 0.0)), \
             mock.patch.object(routes, "read_card_print_text", side_effect=[[], lines]), \
             mock.patch.object(routes, "match_print_text", side_effect=[{}, {"card": evidence}]):
            index.card_records.return_value = [{"id": "card", "name": "Shaymin"}]
            index.search_with_reranking.return_value = [{"id": "card", "score": 0.8, "card": {"id": "card"}}]
            index.metadata.return_value = {"card_count": 1}
            result = client.post("/api/tcg/clip-image-match", json={"image_data_url": data_url})
            self.assertEqual(200, result.status_code)
            self.assertEqual(180, result.get_json()["ocr"]["orientation_degrees"])
            self.assertEqual(lines, result.get_json()["ocr"]["print_lines"])
            self.assertEqual({"card": 0.6}, index.search_with_reranking.call_args.kwargs["print_scores"])

    def test_title_failure_still_uses_print_text_and_metadata_failure_is_reported(self):
        from src.routes import clip_image_routes as routes
        _, photo, _ = photographed_card()
        buffer = io.BytesIO()
        photo.save(buffer, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        app = Flask(__name__)
        app.register_blueprint(routes.tcg_image_bp)
        lines = [{"region": "body", "text": "Leaf Step", "confidence": 0.99}]
        evidence = {"strength": 0.75, "attacks": ["Leaf Step"],
                    "collector_number": None, "artist": None, "set_code": None}
        with app.test_client() as client, mock.patch.object(routes, "_CLIP_INDEX") as index, \
             mock.patch.object(routes, "read_card_title", side_effect=RuntimeError("title unavailable")), \
             mock.patch.object(routes, "read_card_print_text", return_value=lines), \
             mock.patch.object(routes, "match_print_text", return_value={"card": evidence}) as matcher, \
             self.assertLogs("src.routes.clip_image_routes", level="ERROR"):
            index.search_with_reranking.return_value = [{"id": "card", "score": 0.8, "card": {"id": "card"}}]
            index.search.return_value = [{"id": "card", "score": 0.8, "card": {"id": "card"}}]
            index.metadata.return_value = {"card_count": 1}
            result = client.post("/api/tcg/clip-image-match", json={"image_data_url": data_url})
            self.assertEqual(200, result.status_code)
            self.assertEqual("title unavailable", result.get_json()["ocr"]["error"])
            self.assertEqual(set(), matcher.call_args.args[1])
            self.assertEqual({"card": 0.75}, index.search_with_reranking.call_args.kwargs["print_scores"])
            matcher.side_effect = sqlite3.OperationalError("catalog locked")
            result = client.post("/api/tcg/clip-image-match", json={"image_data_url": data_url})
            self.assertEqual(200, result.status_code)
            self.assertEqual("catalog locked", result.get_json()["ocr"]["metadata_error"])
            index.search.assert_called_once()

    def test_print_ocr_failure_reports_error_and_keeps_title_ranking(self):
        from src.routes import clip_image_routes as routes
        _, photo, _ = photographed_card()
        buffer = io.BytesIO()
        photo.save(buffer, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        app = Flask(__name__)
        app.register_blueprint(routes.tcg_image_bp)
        with app.test_client() as client, mock.patch.object(routes, "_CLIP_INDEX") as index, \
             mock.patch.object(routes, "read_card_title", return_value=("Shaymin", 0.99)), \
             mock.patch.object(routes, "read_card_print_text", side_effect=RuntimeError("print OCR unavailable")), \
             mock.patch.object(routes, "match_print_text") as matcher, \
             self.assertLogs("src.routes.clip_image_routes", level="ERROR"):
            index.card_records.return_value = [{"id": "card", "name": "Shaymin"}]
            index.search_with_reranking.return_value = [{"id": "card", "score": 0.8, "card": {"id": "card"}}]
            index.metadata.return_value = {"card_count": 1}
            result = client.post("/api/tcg/clip-image-match", json={"image_data_url": data_url})
            self.assertEqual(200, result.status_code)
            self.assertEqual("print OCR unavailable", result.get_json()["ocr"]["print_error"])
            self.assertEqual({}, index.search_with_reranking.call_args.kwargs["print_scores"])
            matcher.assert_not_called()

    def test_admin_endpoints_route_clip_encoder_and_reject_unknown_encoder(self):
        from src.routes.admin_routes import admin_bp
        app = Flask(__name__)
        app.register_blueprint(admin_bp)
        with app.test_client() as client, \
             mock.patch("src.routes.embedding_routes.require_admin", return_value=None), \
             mock.patch("src.routes.embedding_routes.get_tcg_embedding_service", return_value=self.service) as getter:
            self.assertEqual(200, client.get("/api/admin/embeddings?encoder=clip").status_code)
            getter.assert_called_once_with("clip")
        with app.test_client() as client, mock.patch("src.routes.embedding_routes.require_admin", return_value=None):
            for url in ("/api/admin/embeddings?encoder=wrong", "/api/admin/embeddings/job?encoder=wrong"):
                self.assertEqual(400, client.get(url).status_code)


if __name__ == "__main__":
    unittest.main()
