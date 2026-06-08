"""Proxy PokeAPI requests through Flask with caching."""
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from flask import Blueprint, jsonify, request

from src.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)

POKEAPI_BASE_URL = os.environ.get("POKEMON_API_URL", "https://pokeapi.co/api/v2")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
POKEMON_LIST_PATH = PROJECT_ROOT / "data" / "pokemon_list.json"
CACHE_DIR = PROJECT_ROOT / "cache"
cache_service = get_cache_service()

pokeapi_bp = Blueprint("pokeapi", __name__, url_prefix="/api/pokemon")


@lru_cache(maxsize=1)
def _load_static_pokemon_list():
    with POKEMON_LIST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@pokeapi_bp.route("/list", methods=["GET"])
def get_pokemon_list():
    """Return the static pokemon index for grid rendering."""
    try:
        return jsonify(_load_static_pokemon_list())
    except FileNotFoundError:
        logger.error("Pokemon list file missing at %s", POKEMON_LIST_PATH)
        return jsonify({"error": "Pokemon list unavailable"}), 500
    except json.JSONDecodeError as exc:
        logger.error("Pokemon list file is invalid JSON: %s", exc)
        return jsonify({"error": "Pokemon list invalid"}), 500


_CACHE_FILE_RE = re.compile(r"^pokeapi-(\d+)-(.+)\.json$")
_SPECIES_CACHE_FILE_RE = re.compile(r"^pokeapi-species-(\d+)-(.+)\.json$")

# In-memory metadata cache (built lazily on first request)
_metadata_cache: Optional[Dict] = None
_metadata_cache_count: int = 0  # number of cache files when last built


def _build_metadata() -> Dict[str, dict]:
    """Scan pokeapi cache files and extract lightweight metadata.

    Reads the head of each file for abilities and the tail for
    types/height/weight to avoid full JSON parsing of multi-MB files.
    """
    metadata: Dict[str, dict] = {}
    if not CACHE_DIR.is_dir():
        return metadata

    for filename in os.listdir(CACHE_DIR):
        m = _CACHE_FILE_RE.match(filename)
        if not m:
            continue
        poke_id = m.group(1).lstrip("0") or "0"
        filepath = CACHE_DIR / filename
        try:
            file_size = filepath.stat().st_size
            with filepath.open("r", encoding="utf-8") as fh:
                # Read head for abilities + height (near top of file)
                head = fh.read(min(6000, file_size))

                # Read tail for types/height/weight (near end of file)
                if file_size > 3000:
                    fh.seek(max(0, file_size - 2500))
                    tail = fh.read()
                else:
                    tail = head

            # Extract abilities and height from head
            abilities = re.findall(
                r'"ability":\s*\{\s*"name":\s*"([^"]+)"', head
            )
            height_m = re.search(r'"height":\s*(\d+)', head)

            # Extract types via regex (faster than full JSON parse)
            types = re.findall(r'"type":\s*\{\s*"name":\s*"([^"]+)"', tail)

            # Extract weight from tail
            weight_m = re.search(r'"weight":\s*(\d+)', tail)

            metadata[poke_id] = {
                "name": m.group(2),
                "types": types,
                "abilities": abilities,
                "height": int(height_m.group(1)) if height_m else None,
                "weight": int(weight_m.group(1)) if weight_m else None,
            }
        except (OSError, ValueError):
            continue

    for filename in os.listdir(CACHE_DIR):
        m = _SPECIES_CACHE_FILE_RE.match(filename)
        if not m:
            continue
        poke_id = m.group(1).lstrip("0") or "0"
        filepath = CACHE_DIR / filename
        try:
            file_size = filepath.stat().st_size
            with filepath.open("rb") as fh:
                if file_size > 48000:
                    fh.seek(file_size - 48000)
                content = fh.read().decode("utf-8", errors="ignore")

            is_legendary_m = re.search(r'"is_legendary":\s*(true|false)', content)
            is_mythical_m = re.search(r'"is_mythical":\s*(true|false)', content)

            species_meta = metadata.setdefault(
                poke_id,
                {
                    "name": m.group(2),
                    "types": [],
                    "abilities": [],
                    "height": None,
                    "weight": None,
                },
            )
            species_meta["is_legendary"] = (
                is_legendary_m.group(1) == "true" if is_legendary_m else False
            )
            species_meta["is_mythical"] = (
                is_mythical_m.group(1) == "true" if is_mythical_m else False
            )
        except OSError:
            continue

    return metadata


@pokeapi_bp.route("/metadata", methods=["GET"])
def get_pokemon_metadata():
    """Return lightweight metadata extracted from cached Pokemon JSON files."""
    global _metadata_cache, _metadata_cache_count

    # Count current cache files to detect new additions
    current_count = 0
    if CACHE_DIR.is_dir():
        current_count = sum(
            1 for f in os.listdir(CACHE_DIR)
            if _CACHE_FILE_RE.match(f) or _SPECIES_CACHE_FILE_RE.match(f)
        )

    # Rebuild if first request or cache file count changed
    if _metadata_cache is None or current_count != _metadata_cache_count:
        logger.info("Building Pokemon metadata cache (%d files)...", current_count)
        _metadata_cache = _build_metadata()
        _metadata_cache_count = current_count
        logger.info("Pokemon metadata cache ready (%d entries)", len(_metadata_cache))

    return jsonify(_metadata_cache)


