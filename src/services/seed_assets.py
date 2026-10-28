"""Download raw-seed media and track portable registrations without SQLite."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
from pathlib import Path

from src.config.paths import StoragePaths
from src.services.asset_manager import AssetJob, AssetManager, COMPONENTS, POKEMON_SPRITE_STYLES
from src.services.backup_assets import ASSET_TABLES, local_asset_path, validate_asset_records

logger = logging.getLogger(__name__)
MANIFEST_VERSION = 1


def manifest_path(paths: StoragePaths) -> Path:
    return paths.data_root / "asset-manifest.json"


def asset_path(paths: StoragePaths, record: dict) -> Path:
    component = record["component"]
    relative = Path(record["path"])
    if (component not in ASSET_TABLES or relative.is_absolute() or relative.drive
            or ".." in relative.parts or not relative.parts or relative.parts[0] != component):
        raise ValueError(f"Invalid seed asset path: {record['path']}")
    directory = paths.asset_directories()[component].resolve()
    result = (directory / relative.relative_to(component)).resolve()
    if not result.is_relative_to(directory):
        raise ValueError(f"Seed asset resolves outside its directory: {record['path']}")
    return result


def read_seed_manifest(paths: StoragePaths) -> list[dict]:
    path = manifest_path(paths)
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError(f"Unsupported seed asset manifest: {path}")
    records = payload.get("asset_records")
    if not isinstance(records, list):
        raise ValueError(f"Invalid seed asset registrations: {path}")
    seen = set()
    for record in records:
        required = {"component", "table", "owner_id", "asset_kind", "source_url", "path", "sha256", "media_type"}
        if not isinstance(record, dict) or not required <= record.keys():
            raise ValueError(f"Incomplete seed asset registration: {path}")
        asset_path(paths, record)
        key = _identity(record)
        if key in seen:
            raise ValueError(f"Duplicate seed asset registration: {key}")
        seen.add(key)
    files = [{"path": row["path"], "component": row["component"], "sha256": row["sha256"]} for row in records]
    validate_asset_records({"files": files, "asset_records": records}, set(ASSET_TABLES))
    return records


def save_seed_manifest(paths: StoragePaths, records: list[dict]) -> None:
    path = manifest_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps({
            "manifest_version": MANIFEST_VERSION, "asset_records": records,
        }, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _identity(record: dict) -> tuple:
    return record["table"], str(record["owner_id"]), record["asset_kind"]


def _response(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid raw seed: {path}")
    response = payload.get("response", payload)
    if not isinstance(response, dict):
        raise ValueError(f"Invalid raw seed response: {path}")
    return response


def load_tcg_records(source_dir: Path) -> tuple[list[dict], list[dict]]:
    cards, sets = {}, {}
    for path in sorted(source_dir.glob("*.json")):
        response = _response(path)
        for item in response.get("data") or response.get("cards") or []:
            if not isinstance(item, dict) or not item.get("id"):
                raise ValueError(f"Invalid TCG seed record: {path}")
            if isinstance(item.get("set"), dict) or "supertype" in item or "number" in item:
                cards.setdefault(str(item["id"]), item)
                if isinstance(item.get("set"), dict) and item["set"].get("id"):
                    sets.setdefault(str(item["set"]["id"]), item["set"])
            elif "series" in item or "printedTotal" in item:
                sets.setdefault(str(item["id"]), item)
            else:
                raise ValueError(f"TCG record is neither a card nor a set: {path}")
    if not cards and not sets:
        raise ValueError(f"No TCG records found in {source_dir}")
    return [cards[key] for key in sorted(cards)], [sets[key] for key in sorted(sets)]


def load_unique_cards(source_dir: Path) -> list[dict]:
    cards, _ = load_tcg_records(source_dir)
    if not cards:
        raise ValueError(f"No TCG cards found in {source_dir}")
    return cards


def _source(component, table, owner, kind, url, media="image") -> dict:
    return {"component": component, "table": table, "owner_id": owner,
            "asset_kind": kind, "source_url": url, "media": media}


def seed_asset_sources(pokeapi: Path, tcg: Path, components: list[str]) -> list[dict]:
    sources = []
    if set(components) & {"pokemon_images", "pokemon_cries"}:
        files = sorted(pokeapi.glob("pokeapi-[0-9]*.json"))
        if not files:
            raise ValueError(f"No raw Pokemon seeds found in {pokeapi}")
        for path in files:
            pokemon = _response(path)
            if not isinstance(pokemon.get("id"), int):
                raise ValueError(f"Pokemon seed has no numeric ID: {path}")
            owner = pokemon["id"]
            sprites = pokemon.get("sprites") or {}
            other = sprites.get("other") or {}
            if "pokemon_images" in components:
                for style, (kind, _, media_type) in POKEMON_SPRITE_STYLES.items():
                    block = "dream_world" if style == "dream-world" else style
                    url = (sprites.get("front_default") if style == "default"
                           else (other.get(block) or {}).get("front_default"))
                    if url:
                        sources.append(_source("pokemon_images", "pokemon_asset", owner, kind, url,
                                               "svg" if media_type == "image/svg+xml" else "image"))
            if "pokemon_cries" in components:
                for kind, url in (pokemon.get("cries") or {}).items():
                    if kind in {"latest", "legacy"} and url:
                        sources.append(_source("pokemon_cries", "pokemon_asset", owner, f"cry_{kind}", url, "audio"))
    if "tcg_images" in components:
        cards, sets = load_tcg_records(tcg)
        for card in cards:
            images = card.get("images") or {}
            kind = "large" if images.get("large") else "small"
            if images.get(kind):
                sources.append(_source("tcg_images", "card_asset", card["id"], kind, images[kind]))
        for item in sets:
            for kind in ("logo", "symbol"):
                url = (item.get("images") or {}).get(kind)
                if url:
                    sources.append(_source("tcg_images", "set_asset", item["id"], kind, url))
    order = {component: index for index, component in enumerate(components)}
    return sorted(sources, key=lambda row: (
        order[row["component"]], row["table"] == "set_asset",
        int(row["owner_id"]) if row["table"] == "pokemon_asset" else str(row["owner_id"]), row["asset_kind"],
    ))


def download_seed_media(paths: StoragePaths, pokeapi: Path, tcg: Path, components: list[str], limit: int = 0) -> dict:
    if not components or set(components) - set(COMPONENTS) or limit < 0:
        raise ValueError("Select valid seed media categories and a non-negative limit")
    sources = seed_asset_sources(pokeapi, tcg, list(dict.fromkeys(components)))
    records = {_identity(row): row for row in read_seed_manifest(paths)}
    pending = []
    job = AssetJob(components=components)
    for source in sources:
        old = records.get(_identity(source))
        if old and old["source_url"] == source["source_url"]:
            destination = asset_path(paths, old)
            if local_asset_path(paths, old["component"], destination.relative_to(paths.data_root).as_posix(), old["sha256"]):
                job.skipped += 1
                continue
        pending.append(source)
    pending = pending[:limit] if limit else pending
    job.total = len(pending)
    manager = AssetManager(paths=paths)
    try:
        for source in pending:
            try:
                destination, metadata = manager.store_file(source)
            except (OSError, urllib.error.URLError, ValueError) as exc:
                logger.warning("Seed asset download failed for %s: %s", source["source_url"], exc)
                job.failed += 1
                job.errors.append(f"{source['owner_id']}: {exc}")
            else:
                sha256, media_type, width, height = metadata
                component = source["component"]
                records[_identity(source)] = {
                    **{key: source[key] for key in ("component", "table", "owner_id", "asset_kind", "source_url")},
                    "path": f"{component}/{destination.relative_to(paths.asset_directories()[component]).as_posix()}",
                    "sha256": sha256, "media_type": media_type, "width": width, "height": height,
                }
                job.downloaded += 1
            job.completed += 1
            if job.completed % 50 == 0:
                save_seed_manifest(paths, list(records.values()))
    finally:
        save_seed_manifest(paths, list(records.values()))
    if job.failed:
        raise RuntimeError(f"Seed asset download did not complete successfully: {job.failed} failed; {job.errors}")
    job.status, job.message = "completed", f"Downloaded {job.downloaded} seed assets"
    return job.to_dict()
