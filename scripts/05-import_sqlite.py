#!/usr/bin/env python3
"""Hydrate the normalized SQLite database from the raw JSON seed archives."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import DEFAULT_DATABASE_PATH  # noqa: E402
from src.db.importer import SqliteImporter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--pokeapi-dir", type=Path, default=PROJECT_ROOT / "seeds" / "pokeapi")
    parser.add_argument("--tcg-dir", type=Path, default=PROJECT_ROOT / "seeds" / "tcg")
    parser.add_argument("--asset-dir", type=Path, default=PROJECT_ROOT / "data" / "assets")
    parser.add_argument("--no-network", action="store_true", help="Fail rather than fetch missing forms or artwork")
    parser.add_argument("--skip-artwork", action="store_true", help="Build a development database without downloading artwork")
    parser.add_argument("--resume", action="store_true", help="Repair and validate an existing failed .building database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Starting SQLite hydration. Existing database remains active until validation passes.", flush=True)
    importer = SqliteImporter(
        PROJECT_ROOT,
        args.database,
        args.pokeapi_dir,
        args.tcg_dir,
        args.asset_dir,
        allow_network=not args.no_network,
        download_artwork=not args.skip_artwork,
        require_artwork=not args.skip_artwork,
        require_card_images=not args.skip_artwork,
        progress=lambda message: print(message, flush=True),
    )
    summary = importer.resume() if args.resume else importer.build()
    print(
        f"SQLite import complete: {summary.species_count:,} species, {summary.pokemon_count:,} forms, "
        f"{summary.card_count:,} cards, {summary.set_count:,} sets from {summary.imported_file_count:,} files.",
        flush=True,
    )


if __name__ == "__main__":
    main()