"""
User Account and Membership Service.

Manages persistent user accounts and multi-member profiles backed by SQLite (users.sqlite3).
Supports face photo capture, encoding extraction, and member-scoped face matching.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash

from src.config import get_storage_paths
from src.db.database import UsersDatabase

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserAccountService:
    """Manages user accounts, multiple members per account, and face profiles."""

    def __init__(self, database: Optional[UsersDatabase] = None):
        paths = get_storage_paths()
        self.paths = paths
        self.database = database or UsersDatabase(paths.users_database)
        self.profiles_dir = paths.profile_images
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_default_account(self) -> Dict[str, Any]:
        """Ensure at least one default account exists and return it."""
        self.database.initialize()
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM app_user ORDER BY id ASC LIMIT 1").fetchone()
            if row:
                account = dict(row)
                members = self._get_account_members(connection, account["id"])
                active_member = None
                if account.get("active_member_id"):
                    active_member = next((m for m in members if m["id"] == account["active_member_id"]), None)
                if not active_member and members:
                    active_member = members[0]
                return {"account": account, "active_member": active_member, "members": members}

            # Create initial default account & member
            now = utc_now()
            cursor = connection.execute(
                """
                INSERT INTO app_user (display_name, email, is_admin, created_at, last_seen_at)
                VALUES (?, ?, 1, ?, ?)
                """,
                ("Default Trainer", "trainer@pokedex.local", now, now),
            )
            user_id = int(cursor.lastrowid)

            member_cursor = connection.execute(
                """
                INSERT INTO account_member (user_id, name, created_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, "Trainer", now, now),
            )
            member_id = int(member_cursor.lastrowid)

            connection.execute(
                "UPDATE app_user SET active_member_id = ? WHERE id = ?",
                (member_id, user_id),
            )
            connection.commit()

            account = dict(connection.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone())
            member = dict(connection.execute("SELECT * FROM account_member WHERE id = ?", (member_id,)).fetchone())
            return {"account": account, "active_member": member, "members": [member]}
        finally:
            connection.close()

    def get_account_by_id(self, user_id: int, include_hash: bool = False) -> Optional[Dict[str, Any]]:
        self.database.initialize()
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return None
            account = dict(row)
            has_pwd = bool(account.get("password_hash"))
            if not include_hash:
                account.pop("password_hash", None)
            account["has_password"] = has_pwd
            members = self._get_account_members(connection, user_id)
            active_member = None
            if account.get("active_member_id"):
                active_member = next((m for m in members if m["id"] == account["active_member_id"]), None)
            if not active_member and members:
                active_member = members[0]
            return {"account": account, "active_member": active_member, "members": members}
        finally:
            connection.close()

    def list_all_accounts(self) -> List[Dict[str, Any]]:
        self.database.initialize()
        connection = self.database.connect()
        try:
            rows = connection.execute("SELECT id, external_id, display_name, email, is_admin, password_hash, created_at, last_seen_at FROM app_user ORDER BY id ASC").fetchall()
            accounts = []
            for r in rows:
                acc = dict(r)
                has_pwd = bool(acc.get("password_hash"))
                acc.pop("password_hash", None)
                acc["has_password"] = has_pwd
                members = self._get_account_members(connection, acc["id"])
                acc["member_count"] = len(members)
                accounts.append(acc)
            return accounts
        finally:
            connection.close()

    def create_account(self, display_name: str, email: Optional[str] = None,
                       password: Optional[str] = None,
                       is_admin: bool = False, initial_member_name: Optional[str] = None) -> Dict[str, Any]:
        self.database.initialize()
        connection = self.database.connect()
        try:
            name = (display_name or "").strip() or "New Trainer"
            email_val = (email or "").strip().lower() or None
            now = utc_now()
            pwd_hash = generate_password_hash(password) if password and password.strip() else None

            cursor = connection.execute(
                """
                INSERT INTO app_user (display_name, email, password_hash, is_admin, created_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, email_val, pwd_hash, 1 if is_admin else 0, now, now),
            )
            user_id = int(cursor.lastrowid)

            member_name = (initial_member_name or name).strip()
            member_cursor = connection.execute(
                """
                INSERT INTO account_member (user_id, name, created_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, member_name, now, now),
            )
            member_id = int(member_cursor.lastrowid)

            connection.execute(
                "UPDATE app_user SET active_member_id = ? WHERE id = ?",
                (member_id, user_id),
            )
            connection.commit()
            return self.get_account_by_id(user_id) or {}
        finally:
            connection.close()

    def verify_password(self, user_id: int, password: str) -> bool:
        """Verify the plain password against the stored password hash."""
        self.database.initialize()
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT password_hash FROM app_user WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return False
            stored_hash = row["password_hash"]
            if not stored_hash:
                # Account has no password requirement
                return True
            return check_password_hash(stored_hash, password)
        finally:
            connection.close()

    def update_account(self, user_id: int, display_name: Optional[str] = None,
                       email: Optional[str] = None, password: Optional[str] = None,
                       avatar_data: Optional[str] = None) -> Dict[str, Any]:
        self.database.initialize()
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError(f"Account {user_id} not found")

            updates = []
            params = []
            if display_name is not None:
                updates.append("display_name = ?")
                params.append(display_name.strip() or row["display_name"])
            if email is not None:
                updates.append("email = ?")
                params.append(email.strip().lower() or None)
            if password is not None and password.strip():
                updates.append("password_hash = ?")
                params.append(generate_password_hash(password.strip()))

            if avatar_data:
                avatar_path = self._save_image_payload(avatar_data, f"account-{user_id}")
                if avatar_path:
                    updates.append("avatar_path = ?")
                    params.append(avatar_path)

            if updates:
                updates.append("last_seen_at = ?")
                params.append(utc_now())
                params.append(user_id)
                query = f"UPDATE app_user SET {', '.join(updates)} WHERE id = ?"
                connection.execute(query, params)
                connection.commit()

            return self.get_account_by_id(user_id) or {}
        finally:
            connection.close()

    def set_active_member(self, user_id: int, member_id: int) -> Dict[str, Any]:
        self.database.initialize()
        connection = self.database.connect()
        try:
            member = connection.execute(
                "SELECT id FROM account_member WHERE id = ? AND user_id = ?",
                (member_id, user_id),
            ).fetchone()
            if not member:
                raise ValueError(f"Member {member_id} does not belong to user {user_id}")

            connection.execute(
                "UPDATE app_user SET active_member_id = ?, last_seen_at = ? WHERE id = ?",
                (member_id, utc_now(), user_id),
            )
            connection.execute(
                "UPDATE account_member SET last_seen_at = ? WHERE id = ?",
                (utc_now(), member_id),
            )
            connection.commit()
            return self.get_account_by_id(user_id) or {}
        finally:
            connection.close()

    def add_member(self, user_id: int, name: str, photo_base64: Optional[str] = None) -> Dict[str, Any]:
        self.database.initialize()
        connection = self.database.connect()
        try:
            user = connection.execute("SELECT id FROM app_user WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise ValueError(f"Account {user_id} not found")

            member_name = name.strip()
            if not member_name:
                raise ValueError("Member name is required")

            now = utc_now()
            cursor = connection.execute(
                """
                INSERT INTO account_member (user_id, name, created_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, member_name, now, now),
            )
            member_id = int(cursor.lastrowid)

            avatar_path = None
            face_encoding_json = None

            if photo_base64:
                avatar_path, face_encoding_json = self._process_member_photo(photo_base64, user_id, member_id, member_name)
                connection.execute(
                    """
                    UPDATE account_member
                    SET avatar_path = ?, face_encoding = ?
                    WHERE id = ?
                    """,
                    (avatar_path, face_encoding_json, member_id),
                )

            # If user has no active member, set this one
            user_row = connection.execute("SELECT active_member_id FROM app_user WHERE id = ?", (user_id,)).fetchone()
            if not user_row or not user_row["active_member_id"]:
                connection.execute("UPDATE app_user SET active_member_id = ? WHERE id = ?", (member_id, user_id))

            connection.commit()

            # Refresh face recognition service if available
            self._notify_face_service_reload()

            row = connection.execute("SELECT * FROM account_member WHERE id = ?", (member_id,)).fetchone()
            return dict(row)
        finally:
            connection.close()

    def update_member(self, member_id: int, name: Optional[str] = None,
                      photo_base64: Optional[str] = None) -> Dict[str, Any]:
        self.database.initialize()
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM account_member WHERE id = ?", (member_id,)).fetchone()
            if not row:
                raise ValueError(f"Member {member_id} not found")

            member = dict(row)
            updates = []
            params = []

            if name is not None and name.strip():
                updates.append("name = ?")
                params.append(name.strip())

            if photo_base64:
                avatar_path, face_encoding_json = self._process_member_photo(
                    photo_base64, member["user_id"], member_id, name or member["name"]
                )
                updates.append("avatar_path = ?")
                params.append(avatar_path)
                if face_encoding_json:
                    updates.append("face_encoding = ?")
                    params.append(face_encoding_json)

            if updates:
                updates.append("last_seen_at = ?")
                params.append(utc_now())
                params.append(member_id)
                query = f"UPDATE account_member SET {', '.join(updates)} WHERE id = ?"
                connection.execute(query, params)
                connection.commit()
                self._notify_face_service_reload()

            updated = connection.execute("SELECT * FROM account_member WHERE id = ?", (member_id,)).fetchone()
            return dict(updated)
        finally:
            connection.close()

    def delete_member(self, member_id: int) -> bool:
        self.database.initialize()
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM account_member WHERE id = ?", (member_id,)).fetchone()
            if not row:
                return False

            user_id = row["user_id"]
            avatar_path = row["avatar_path"]

            connection.execute("DELETE FROM account_member WHERE id = ?", (member_id,))

            # If this was active member, update to another member or None
            remaining = connection.execute(
                "SELECT id FROM account_member WHERE user_id = ? LIMIT 1", (user_id,)
            ).fetchone()
            new_active = remaining["id"] if remaining else None
            connection.execute(
                "UPDATE app_user SET active_member_id = ? WHERE id = ?", (new_active, user_id)
            )
            connection.commit()

            if avatar_path:
                try:
                    full_path = self.paths.data_root / avatar_path
                    full_path.unlink(missing_ok=True)
                except OSError:
                    pass

            self._notify_face_service_reload()
            return True
        finally:
            connection.close()

    def delete_account(self, user_id: int) -> bool:
        """Permanently delete an account and all its members, cards, preferences, and files."""
        self.database.initialize()
        connection = self.database.connect()
        try:
            account = connection.execute("SELECT id, avatar_path FROM app_user WHERE id = ?", (user_id,)).fetchone()
            if not account:
                return False

            # Collect avatar files to remove
            member_avatars = [
                row["avatar_path"] for row in connection.execute(
                    "SELECT avatar_path FROM account_member WHERE user_id = ? AND avatar_path IS NOT NULL",
                    (user_id,)
                ).fetchall()
            ]
            if account["avatar_path"]:
                member_avatars.append(account["avatar_path"])

            # Delete the user (foreign keys ON will cascade to account_member, user_card, user_preference)
            connection.execute("DELETE FROM app_user WHERE id = ?", (user_id,))
            connection.commit()

            # Clean up avatar files from disk
            for rel_path in member_avatars:
                if rel_path:
                    try:
                        (self.paths.data_root / rel_path).unlink(missing_ok=True)
                    except OSError:
                        pass

            self._notify_face_service_reload()
            return True
        finally:
            connection.close()

    def get_known_face_encodings(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return all members with valid face encodings, optionally scoped to a user account."""
        self.database.initialize()
        connection = self.database.connect()
        try:
            query = "SELECT id, user_id, name, avatar_path, face_encoding FROM account_member WHERE face_encoding IS NOT NULL AND face_encoding != ''"
            params = []
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)

            rows = connection.execute(query, params).fetchall()
            results = []
            for r in rows:
                try:
                    enc_list = json.loads(r["face_encoding"])
                    enc_arr = np.array(enc_list, dtype=np.float64)
                    results.append({
                        "member_id": r["id"],
                        "user_id": r["user_id"],
                        "name": r["name"],
                        "avatar_path": r["avatar_path"],
                        "encoding": enc_arr,
                    })
                except Exception as exc:
                    logger.warning("Could not parse face encoding for member %s: %s", r["id"], exc)
            return results
        finally:
            connection.close()

    def _get_account_members(self, connection, user_id: int) -> List[Dict[str, Any]]:
        rows = connection.execute(
            "SELECT id, user_id, name, avatar_path, created_at, last_seen_at FROM account_member WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _process_member_photo(self, photo_base64: str, user_id: int, member_id: int, name: str) -> Tuple[Optional[str], Optional[str]]:
        sanitized = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-_").lower() or "member"
        filename_prefix = f"user-{user_id}-member-{member_id}-{sanitized}"
        avatar_path = self._save_image_payload(photo_base64, filename_prefix)

        # Extract face encoding using face_recognition
        face_encoding_json = None
        if avatar_path:
            try:
                import face_recognition

                full_path = self.paths.data_root / avatar_path
                image = face_recognition.load_image_file(str(full_path))
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    face_encoding_json = json.dumps(encodings[0].tolist())
                    logger.info("Computed face encoding for member %s (%s)", member_id, name)
                else:
                    logger.warning("No face detected in photo for member %s (%s)", member_id, name)
            except Exception as exc:
                logger.warning("Failed to compute face encoding for member %s: %s", member_id, exc)

        return avatar_path, face_encoding_json

    def _save_image_payload(self, base64_data: str, filename_prefix: str) -> Optional[str]:
        if not base64_data:
            return None
        data = base64_data
        if "," in data:
            data = data.split(",", 1)[1]
        try:
            image_bytes = base64.b64decode(data)
            image = Image.open(io.BytesIO(image_bytes))
            image.thumbnail((400, 400))

            filename = f"{filename_prefix}.png"
            dest = self.profiles_dir / filename
            image.save(dest, format="PNG")
            return self.paths.relative_to_root(dest)
        except Exception as exc:
            logger.error("Failed to save image payload: %s", exc)
            return None

    def _notify_face_service_reload(self) -> None:
        try:
            from src.services.face_recognition_service import get_face_recognition_service
            service = get_face_recognition_service()
            service.reload_profiles()
        except Exception as exc:
            logger.debug("Could not reload face recognition service: %s", exc)


_USER_ACCOUNT_SERVICE: Optional[UserAccountService] = None


def get_user_account_service() -> UserAccountService:
    global _USER_ACCOUNT_SERVICE
    if _USER_ACCOUNT_SERVICE is None:
        _USER_ACCOUNT_SERVICE = UserAccountService()
    return _USER_ACCOUNT_SERVICE
