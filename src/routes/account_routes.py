"""
Account and Member Routes.

Endpoints for user authentication, account management, multi-member family/team profiles,
and face photo enrollment.
"""

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory, session

from src.config import get_storage_paths
from src.services.user_account_service import get_user_account_service

logger = logging.getLogger(__name__)

account_bp = Blueprint('account', __name__, url_prefix='/api/account')


def _resolve_user_id() -> int:
    """Determine user_id from query params, request body, header, session, or default."""
    if request.is_json:
        body = request.get_json(silent=True) or {}
        if body.get('user_id'):
            try:
                return int(body['user_id'])
            except (ValueError, TypeError):
                pass

    if request.args.get('user_id'):
        try:
            return int(request.args['user_id'])
        except (ValueError, TypeError):
            pass

    header_id = request.headers.get('X-User-Id')
    if header_id:
        try:
            return int(header_id)
        except (ValueError, TypeError):
            pass

    session_id = session.get('active_user_id')
    if session_id:
        try:
            return int(session_id)
        except (ValueError, TypeError):
            pass

    service = get_user_account_service()
    default = service.get_or_create_default_account()
    return int(default["account"]["id"])


@account_bp.route('/current', methods=['GET'])
def get_current_account():
    """Return the active account and its members."""
    service = get_user_account_service()
    user_id = _resolve_user_id()
    data = service.get_account_by_id(user_id)
    if not data:
        data = service.get_or_create_default_account()
    return jsonify(data)


@account_bp.route('/list', methods=['GET'])
def list_accounts():
    """Return list of all registered accounts for easy switching."""
    service = get_user_account_service()
    service.get_or_create_default_account()  # ensure at least one
    accounts = service.list_all_accounts()
    return jsonify({"accounts": accounts})


@account_bp.route('/login', methods=['POST'])
def login():
    """Log in / switch to an existing account by id or email, with optional password verification."""
    service = get_user_account_service()
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    if user_id:
        account_data = service.get_account_by_id(int(user_id), include_hash=True)
    elif email:
        all_accounts = service.list_all_accounts()
        matched = next((a for a in all_accounts if (a.get('email') or '').lower() == email), None)
        if matched:
            account_data = service.get_account_by_id(matched['id'], include_hash=True)
        else:
            return jsonify({"error": f"No account found with email '{email}'"}), 404
    else:
        return jsonify({"error": "user_id or email is required"}), 400

    if not account_data:
        return jsonify({"error": "Account not found"}), 404

    # Check password if set on account
    acc_id = account_data["account"]["id"]
    if account_data["account"].get("has_password"):
        if not password:
            return jsonify({"error": "Password is required for this account", "requires_password": True}), 401
        if not service.verify_password(acc_id, password):
            return jsonify({"error": "Incorrect password", "requires_password": True}), 401

    session['active_user_id'] = acc_id
    sanitized_account = service.get_account_by_id(acc_id)
    return jsonify({"message": "Logged in successfully", **sanitized_account})


@account_bp.route('/logout', methods=['POST'])
def logout():
    """Log out of the current session and revert to default guest/trainer account."""
    service = get_user_account_service()
    session.pop('active_user_id', None)
    default_account = service.get_or_create_default_account()
    return jsonify({"message": "Logged out successfully", **default_account})


@account_bp.route('/signup', methods=['POST'])
def signup():
    """Create a brand-new user account with password and initial member."""
    service = get_user_account_service()
    data = request.get_json(silent=True) or {}
    display_name = (data.get('display_name') or '').strip()
    email = (data.get('email') or '').strip()
    password = (data.get('password') or '').strip()
    member_name = (data.get('member_name') or display_name).strip()

    if not display_name:
        return jsonify({"error": "Display name is required"}), 400

    try:
        account_data = service.create_account(
            display_name=display_name,
            email=email or None,
            password=password or None,
            is_admin=bool(data.get('is_admin')),
            initial_member_name=member_name,
        )
        session['active_user_id'] = account_data["account"]["id"]
        return jsonify({"message": "Account created successfully", **account_data}), 201
    except Exception as exc:
        logger.exception("Failed to create account")
        return jsonify({"error": str(exc)}), 500


@account_bp.route('/update', methods=['POST'])
def update_account():
    """Update display name, email, password, or avatar of the account."""
    service = get_user_account_service()
    user_id = _resolve_user_id()
    data = request.get_json(silent=True) or {}

    try:
        updated = service.update_account(
            user_id=user_id,
            display_name=data.get('display_name'),
            email=data.get('email'),
            password=data.get('password'),
            avatar_data=data.get('avatar'),
        )
        return jsonify({"message": "Account updated", **updated})
    except Exception as exc:
        logger.exception("Failed to update account")
        return jsonify({"error": str(exc)}), 500


