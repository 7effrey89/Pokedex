"""Bounded persistent logs for catalog operations, excluding conversations."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_catalog_logging(log_directory: Path) -> Path:
    log_directory = log_directory.resolve()
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "catalog.log"
    names = (
        "src.services.catalog_ingest",
        "src.services.catalog_refresh",
        "src.services.asset_manager",
    )
    if any(
        isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(log_path.resolve())
        for handler in logging.getLogger(names[0]).handlers
    ):
        return log_path
    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    for name in names:
        logging.getLogger(name).addHandler(handler)
    return log_path
