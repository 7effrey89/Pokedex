#!/usr/bin/env python3
"""Zip the seed workspace for reproducible, offline preparation.

The archive preserves paths under seeds/: pokeapi/, tcg/, prepared/ when
present, and root-level seed files such as pokemon_list.json. Extract a
.snapshot.tar.gz at the seeds/ root to repopulate an empty seed directory.
Generated backup-bundles/ and staged user accounts are excluded by default.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_storage_paths  # noqa: E402

SNAPSHOT_VERSION = 2
EXCLUDED_DIRECTORIES = {"backup-bundles"}
USERS_DATABASE = Path("prepared/data/users.sqlite3")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_seed_files(seed_root: Path, output_root: Path, include_users: bool) -> list[Path]:
    seed_root = seed_root.absolute()
    resolved_seed_root = seed_root.resolve()
    output_root = output_root.resolve()
    files = []
    for item in sorted(seed_root.rglob("*")):
        if not item.is_file():
            continue
        if item.is_symlink():
            raise ValueError(f"Seed snapshot does not accept symbolic links: {item}")
        relative = item.relative_to(seed_root)
        if relative.parts[0] in EXCLUDED_DIRECTORIES:
            continue
        if not include_users and relative == USERS_DATABASE:
            continue
        resolved = item.resolve()
        if not resolved.is_relative_to(resolved_seed_root):
            raise ValueError(f"Seed file resolves outside the seed directory: {item}")
        if resolved == output_root or output_root in resolved.parents:
            continue
        files.append(item)
    return files


def create_snapshot(seed_root: Path, output_root: Path, *, compress: bool = False,
                    include_users: bool = False) -> Path:
    seed_root = seed_root.absolute()
    if not seed_root.is_dir():
        raise ValueError(f"Seed directory does not exist: {seed_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    files = collect_seed_files(seed_root, output_root, include_users)
    if not files:
        raise ValueError(f"No seed files found under {seed_root}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest = {
        "snapshot_version": SNAPSHOT_VERSION,
        "snapshot_id": stamp,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": "seeds",
        "includes_users_database": include_users and any(
            item.relative_to(seed_root) == USERS_DATABASE for item in files
        ),
        "files": [],
    }

    for index, item in enumerate(files, start=1):
        relative = item.relative_to(seed_root).as_posix()
        manifest["files"].append({
            "path": relative,
            "size_bytes": item.stat().st_size,
            "sha256": file_hash(item),
        })
        if index % 250 == 0 or index == len(files):
            print(f"Indexed {index:,}/{len(files):,} seed files", flush=True)

    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    if compress:
        target = output_root / f"{stamp}.snapshot.tar.gz"
        print(f"Writing {target}", flush=True)
        with tarfile.open(target, "w:gz") as archive:
            for item in files:
                archive.add(item, arcname=item.relative_to(seed_root).as_posix())
            info = tarfile.TarInfo("snapshot-manifest.json")
            info.size = len(manifest_bytes)
            archive.addfile(info, io.BytesIO(manifest_bytes))
    else:
        target = output_root / stamp
        target.mkdir(parents=True, exist_ok=False)
        print(f"Writing {target}", flush=True)
        for item in files:
            destination = target / item.relative_to(seed_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
        (target / "snapshot-manifest.json").write_bytes(manifest_bytes)

    total_bytes = sum(entry["size_bytes"] for entry in manifest["files"])
    print(
        f"Snapshot {stamp} complete: {len(files):,} seed files, "
        f"{total_bytes / 1024 / 1024:.1f} MB -> {target}",
        flush=True,
    )
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--seed-dir", type=Path, default=PROJECT_ROOT / "seeds",
                        help="Seed workspace to archive")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Snapshot directory (defaults to the configured data root)")
    parser.add_argument("--compress", action="store_true",
                        help="Write a single .tar.gz bundle instead of a directory")
    parser.add_argument("--include-users", action="store_true",
                        help="Include the staged user accounts database (contains private data)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = args.output_dir or get_storage_paths().snapshots
    create_snapshot(args.seed_dir, output_root, compress=args.compress, include_users=args.include_users)


if __name__ == "__main__":
    main()
