"""Central administrative authorization.

Every user is treated as an administrator until accounts are introduced. Keeping
the decision here means adding real authentication only changes this module.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import jsonify


def is_admin() -> bool:
    if os.environ.get("POKEDEX_DISABLE_ADMIN", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return True


def admin_context() -> Dict[str, Any]:
    return {"is_admin": is_admin(), "open_admin_access": True}


def require_admin():
    """Return an error response when the caller is not an administrator."""
    if is_admin():
        return None
    return jsonify({"error": "Administrator access is required"}), 403
