"""SQLite catalog reads and explicit, persisted PokeAPI refreshes."""

import json
import logging
import os
import sqlite3
from functools import lru_cache
from pathlib import Path

import requests
from flask import Blueprint, jsonify, request, send_file

from src.db.database import SqliteDatabase
from src.db.pokemon_repository import SqlitePokemonRepository
from src.services.catalog_refresh import CatalogRefreshService

logger = logging.getLogger(__name__)
POKEAPI_BASE_URL = os.environ.get("POKEMON_API_URL", "https://pokeapi.co/api/v2")
POKEMON_LIST_PATH = Path(__file__).resolve().parents[2] / "data" / "pokemon_list.json"
pokeapi_bp = Blueprint("pokeapi", __name__, url_prefix="/api/pokemon")


@lru_cache(maxsize=1)
def _load_static_pokemon_list():
    return json.loads(POKEMON_LIST_PATH.read_text(encoding="utf-8"))


@pokeapi_bp.route("/list", methods=["GET"])
def get_pokemon_list():
    try:
        return jsonify(_load_static_pokemon_list())
    except (OSError, ValueError):
        logger.exception("Pokemon index unavailable")
        return jsonify({"error": "Pokemon list unavailable"}), 500


@pokeapi_bp.route("/metadata", methods=["GET"])
def get_pokemon_metadata():
    connection = SqliteDatabase().connect(read_only=True)
    try:
        metadata = {
            str(row["id"]): {
                "name": row["name"], "height": row["height_decimetres"],
                "weight": row["weight_hectograms"], "is_legendary": bool(row["is_legendary"]),
                "is_mythical": bool(row["is_mythical"]), "types": [], "abilities": [],
            }
            for row in connection.execute(
                "SELECT p.*, s.is_legendary, s.is_mythical FROM pokemon p "
                "JOIN pokemon_species s ON s.id = p.species_id"
            )
        }
        for relation, lookup, key, foreign_key in (
            ("pokemon_type", "type", "types", "type_id"),
            ("pokemon_ability", "ability", "abilities", "ability_id"),
        ):
            for row in connection.execute(
                f"SELECT r.pokemon_id, l.name FROM {relation} r "
                f"JOIN {lookup} l ON l.id = r.{foreign_key} ORDER BY r.pokemon_id, r.slot"
            ):
                metadata[str(row["pokemon_id"])][key].append(row["name"])
        return jsonify(metadata)
    finally:
        connection.close()


@pokeapi_bp.route("/<int:pokemon_id>/cry", methods=["GET"])
def get_pokemon_cry(pokemon_id: int):
    from src.services.asset_manager import get_asset_manager

    try:
        materialized = get_asset_manager().materialize_pokemon_cry(pokemon_id)
    except (OSError, requests.RequestException) as exc:
        logger.warning("Unable to materialize Pokemon cry %s: %s", pokemon_id, exc)
        return jsonify({"error": "Unable to fetch Pokemon cry"}), 502
    if materialized is None:
        return jsonify({"error": "Pokemon cry not found"}), 404
    path, media_type = materialized
    return send_file(path, mimetype=media_type, conditional=True, max_age=86400)


@pokeapi_bp.route("/<int:pokemon_id>/sprite/<style>", methods=["GET"])
def get_pokemon_sprite(pokemon_id: int, style: str):
    from src.services.asset_manager import get_asset_manager

    manager = get_asset_manager()
    try:
        materialized = manager.materialize_pokemon_sprite(pokemon_id, style)
        if materialized is None and style != "official-artwork":
            materialized = manager.materialize_pokemon_sprite(pokemon_id, "official-artwork")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError as exc:
        logger.warning("Unable to materialize Pokemon sprite %s: %s", pokemon_id, exc)
        return jsonify({"error": "Unable to fetch Pokemon sprite"}), 502
    if materialized is None:
        return jsonify({"error": "Pokemon sprite not found"}), 404
    path, media_type = materialized
    return send_file(path, mimetype=media_type, conditional=True, max_age=86400)


def _should_refresh() -> bool:
    return request.args.get("refresh", "").lower() in {"1", "true", "yes"}


def _refresh_resource(resource_path, persist):
    try:
        upstream = requests.get(
            f"{POKEAPI_BASE_URL.rstrip('/')}/{resource_path}", timeout=15
        )
        if upstream.status_code == 404:
            return jsonify({"error": "Resource not found"}), 404
        upstream.raise_for_status()
        payload = upstream.json()
    except (requests.RequestException, ValueError):
        logger.exception("Unable to fetch PokeAPI resource %s", resource_path)
        return jsonify({"error": "Failed to reach PokeAPI"}), 502
    try:
        persist(payload)
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error):
        logger.exception("Unable to persist PokeAPI resource %s", resource_path)
        return jsonify({"error": "Fresh data was fetched but could not be persisted"}), 500
    response = jsonify(payload)
    response.headers["X-PokeAPI-Source"] = "upstream"
    response.headers["X-PokeAPI-Cache"] = "refresh"
    return response


def _catalog_response(payload):
    if payload is None:
        return jsonify({"error": "Resource not found"}), 404
    response = jsonify(payload)
    response.headers["X-PokeAPI-Source"] = "sqlite"
    return response


@pokeapi_bp.route("/<string:name_or_id>", methods=["GET"])
def get_pokemon(name_or_id: str):
    if _should_refresh():
        return _refresh_resource(
            f"pokemon/{name_or_id}", CatalogRefreshService().refresh_pokemon
        )
    return _catalog_response(SqlitePokemonRepository().get_pokemon(name_or_id))


@pokeapi_bp.route("/species/<string:name_or_id>", methods=["GET"])
def get_pokemon_species(name_or_id: str):
    if _should_refresh():
        return _refresh_resource(
            f"pokemon-species/{name_or_id}", CatalogRefreshService().refresh_species
        )
    return _catalog_response(SqlitePokemonRepository().get_species(name_or_id))


@pokeapi_bp.route("/type/<string:type_name>", methods=["GET"])
def get_type(type_name: str):
    if not _should_refresh():
        stored = SqlitePokemonRepository().get_type(type_name)
        if stored is not None:
            return _catalog_response(stored)
    return _refresh_resource(f"type/{type_name}", CatalogRefreshService().refresh_type)


@pokeapi_bp.route("/evolution-chain/<string:chain_id>", methods=["GET"])
def get_evolution_chain(chain_id: str):
    if not chain_id.isdigit():
        return jsonify({"error": "Evolution chain ID must be numeric"}), 400
    if _should_refresh():
        return _refresh_resource(
            f"evolution-chain/{chain_id}", CatalogRefreshService().refresh_evolution
        )
    return _catalog_response(SqlitePokemonRepository().get_evolution_chain(int(chain_id)))
