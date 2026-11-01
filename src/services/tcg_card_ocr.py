"""Local OCR and catalog-name matching for TCG card scans."""

from __future__ import annotations

import difflib
import re
import threading
from typing import Literal, NotRequired, TypedDict

import numpy as np
from PIL import Image, ImageOps

_ENGINE = None
_ENGINE_LOCK = threading.RLock()
_NAME_MATCH_THRESHOLD = 0.82
_OCR_CONFIDENCE_THRESHOLD = 0.75


class OcrLine(TypedDict):
    text: str
    confidence: float
    region: Literal["body", "footer"]
    verification_text: NotRequired[str | None]
    verification_confidence: NotRequired[float | None]


def _engine():
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            from rapidocr import RapidOCR

            _ENGINE = RapidOCR(params={
                "Global.use_det": False,
                "Global.use_cls": False,
                "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                "Det.limit_type": "max",
                "Det.limit_side_len": 640,
                "Det.box_thresh": 0.3,
            })
        return _ENGINE


def read_card_title(image: Image.Image) -> tuple[str | None, float | None]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    title = image.crop((
        round(image.width * 0.15),
        round(image.height * 0.01),
        round(image.width * 0.75),
        round(image.height * 0.10),
    ))
    title = title.resize((title.width * 3, title.height * 3), Image.Resampling.LANCZOS)
    with _ENGINE_LOCK:
        result = _engine()(np.asarray(title), use_det=False, use_cls=False, use_rec=True)
    texts, scores = result.txts or (), result.scores or ()
    if not texts or not scores:
        return None, None
    best = max(zip(texts, scores), key=lambda item: float(item[1]))
    confidence = float(best[1])
    if not np.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("OCR recognizer returned an invalid title score")
    return str(best[0]), confidence


def read_card_print_text(image: Image.Image) -> list[OcrLine]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    top = round(image.height * 0.35)
    region = image.crop((0, top, image.width, image.height))
    with _ENGINE_LOCK:
        engine = _engine()
        detected = engine(np.asarray(region), use_det=True, use_cls=False, use_rec=False)
        if detected.boxes is None:
            return []
        candidates = []
        for box in detected.boxes:
            points = np.asarray(box)
            if points.shape != (4, 2) or not np.isfinite(points).all():
                raise ValueError("OCR detector returned invalid text-box coordinates")
            x1, y1 = np.floor(points.min(axis=0)).astype(int)
            x2, y2 = np.ceil(points.max(axis=0)).astype(int)
            center_y = (top + (y1 + y2) / 2) / image.height
            width_fraction = (x2 - x1) / image.width
            if 0.35 <= center_y < 0.85 and 0.05 <= width_fraction <= 0.55:
                kind = "body"
            elif center_y >= 0.91 and 0.025 <= width_fraction <= 0.32:
                kind = "footer"
            else:
                continue
            bounds = (
                max(0, x1 - 3), max(0, y1 - 3),
                min(region.width, x2 + 3), min(region.height, y2 + 3),
            )
            if bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                candidates.append((kind, center_y, bounds))

        lines: list[OcrLine] = []
        for kind, _, bounds in sorted(candidates, key=lambda item: (item[0] != "footer", item[1]))[:16]:
            patch = region.crop(bounds)
            patch = patch.resize((patch.width * 3, patch.height * 3), Image.Resampling.LANCZOS)
            result = engine(np.asarray(patch), use_det=False, use_cls=False, use_rec=True)
            for text, confidence in zip(result.txts or (), result.scores or ()):
                confidence = float(confidence)
                if not np.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise ValueError("OCR recognizer returned an invalid score")
                if str(text).strip():
                    line: OcrLine = {"text": str(text).strip(), "confidence": confidence, "region": kind}
                    if (kind == "footer" and confidence >= 0.9
                            and any(separator in line["text"] for separator in ("/", "／"))
                            and any(character.isdigit() for character in line["text"])):
                        grayscale = ImageOps.autocontrast(ImageOps.grayscale(patch)).convert("RGB")
                        verification = engine(np.asarray(grayscale), use_det=False, use_cls=False, use_rec=True)
                        verified = list(zip(verification.txts or (), verification.scores or ()))
                        if verified:
                            verified_text, verified_confidence = max(verified, key=lambda item: float(item[1]))
                            verified_confidence = float(verified_confidence)
                            if not np.isfinite(verified_confidence) or not 0 <= verified_confidence <= 1:
                                raise ValueError("OCR verification returned an invalid score")
                            line["verification_text"] = str(verified_text).strip()
                            line["verification_confidence"] = verified_confidence
                        else:
                            line["verification_text"] = None
                            line["verification_confidence"] = None
                    lines.append(line)
        return lines


def card_name_match_scores(
    cards: list[dict], recognized_text: str | None, confidence: float | None,
) -> dict[str, float]:
    if not recognized_text or confidence is None or confidence < _OCR_CONFIDENCE_THRESHOLD:
        return {}
    cards_by_token: dict[str, set[str]] = {}
    for card in cards:
        card_id, name = card.get("id"), card.get("name")
        if not isinstance(card_id, str) or not isinstance(name, str):
            continue
        tokens = set(re.findall(r"[a-z0-9]+", name.casefold()))
        for token in tokens:
            if len(token) >= 3:
                cards_by_token.setdefault(token, set()).add(card_id)

    scores: dict[str, float] = {}
    for token in re.findall(r"[a-z0-9]+", recognized_text.casefold()):
        if len(token) < 3:
            continue
        if token in cards_by_token:
            matched_token, similarity = token, 1.0
        else:
            candidates = difflib.get_close_matches(
                token, cards_by_token, n=1, cutoff=_NAME_MATCH_THRESHOLD,
            )
            if not candidates:
                continue
            matched_token = candidates[0]
            similarity = difflib.SequenceMatcher(None, token, matched_token).ratio()
        score = float(confidence) * similarity
        for card_id in cards_by_token[matched_token]:
            scores[card_id] = max(score, scores.get(card_id, 0.0))
    return scores
