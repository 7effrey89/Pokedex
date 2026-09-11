"""Connection, initialization, and readiness checks for the local database."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import get_storage_paths


SCHEMA_VERSION = 1
USERS_SCHEMA_VERSION = 1
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "data" / "schema"
SCHEMA_PATH = SCHEMA_DIR / "001.sql"
USERS_SCHEMA_PATH = SCHEMA_DIR / "users-001.sql"
DEFAULT_DATABASE_PATH = get_storage_paths().catalog_database
DEFAULT_USERS_DATABASE_PATH = get_storage_paths().users_database


def apply_catalog_schema(connection: sqlite3.Connection) -> None:
    """Create or migrate a catalog database to the supported schema version."""
    current = int(connection.execute("PRAGMA user_version").fetchone()[0])
    for version in range(current + 1, SCHEMA_VERSION + 1):
        script = SCHEMA_DIR / f"{version:03d}.sql"
        connection.executescript(script.read_text(encoding="utf-8"))
    connection.commit()


def apply_users_schema(connection: sqlite3.Connection) -> None:
    """Create or migrate a users database to the supported schema version."""
    current = int(connection.execute("PRAGMA user_version").fetchone()[0])
    for version in range(current + 1, USERS_SCHEMA_VERSION + 1):
        script = SCHEMA_DIR / f"users-{version:03d}.sql"
        connection.executescript(script.read_text(encoding="utf-8"))
    connection.commit()


@dataclass(frozen=True)
class DatabaseStatus:
    available: bool
    schema_version: Optional[int]
    last_imported_at: Optional[str]
    pokemon_count: int
    card_count: int
    missing_asset_count: int
    reason: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SqliteDatabase:
    """Owns SQLite connections without sharing them across Flask threads."""

    def __init__(self, path: Path | str = DEFAULT_DATABASE_PATH):
        self.path = Path(path)

    def connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            connection = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if not read_only:
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        connection = self.connect()
        try:
            apply_catalog_schema(connection)
        finally:
            connection.close()

    def status(self) -> DatabaseStatus:
        if not self.path.is_file():
            return DatabaseStatus(False, None, None, 0, 0, 0, "Database has not been built")

        try:
            connection = self.connect(read_only=True)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    return DatabaseStatus(False, None, None, 0, 0, 0, f"Integrity check failed: {integrity}")

                schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if schema_version != SCHEMA_VERSION:
                    return DatabaseStatus(
                        False, schema_version, None, 0, 0, 0,
                        f"Schema version {schema_version} is not supported",
                    )

                pokemon_count = connection.execute("SELECT COUNT(*) FROM pokemon").fetchone()[0]
                card_count = connection.execute("SELECT COUNT(*) FROM tcg_card").fetchone()[0]
                missing_asset_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM pokemon AS p
                    LEFT JOIN pokemon_asset AS a
                      ON a.pokemon_id = p.id
                     AND a.asset_kind = 'official_artwork'
                     AND a.local_path IS NOT NULL
                    WHERE p.is_default = 1 AND a.id IS NULL
                    """
                ).fetchone()[0]
                last_imported_row = connection.execute(
                    """
                    SELECT completed_at FROM import_run
                    WHERE status = 'completed'
                    ORDER BY id DESC LIMIT 1
                    """
                ).fetchone()
                last_imported_at = last_imported_row[0] if last_imported_row else None
                available = pokemon_count > 0 and missing_asset_count == 0
                reason = None if available else "Database needs Pokemon data and official artwork"
                return DatabaseStatus(
                    available, schema_version, last_imported_at, pokemon_count,
                    card_count, missing_asset_count, reason,
                )
            finally:
                connection.close()
        except (OSError, sqlite3.Error, ValueError) as exc:
            return DatabaseStatus(False, None, None, 0, 0, 0, f"Database validation failed: {exc}")


class UsersDatabase:
    """Owns user accounts and collections; never replaced by catalog imports."""

    def __init__(self, path: Path | str = DEFAULT_USERS_DATABASE_PATH):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        connection = self.connect()
        try:
            apply_users_schema(connection)
        finally:
            connection.close()

    def status(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {"available": False, "schema_version": None, "user_count": 0, "card_count": 0, "member_count": 0}
        connection = self.connect()
        try:
            member_count = 0
            try:
                member_count = int(connection.execute("SELECT COUNT(*) FROM account_member").fetchone()[0])
            except sqlite3.Error:
                pass
            return {
                "available": True,
                "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
                "user_count": int(connection.execute("SELECT COUNT(*) FROM app_user").fetchone()[0]),
                "card_count": int(connection.execute("SELECT COUNT(*) FROM user_card").fetchone()[0]),
                "member_count": member_count,
            }
        except sqlite3.Error as exc:
            return {"available": False, "schema_version": None, "user_count": 0,
                    "card_count": 0, "member_count": 0, "reason": str(exc)}
        finally:
            connection.close()