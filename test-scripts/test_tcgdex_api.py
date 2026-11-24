"""Provider migration regressions: stable IDs, complete pages, and real price shapes."""

import copy
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

import requests

from src.api.pokemon_tcg_api import PokemonTCGTools
from src.api.tcgdex_normalization import normalize_prices
from src.db.database import SqliteDatabase


class TcgDexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = SqliteDatabase(Path(temporary.name) / "catalog.sqlite3")
        self.database.initialize()
        with closing(self.database.connect()) as connection:
            connection.executemany("INSERT INTO tcg_set (id, name) VALUES (?, ?)", [
                ("me3", "Perfect Order"), ("base2", "Base Set 2"),
                ("legacy-jungle", "Jungle"), ("bw11", "Legendary Treasures"),
            ])
            connection.executemany(
                "INSERT INTO tcg_card (id, set_id, name, number) VALUES (?, ?, ?, ?)", [
                    ("me3-1", "me3", "Spinarak", "1"),
                    ("base2-1", "base2", "Alakazam", "1"),
                    ("legacy-jungle-1", "legacy-jungle", "Clefable", "1"),
                    ("bw11-RC1", "bw11", "Snivy", "RC1"),
                ],
            )
            connection.commit()
        self.index = [
            {"id": "me03", "name": "Perfect Order"}, {"id": "base2", "name": "Jungle"},
            {"id": "base4", "name": "Base Set 2"}, {"id": "bw11", "name": "Legendary Treasures"},
            {"id": "rc", "name": "Radiant Collection"}, {"id": "A1", "name": "Genetic Apex"},
        ]
        self.cards = {
            "me03-001": self.card("me03-001", "me03", "001", "Spinarak", hp=60),
            "me03-002": self.card("me03-002", "me03", "002", "Ariados", hp=100),
            "base2-1": self.card("base2-1", "base2", "1", "Clefable"),
            "base4-1": self.card("base4-1", "base4", "1", "Alakazam"),
            "rc-RC01": self.card("rc-RC01", "rc", "RC01", "Snivy"),
        }
        self.sets = {}
        for item in self.index:
            self.sets[item["id"]] = {
                **item, "releaseDate": "2026-03-27", "serie": {"name": "Mega Evolution"},
                "cardCount": {"official": 88, "total": 124},
                "cards": [{"id": c["id"], "localId": c["localId"], "name": c["name"]}
                          for c in self.cards.values() if c["set"]["id"] == item["id"]],
            }
        self.session = Mock()
        self.session.get.side_effect = self.get
        self.client = PokemonTCGTools(self.database, session=self.session)

    @staticmethod
    def card(card_id, set_id, number, name, hp=60):
        return {
            "id": card_id, "set": {"id": set_id}, "localId": number, "name": name,
            "category": "Pokemon", "hp": hp, "types": ["Grass"], "stage": "Basic",
            "image": "https://assets.tcgdex.net/en/me/me03/001", "dexId": [167],
            "attacks": [{"name": "Gooey Thread", "cost": ["Grass"], "damage": 0, "effect": "No retreat."}],
            "pricing": {
                "tcgplayer": {"unit": "USD", "updated": "2026-11-23T22:24:06Z",
                              "normal": {"productId": 684397, "marketPrice": 0.07, "midPrice": 0.15},
                              "reverse-holofoil": {"marketPrice": 0.17}},
                "cardmarket": {"unit": "EUR", "updated": "2026-11-23T22:24:06Z",
                               "idProduct": 877413, "avg": 0.02, "low": 0, "avg-holo": None,
                               "trend-holo": 0.06},
            },
        }

    def get(self, url, **kwargs):
        path = url.removeprefix(self.client.base_url + "/")
        if path == "sets":
            payload = self.index
        elif path.startswith("sets/"):
            payload = self.sets[path.removeprefix("sets/")]
        elif path.startswith("cards/"):
            payload = self.cards[path.removeprefix("cards/")]
        else:
            payload = self.sets["me03"]["cards"]
        result = Mock()
        result.json.return_value = copy.deepcopy(payload)
        return result

    def test_card_prices_metadata_and_ids_match_existing_contract(self):
        card = self.client.get_card("me3-1")["data"]
        self.assertEqual("me3-1", card["id"])
        self.assertEqual("1", card["number"])
        self.assertEqual("me3", card["set"]["id"])
        self.assertEqual(0.07, card["tcgplayer"]["prices"]["normal"]["market"])
        self.assertEqual(0.17, card["tcgplayer"]["prices"]["reverseHolofoil"]["market"])
        self.assertEqual(0, card["cardmarket"]["prices"]["lowPrice"])
        self.assertNotIn("reverseHoloSell", card["cardmarket"]["prices"])
        self.assertEqual("https://www.tcgplayer.com/product/684397", card["tcgplayer"]["url"])
        self.assertEqual("0", card["attacks"][0]["damage"])
        self.assertEqual("No retreat.", card["attacks"][0]["text"])
        self.assertEqual([167], card["nationalPokedexNumbers"])
        self.assertEqual("Pok\u00e9mon", card["supertype"])
        for call in self.session.get.call_args_list:
            self.assertTrue(call.args[0].startswith("https://api.tcgdex.net/"))
            self.assertNotIn("headers", call.kwargs)

    def test_set_id_collisions_and_prefixed_card_numbers_are_preserved(self):
        self.assertEqual("Clefable", self.client.get_card("legacy-jungle-1")["data"]["name"])
        self.assertEqual("Alakazam", self.client.get_card("base2-1")["data"]["name"])
        card = self.client.get_card("bw11-RC1")["data"]
        self.assertEqual("bw11-RC1", card["id"])
        self.assertEqual("bw11", card["set"]["id"])
        self.assertEqual("Legendary Treasures", card["set"]["name"])
        sets = self.client.get_sets(page_size=250)["data"]
        self.assertNotIn("A1", {item["id"] for item in sets})
        self.assertNotIn("rc", {item["id"] for item in sets})

    def test_pagination_and_search_filters_return_complete_counts(self):
        first = self.client.search_cards_by_set("me3", page=1, page_size=1)
        second = self.client.search_cards_by_set("me3", page=2, page_size=1)
        self.assertEqual(2, first["totalCount"])
        self.assertEqual("me3-1", first["data"][0]["id"])
        self.assertEqual("me3-2", second["data"][0]["id"])
        self.assertEqual([], self.client.search_cards_by_set("me3", page=3, page_size=1)["data"])
        result = self.client.search_cards_advanced(name="!Spinarak", types=["Grass"],
                                                 hp_min=50, hp_max=70, page_size=1)
        self.assertEqual(1, result["totalCount"])
        search = next(call for call in self.session.get.call_args_list if call.args[0].endswith("/cards"))
        self.assertEqual("eq:Spinarak", search.kwargs["params"]["name"])
        self.assertEqual("eq:Grass", search.kwargs["params"]["types"])
        self.assertEqual("gte:50", search.kwargs["params"]["hp"])

    def test_upstream_failures_and_identity_mismatches_are_not_hidden(self):
        self.cards["me03-001"]["name"] = "Wrong Pokemon"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.client.get_card("me3-1")
        self.session.get.side_effect = requests.HTTPError("503 unavailable")
        with self.assertRaises(requests.HTTPError):
            self.client.search_cards("Spinarak")

    def test_missing_invalid_prices_and_unexpected_currency(self):
        prices = normalize_prices({"tcgplayer": {"unit": "USD", "normal": {
            "marketPrice": None, "midPrice": float("nan"), "lowPrice": -1, "highPrice": True,
        }}})
        self.assertEqual({}, prices["tcgplayer"]["prices"])
        with self.assertRaisesRegex(ValueError, "currency"):
            normalize_prices({"tcgplayer": {"unit": "EUR", "normal": {"marketPrice": 1}}})


if __name__ == "__main__":
    unittest.main()
