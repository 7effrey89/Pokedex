#!/usr/bin/env python3
"""Normalize cached Pokemon TCG API responses.

This utility converts legacy cache files (produced by the old CacheService
mock) into the same structure written by `scripts/download_tcg_cache.py`.
It can:
  * rewrite the JSON payload so `response.data` holds the cards list
  * ensure `endpoint`, `params`, `cache_key`, and `cached_at` fields match
    the live cache schema
  * rename cache files to the canonical `tcg-<dex>-<name>-<timestamp>.json`
    pattern so future download runs can resume cleanly

Typical usage:
    python scripts/normalize_tcg_cache.py                 # normalize entire cache
    python scripts/normalize_tcg_cache.py tcg-cache/foo.json other.json
    python scripts/normalize_tcg_cache.py --dry-run       # preview only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_ENDPOINT = "https://api.pokemontcg.io/v2/cards"
PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_DIR / "tcg-cache"
DEFAULT_POKEMON_LIST = PROJECT_DIR / "data" / "pokemon_list.json"
FILENAME_RE = re.compile(r"^tcg-(\d{3})-([a-z0-9-]+)-(\d{12})\.json$", re.IGNORECASE)
NAME_IN_QUERY_RE = re.compile(r"name:([a-z0-9-]+)", re.IGNORECASE)


@dataclass
class NormalizeResult:
    path: Path
    new_path: Path
    normalized: bool
    renamed: bool
    skipped: bool
    reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize cached Pokemon TCG API responses",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific cache files or directories to process (defaults to entire cache dir)",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(DEFAULT_CACHE_DIR),
        help="Directory that stores cache files when no explicit targets are given",
    )
    parser.add_argument(
        "--pokemon-list",
        default=str(DEFAULT_POKEMON_LIST),
        help="Path to pokemon_list.json (used for dex numbers when renaming)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without touching the filesystem",
    )
    parser.add_argument(
        "--no-rename",
        dest="rename",
        action="store_false",
        help="Normalize JSON content only (keep original filenames)",
    )
    parser.set_defaults(rename=True)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print details for every processed file",
    )
    return parser.parse_args()


def load_pokedex_map(pokemon_list_path: Path) -> Dict[str, int]:
    if not pokemon_list_path.exists():
        return {}
    try:
        with pokemon_list_path.open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
    except json.JSONDecodeError:
        return {}
    mapping = {}
    for entry in entries:
        name = str(entry.get("name", "")).strip().lower()
        number = entry.get("number")
        if not name or number is None:
            continue
        mapping[name] = int(number)
    return mapping


def iter_target_files(paths: List[str], fallback_dir: Path) -> Iterable[Path]:
    if not paths:
        paths = [str(fallback_dir)]
    seen = set()
    for raw in paths:
        path = Path(raw).resolve()
        if path in seen:
            continue
        seen.add(path)
        if path.is_dir():
            for json_file in sorted(path.glob("*.json")):
                yield json_file
        elif path.is_file():
            yield path
        else:
            print(f"⚠️  Skipping unknown path: {path}")


def extract_name(data: dict, path: Path) -> Optional[str]:
    params = data.get("params")
    if isinstance(params, dict):
        name = params.get("pokemon_name")
        if name:
            return slugify(name)
        query = params.get("q")
        if isinstance(query, str):
            match = NAME_IN_QUERY_RE.search(query)
            if match:
                return slugify(match.group(1))
    match = FILENAME_RE.match(path.name.lower())
    if match:
        return slugify(match.group(2))
    # Last resort: try to pull slug from filename pieces
    pieces = path.stem.lower().split("-")
    if len(pieces) >= 3:
        return slugify(pieces[2])
    return None


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "", name.lower())
    return slug or name.lower()


def extract_dex_number(name: str, path: Path, pokedex_map: Dict[str, int]) -> Optional[int]:
    match = FILENAME_RE.match(path.name.lower())
    if match:
        return int(match.group(1))
    return pokedex_map.get(name)


def ensure_response_payload(response: dict) -> Tuple[List[dict], int, int, int, int]:
    response = response or {}
    cards = response.get("data")
    if cards is None:
        cards = response.get("cards", [])
    if not isinstance(cards, list):
        cards = []

    def to_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    count = to_int(response.get("count"), len(cards))
    total = to_int(response.get("totalCount"), len(cards))
    page = to_int(response.get("page"), 1)
    page_size = to_int(response.get("pageSize"), 250)
    return cards, page, page_size, count, total


def build_cache_key(endpoint: str, params: dict) -> str:
    normalized = {k: v for k, v in params.items() if v is not None}
    key_data = f"{endpoint}:{json.dumps(normalized, sort_keys=True)}"
    return hashlib.md5(key_data.encode()).hexdigest()


def normalize_file(
    path: Path,
    rename: bool,
    dry_run: bool,
    pokedex_map: Dict[str, int],
    verbose: bool,
) -> NormalizeResult:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        reason = f"Invalid JSON: {exc}"
        if verbose:
            print(f"✗ {path.name}: {reason}")
        return NormalizeResult(path, path, False, False, True, reason)

    pokemon_name = extract_name(data, path)
    if not pokemon_name:
        reason = "Could not determine Pokémon name"
        if verbose:
            print(f"✗ {path.name}: {reason}")
        return NormalizeResult(path, path, False, False, True, reason)

    params = data.get("params") if isinstance(data.get("params"), dict) else {}
    if "q" in params and isinstance(params["q"], str):
        query_value = params["q"]
    else:
        query_value = f"name:{pokemon_name}"
    normalized_params = {"q": query_value}

    endpoint = data.get("endpoint") or DEFAULT_ENDPOINT
    if endpoint != DEFAULT_ENDPOINT:
        endpoint = DEFAULT_ENDPOINT

    cached_at = data.get("cached_at")
    try:
        cached_at = float(cached_at)
    except (TypeError, ValueError):
        cached_at = path.stat().st_mtime

    cards, page, page_size, count, total = ensure_response_payload(data.get("response", {}))

    normalized_payload = {
        "endpoint": endpoint,
        "params": normalized_params,
        "cache_key": build_cache_key(endpoint, normalized_params),
        "cached_at": cached_at,
        "response": {
            "data": cards,
            "page": page,
            "pageSize": page_size,
            "count": count if count else len(cards),
            "totalCount": total if total else len(cards),
        },
    }

    normalized = normalized_payload != data
    if normalized and not dry_run:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(normalized_payload, handle, indent=2, ensure_ascii=False)
    if normalized and verbose:
        action = "Would normalize" if dry_run else "✓ Normalized"
        print(f"{action} {path.name}")

    new_path = path
    renamed = False
    if rename:
        dex_number = extract_dex_number(pokemon_name, path, pokedex_map)
        if dex_number is not None:
            timestamp_str = datetime.fromtimestamp(cached_at).strftime("%Y%m%d%H%M")
            candidate = f"tcg-{dex_number:03d}-{pokemon_name}-{timestamp_str}.json"
            candidate_path = path.with_name(candidate)
            if candidate_path != path:
                if candidate_path.exists() and candidate_path != path:
                    if verbose:
                        print(f"⚠️  Target filename already exists: {candidate_path.name}")
                else:
                    renamed = True
                    if dry_run:
                        if verbose:
                            print(f"Would rename {path.name} -> {candidate}")
                    else:
                        path.rename(candidate_path)
                        new_path = candidate_path
                        if verbose:
                            print(f"↪ Renamed to {candidate}")
        elif verbose:
            print(f"⚠️  Skipping rename for {path.name} (no dex number)")

    return NormalizeResult(path, new_path, normalized, renamed, False)


def main() -> None:
    args = parse_args()
    pokedex_map = load_pokedex_map(Path(args.pokemon_list))
    stats = {
        "processed": 0,
        "normalized": 0,
        "renamed": 0,
        "skipped": 0,
    }
    for file_path in iter_target_files(args.targets, Path(args.cache_dir)):
        stats["processed"] += 1
        result = normalize_file(
            file_path,
            rename=args.rename,
            dry_run=args.dry_run,
            pokedex_map=pokedex_map,
            verbose=args.verbose or args.dry_run,
        )
        if result.skipped:
            stats["skipped"] += 1
        if result.normalized:
            stats["normalized"] += 1
        if result.renamed:
            stats["renamed"] += 1
    print("\nDone.")
    print(
        f"Processed {stats['processed']} file(s) — "
        f"normalized: {stats['normalized']}, renamed: {stats['renamed']}, skipped: {stats['skipped']}"
    )
    if args.dry_run:
        print("(Dry run: no files were modified.)")


if __name__ == "__main__":
    main()
