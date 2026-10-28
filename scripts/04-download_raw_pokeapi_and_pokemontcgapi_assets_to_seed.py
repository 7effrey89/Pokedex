#!/usr/bin/env python3
"""Download media from raw API seeds and record an asset manifest, without SQLite."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.asset_manager import COMPONENTS
from src.services.seed_pipeline import DEFAULT_SEED_ROOT, download_seed_assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    parser.add_argument("--pokeapi-dir", type=Path)
    parser.add_argument("--tcg-dir", type=Path)
    parser.add_argument("--components", nargs="+", choices=COMPONENTS, default=list(COMPONENTS))
    parser.add_argument("--limit", type=int, default=0, help="Optional total asset limit for a trial run")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit cannot be negative")
    print(download_seed_assets(args.seed_root, args.components, args.limit,
                               pokeapi=args.pokeapi_dir, tcg=args.tcg_dir))


if __name__ == "__main__":
    main()
