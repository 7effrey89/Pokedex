"""
TCG Image Routes - Visual matching helpers for scanned card images
"""

import base64
import binascii
import io
import json
import logging
import re
from urllib.parse import urlparse

import requests
from flask import Blueprint, Response, jsonify, request
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

tcg_image_bp = Blueprint('tcg_image', __name__, url_prefix='/api/tcg')

CARD_ASPECT_RATIO = 63 / 88
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_CANDIDATES = 24
IMAGE_TIMEOUT_SECONDS = 8
ALLOWED_IMAGE_HOSTS = {'images.pokemontcg.io', 'images.scrydex.com'}
_FEATURE_CACHE = {}


@tcg_image_bp.route('/image-proxy', methods=['GET'])
def proxy_tcg_card_image():
    """Proxy official TCG card images so browser canvas POCs can read pixels."""
    image_url = request.args.get('url', '').strip()
    if not _is_allowed_image_url(image_url):
        return jsonify({"error": "url must be an allowed HTTPS card image URL"}), 400

    judge_context = None

    try:
        response = requests.get(image_url, timeout=IMAGE_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Unable to proxy TCG image %s: %s", image_url, exc)
        return jsonify({"error": "unable to fetch image"}), 502

    if len(response.content) > MAX_IMAGE_BYTES:
        return jsonify({"error": "candidate image is too large"}), 413

    content_type = response.headers.get('Content-Type', 'image/png')
    proxied = Response(response.content, mimetype=content_type)
    proxied.headers['Cache-Control'] = 'public, max-age=86400'
    proxied.headers['Access-Control-Allow-Origin'] = '*'
    return proxied


@tcg_image_bp.route('/image-match', methods=['POST'])
def match_tcg_card_image():
    """Compare a camera frame against candidate TCG card images."""
    data = request.get_json(silent=True) or {}
    image_data_url = data.get('image_data_url') or data.get('imageDataUrl')
    candidates = data.get('candidates') or []

    if not image_data_url:
        return jsonify({"error": "image_data_url is required"}), 400
    if not isinstance(candidates, list) or not candidates:
        return jsonify({"error": "candidates must be a non-empty list"}), 400

    try:
        source_image = _load_data_url_image(image_data_url)
        source_features = _build_image_features(_crop_to_card_aspect(source_image))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    matches = []
    for candidate in candidates[:MAX_CANDIDATES]:
        card_id = candidate.get('id')
        image_url = _candidate_image_url(candidate)
        if not card_id or not image_url:
            continue

        try:
            candidate_features = _get_remote_image_features(image_url)
            visual_score, score_parts = _compare_features(source_features, candidate_features)
            matches.append({
                "id": card_id,
                "name": candidate.get('name'),
                "visual_score": round(visual_score, 2),
                **score_parts
            })
        except Exception as exc:
            logger.warning("Unable to score TCG image candidate %s: %s", card_id, exc)

    matches.sort(key=lambda item: item["visual_score"], reverse=True)
    return jsonify({
        "matches": matches,
        "best_id": matches[0]["id"] if matches else None,
        "matched_count": len(matches)
    })


@tcg_image_bp.route('/extract-card-text', methods=['POST'])
def extract_tcg_card_text():
    """Use the configured Azure OpenAI vision model to read text from a card crop."""
    data = request.get_json(silent=True) or {}
    image_data_url = data.get('image_data_url') or data.get('imageDataUrl')
    api_settings_payload = data.get('api_settings')

    if not image_data_url:
        return jsonify({"error": "image_data_url is required"}), 400

    try:
        _load_data_url_image(image_data_url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        from azure_openai_chat import get_azure_chat
        from src.utils.api_settings import resolve_api_settings

        client_config = None
        if api_settings_payload:
            client_config = resolve_api_settings(api_settings_payload, require_chat=True).get('chat')
        azure_chat = get_azure_chat()
        client, deployment = azure_chat._get_client(client_config)

        extraction_schema = {
            "extracted_text": "short readable summary of all visible evidence",
            "metadata": {
                "name": "Pokemon/card name or null",
                "hp": "printed HP number or null",
                "types": ["Pokemon energy/type icons, for example Dragon, Fighting, Metal"],
                "stage": "Basic, Stage 1, Stage 2, Restored, etc. or null",
                "evolves_from": "previous evolution text or null",
                "set_name": "visible set/expansion text or null",
                "number": "collector number such as 45/108 or 45 or null",
                "rarity": "rarity text/symbol interpretation or null",
                "attacks": [
                    {
                        "name": "attack name",
                        "cost": ["energy symbols before the attack, including Colorless"],
                        "damage": "printed damage or null",
                        "text": "attack effect text or null"
                    }
                ],
                "weaknesses": [{"type": "energy type icon", "value": "modifier such as x2 or +20"}],
                "resistances": [{"type": "energy type icon", "value": "modifier such as -20"}],
                "retreat_cost": "number of retreat icons or null",
                "retreat_types": ["retreat cost icons, usually Colorless"],
                "artist": "artist name or null"
            },
            "confidence": "0-100 number",
            "notes": "brief uncertainty notes"
        }
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON only. You are reading a Pokemon Trading Card Game card from an image. "
                        "Extract visible printed text and infer Pokemon TCG icon metadata when it is visually clear. "
                        "Use standard Pokemon TCG type names for icons: Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness, Metal, Fairy, Dragon, Colorless. "
                        "Energy symbols before attack names are attack costs. Weakness, Resistance, and Retreat are often logos/icons near the lower card area, not OCR text. "
                        "Do not invent fields that are not visible; use null or empty arrays when uncertain."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Read this cropped Pokemon TCG card image as structured card metadata. "
                                "Use the same attribute names that candidate card data uses so it can be compared field-by-field. "
                                "Pay special attention to the card name, HP, Pokemon type icons, set/collector number, rarity symbol, "
                                "attack names, attack energy cost icons, attack damage, weakness icons, resistance icons, and retreat cost icons. "
                                "Return JSON matching this shape exactly:\n"
                                f"{json.dumps(extraction_schema, ensure_ascii=True)}"
                            )
                        },
                        {"type": "image_url", "image_url": {"url": image_data_url, "detail": "high"}}
                    ]
                }
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=600
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        metadata = parsed.get('metadata') if isinstance(parsed.get('metadata'), dict) else {}
        return jsonify({
            "extracted_text": str(parsed.get('extracted_text') or '').strip(),
            "metadata": metadata,
            "confidence": _safe_float(parsed.get('confidence')),
            "notes": str(parsed.get('notes') or '').strip(),
            "source": "llm_vision"
        })
    except Exception as exc:
        logger.warning("LLM card text extraction unavailable: %s", exc)
        return jsonify({"error": str(exc), "source": "llm_vision"}), 502


