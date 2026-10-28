#!/usr/bin/env python3
"""Build TCG image embeddings from downloaded seed assets, without network access."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.seed_pipeline import DEFAULT_SEED_ROOT, seed_paths
from src.services.seed_assets import asset_path, load_unique_cards, read_seed_manifest
from src.services.backup_assets import local_asset_path
from src.services.tcg_image_index import ENCODER_VERSION, VECTOR_SIZE, encode_card_image, validate_index


def build_embeddings(
    root: Path, source_dir: Path, *, parallel: int = 4, limit: int | None = None, allow_partial: bool = False,
) -> dict:
    paths = seed_paths(root)
    cards = load_unique_cards(source_dir)
    if limit is not None:
        cards = cards[:limit]
    images = {}
    by_id = {str(card["id"]): card for card in cards}
    for record in sorted(read_seed_manifest(paths), key=lambda row: row["asset_kind"] != "large"):
        card_id = str(record["owner_id"])
        if record["table"] != "card_asset" or card_id not in by_id:
            continue
        url = (by_id[card_id].get("images") or {}).get(record["asset_kind"])
        candidate = asset_path(paths, record)
        if record["source_url"] == url and local_asset_path(
            paths, "tcg_images", candidate.relative_to(paths.data_root).as_posix(), record["sha256"],
        ):
            images.setdefault(card_id, candidate)

    def encode(card):
        image_path = images.get(str(card["id"]))
        if image_path is None:
            return None
        try:
            with Image.open(image_path) as image:
                return encode_card_image(image)
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            print(f"Invalid seed image for {card['id']}: {exc}", file=sys.stderr)
            return None

    indexed, vectors, failures = [], [], []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        for card, vector in zip(cards, executor.map(encode, cards)):
            if vector is None:
                failures.append(str(card["id"]))
            else:
                indexed.append(card)
                vectors.append(vector)
    if failures and not allow_partial:
        raise ValueError(f"{len(failures):,} seed card images are missing or invalid; download them or use --allow-partial")
    if not vectors:
        raise ValueError("No valid seed card images were available to embed")
    paths.tcg_index.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="embeddings-", dir=paths.tcg_index.parent) as directory:
        staging = Path(directory)
        with (staging / "vectors.npy").open("wb") as handle:
            np.save(handle, np.stack(vectors).astype(np.float32), allow_pickle=False)
        manifest = {
            "encoder_version": ENCODER_VERSION, "vector_size": VECTOR_SIZE, "dtype": "float32",
            "normalized": True, "card_count": len(indexed), "skipped_count": len(failures),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_fingerprint": hashlib.sha256(json.dumps(cards, sort_keys=True).encode()).hexdigest(),
        }
        for name, value in (("cards.json", indexed), ("manifest.json", manifest), ("failures.json", failures)):
            (staging / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
        validate_index(staging)
        paths.tcg_index.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            os.replace(item, paths.tcg_index / item.name)
    return {"card_count": len(indexed), "skipped_count": len(failures), "directory": str(paths.tcg_index)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    parser.add_argument("--source-dir", type=Path, default=PROJECT_ROOT / "seeds" / "tcg")
    parser.add_argument("--parallel", type=int, default=4, choices=range(1, 11))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--allow-partial", action="store_true", help="Explicitly allow missing seed images to be omitted")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    print(build_embeddings(
        args.seed_root, args.source_dir, parallel=args.parallel, limit=args.limit, allow_partial=args.allow_partial,
    ))


if __name__ == "__main__":
    main()
