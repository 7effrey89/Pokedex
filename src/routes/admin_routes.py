"""Administrator data-management endpoints.

Covers storage status, selective asset hydration, and backup/restore. Access is
gated by src.services.admin_access so introducing accounts changes one module.
"""

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from src.config import PROJECT_ROOT, get_storage_paths
from src.services.admin_access import admin_context, require_admin

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

MAX_UPLOAD_BYTES = 40 * 1024 * 1024 * 1024


@admin_bp.route('/status', methods=['GET'])
def get_admin_status():
    """Storage locations, database health, asset inventory, and backup state."""
    denied = require_admin()
    if denied:
        return denied

    from src.db import SqliteDatabase
    from src.db.database import UsersDatabase
    from src.services.asset_manager import get_asset_manager
    from src.services.backup_service import get_backup_service

    paths = get_storage_paths()
    asset_manager = get_asset_manager()
    backup_service = get_backup_service()

    return jsonify({
        **admin_context(),
        "storage": {
            "data_root": str(paths.data_root),
            "catalog_database": str(paths.catalog_database),
            "users_database": str(paths.users_database),
            "persistent": paths.data_root != PROJECT_ROOT,
        },
        "catalog": SqliteDatabase(paths.catalog_database).status().to_dict(),
        "users": UsersDatabase(paths.users_database).status(),
        "assets": asset_manager.inventory(),
        "asset_job": asset_manager.job_status(),
        "backup_components": backup_service.available_components(),
        "backups": backup_service.list_backups(),
    })


@admin_bp.route('/assets/download', methods=['POST'])
def start_asset_download():
    """Download only the selected assets the catalog does not already store."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.asset_manager import get_asset_manager

    data = request.get_json(silent=True) or {}
    components = data.get('components') or []
    limit = int(data.get('limit') or 0)

    try:
        job = get_asset_manager().start_download(components, limit=limit)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409

    return jsonify({"message": "Asset download started", "job": job})


@admin_bp.route('/assets/job', methods=['GET'])
def get_asset_job():
    """Poll the active or most recent asset download."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.asset_manager import get_asset_manager

    manager = get_asset_manager()
    return jsonify({"job": manager.job_status(), "assets": manager.inventory()})


@admin_bp.route('/scan', methods=['GET'])
def scan_for_new_content():
    """Diff the live PokeAPI/TCG API against the local catalog to find new content."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.catalog_ingest import get_catalog_scan_service

    scanner = get_catalog_scan_service()
    try:
        pokemon = scanner.scan_pokemon()
    except Exception as exc:
        logger.exception("PokeAPI scan failed")
        pokemon = {"available": False, "reason": f"PokeAPI scan failed: {exc}"}
    try:
        tcg = scanner.scan_tcg()
    except Exception as exc:
        logger.exception("TCG API scan failed")
        tcg = {"available": False, "reason": f"TCG API scan failed: {exc}"}

    return jsonify({"pokemon": pokemon, "tcg": tcg})


@admin_bp.route('/ingest/species', methods=['POST'])
def ingest_species():
    """Add one newly-discovered Pokemon species (and its forms) to the catalog."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.catalog_ingest import get_catalog_ingest_service

    data = request.get_json(silent=True) or {}
    species_id = data.get('species_id')
    if not isinstance(species_id, int):
        return jsonify({"error": "species_id (integer) is required"}), 400

    try:
        result = get_catalog_ingest_service().add_species(species_id)
    except Exception as exc:
        logger.exception("Failed to add species %s", species_id)
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


@admin_bp.route('/ingest/tcg-set', methods=['POST'])
def ingest_tcg_set():
    """Add one newly-discovered TCG set (or its missing cards) to the catalog."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.catalog_ingest import get_catalog_ingest_service

    data = request.get_json(silent=True) or {}
    set_id = data.get('set_id')
    if not set_id or not isinstance(set_id, str):
        return jsonify({"error": "set_id (string) is required"}), 400

    try:
        result = get_catalog_ingest_service().add_tcg_set(set_id)
    except Exception as exc:
        logger.exception("Failed to add TCG set %s", set_id)
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


@admin_bp.route('/ingest/batch', methods=['POST'])
def start_ingest_batch():
    """Start a background job adding multiple new species or TCG sets, with progress."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.catalog_ingest import get_catalog_ingest_service

    data = request.get_json(silent=True) or {}
    kind = data.get('kind')
    ids = data.get('ids') or []

    try:
        job = get_catalog_ingest_service().start_batch(kind, ids)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409

    return jsonify({"message": "Ingest started", "job": job})


@admin_bp.route('/ingest/batch/job', methods=['GET'])
def get_ingest_batch_job():
    """Poll the active or most recent ingest batch job."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.catalog_ingest import get_catalog_ingest_service

    return jsonify({"job": get_catalog_ingest_service().job_status()})


@admin_bp.route('/backup', methods=['POST'])
def create_backup():
    """Create a versioned backup bundle for the selected components."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.backup_service import get_backup_service

    data = request.get_json(silent=True) or {}
    components = data.get('components') or []

    try:
        bundle = get_backup_service().create_backup(components)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Backup failed")
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "message": "Backup created",
        "name": bundle.name,
        "size_bytes": bundle.stat().st_size,
        "download_url": f"/api/admin/backup/download/{bundle.name}",
    })


@admin_bp.route('/backup/download/<name>', methods=['GET'])
def download_backup(name):
    """Download a previously created bundle."""
    denied = require_admin()
    if denied:
        return denied

    paths = get_storage_paths()
    safe_name = secure_filename(name)
    bundle = (paths.backups / safe_name).resolve()
    try:
        bundle.relative_to(paths.backups.resolve())
    except ValueError:
        return jsonify({"error": "Invalid backup name"}), 400
    if not bundle.is_file():
        return jsonify({"error": "Backup not found"}), 404
    return send_file(bundle, as_attachment=True, download_name=safe_name)


@admin_bp.route('/restore', methods=['POST'])
def restore_backup():
    """Restore selected components from an uploaded bundle."""
    denied = require_admin()
    if denied:
        return denied

    from src.services.backup_service import get_backup_service

    upload = request.files.get('bundle')
    if upload is None:
        return jsonify({"error": "A backup bundle file is required"}), 400

    components = [value for value in request.form.getlist('components') if value]
    paths = get_storage_paths()
    paths.backups.mkdir(parents=True, exist_ok=True)
    staged = paths.backups / f"upload-{secure_filename(upload.filename or 'bundle.zip')}"
    upload.save(staged)

    try:
        if staged.stat().st_size > MAX_UPLOAD_BYTES:
            return jsonify({"error": "Uploaded backup is too large"}), 413
        result = get_backup_service().restore_backup(staged, components or None)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Restore failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        staged.unlink(missing_ok=True)

    return jsonify({"message": "Restore completed", **result})