@tcg_image_bp.route('/rerank-match', methods=['POST'])
def rerank_tcg_card_match():
    """Use an LLM judge to rerank POC card candidates from extracted text and embedding scores."""
    data = request.get_json(silent=True) or {}
    candidates = data.get('candidates') or []
    extracted_text = str(data.get('extracted_text') or data.get('extractedText') or '').strip()
    extracted_metadata = data.get('extracted_metadata') or data.get('extractedMetadata') or {}
    if not isinstance(extracted_metadata, dict):
        extracted_metadata = {}
    api_settings_payload = data.get('api_settings')

    if not isinstance(candidates, list) or not candidates:
        return jsonify({"error": "candidates must be a non-empty list"}), 400

    safe_candidates = []
    for candidate in candidates[:MAX_CANDIDATES]:
        if not isinstance(candidate, dict) or not candidate.get('id'):
            continue
        safe_candidates.append({
            "id": str(candidate.get('id')),
            "name": str(candidate.get('name') or ''),
            "set": str(candidate.get('set') or ''),
            "number": str(candidate.get('number') or ''),
            "rarity": str(candidate.get('rarity') or ''),
            "hp": str(candidate.get('hp') or ''),
            "supertype": str(candidate.get('supertype') or ''),
            "subtypes": candidate.get('subtypes') if isinstance(candidate.get('subtypes'), list) else [],
            "types": candidate.get('types') if isinstance(candidate.get('types'), list) else [],
            "attacks": candidate.get('attacks') if isinstance(candidate.get('attacks'), list) else [],
            "weaknesses": candidate.get('weaknesses') if isinstance(candidate.get('weaknesses'), list) else [],
            "resistances": candidate.get('resistances') if isinstance(candidate.get('resistances'), list) else [],
            "retreatCost": candidate.get('retreatCost') if isinstance(candidate.get('retreatCost'), list) else [],
            "convertedRetreatCost": candidate.get('convertedRetreatCost'),
            "embedding_score": _safe_float(candidate.get('embedding_score')),
            "text_score": _safe_float(candidate.get('text_score')),
            "combined_score": _safe_float(candidate.get('combined_score')),
            "text_matches": candidate.get('text_matches') if isinstance(candidate.get('text_matches'), list) else []
        })

    fallback = sorted(safe_candidates, key=lambda item: item["combined_score"], reverse=True)
    judge_context = None
    if not safe_candidates:
        return jsonify({"error": "no valid candidates supplied"}), 400

    try:
        from azure_openai_chat import get_azure_chat
        from src.utils.api_settings import resolve_api_settings

        client_config = None
        if api_settings_payload:
            client_config = resolve_api_settings(api_settings_payload, require_chat=True).get('chat')
        azure_chat = get_azure_chat()
        client, deployment = azure_chat._get_client(client_config)

        prompt = (
            "You are reranking Pokemon TCG card identification candidates. "
            "Use structured extracted metadata first when it clearly matches card name, HP, type icons, set, number, rarity, attacks, attack energy costs, weakness, resistance, or retreat cost. "
            "Use embedding_score as visual evidence. Return only JSON with keys: ranked_ids, reasoning_by_id. "
            "ranked_ids must contain candidate ids from best to worst. reasoning_by_id values must be short.\n\n"
            f"Extracted text from camera crop:\n{extracted_text or '[none]'}\n\n"
            f"Extracted structured metadata:\n{json.dumps(extracted_metadata, ensure_ascii=True)}\n\n"
            f"Candidates:\n{json.dumps(safe_candidates, ensure_ascii=True)}"
        )
        judge_context = {
            "system": "Return strict JSON only. Do not invent candidate ids.",
            "user": prompt
        }
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "Return strict JSON only. Do not invent candidate ids."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=700
        )
        content = response.choices[0].message.content or "{}"
        judged = json.loads(content)
        ranked_ids = [str(card_id) for card_id in judged.get('ranked_ids', [])]
        reasoning = judged.get('reasoning_by_id') if isinstance(judged.get('reasoning_by_id'), dict) else {}
        by_id = {candidate["id"]: candidate for candidate in safe_candidates}
        ranked = []
        seen = set()
        for card_id in ranked_ids:
            if card_id in by_id and card_id not in seen:
                item = {**by_id[card_id], "judge_reason": str(reasoning.get(card_id, '')).strip()}
                ranked.append(item)
                seen.add(card_id)
        for item in fallback:
            if item["id"] not in seen:
                ranked.append({**item, "judge_reason": "Fallback order from deterministic combined score."})

        return jsonify({"ranked": ranked, "judge_used": True, "judge_context": judge_context})
    except Exception as exc:
        logger.warning("LLM rerank unavailable, returning deterministic fallback: %s", exc)
        return jsonify({
            "ranked": [{**item, "judge_reason": "LLM judge unavailable; deterministic fallback."} for item in fallback],
            "judge_used": False,
            "warning": str(exc),
            "judge_context": judge_context or {
                "system": "Return strict JSON only. Do not invent candidate ids.",
                "user": (
                    "You are reranking Pokemon TCG card identification candidates. "
                    f"Extracted text from camera crop:\n{extracted_text or '[none]'}\n\n"
                    f"Extracted structured metadata:\n{json.dumps(extracted_metadata, ensure_ascii=True)}\n\n"
                    f"Candidates:\n{json.dumps(safe_candidates, ensure_ascii=True)}"
                )
            }
        })


