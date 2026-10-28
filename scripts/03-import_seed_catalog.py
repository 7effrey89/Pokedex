#!/usr/bin/env python3
"""Validate raw seed metadata, then optionally SQL-merge it into the runtime catalog."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_storage_paths
from src.config.paths import StoragePaths
from src.services.seed_pipeline import import_seed_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pokeapi-dir", type=Path, default=PROJECT_ROOT / "seeds" / "pokeapi")
    parser.add_argument("--tcg-dir", type=Path, default=PROJECT_ROOT / "seeds" / "tcg")
    parser.add_argument("--target-root", type=Path, default=get_storage_paths().data_root)
    parser.add_argument("--allow-network", action="store_true", help="Explicitly fetch metadata absent from raw seeds")
    parser.add_argument("--apply", action="store_true", help="Merge into the target; default only validates raw inputs")
    parser.add_argument("--server-stopped", action="store_true", help="Confirm the target server is stopped")
    args = parser.parse_args()
    if args.apply and not args.server_stopped:
        parser.error("Stop the target server and specify --server-stopped before applying a catalog import")
    result = import_seed_catalog(
        args.pokeapi_dir, args.tcg_dir, StoragePaths(args.target_root.resolve()),
        apply=args.apply, allow_network=args.allow_network,
    )
    print(result)
    print("Catalog merged. Restart the target server." if args.apply
          else "Validation only. No target database changed. Use --apply --server-stopped to import.")


if __name__ == "__main__":
    main()
