"""Resolve every mutable storage location from one environment-aware root.

Local development keeps data inside the repository. Azure App Service sets
POKEDEX_DATA_ROOT to /home/data so persistent storage survives container
replacement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AZURE_PERSISTENT_ROOT = Path("/home/data")


def _resolve_data_root() -> Path:
    configured = os.environ.get("POKEDEX_DATA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.environ.get("WEBSITE_SITE_NAME"):
        return AZURE_PERSISTENT_ROOT
    return PROJECT_ROOT


@dataclass(frozen=True)
class StoragePaths:
    """Absolute locations for catalog, user, asset, snapshot, and backup data."""

    data_root: Path

    @property
    def catalog_database(self) -> Path:
        return self.data_root / "data" / "pokedex.sqlite3"

    @property
    def users_database(self) -> Path:
        return self.data_root / "data" / "users.sqlite3"

    @property
    def pokemon_assets(self) -> Path:
        return self.data_root / "data" / "assets" / "pokemon"

    @property
    def cry_assets(self) -> Path:
        return self.data_root / "data" / "assets" / "cries"

    @property
    def tcg_images(self) -> Path:
        return self.data_root / "data" / "assets" / "tcg"

    @property
    def tcg_index(self) -> Path:
        return self.data_root / "data" / "index"

    @property
    def snapshots(self) -> Path:
        return self.data_root / "data" / "snapshots"

    @property
    def backups(self) -> Path:
        return self.data_root / "data" / "backups"

    @property
    def profile_images(self) -> Path:
        return self.data_root / "data" / "assets" / "profiles"

    def asset_directories(self) -> dict[str, Path]:
        return {
            "pokemon_images": self.pokemon_assets,
            "pokemon_cries": self.cry_assets,
            "tcg_images": self.tcg_images,
            "profile_images": self.profile_images,
        }

    def ensure_directories(self) -> None:
        for path in (
            self.catalog_database.parent, self.pokemon_assets, self.cry_assets,
            self.tcg_images, self.tcg_index, self.snapshots, self.backups, self.profile_images,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def relative_to_root(self, path: Path) -> str:
        """Return a portable identifier for a stored file."""
        resolved = Path(path).resolve()
        for base in (self.data_root, PROJECT_ROOT):
            try:
                return resolved.relative_to(base).as_posix()
            except ValueError:
                continue
        return resolved.as_posix()

    def resolve_stored(self, relative_path: str) -> Path | None:
        """Resolve a stored relative path, rejecting anything outside known roots."""
        if not relative_path:
            return None
        candidates = (self.data_root / relative_path, PROJECT_ROOT / relative_path)
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            for base in (self.data_root, PROJECT_ROOT):
                try:
                    resolved.relative_to(base)
                except ValueError:
                    continue
                if resolved.is_file():
                    return resolved
        return None


_STORAGE_PATHS: StoragePaths | None = None


def get_storage_paths() -> StoragePaths:
    global _STORAGE_PATHS
    if _STORAGE_PATHS is None:
        _STORAGE_PATHS = StoragePaths(_resolve_data_root())
    return _STORAGE_PATHS
