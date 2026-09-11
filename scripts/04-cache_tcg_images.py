#!/usr/bin/env python3
"""Cache official TCG card images and build the full-catalog NumPy index.

The script reads card records already downloaded by pipeline step 01, removes
duplicates by card ID, resumes image downloads, and writes an index consumed by
POST /api/tcg/numpy-image-match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests
from PIL import Image, UnidentifiedImageError

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.services.tcg_image_index import ENCODER_VERSION, VECTOR_SIZE, encode_card_image  # noqa: E402

DEFAULT_SOURCE_DIR = PROJECT_DIR / "tcg-cache"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "tcg-image-cache"
USER_AGENT = "Pokedex-TCG-Image-Indexer/1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache TCG images and build an exact NumPy cosine index",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Directory containing TCG card JSON files")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Root directory for cached images and index files")
    parser.add_argument("--limit", type=int, help="Process only the first N unique cards for testing")
    parser.add_argument("--parallel", type=int, default=4, choices=range(1, 11), metavar="1-10", help="Concurrent image downloads")
    parser.add_argument("--max-retries", type=int, default=4, help="Download attempts per image")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--refresh", action="store_true", help="Redownload images that are already valid")
    parser.add_argument("--index-only", action="store_true", help="Skip downloads and index existing cached images")
    parser.add_argument("--download-only", action="store_true", help="Cache images without rebuilding the NumPy index")
    return parser.parse_args()


def extract_cards(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    response = payload.get("response", payload)
    if not isinstance(response, dict):
        return []
    cards = response.get("data") or response.get("cards") or []
    return [card for card in cards if isinstance(card, dict) and card.get("id")]


def load_unique_cards(source_dir: Path) -> list[dict]:
    cards_by_id: dict[str, dict] = {}
    invalid_files = 0
    for path in sorted(source_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                cards = extract_cards(json.load(handle))
        except (OSError, json.JSONDecodeError):
            invalid_files += 1
            continue
        for card in cards:
            cards_by_id.setdefault(str(card["id"]), card)
    print(f"Loaded {len(cards_by_id):,} unique cards from {source_dir} ({invalid_files} invalid files skipped).")
    return sorted(cards_by_id.values(), key=lambda card: str(card["id"]))


def card_image_url(card: dict) -> str | None:
    images = card.get("images") if isinstance(card.get("images"), dict) else {}
    return images.get("large") or images.get("small") or card.get("imageLarge") or card.get("imageSmall") or card.get("image")


def image_path(images_dir: Path, card_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", card_id).strip("-")
    suffix = hashlib.sha1(card_id.encode("utf-8")).hexdigest()[:8]
    return images_dir / f"{safe_id}-{suffix}.img"


def validate_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, UnidentifiedImageError):
        return False


def download_image(card: dict, images_dir: Path, refresh: bool, max_retries: int, timeout: int) -> tuple[str, str]:
    card_id = str(card["id"])
    url = card_image_url(card)
    if not url:
        return card_id, "missing-url"
    destination = image_path(images_dir, card_id)
    if not refresh and destination.exists() and validate_image(destination):
        return card_id, "cached"

    for attempt in range(1, max_retries + 1):
        temporary = destination.with_suffix(".tmp")
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
            temporary.write_bytes(response.content)
            if not validate_image(temporary):
                raise ValueError("response was not a valid image")
            temporary.replace(destination)
            return card_id, "downloaded"
        except (OSError, ValueError, requests.RequestException):
            temporary.unlink(missing_ok=True)
            if attempt < max_retries:
                time.sleep(min(2 ** (attempt - 1), 8))
    return card_id, "failed"


def cache_images(cards: list[dict], images_dir: Path, args: argparse.Namespace) -> dict[str, int]:
    counts = {"downloaded": 0, "cached": 0, "failed": 0, "missing-url": 0}
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {
            executor.submit(download_image, card, images_dir, args.refresh, args.max_retries, args.timeout): card
            for card in cards
        }
        for position, future in enumerate(as_completed(futures), start=1):
            card_id, status = future.result()
            counts[status] += 1
            if status in {"failed", "missing-url"}:
                print(f"  {status}: {card_id}")
            if position % 250 == 0 or position == len(futures):
                print(f"Images: {position:,}/{len(futures):,} processed")
    return counts


def source_fingerprint(cards: list[dict]) -> str:
    digest = hashlib.sha256()
    for card in cards:
        digest.update(str(card.get("id", "")).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(card_image_url(card) or "").encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
    temporary.replace(path)


def encode_cached_card(card: dict, images_dir: Path) -> tuple[dict, np.ndarray | None]:
    path = image_path(images_dir, str(card["id"]))
    if not path.exists():
        return card, None
    try:
        with Image.open(path) as image:
            return card, encode_card_image(image)
    except (OSError, UnidentifiedImageError, ValueError):
        return card, None


def build_index(cards: list[dict], images_dir: Path, index_dir: Path, parallel: int) -> tuple[int, list[str]]:
    indexed_cards = []
    vectors = []
    failures = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        encoded_cards = executor.map(lambda card: encode_cached_card(card, images_dir), cards)
        for position, (card, vector) in enumerate(encoded_cards, start=1):
            if vector is not None:
                vectors.append(vector)
                indexed_cards.append(card)
            else:
                failures.append(str(card["id"]))
            if position % 500 == 0 or position == len(cards):
                print(f"Index: {position:,}/{len(cards):,} inspected")

    if not vectors:
        raise RuntimeError("No valid cached images were available to index")

    matrix = np.stack(vectors).astype(np.float32)
    temporary_vectors = index_dir / "vectors.npy.tmp"
    with temporary_vectors.open("wb") as handle:
        np.save(handle, matrix, allow_pickle=False)
    temporary_vectors.replace(index_dir / "vectors.npy")
    write_json_atomic(index_dir / "cards.json", indexed_cards)
    write_json_atomic(index_dir / "manifest.json", {
        "encoder_version": ENCODER_VERSION,
        "vector_size": VECTOR_SIZE,
        "dtype": "float32",
        "normalized": True,
        "card_count": len(indexed_cards),
        "source_fingerprint": source_fingerprint(cards),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    write_json_atomic(index_dir / "failures.json", failures)
    return len(indexed_cards), failures


def main() -> None:
    args = parse_args()
    if args.index_only and args.download_only:
        raise SystemExit("--index-only and --download-only cannot be combined")

    source_dir = Path(args.source_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    images_dir = output_dir / "images"
    index_dir = output_dir / "index"
    if not source_dir.exists():
        raise SystemExit(f"Source directory does not exist: {source_dir}")
    images_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    cards = load_unique_cards(source_dir)
    if args.limit is not None:
        cards = cards[:max(0, args.limit)]
    if not cards:
        raise SystemExit("No card records with IDs were found")

    if not args.index_only:
        counts = cache_images(cards, images_dir, args)
        print("Image cache: " + ", ".join(f"{key}={value:,}" for key, value in counts.items()))
    if not args.download_only:
        indexed_count, failures = build_index(cards, images_dir, index_dir, args.parallel)
        print(f"Index complete: {indexed_count:,} cards, {len(failures):,} skipped.")
        print(f"Artifacts: {index_dir}")


if __name__ == "__main__":
    main()