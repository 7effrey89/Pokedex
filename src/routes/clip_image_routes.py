"""Local CLIP scan experiment with a same-capture legacy baseline."""

import base64
import io
import logging
import sqlite3
import time

from flask import jsonify, request

from src.config import get_storage_paths
from src.routes.tcg_image_routes import _NUMPY_INDEX, _SQLITE_TCG_REPOSITORY, _load_data_url_image, tcg_image_bp
from src.services.tcg_card_crop import rectify_card
from src.services.tcg_card_ocr import card_name_match_scores, read_card_print_text, read_card_title
from src.services.tcg_image_index import TcgImageIndex
from src.services.tcg_print_matching import PrintMatch, match_print_text

logger = logging.getLogger(__name__)
_CLIP_INDEX = TcgImageIndex(get_storage_paths().tcg_clip_index, encoder="clip")


@tcg_image_bp.route('/clip-image-match', methods=['POST'])
def match_tcg_card_clip():
    data = request.get_json(silent=True) or {}
    started = time.monotonic()
    try:
        image = _load_data_url_image(data.get("image_data_url") or data.get("imageDataUrl") or "")
        limit = max(1, min(int(data.get("limit", 6)), 24))
        cropped, crop = rectify_card(image)
        if not crop["detected"]:
            logger.warning("CLIP scan crop: %s", crop["warning"])
        ocr: dict[str, object] = {
            "enabled": crop["detected"], "recognized_text": None,
            "confidence": None, "matched_names": [], "print_lines": [], "orientation_degrees": 0,
        }
        name_scores: dict[str, float] = {}
        print_matches: dict[str, PrintMatch] = {}
        ocr_image = cropped
        rotated_title: tuple[str | None, float | None] | None = None
        if crop["detected"]:
            try:
                recognized_text, confidence = read_card_title(cropped)
                cards = _CLIP_INDEX.card_records()
                name_scores = card_name_match_scores(cards, recognized_text, confidence)
                if not name_scores:
                    rotated_image = cropped.rotate(180)
                    rotated_text, rotated_confidence = read_card_title(rotated_image)
                    rotated_title = (rotated_text, rotated_confidence)
                    rotated_scores = card_name_match_scores(cards, rotated_text, rotated_confidence)
                    if rotated_scores and max(rotated_scores.values()) >= 0.9:
                        ocr_image = rotated_image
                        recognized_text, confidence, name_scores = rotated_text, rotated_confidence, rotated_scores
                        ocr["orientation_degrees"] = 180
                ocr["recognized_text"] = recognized_text
                ocr["confidence"] = confidence
                ocr["matched_names"] = sorted({
                    card["name"] for card in cards
                    if card.get("id") in name_scores and isinstance(card.get("name"), str)
                })[:5]
            except (OSError, RuntimeError, ValueError) as exc:
                logger.exception("TCG card title OCR failed")
                ocr["error"] = str(exc)
            try:
                print_lines = read_card_print_text(ocr_image)
                ocr["print_lines"] = print_lines
            except (OSError, RuntimeError, ValueError) as exc:
                logger.exception("TCG card print OCR failed")
                ocr["print_error"] = str(exc)
            else:
                try:
                    print_matches = match_print_text(_SQLITE_TCG_REPOSITORY, set(name_scores), print_lines)
                except (OSError, sqlite3.Error, ValueError) as exc:
                    logger.exception("TCG card print metadata lookup failed")
                    ocr["metadata_error"] = str(exc)
            current_strength = max((item["strength"] for item in print_matches.values()), default=0.0)
            if (not name_scores and current_strength < 0.12
                    and "print_error" not in ocr and "metadata_error" not in ocr):
                try:
                    rotated_lines = read_card_print_text(cropped.rotate(180))
                except (OSError, RuntimeError, ValueError) as exc:
                    logger.exception("Rotated TCG card print OCR failed")
                    ocr["rotation_error"] = str(exc)
                else:
                    try:
                        rotated_matches = match_print_text(_SQLITE_TCG_REPOSITORY, set(), rotated_lines)
                    except (OSError, sqlite3.Error, ValueError) as exc:
                        logger.exception("Rotated TCG card print metadata lookup failed")
                        ocr["rotation_error"] = str(exc)
                    else:
                        rotated_strength = max((item["strength"] for item in rotated_matches.values()), default=0.0)
                        if rotated_strength >= 0.12 and rotated_strength > current_strength:
                            print_matches = rotated_matches
                            ocr["print_lines"] = rotated_lines
                            ocr["orientation_degrees"] = 180
                            if rotated_title is not None:
                                ocr["recognized_text"], ocr["confidence"] = rotated_title
        else:
            ocr["skipped_reason"] = "No reliable card boundary was detected."
        if name_scores or print_matches:
            matches = _CLIP_INDEX.search_with_reranking(
                cropped, limit, name_scores,
                print_scores={card_id: evidence["strength"] for card_id, evidence in print_matches.items()},
            )
        else:
            matches = _CLIP_INDEX.search(cropped, limit=limit)
        for match in matches:
            if match["id"] in print_matches:
                match["ocr_print_evidence"] = print_matches[match["id"]]
        metadata = _CLIP_INDEX.metadata()
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": f"{exc} Use Settings > Step 3 > CLIP + crop first.", "index_ready": False}), 503
    except Exception:
        logger.exception("CLIP TCG image search failed")
        return jsonify({"error": "CLIP search failed; see server logs."}), 500
    comparison = {}
    if data.get("compare") is True:
        try:
            comparison = {
                "legacy": _NUMPY_INDEX.search(image, limit=limit),
                "legacy_crop": _NUMPY_INDEX.search(cropped, limit=limit),
            }
        except (OSError, ValueError) as exc:
            logger.warning("Legacy scan comparison unavailable: %s", exc)
            comparison = {"error": str(exc)}
    output = io.BytesIO()
    cropped.save(output, format="JPEG", quality=90)
    return jsonify({
        "matches": matches, "best_id": matches[0]["id"] if matches else None,
        "matched_count": len(matches), "index_ready": True, "index_metadata": metadata,
        "ocr": ocr,
        "crop": crop, "cropped_image_data_url": "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode(),
        "comparison": comparison, "elapsed_ms": round((time.monotonic() - started) * 1000),
        "score_kind": "cosine_similarity_not_confidence",
        "descriptor_method": "CLIP ViT-B/32, perspective card crop, full-card square framing",
    })
