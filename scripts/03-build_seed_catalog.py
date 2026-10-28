#!/usr/bin/env python3
"""Build a seed-only SQLite catalog. Runtime data is changed only by script 07."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.seed_pipeline import DEFAULT_SEED_ROOT, build_seed_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    parser.add_argument("--pokeapi-dir", type=Path, default=PROJECT_ROOT / "seeds" / "pokeapi")
    parser.add_argument("--tcg-dir", type=Path, default=PROJECT_ROOT / "seeds" / "tcg")
    parser.add_argument("--no-network", action="store_true", help="Require complete raw seeds, including every form")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = build_seed_catalog(
        args.seed_root, args.pokeapi_dir, args.tcg_dir, allow_network=not args.no_network, resume=args.resume,
    )
    print(f"Seed catalog ready: {result.species_count:,} species, {result.pokemon_count:,} forms, "
          f"{result.card_count:,} cards, {result.set_count:,} sets. Live storage was not changed.")


if __name__ == "__main__":
    main()
