#!/usr/bin/env python3
"""Archive raw API responses as an immutable, versioned snapshot.

Snapshots are the reproducible input for catalog builds. Only verbatim upstream
responses are archived; derived caches are regenerable and deliberately skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_storage_paths  # noqa: E402

SNAPSHOT_VERSION = 1
RAW_SOURCES = {
    "pokeapi": PROJECT_ROOT / "seeds" / "pokeapi",
    "tcg": PROJECT_ROOT / "seeds" / "tcg",
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Snapshot directory (defaults to the configured data root)")
    parser.add_argument("--compress", action="store_true",
                        help="Write a single .tar.gz bundle instead of a directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = args.output_dir or get_storage_paths().snapshots
    output_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "snapshot_version": SNAPSHOT_VERSION,
        "snapshot_id": stamp,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": {},
        "files": [],
    }

    files: list[tuple[str, Path]] = []
    for source_kind, directory in RAW_SOURCES.items():
        if not directory.is_dir():
            print(f"Skipping missing raw source: {directory}", flush=True)
            continue
        found = sorted(item for item in directory.rglob("*.json") if item.is_file())
        manifest["sources"][source_kind] = {
            "directory": directory.relative_to(PROJECT_ROOT).as_posix(),
            "file_count": len(found),
        }
        print(f"Indexing {len(found):,} {source_kind} responses", flush=True)
        for index, item in enumerate(found, start=1):
            entry = f"{source_kind}/{item.relative_to(directory).as_posix()}"
            manifest["files"].append({
                "path": entry,
                "size_bytes": item.stat().st_size,
                "sha256": file_hash(item),
            })
            files.append((entry, item))
            if index % 250 == 0 or index == len(found):
                print(f"  {source_kind}: {index:,}/{len(found):,}", flush=True)

    if not files:
        raise SystemExit("No raw API responses found to archive")

    if args.compress:
        bundle = output_root / f"{stamp}.snapshot.tar.gz"
        print(f"Writing {bundle}", flush=True)
        with tarfile.open(bundle, "w:gz") as archive:
            for entry, item in files:
                archive.add(item, arcname=entry)
            manifest_path = output_root / f"{stamp}.manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            archive.add(manifest_path, arcname="snapshot-manifest.json")
            manifest_path.unlink()
        target = bundle
    else:
        target = output_root / stamp
        target.mkdir(parents=True, exist_ok=True)
        print(f"Writing {target}", flush=True)
        for entry, item in files:
            destination = target / entry
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item.read_bytes())
        (target / "snapshot-manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    total_bytes = sum(entry["size_bytes"] for entry in manifest["files"])
    print(
        f"Snapshot {stamp} complete: {len(manifest['files']):,} files, "
        f"{total_bytes / 1024 / 1024:.1f} MB raw -> {target}",
        flush=True,
    )


if __name__ == "__main__":
    main()
