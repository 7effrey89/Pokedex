"""SQLite-backed TCG endpoints shared by the optional MCP server."""

import logging

from flask import jsonify, request

from src.db.tcg_repository import SqliteTcgRepository
from src.routes.tcg_image_routes import tcg_image_bp
from src.tools.handlers.tcg_handlers import handle_get_card_price

logger = logging.getLogger(__name__)


@tcg_image_bp.get("/catalog/cards")
def search_catalog_cards():
    try:
        page_size = int(request.args.get("pageSize", "20"))
        if not 1 <= page_size <= 250:
            raise ValueError("pageSize must be between 1 and 250")
        filters = {key: int(request.args[key]) for key in ("hp_min", "hp_max") if key in request.args}
        if any(value < 0 for value in filters.values()) or filters.get("hp_min", 0) > filters.get("hp_max", float("inf")):
            raise ValueError("HP bounds must be non-negative and ordered")
        result = SqliteTcgRepository().search_cards(
            pokemon_name=request.args.get("name"), card_type=request.args.get("types"),
            rarity=request.args.get("rarity"), supertype=request.args.get("supertype"),
            subtype=request.args.get("subtypes"), set_id=request.args.get("set"),
            limit=page_size, **filters,
        )
        return jsonify({"data": result["cards"]})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@tcg_image_bp.get("/catalog/cards/<card_id>/price")
def get_catalog_card_price(card_id):
    try:
        return jsonify({"data": handle_get_card_price(card_id)["card"]})
    except (ValueError, RuntimeError, OSError) as exc:
        logger.warning("Unable to fetch TCGdex price for %s: %s", card_id, exc)
        return jsonify({"error": str(exc)}), 502
