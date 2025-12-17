#!/usr/bin/env python3
"""Normalize cached Pokemon TCG API responses (legacy + download-manager).

This utility converts any cached Pokemon TCG payload-whether it was produced
by the legacy CacheService mock, the direct download script, or the
download-manager formatter-into the canonical structure consumed by the live
`search_pokemon_cards` handler. It can:
  * rewrite JSON so the `response` block contains formatted `cards`
    (matching `PokemonTCGTools.format_cards_response`)
  * ensure `endpoint`, `params`, `cache_key`, and `cached_at` align with
    CacheService expectations
    * rename files to the deterministic `tcg-<dex>-<slug>.json` pattern and
        copy them into the main `cache/` directory by default (use --in-place to
        leave files where they are)

Typical usage:
    python scripts/normalize_tcg_cache.py                 # normalize entire cache
    python scripts/normalize_tcg_cache.py tcg-cache/foo.json other.json
    python scripts/normalize_tcg_cache.py --dry-run       # preview only
    python scripts/normalize_tcg_cache.py tcg-cache --dest-dir cache --verbose
    python scripts/normalize_tcg_cache.py --in-place      # skip copying into cache/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

CACHE_ENDPOINT = "search_pokemon_cards"
PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_DIR / "tcg-cache"
DEFAULT_POKEMON_LIST = PROJECT_DIR / "data" / "pokemon_list.json"
DEFAULT_DEST_DIR = PROJECT_DIR / "cache"
FILENAME_RE = re.compile(r"^tcg-(\d{3})-([a-z0-9-]+)(?:-(\d{12}))?\.json$", re.IGNORECASE)
NAME_IN_QUERY_RE = re.compile(r"name:([a-z0-9-]+)", re.IGNORECASE)

sys.path.insert(0, str(PROJECT_DIR))
from src.api import pokemon_tcg_api  # noqa: E402


tcg_formatter = pokemon_tcg_api.PokemonTCGTools()


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
        description="Normalize Pokemon TCG cache files to the live handler schema",
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
    parser.add_argument(
        "--dest-dir",
        default=str(DEFAULT_DEST_DIR),
        help="Directory to copy normalized files into (default: cache/)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Rewrite files where they currently live instead of copying into dest-dir",
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
        mapping[slugify(name)] = int(number)
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


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or value.lower()


def detect_pokemon_name(data: Dict[str, Any], path: Path) -> Optional[str]:
    params = data.get("params") if isinstance(data.get("params"), dict) else {}
    candidates = [
        params.get("pokemon_name"),
        params.get("name"),
        data.get("response", {}).get("search_query") if isinstance(data.get("response"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return slugify(candidate)
    query = params.get("q") if isinstance(params, dict) else None
    if isinstance(query, str):
        match = NAME_IN_QUERY_RE.search(query)
        if match:
            return slugify(match.group(1))
    match = FILENAME_RE.match(path.name.lower())
    if match:
        return slugify(match.group(2))
    pieces = path.stem.lower().split("-")
    if len(pieces) >= 3:
        return slugify(pieces[2])
    return None


def extract_dex_number(name: str, path: Path, pokedex_map: Dict[str, int]) -> Optional[int]:
    match = FILENAME_RE.match(path.name.lower())
    if match:
        return int(match.group(1))
    return pokedex_map.get(name)


def cast_hp(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_params(pokemon_name: str, original_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = {
        "pokemon_name": slugify(pokemon_name),
        "card_type": None,
        "hp_min": None,
        "hp_max": None,
        "rarity": None,
    }
    if not isinstance(original_params, dict):
        return normalized
    if isinstance(original_params.get("pokemon_name"), str):
        normalized["pokemon_name"] = slugify(original_params["pokemon_name"])
    for key in ("card_type", "rarity"):
        value = original_params.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()
    normalized["hp_min"] = cast_hp(original_params.get("hp_min"))
    normalized["hp_max"] = cast_hp(original_params.get("hp_max"))
    return normalized


def build_search_label(params: Dict[str, Any]) -> str:
    label = params.get("pokemon_name") or params.get("card_type") or params.get("rarity") or "filtered cards"
    if params.get("hp_min") is not None or params.get("hp_max") is not None:
        return f"{label} (HP filtered)"
    return label


def build_response_payload(raw_response: Any, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_response, dict):
        return None
    if isinstance(raw_response.get("cards"), list):
        cards = raw_response["cards"]
        total = (
            raw_response.get("total_count")
            or raw_response.get("totalCount")
            or raw_response.get("count")
            or len(cards)
        )
        search_query = raw_response.get("search_query") or build_search_label(params)
        return {
            "cards": cards,
            "total_count": total,
            "search_query": search_query,
        }
    cards = tcg_formatter.format_cards_response(raw_response)
    total = (
        raw_response.get("total_count")
        or raw_response.get("totalCount")
        or raw_response.get("count")
        or len(cards)
    )
    search_query = build_search_label(params)
    return {
        "cards": cards,
        "total_count": total,
        "search_query": search_query,
    }


def build_cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    normalized = {k: v for k, v in params.items() if v is not None}
    key_data = f"{endpoint}:{json.dumps(normalized, sort_keys=True)}"
    return hashlib.md5(key_data.encode()).hexdigest()


def normalize_file(
    path: Path,
    rename: bool,
    dry_run: bool,
    pokedex_map: Dict[str, int],
    verbose: bool,
    target_dir: Optional[Path],
) -> NormalizeResult:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        reason = f"Invalid JSON: {exc}"
        if verbose:
            print(f"✗ {path.name}: {reason}")
        return NormalizeResult(path, path, False, False, True, reason)

    pokemon_name = detect_pokemon_name(data, path)
    if not pokemon_name:
        reason = "Could not determine Pokemon name"
        if verbose:
            print(f"✗ {path.name}: {reason}")
        return NormalizeResult(path, path, False, False, True, reason)

    params = build_params(pokemon_name, data.get("params"))
    response_payload = build_response_payload(data.get("response", {}), params)
    if response_payload is None:
        reason = "Missing or invalid response payload"
        if verbose:
            print(f"✗ {path.name}: {reason}")
        return NormalizeResult(path, path, False, False, True, reason)

    cached_at = data.get("cached_at")
    try:
        cached_at = float(cached_at)
    except (TypeError, ValueError):
        cached_at = path.stat().st_mtime

    normalized_payload = {
        "endpoint": CACHE_ENDPOINT,
        "params": params,
        "cache_key": build_cache_key(CACHE_ENDPOINT, params),
        "cached_at": cached_at,
        "response": response_payload,
    }

    normalized = normalized_payload != data
    copy_mode = target_dir is not None

    if not copy_mode and normalized and not dry_run:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(normalized_payload, handle, indent=2, ensure_ascii=False)
    if not copy_mode and normalized and verbose:
        action = "Would normalize" if dry_run else "✓ Normalized"
        print(f"{action} {path.name}")

    output_dir = target_dir if target_dir else path.parent
    new_path = path
    renamed = False
    output_name = path.name
    if rename:
        dex_number = extract_dex_number(params["pokemon_name"], path, pokedex_map)
        if dex_number is None:
            if verbose:
                print(f"⚠️  Skipping rename for {path.name} (no dex number)")
        else:
            output_name = f"tcg-{dex_number:03d}-{params['pokemon_name']}.json"
            renamed = True
    output_path = output_dir / output_name

    if copy_mode:
        if dry_run:
            verb = "Would copy"
            print(f"{verb} normalized data to {output_path}")
        else:
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(normalized_payload, handle, indent=2, ensure_ascii=False)
            if verbose:
                print(f"↪ Copied normalized data to {output_path}")
        new_path = output_path
    else:
        if renamed and output_path != path:
            if dry_run:
                print(f"Would rename {path.name} -> {output_path}")
                new_path = output_path
            else:
                if output_path.exists():
                    output_path.unlink()
                path.rename(output_path)
                new_path = output_path
                if verbose:
                    print(f"↪ Renamed to {output_path}")

    return NormalizeResult(path, new_path, normalized, renamed, False)


def main() -> None:
    args = parse_args()
    pokedex_map = load_pokedex_map(Path(args.pokemon_list))
    dest_dir: Optional[Path] = None
    if not args.in_place:
        dest_value = args.dest_dir or str(DEFAULT_DEST_DIR)
        dest_dir = Path(dest_value).resolve()
    if dest_dir and not args.dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
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
            target_dir=dest_dir,
        )
        if result.skipped:
            stats["skipped"] += 1
        if result.normalized:
            stats["normalized"] += 1
        if result.renamed:
            stats["renamed"] += 1
    print("\nDone.")
    print(
        f"Processed {stats['processed']} file(s) - "
        f"normalized: {stats['normalized']}, renamed: {stats['renamed']}, skipped: {stats['skipped']}"
    )
    if args.dry_run:
        print("(Dry run: no files were modified.)")


if __name__ == "__main__":
    main()
