"""Database-backed catalog refresh settings."""

import json
import logging
from pathlib import Path

from src.db.database import PROJECT_ROOT, SqliteDatabase

logger = logging.getLogger(__name__)
TCG_PRICE_REFRESH_INTERVALS = (300, 3600, 86400, 259200, 604800, 0)
PRICE_INTERVAL_KEY = "tcg_price_expiry_seconds"


class CatalogSettings:
    def __init__(self, database: SqliteDatabase | None = None, legacy_config: Path | None = None):
        self.database = database or SqliteDatabase()
        self.database.initialize()
        connection = self.database.connect()
        try:
            existing = connection.execute(
                "SELECT value FROM catalog_setting WHERE key = ?", (PRICE_INTERVAL_KEY,)
            ).fetchone()
            if existing is None:
                seconds = 604800
                legacy_path = legacy_config or PROJECT_ROOT / "cache" / "cache_config.json"
                if legacy_path.is_file():
                    config = json.loads(legacy_path.read_text(encoding="utf-8"))
                    if PRICE_INTERVAL_KEY in config:
                        seconds = int(config[PRICE_INTERVAL_KEY])
                    elif "tcg_price_expiry_days" in config:
                        old_seconds = max(0, int(config["tcg_price_expiry_days"]) * 86400)
                        seconds = min(TCG_PRICE_REFRESH_INTERVALS, key=lambda value: (abs(value - old_seconds), -value))
                    logger.info("Migrating legacy price refresh settings into SQLite")
                if seconds not in TCG_PRICE_REFRESH_INTERVALS:
                    raise ValueError("Unsupported stored TCG price refresh interval")
                connection.execute(
                    "INSERT OR IGNORE INTO catalog_setting (key, value) VALUES (?, ?)",
                    (PRICE_INTERVAL_KEY, str(seconds)),
                )
                connection.commit()
        finally:
            connection.close()

    def get_config(self) -> dict:
        connection = self.database.connect(read_only=True)
        try:
            row = connection.execute(
                "SELECT value FROM catalog_setting WHERE key = ?", (PRICE_INTERVAL_KEY,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Catalog refresh settings have not been initialized")
            return {PRICE_INTERVAL_KEY: int(row["value"]), "storage": "sqlite"}
        finally:
            connection.close()

    def set_tcg_price_expiry_seconds(self, seconds: int) -> None:
        if seconds not in TCG_PRICE_REFRESH_INTERVALS:
            raise ValueError("Unsupported TCG price refresh interval")
        connection = self.database.connect()
        try:
            connection.execute(
                "INSERT INTO catalog_setting (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (PRICE_INTERVAL_KEY, str(seconds)),
            )
            connection.commit()
        finally:
            connection.close()


_settings: CatalogSettings | None = None


def get_catalog_settings() -> CatalogSettings:
    global _settings
    if _settings is None:
        _settings = CatalogSettings()
    return _settings
