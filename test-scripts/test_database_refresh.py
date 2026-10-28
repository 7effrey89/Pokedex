"""Refresh requests must fetch upstream, persist SQLite, and never write runtime JSON caches."""

import importlib.util
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

from src.config.paths import StoragePaths
from src.db.database import SqliteDatabase
from src.db.importer import SqliteImporter
from src.db.pokemon_repository import SqlitePokemonRepository
from src.db.tcg_repository import SqliteTcgRepository
from src.routes import cache_routes, pokeapi_routes
from src.services.catalog_refresh import CatalogRefreshService
from src.services.catalog_settings import CatalogSettings
from src.tools.handlers import pokemon_handlers, tcg_handlers


class DatabaseRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = StoragePaths(self.root)
        self.database = SqliteDatabase(self.paths.catalog_database)
        self.database.initialize()
        with closing(self.database.connect()) as connection:
            connection.execute("INSERT INTO pokemon_species (id, name) VALUES (25, 'pikachu'), (26, 'raichu')")
            connection.execute(
                "INSERT INTO pokemon (id, species_id, name, display_order, is_default) VALUES (25, 25, 'pikachu', 25, 1)"
            )
            connection.execute("INSERT INTO tcg_set (id, name) VALUES ('base1', 'Old Set')")
            connection.execute(
                "INSERT INTO tcg_card (id, set_id, name, number) VALUES ('base1-1', 'base1', 'Old Name', '1')"
            )
            connection.execute(
                "INSERT INTO card_asset (card_id, asset_kind, source_url, local_path) "
                "VALUES ('base1-1', 'large', 'https://example.test/large.png', 'data/assets/tcg/existing.png')"
            )
            connection.commit()
        self.settings = CatalogSettings(self.database, self.root / "missing.json")
        self.repository = SqliteTcgRepository(self.database)
        self.client = Mock()
        for target, value in (
            ("src.services.tcg_refresh.get_storage_paths", self.paths),
            ("src.services.catalog_refresh.get_storage_paths", self.paths),
            ("src.tools.handlers.tcg_handlers.sqlite_tcg_repository", self.repository),
        ):
            patcher = patch(target, return_value=value) if target.endswith("get_storage_paths") else patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, value in (
            ("src.tools.handlers.tcg_handlers.get_catalog_settings", self.settings),
            ("src.tools.handlers.tcg_handlers._get_tcg_client", self.client),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def card(self, card_id="base1-1"):
        return {
            "id": card_id, "name": "Fresh Pikachu", "number": card_id.split("-")[-1],
            "set": {"id": "base1", "name": "Fresh Set", "total": 2},
            "nationalPokedexNumbers": [25],
            "images": {"large": "https://example.test/large.png", "small": "https://example.test/small.png"},
            "tcgplayer": {"url": "https://example.test/market", "updatedAt": "2026/10/28", "prices": {"normal": {"market": 42.5, "low": 40}}},
            "cardmarket": {"prices": {"averageSellPrice": 39.5}},
        }

    def test_set_refresh_fetches_every_page_and_preserves_unchanged_asset(self):
        self.client.search_cards_by_set.side_effect = [
            {"data": [self.card()], "totalCount": 2},
            {"data": [self.card("base1-2")], "totalCount": 2},
        ]
        result = tcg_handlers.handle_search_cards_by_set("base1", force_refresh=True, slim=True, limit=1)
        self.assertEqual(self.client.search_cards_by_set.call_count, 2)
        self.assertEqual(result["total_count"], 2)
        self.assertEqual(len(result["cards"]), 1)
        self.assertEqual(result["cards"][0]["name"], "Fresh Pikachu")
        with closing(self.database.connect(read_only=True)) as connection:
            asset = connection.execute(
                "SELECT local_path FROM card_asset WHERE card_id = 'base1-1' AND asset_kind = 'large'"
            ).fetchone()
            self.assertEqual(asset["local_path"], "data/assets/tcg/existing.png")
        self.assertFalse((self.root / "cache").exists())

    def test_search_refresh_persists_filters_and_normal_reads_do_not_fetch(self):
        self.client.search_cards_advanced.return_value = {"data": [self.card()], "totalCount": 1}
        result = tcg_handlers.handle_search_pokemon_cards("Pikachu", rarity=None, force_refresh=True)
        self.assertEqual(result["cards"][0]["name"], "Fresh Pikachu")
        self.client.search_cards_advanced.assert_called_once_with(
            name="Pikachu", types=None, hp_min=None, hp_max=None, rarity=None, page=1, page_size=250
        )
        self.client.reset_mock()
        self.assertEqual(tcg_handlers.handle_search_pokemon_cards("Pikachu")["total_count"], 1)
        self.client.search_cards_advanced.assert_not_called()

    def test_refreshed_image_url_does_not_reuse_an_old_local_file(self):
        card = self.card()
        card["images"]["large"] = "https://example.test/replacement.png"
        self.client.get_card.return_value = {"data": card}
        tcg_handlers.handle_get_card_price("base1-1", force_refresh=True)
        with closing(self.database.connect(read_only=True)) as connection:
            asset = connection.execute(
                "SELECT source_url, local_path FROM card_asset "
                "WHERE card_id = 'base1-1' AND asset_kind = 'large'"
            ).fetchone()
            self.assertEqual(asset["source_url"], card["images"]["large"])
            self.assertIsNone(asset["local_path"])

    def test_sets_refresh_updates_existing_sets_and_adds_new_sets(self):
        self.client.get_sets.side_effect = [
            {"data": [{"id": "base1", "name": "Updated Set"}], "totalCount": 2},
            {"data": [{"id": "base2", "name": "New Set"}], "totalCount": 2},
        ]
        result = tcg_handlers.handle_get_tcg_sets(force_refresh=True)
        self.assertEqual({item["name"] for item in result["sets"]}, {"Updated Set", "New Set"})
        self.assertEqual(self.client.get_sets.call_count, 2)

    def test_price_refresh_ttl_force_refresh_and_unlimited_use_database(self):
        self.client.get_card.return_value = {"data": self.card()}
        first = tcg_handlers.handle_get_card_price("base1-1")
        self.assertEqual(first["card"]["tcgplayer"]["prices"]["normal"]["market"], 42.5)
        self.assertEqual(first["card"]["cardmarket"]["prices"]["averageSellPrice"], 39.5)
        self.assertEqual(first["card"]["image"], "/api/tcg/card-image/base1-1/small")
        self.assertEqual(tcg_handlers.handle_get_card_price("base1-1"), first)
        self.assertEqual(self.client.get_card.call_count, 1)
        tcg_handlers.handle_get_card_price("base1-1", force_refresh=True)
        self.assertEqual(self.client.get_card.call_count, 2)
        with closing(self.database.connect()) as connection:
            connection.execute("UPDATE tcg_card SET last_refreshed_at = '2000-01-01T00:00:00+00:00'")
            connection.commit()
        tcg_handlers.handle_get_card_price("base1-1")
        self.assertEqual(self.client.get_card.call_count, 3)
        self.settings.set_tcg_price_expiry_seconds(0)
        with closing(self.database.connect()) as connection:
            connection.execute("UPDATE tcg_card SET last_refreshed_at = NULL")
            connection.commit()
        tcg_handlers.handle_get_card_price("base1-1")
        self.assertEqual(self.client.get_card.call_count, 3)
        self.assertFalse((self.root / "cache").exists())

    def test_failed_pagination_does_not_partially_update_database(self):
        self.client.search_cards_by_set.side_effect = [
            {"data": [self.card()], "totalCount": 2}, None,
        ]
        with self.assertRaises(RuntimeError):
            tcg_handlers.handle_search_cards_by_set("base1", force_refresh=True)
        self.assertEqual(self.repository.get_card("base1-1")["name"], "Old Name")

    def test_persistence_failure_rolls_back_previous_card_changes(self):
        invalid = self.card("base1-2")
        invalid["types"] = None
        self.client.search_cards_by_set.return_value = {"data": [self.card(), invalid], "totalCount": 2}
        with self.assertRaises(TypeError):
            tcg_handlers.handle_search_cards_by_set("base1", force_refresh=True)
        self.assertEqual(self.repository.get_card("base1-1")["name"], "Old Name")

    def test_pokemon_species_evolution_and_type_refreshes_are_persisted_by_routes(self):
        app = Flask(__name__)
        app.register_blueprint(pokeapi_routes.pokeapi_bp)
        repository = SqlitePokemonRepository(self.database)
        service = CatalogRefreshService(self.database, self.paths.snapshots)
        with closing(self.database.connect()) as connection:
            connection.execute("INSERT INTO type (id, name) VALUES (13, 'electric'), (5, 'ground')")
            connection.commit()
        payloads = [
            ("/25", {"id": 25, "name": "pikachu", "height": 99, "species": {"url": "https://pokeapi.co/api/v2/pokemon-species/25/"}}),
            ("/species/25", {"id": 25, "name": "pikachu", "capture_rate": 77, "evolution_chain": {"url": "https://pokeapi.co/api/v2/evolution-chain/10/"}}),
            ("/evolution-chain/10", {"id": 10, "chain": {"species": {"name": "pikachu"}, "evolves_to": [{"species": {"name": "raichu"}, "evolution_details": [{"min_level": 31}]}]}}),
            ("/type/electric", {"id": 13, "name": "electric", "damage_relations": {"double_damage_from": [{"name": "ground", "url": "https://pokeapi.co/api/v2/type/5/"}]}}),
        ]
        with patch.object(pokeapi_routes, "SqlitePokemonRepository", return_value=repository), \
                patch.object(pokeapi_routes, "CatalogRefreshService", return_value=service):
            with app.test_client() as client:
                for path, payload in payloads:
                    response = Mock(status_code=200)
                    response.json.return_value = payload
                    with patch.object(pokeapi_routes.requests, "get", return_value=response) as upstream:
                        fresh = client.get(f"/api/pokemon{path}?refresh=1")
                        self.assertEqual(fresh.status_code, 200, fresh.get_json())
                        self.assertEqual(client.get(f"/api/pokemon{path}").status_code, 200)
                        upstream.assert_called_once()
                self.assertEqual(client.get("/api/pokemon/25").get_json()["height"], 99)
                self.assertEqual(client.get("/api/pokemon/species/25").get_json()["capture_rate"], 77)
                chain = client.get("/api/pokemon/evolution-chain/10").get_json()
                self.assertEqual(chain["chain"]["evolves_to"][0]["evolution_details"][0]["min_level"], 31)
                damage = client.get("/api/pokemon/type/electric").get_json()["damage_relations"]
                self.assertEqual(damage["double_damage_from"][0]["name"], "ground")
        self.assertFalse((self.root / "cache").exists())

    def test_acquisition_scripts_write_import_seeds_not_runtime_cache(self):
        project = Path(__file__).resolve().parents[1]
        for filename in (
            "01-download_raw_pokemontcgapi_to_seed.py",
            "02-download_raw_pokeapi_to_seed.py",
        ):
            spec = importlib.util.spec_from_file_location("seed_script", project / "scripts" / filename)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if filename.startswith("01"):
                self.assertEqual(module.DATA_DIR, project / "seeds")
                self.assertEqual(module.TCG_SEED_DIR, project / "seeds" / "tcg")
                with patch.object(module, "TCG_SEED_DIR", self.root / "seeds" / "tcg"):
                    payload = {"data": [self.card()]}
                    path = module.save_tcg_cache(25, "pikachu", payload, "cards", {})
                    self.assertEqual(path.name, "tcg-025-pikachu.json")
                    self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["response"], payload)
            else:
                self.assertEqual(module.DATA_FILE, project / "seeds" / "pokemon_list.json")
                self.assertEqual(module.POKEAPI_SEED_DIR, project / "seeds" / "pokeapi")
                resources = (
                    ("pokemon/25", {"id": 25, "name": "pikachu"}, "pokeapi-0025-pikachu.json"),
                    ("pokemon-species/25", {"id": 25, "name": "pikachu"}, "pokeapi-species-0025-pikachu.json"),
                    ("evolution-chain/10", {"id": 10}, "pokeapi-evolution-chain-0010.json"),
                    ("type/electric", {"id": 13, "name": "electric"}, "pokeapi-type-electric.json"),
                )
                for resource, payload, expected in resources:
                    with patch.object(module, "POKEAPI_SEED_DIR", self.root / "seeds" / "pokeapi"), \
                            patch.object(module, "fetch_json", return_value=payload) as fetch:
                        self.assertEqual(module.ensure_cached(Mock(), resource, {}, resource, False), ("fetched", payload))
                        self.assertTrue((module.POKEAPI_SEED_DIR / expected).is_file())
                        self.assertEqual(module.ensure_cached(Mock(), resource, {}, resource, False), ("cached", payload))
                        fetch.assert_called_once()
        self.assertFalse((self.root / "cache").exists())

    def test_removed_clear_and_invalidate_endpoints_do_not_exist(self):
        app = Flask(__name__)
        app.register_blueprint(cache_routes.cache_bp)
        with app.test_client() as client:
            for path in ("clear", "invalidate", "enable", "pokeapi"):
                self.assertEqual(client.post(f"/api/cache/{path}", json={}).status_code, 404)

    def test_refresh_policy_route_validates_and_persists_database_settings(self):
        app = Flask(__name__)
        app.register_blueprint(cache_routes.cache_bp)
        with patch.object(cache_routes, "get_catalog_settings", return_value=self.settings), \
                app.test_client() as client:
            for body in ([1], {}, {"seconds": "300"}, {"seconds": True}, {"seconds": -1}):
                with self.subTest(body=body):
                    self.assertEqual(client.post("/api/cache/expiry", json=body).status_code, 400)
            response = client.post("/api/cache/expiry", json={"seconds": 300})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["config"]["storage"], "sqlite")
            self.assertEqual(CatalogSettings(self.database).get_config()["tcg_price_expiry_seconds"], 300)

    def test_settings_migrate_once_and_survive_catalog_replacement(self):
        legacy = self.root / "old-config.json"
        legacy.write_text(json.dumps({"tcg_price_expiry_seconds": 300}), encoding="utf-8")
        with closing(self.database.connect()) as connection:
            connection.execute("DELETE FROM catalog_setting")
            connection.commit()
        self.assertEqual(CatalogSettings(self.database, legacy).get_config()["tcg_price_expiry_seconds"], 300)
        legacy.unlink()
        target = SqliteDatabase(self.root / "replacement.sqlite3")
        target.initialize()
        importer = SqliteImporter(self.root, self.database.path, self.root, self.root, self.root)
        with closing(target.connect()) as connection:
            importer._preserve_settings(connection)
            connection.commit()
        self.assertEqual(CatalogSettings(target).get_config()["tcg_price_expiry_seconds"], 300)

    def test_pokemon_tool_uses_current_database_data_without_file_cache(self):
        tools = pokemon_handlers.pokemon_api_client
        with patch.object(tools, "repository", SqlitePokemonRepository(self.database)), \
                patch.object(pokemon_handlers.tool_manager, "is_tool_enabled", return_value=True):
            result = pokemon_handlers.handle_get_pokemon("pikachu")
            self.assertEqual(result["id"], 25)
        self.assertFalse((self.root / "cache").exists())


if __name__ == "__main__":
    unittest.main()