def _load_data_url_image(image_data_url):
    match = re.match(r'^data:image/(?:jpeg|jpg|png|webp);base64,(.+)$', image_data_url, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("image_data_url must be a base64 image data URL")

    try:
        image_bytes = base64.b64decode(match.group(1), validate=True)
    except binascii.Error as exc:
        raise ValueError("image_data_url contains invalid base64 data") from exc

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("image_data_url is too large")

    return _load_image_bytes(image_bytes)


def _load_image_bytes(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    return ImageOps.exif_transpose(image).convert('RGB')


def _candidate_image_url(candidate):
    images = candidate.get('images') or {}
    image_url = (
        images.get('large') or
        images.get('small') or
        candidate.get('imageLarge') or
        candidate.get('imageSmall') or
        candidate.get('image') or
        candidate.get('imageUrl')
    )
    if not image_url:
        return None

    parsed = urlparse(image_url)
    if not _is_allowed_image_url(image_url, parsed=parsed):
        return None
    return image_url


def _is_allowed_image_url(image_url, parsed=None):
    if not image_url:
        return False
    parsed = parsed or urlparse(image_url)
    hostname = (parsed.hostname or '').lower()
    host_allowed = any(hostname == allowed_host or hostname.endswith(f'.{allowed_host}') for allowed_host in ALLOWED_IMAGE_HOSTS)
    return parsed.scheme == 'https' and host_allowed


def _get_remote_image_features(image_url):
    cached = _FEATURE_CACHE.get(image_url)
    if cached:
        return cached

    response = requests.get(image_url, timeout=IMAGE_TIMEOUT_SECONDS)
    response.raise_for_status()
    if len(response.content) > MAX_IMAGE_BYTES:
        raise ValueError("candidate image is too large")

    features = _build_image_features(_load_image_bytes(response.content))
    if len(_FEATURE_CACHE) > 200:
        _FEATURE_CACHE.clear()
    _FEATURE_CACHE[image_url] = features
    return features


def _crop_to_card_aspect(image):
    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    current_ratio = width / height
    if current_ratio > CARD_ASPECT_RATIO:
        crop_width = int(height * CARD_ASPECT_RATIO)
        left = max(0, (width - crop_width) // 2)
        return image.crop((left, 0, left + crop_width, height))

    crop_height = int(width / CARD_ASPECT_RATIO)
    top = max(0, (height - crop_height) // 2)
    return image.crop((0, top, width, top + crop_height))


def _build_image_features(image):
    fitted = ImageOps.fit(image, (96, 134), method=Image.Resampling.LANCZOS)
    grayscale = ImageOps.grayscale(fitted)
    return {
        "average_hash": _average_hash(grayscale),
        "difference_hash": _difference_hash(grayscale),
        "edge_hash": _average_hash(grayscale.filter(ImageFilter.FIND_EDGES)),
        "color_signature": _color_signature(fitted)
    }


def _average_hash(grayscale_image, hash_size=16):
    small = grayscale_image.resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    average = sum(pixels) / len(pixels)
    return tuple(pixel >= average for pixel in pixels)


def _difference_hash(grayscale_image, hash_size=16):
    small = grayscale_image.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = []
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            bits.append(pixels[offset + col] > pixels[offset + col + 1])
    return tuple(bits)


def _color_signature(image):
    small = image.resize((8, 10), Image.Resampling.LANCZOS)
    return tuple(tuple(channel / 255 for channel in pixel) for pixel in small.getdata())


def _compare_features(source, candidate):
    average_score = _bit_similarity(source["average_hash"], candidate["average_hash"])
    difference_score = _bit_similarity(source["difference_hash"], candidate["difference_hash"])
    edge_score = _bit_similarity(source["edge_hash"], candidate["edge_hash"])
    color_score = _color_similarity(source["color_signature"], candidate["color_signature"])
    visual_score = (
        average_score * 0.28 +
        difference_score * 0.36 +
        edge_score * 0.18 +
        color_score * 0.18
    ) * 100
    return visual_score, {
        "hash_score": round(((average_score + difference_score) / 2) * 100, 2),
        "edge_score": round(edge_score * 100, 2),
        "color_score": round(color_score * 100, 2)
    }


def _bit_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0
    distance = sum(1 for left_bit, right_bit in zip(left, right) if left_bit != right_bit)
    return 1 - (distance / len(left))


def _color_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0
    total_distance = 0
    for left_pixel, right_pixel in zip(left, right):
        total_distance += sum(abs(left_channel - right_channel) for left_channel, right_channel in zip(left_pixel, right_pixel)) / 3
    return max(0, 1 - (total_distance / len(left)))


def _safe_float(value):
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0