"""Administrator-only incremental TCG embedding jobs."""

import logging

from flask import jsonify, request

from src.routes.admin_routes import admin_bp
from src.services.admin_access import require_admin
from src.services.tcg_embedding_service import get_tcg_embedding_service

logger = logging.getLogger(__name__)


@admin_bp.route('/embeddings', methods=['GET'])
def get_embedding_inventory():
    denied = require_admin()
    if denied:
        return denied
    try:
        service = get_tcg_embedding_service(request.args.get("encoder", "legacy"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"embeddings": service.inventory(), "job": service.job_status()})


@admin_bp.route('/embeddings/generate', methods=['POST'])
def generate_missing_embeddings():
    denied = require_admin()
    if denied:
        return denied
    try:
        job = get_tcg_embedding_service(request.args.get("encoder", "legacy")).start()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception:
        logger.exception("Unable to start TCG embedding job")
        return jsonify({"error": "Unable to start TCG embedding job; see server logs."}), 500
    return jsonify({"message": "TCG embedding generation started", "job": job}), 202


@admin_bp.route('/embeddings/job', methods=['GET'])
def get_embedding_job():
    denied = require_admin()
    if denied:
        return denied
    try:
        return jsonify({"job": get_tcg_embedding_service(request.args.get("encoder", "legacy")).job_status()})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