def _should_refresh() -> bool:
    """Check if the client requested a cache refresh."""
    value = request.args.get("refresh")
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes"}


def _is_pokeapi_cache_enabled() -> bool:
    """Determine whether the PokéAPI proxy should use CacheService."""
    if hasattr(cache_service, "should_use_pokeapi_cache"):
        return cache_service.should_use_pokeapi_cache()
    config = cache_service.get_config()
    return config.get("enabled", True)


def _is_form_variant(name_or_id: str) -> bool:
    """Check if a Pokemon identifier refers to a form variant (mega, gmax, regional).

    Form variants have numeric IDs > 10000 or hyphenated names like
    ``charizard-mega-x``, ``charizard-gmax``, ``pikachu-alola``.
    """
    text = name_or_id.strip().lower()
    if text.isdigit() and int(text) > 10000:
        return True
    # Hyphenated names with form suffixes
    return bool(re.search(
        r'-(mega|gmax|alola|galar|hisui|paldea|totem|(?:mega-[xy]))$', text
    ))


def _fetch_with_cache(
    cache_key: str,
    params: Dict[str, str],
    resource_path: str,
    refresh: bool,
    use_cache: bool,
    force_cache: bool = False,
) -> Tuple[Optional[Dict], str]:
    """Fetch a PokeAPI resource with CacheService backing.

    Uses stale-while-revalidate: expired cache entries are returned
    immediately with status ``stale`` so callers can serve them while a
    background refresh is kicked off.
    """
    cache_label = "bypass"
    if use_cache:
        cache_label = "refresh" if refresh else "miss"
        if not refresh:
            data, status = cache_service.get_with_stale(cache_key, params, force=force_cache)
            if data is not None:
                return data, status  # 'hit' or 'stale'

    url = f"{POKEAPI_BASE_URL.rstrip('/')}/{resource_path.lstrip('/')}"
    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException as exc:
        logger.error("Error contacting PokeAPI for %s: %s", resource_path, exc)
        raise

    if resp.status_code == 404:
        return None, cache_label

    try:
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Unexpected response from PokeAPI for %s: %s", resource_path, exc)
        raise

    data = resp.json()
    if use_cache:
        cache_service.set(cache_key, params, data, force=force_cache)
    return data, cache_label


def _proxy_resource(cache_key: str, params: Dict[str, str], resource_path: str,
                    force_cache: bool = False):
    refresh = _should_refresh()
    use_cache = _is_pokeapi_cache_enabled() or force_cache
    try:
        data, cache_status = _fetch_with_cache(
            cache_key, params, resource_path, refresh, use_cache,
            force_cache=force_cache)
    except requests.RequestException:
        error_response = jsonify({"error": "Failed to reach PokeAPI"})
        error_response.status_code = 502
        error_response.headers["X-PokeAPI-Cache"] = "error"
        logger.info("PokeAPI proxy %s cache=%s status=%s", resource_path, "error", 502)
        return error_response

    if data is None:
        error_response = jsonify({"error": "Resource not found"})
        error_response.status_code = 404
        error_response.headers["X-PokeAPI-Cache"] = cache_status
        logger.info("PokeAPI proxy %s cache=%s status=%s", resource_path, cache_status, 404)
        return error_response

    response = jsonify(data)
    response.headers["X-PokeAPI-Cache"] = cache_status
    if cache_status == "stale":
        # Tell the frontend it can revalidate this resource asynchronously
        response.headers["X-PokeAPI-Stale"] = "true"
    logger.info(
        "PokeAPI proxy %s cache=%s status=%s",
        resource_path,
        cache_status,
        200,
    )
    return response


@pokeapi_bp.route("/<string:name_or_id>", methods=["GET"])
def get_pokemon(name_or_id: str):
    """Return Pokemon data by name or ID via cache-aware proxy."""
    params = {"pokemon": name_or_id.lower()}
    return _proxy_resource("pokeapi_pokemon", params, f"pokemon/{name_or_id}",
                           force_cache=_is_form_variant(name_or_id))


@pokeapi_bp.route("/species/<string:name_or_id>", methods=["GET"])
def get_pokemon_species(name_or_id: str):
    """Return Pokemon species data via cache-aware proxy."""
    params = {"species": name_or_id.lower()}
    return _proxy_resource("pokeapi_species", params, f"pokemon-species/{name_or_id}")


@pokeapi_bp.route("/type/<string:type_name>", methods=["GET"])
def get_type(type_name: str):
    """Return Pokemon type data via cache-aware proxy."""
    params = {"type": type_name.lower()}
    return _proxy_resource("pokeapi_type", params, f"type/{type_name}")


@pokeapi_bp.route("/evolution-chain/<string:chain_id>", methods=["GET"])
def get_evolution_chain(chain_id: str):
    """Return evolution chain data by ID."""
    params = {"chain": chain_id}
    return _proxy_resource("pokeapi_evolution_chain", params, f"evolution-chain/{chain_id}")
