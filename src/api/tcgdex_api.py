"""Free, keyless TCGdex access using the existing importer response contracts."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.api.tcgdex_ids import TcgDexIds, card_number
from src.api.tcgdex_normalization import normalize_card, normalize_set
from src.db.database import SqliteDatabase

logger = logging.getLogger(__name__)
TCGDEX_BASE_URL = "https://api.tcgdex.net/v2/en"


class TcgDexClient:
    def __init__(self, database: SqliteDatabase | None = None, *, session: requests.Session | None = None):
        self.base_url = TCGDEX_BASE_URL
        self.timeout = 20
        self.session = session or requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        )))
        self.ids = TcgDexIds(database or SqliteDatabase())
        self._index: list[dict[str, Any]] | None = None
        self._index_at = 0.0
        self._sets: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{path}"
        logger.info("Fetching TCGdex %s", url)
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _ensure_index(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._index is None or time.monotonic() - self._index_at > 300:
                index = self._get("sets")
                if not isinstance(index, list) or any(
                    not isinstance(item, dict) or not item.get("id") or not item.get("name") for item in index
                ):
                    raise ValueError("Invalid TCGdex set index")
                index = [item for item in index if not re.fullmatch(r"(?:[AB]\d+[a-z]?|P-[AB])", item["id"])]
                self.ids.build(index)
                self._index = index
                self._index_at = time.monotonic()
                self._sets.clear()
            return self._index

    def _set(self, remote_id: str) -> dict[str, Any]:
        with self._lock:
            if remote_id not in self._sets:
                value = self._get(f"sets/{quote(remote_id, safe='')}")
                if not isinstance(value, dict) or value.get("id") != remote_id or not isinstance(value.get("cards"), list):
                    raise ValueError(f"Invalid TCGdex set response: {remote_id}")
                self._sets[remote_id] = value
            return self._sets[remote_id]

    def _card(self, remote_id: str) -> dict[str, Any]:
        value = self._get(f"cards/{quote(remote_id, safe='')}")
        if not isinstance(value, dict) or value.get("id") != remote_id:
            raise ValueError(f"Invalid TCGdex card response: {remote_id}")
        card_id, number = self.ids.local_card(value)
        set_id = value["set"]["id"]
        return normalize_card(value, card_id, number, self._set_data(self.ids.remote_to_local[set_id]))

    def _set_data(self, local_id: str) -> dict[str, Any]:
        members = self.ids.remote_sets(local_id)
        result = normalize_set(self._set(members[0]), local_id)
        if len(members) > 1:
            result["total"] = sum(len(self._set(member)["cards"]) for member in members)
        result["_source"] = "tcgdex"
        return result

    @staticmethod
    def _page(page: int, page_size: int) -> None:
        if page < 1 or page_size < 1:
            raise ValueError("TCG page and page size must be positive")

    def get_sets(self, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        self._page(page, page_size)
        index = self._ensure_index()
        local_ids = list(dict.fromkeys(self.ids.remote_to_local[item["id"]] for item in index))
        items = local_ids[(page - 1) * page_size:page * page_size]
        return {"data": [self._set_data(local_id) for local_id in items], "totalCount": len(local_ids)}

    def search_cards_by_set(self, set_id: str, page: int = 1, page_size: int = 250) -> dict[str, Any]:
        self._page(page, page_size)
        self._ensure_index()
        cards = [card for member in self.ids.remote_sets(set_id) for card in self._set(member)["cards"]]
        batch = cards[(page - 1) * page_size:page * page_size]
        return {"data": [self._card(card["id"]) for card in batch], "totalCount": len(cards)}

    def get_card(self, card_id: str) -> dict[str, Any]:
        self._ensure_index()
        set_id, number = self.ids.card_location(card_id)
        local_set = self.ids.remote_to_local[set_id]
        cards = [card for member in self.ids.remote_sets(local_set) for card in self._set(member)["cards"]]
        matches = [card for card in cards if card_number(str(card["localId"])) == card_number(number)]
        if len(matches) != 1:
            raise ValueError(f"TCGdex cannot uniquely resolve card {card_id}")
        card = self._card(matches[0]["id"])
        if card["id"] != card_id:
            raise ValueError(f"TCGdex resolved {card_id} to a different catalog ID: {card['id']}")
        return {"data": card}

    def search_cards(self, query: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        return self.search_cards_advanced(name=query, page=page, page_size=page_size)

    def search_cards_advanced(
        self, name: str | None = None, types: list[str] | None = None,
        subtypes: list[str] | None = None, hp_min: int | None = None,
        hp_max: int | None = None, legality: str | None = None,
        retreat_cost: int | None = None, page: int = 1, page_size: int = 10,
        rarity: str | None = None,
    ) -> dict[str, Any]:
        self._page(page, page_size)
        if hp_min is not None and hp_max is not None and hp_min > hp_max:
            raise ValueError("Minimum HP cannot exceed maximum HP")
        self._ensure_index()
        params: dict[str, Any] = {
            "pagination:page": page, "pagination:itemsPerPage": page_size,
            "sort:field": "releaseDate", "sort:order": "DESC",
        }
        if name:
            params["name"] = f"eq:{name[1:]}" if name.startswith("!") else f"like:{name}"
        if types:
            params["types"] = "eq:" + "|".join(types)
        if subtypes:
            stages = {"Basic": "Basic", "Stage1": "Stage1", "Stage 1": "Stage1",
                      "Stage2": "Stage2", "Stage 2": "Stage2"}
            for subtype in subtypes:
                params["stage" if subtype in stages else "suffix"] = f"eq:{stages.get(subtype, subtype)}"
        if hp_min is not None:
            params["hp"] = f"gte:{hp_min}"
        elif hp_max is not None:
            params["hp"] = f"lte:{hp_max}"
        if legality:
            params[f"legal.{legality}"] = "true"
        if retreat_cost is not None:
            params["retreat"] = f"eq:{retreat_cost}"
        if rarity:
            params["rarity"] = f"eq:{rarity}"
        # TCGdex lists briefs without totals. Fetch the filtered index once so
        # the downstream refresh can paginate completely even with both HP bounds.
        params.pop("pagination:page")
        params.pop("pagination:itemsPerPage")
        briefs = self._get("cards", params)
        if not isinstance(briefs, list):
            raise ValueError("Invalid TCGdex card search response")
        if hp_min is not None and hp_max is not None:
            cards = [self._card(brief["id"]) for brief in briefs]
            cards = [card for card in cards if card.get("hp") is not None and card["hp"] <= hp_max]
            return {"data": cards[(page - 1) * page_size:page * page_size], "totalCount": len(cards)}
        batch = briefs[(page - 1) * page_size:page * page_size]
        return {"data": [self._card(brief["id"]) for brief in batch], "totalCount": len(briefs)}
