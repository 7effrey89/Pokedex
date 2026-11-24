"""Map provider identities without changing existing catalog/collection IDs."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from contextlib import closing
from typing import Any

from src.db.database import SqliteDatabase


def identity(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_value.casefold())


def card_number(value: str) -> str:
    match = re.fullmatch(r"([a-z]*)(\d+)([a-z]*)", value.casefold())
    return f"{match[1]}{int(match[2])}{match[3]}" if match else value.casefold()


# These catalog names differ from TCGdex's English names.
SET_ALIASES = {
    "base1": "base1", "svp": "svp", "hgss2": "hgss2", "hgss3": "hgss3",
    "hgss4": "hgss4", "fut20": "fut2020", "me55c": "30th-c", "sve": "sve",
}


class TcgDexIds:
    def __init__(self, database: SqliteDatabase):
        self.database = database
        self.remote_to_local: dict[str, str] = {}
        self.local_to_remote: dict[str, str] = {}

    def build(self, remote_sets: list[dict[str, Any]]) -> None:
        local_sets = []
        if self.database.path.is_file():
            with closing(self.database.connect(read_only=True)) as connection:
                local_sets = connection.execute("SELECT id, name FROM tcg_set").fetchall()
        by_name: dict[str, list[str]] = defaultdict(list)
        for row in local_sets:
            by_name[identity(row["name"])].append(row["id"])
        occupied = {row["id"] for row in local_sets}
        aliases = {remote: local for local, remote in SET_ALIASES.items() if local in occupied}
        mapping = {}
        for remote in remote_sets:
            if remote["id"] == "rc" and not by_name[identity(remote["name"])]:
                continue
            matches = by_name[identity(remote["name"])]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous catalog set name: {remote['name']}")
            local = aliases.get(remote["id"]) or (matches[0] if matches else None)
            if local is None:
                # Native provider IDs can collide with a different legacy set.
                local = remote["id"]
                if local in occupied:
                    local = f"tcgdex-{local}"
                if local in occupied:
                    raise ValueError(f"Conflicting TCGdex set ID: {local}")
            if local in mapping.values():
                raise ValueError(f"Multiple TCGdex sets map to {local}")
            mapping[remote["id"]] = local
        # The old catalog includes Legendary Treasures' RC cards in bw11.
        if any(row["id"] == "rc" for row in remote_sets) and "rc" not in mapping and "bw11" in mapping:
            mapping["rc"] = mapping["bw11"]
        self.remote_to_local = mapping
        self.local_to_remote = {local: remote for remote, local in mapping.items()}
        if "rc" in mapping and "bw11" in mapping and mapping["rc"] == mapping["bw11"]:
            self.local_to_remote[mapping["bw11"]] = "bw11"

    def remote_sets(self, local_id: str) -> list[str]:
        primary = self.remote_set(local_id)
        return [primary] + [remote for remote, local in self.remote_to_local.items()
                            if local == local_id and remote != primary]

    def remote_set(self, local_id: str) -> str:
        if local_id not in self.local_to_remote:
            raise ValueError(f"Set {local_id} is not available from TCGdex")
        return self.local_to_remote[local_id]

    def local_card(self, remote: dict[str, Any]) -> tuple[str, str]:
        set_id = self.remote_to_local[remote["set"]["id"]]
        number = str(remote["localId"])
        if self.database.path.is_file():
            with closing(self.database.connect(read_only=True)) as connection:
                rows = connection.execute(
                    "SELECT id, number, name FROM tcg_card WHERE set_id = ?", (set_id,),
                ).fetchall()
            matches = [row for row in rows if card_number(row["number"]) == card_number(number)]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous catalog card number: {set_id}/{number}")
            if matches:
                row = matches[0]
                if identity(row["name"]) != identity(remote["name"]):
                    raise ValueError(f"TCGdex card identity mismatch: {row['id']} ({row['name']} vs {remote['name']})")
                return row["id"], row["number"]
        canonical_number = str(int(number)) if number.isdigit() else number
        return f"{set_id}-{canonical_number}", canonical_number

    def card_location(self, local_id: str) -> tuple[str, str]:
        if self.database.path.is_file():
            with closing(self.database.connect(read_only=True)) as connection:
                row = connection.execute(
                    "SELECT set_id, number FROM tcg_card WHERE id = ?", (local_id,),
                ).fetchone()
            if row:
                return self.remote_set(row["set_id"]), row["number"]
        for set_id in sorted(self.local_to_remote, key=len, reverse=True):
            if local_id.startswith(f"{set_id}-"):
                return self.remote_set(set_id), local_id[len(set_id) + 1:]
        raise ValueError(f"Unknown TCG card ID: {local_id}")
