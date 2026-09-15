"""Central administrative authorization for the logged-in account."""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import jsonify, session

from src.services.user_account_service import get_user_account_service


def is_admin() -> bool:
    if os.environ.get("POKEDEX_DISABLE_ADMIN", "").strip().lower() in {"1", "true", "yes"}:
        return False
    user_id = session.get("active_user_id")
    if not user_id:
        return False
    account = get_user_account_service().get_account_by_id(int(user_id))
    return bool(account and account["account"].get("is_admin"))


def admin_context() -> Dict[str, Any]:
    return {"is_admin": is_admin(), "open_admin_access": False}


def require_admin():
    """Return an error response when the caller is not an administrator."""
    if is_admin():
        return None
    return jsonify({"error": "Administrator access is required"}), 403