@account_bp.route('/active-member', methods=['POST'])
def set_active_member():
    """Set the active speaking/browsing member for the account."""
    service = get_user_account_service()
    user_id = _resolve_user_id()
    data = request.get_json(silent=True) or {}
    member_id = data.get('member_id')
    if not member_id:
        return jsonify({"error": "member_id is required"}), 400

    try:
        updated = service.set_active_member(user_id=user_id, member_id=int(member_id))
        return jsonify({"message": "Active member updated", **updated})
    except Exception as exc:
        logger.exception("Failed to set active member")
        return jsonify({"error": str(exc)}), 500


@account_bp.route('/members', methods=['GET'])
def list_members():
    """List members belonging to the current account."""
    service = get_user_account_service()
    user_id = _resolve_user_id()
    account_data = service.get_account_by_id(user_id)
    if not account_data:
        return jsonify({"members": []})
    return jsonify({"members": account_data.get("members", [])})


@account_bp.route('/members', methods=['POST'])
def add_member():
    """Add a new member with name and optional face photo to the account."""
    service = get_user_account_service()
    user_id = _resolve_user_id()
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    photo = data.get('photo')

    if not name:
        return jsonify({"error": "Member name is required"}), 400

    try:
        member = service.add_member(user_id=user_id, name=name, photo_base64=photo)
        account_data = service.get_account_by_id(user_id)
        return jsonify({"message": "Member added successfully", "member": member, **(account_data or {})}), 201
    except Exception as exc:
        logger.exception("Failed to add member")
        return jsonify({"error": str(exc)}), 500


@account_bp.route('/members/<int:member_id>', methods=['PUT', 'POST'])
def update_member(member_id: int):
    """Update an existing member's name or photo."""
    service = get_user_account_service()
    user_id = _resolve_user_id()
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    photo = data.get('photo')

    try:
        member = service.update_member(member_id=member_id, name=name, photo_base64=photo)
        account_data = service.get_account_by_id(user_id)
        return jsonify({"message": "Member updated successfully", "member": member, **(account_data or {})})
    except Exception as exc:
        logger.exception("Failed to update member")
        return jsonify({"error": str(exc)}), 500


@account_bp.route('/members/<int:member_id>', methods=['DELETE'])
def delete_member(member_id: int):
    """Delete a member from the account."""
    service = get_user_account_service()
    user_id = _resolve_user_id()

    try:
        success = service.delete_member(member_id=member_id)
        if not success:
            return jsonify({"error": "Member not found"}), 404
        account_data = service.get_account_by_id(user_id)
        return jsonify({"message": "Member deleted", **(account_data or {})})
    except Exception as exc:
        logger.exception("Failed to delete member")
        return jsonify({"error": str(exc)}), 500


@account_bp.route('/delete', methods=['POST', 'DELETE'])
def delete_account():
    """Delete the active account (or specified user_id) and return the fallback account."""
    service = get_user_account_service()
    data = request.get_json(silent=True) or {}
    target_id = data.get('user_id') or _resolve_user_id()

    try:
        success = service.delete_account(int(target_id))
        if not success:
            return jsonify({"error": "Account not found"}), 404

        if session.get('active_user_id') == int(target_id):
            session.pop('active_user_id', None)

        # Fallback to another existing account or initialize default
        next_account = service.get_or_create_default_account()
        session['active_user_id'] = next_account["account"]["id"]
        return jsonify({
            "message": "Account deleted successfully",
            "deleted_user_id": int(target_id),
            **next_account
        })
    except Exception as exc:
        logger.exception("Failed to delete account")
        return jsonify({"error": str(exc)}), 500


@account_bp.route('/avatar/<path:filename>', methods=['GET'])
def get_avatar_image(filename: str):
    """Serve member or account avatar images."""
    paths = get_storage_paths()
    profiles_dir = paths.profile_images
    safe_name = Path(filename).name
    target = profiles_dir / safe_name
    if not target.is_file():
        # Fallback check project root data/assets/profiles
        fallback = paths.data_root / "data" / "assets" / "profiles" / safe_name
        if fallback.is_file():
            return send_from_directory(str(fallback.parent), safe_name)
        return jsonify({"error": "Avatar not found"}), 404
    return send_from_directory(str(profiles_dir), safe_name)
