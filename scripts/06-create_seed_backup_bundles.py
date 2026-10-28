#!/usr/bin/env python3
"""Create one admin-compatible ZIP per selected category under seeds/backup-bundles."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.seed_pipeline import (
    DEFAULT_BUNDLE_DIR, DEFAULT_COMPONENTS, DEFAULT_SEED_ROOT, SEED_COMPONENTS, create_seed_bundles,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--components", nargs="+", choices=SEED_COMPONENTS)
    parser.add_argument("--users-database", type=Path, help="Explicit existing accounts source; never inferred from live data")
    args = parser.parse_args()
    components = args.components or list(DEFAULT_COMPONENTS)
    if args.users_database and "users_database" not in components:
        components.append("users_database")
    for path in create_seed_bundles(args.seed_root, args.output_dir, components, users_database=args.users_database):
        print(path)


if __name__ == "__main__":
    main()
