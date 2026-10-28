#!/usr/bin/env python3
"""Verify seed ZIPs, then optionally restore them with the admin panel's exact service."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import get_storage_paths
from src.config.paths import StoragePaths
from src.services.backup_service import BackupService, COMPONENT_LABELS
from src.services.seed_pipeline import DEFAULT_BUNDLE_DIR, DEFAULT_COMPONENTS, restore_seed_bundles, select_seed_bundles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundles", nargs="*", type=Path, help="Explicit ZIPs, including exported admin backups")
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--components", nargs="+", choices=COMPONENT_LABELS,
                        help="Select newest category ZIPs; accounts require explicit selection")
    parser.add_argument("--target-root", type=Path, default=get_storage_paths().data_root)
    parser.add_argument("--apply", action="store_true",
                        help="Merge catalog rows and install selected files; default is verification only")
    parser.add_argument("--server-stopped", action="store_true", help="Confirm the target Flask/Gunicorn server is stopped")
    args = parser.parse_args()
    if args.bundles and args.components:
        parser.error("Use explicit ZIP paths or --components, not both")
    if args.apply and not args.server_stopped:
        parser.error("Stop the target server and specify --server-stopped before applying a restore")
    bundles = args.bundles or select_seed_bundles(args.bundle_dir, args.components or list(DEFAULT_COMPONENTS))
    service = BackupService()
    for bundle in bundles:
        manifest = service.verify_backup(bundle)
        print(f"Verified {bundle.name}: {', '.join(COMPONENT_LABELS[key] for key in manifest['components'])}")
        if "catalog_database" in manifest["components"]:
            print("  Catalog: SQL merge, newer records win; existing settings and valid local assets are preserved.")
        if "users_database" in manifest["components"]:
            print("  Accounts: replaces the separate accounts database (not merged).")
    print(f"Target: {args.target_root.resolve()}")
    if not args.apply:
        print("Verification only. No target files changed. Use --apply --server-stopped to restore.")
        return
    for result in restore_seed_bundles(bundles, StoragePaths(args.target_root.resolve())):
        print(result)
    print("Restore complete. Restart the target server and refresh the browser.")


if __name__ == "__main__":
    main()
