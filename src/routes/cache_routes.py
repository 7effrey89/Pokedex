"""Database cache status and refresh policy; no destructive clearing endpoints."""

import logging

from flask import Blueprint, jsonify, request

from src.db.database import SqliteDatabase
from src.services.catalog_settings import get_catalog_settings

logger = logging.getLogger(__name__)
cache_bp = Blueprint("cache", __name__, url_prefix="/api/cache")


@cache_bp.route("/config", methods=["GET"])
def get_cache_config():
    return jsonify({
        **get_catalog_settings().get_config(),
        "sqlite": SqliteDatabase().status().to_dict(),
    })


@cache_bp.route("/expiry", methods=["POST"])
def set_cache_expiry():
    data = request.get_json() or {}
    if not isinstance(data, dict):
        logger.warning("Rejected a non-object catalog refresh policy")
        return jsonify({"error": "Request body must be an object"}), 400
    seconds = data.get("seconds")
    if not isinstance(seconds, int) or isinstance(seconds, bool):
        logger.warning("Rejected a non-integer catalog refresh interval")
        return jsonify({"error": "seconds must be an integer"}), 400
    try:
        settings = get_catalog_settings()
        settings.set_tcg_price_expiry_seconds(seconds)
    except ValueError as exc:
        logger.warning("Rejected catalog refresh interval: %s", exc)
        return jsonify({"error": str(exc)}), 400
    logger.info("TCG database price refresh interval set to %s seconds", seconds)
    return jsonify({
        "message": "TCG price refresh interval saved",
        "config": settings.get_config(),
    })
