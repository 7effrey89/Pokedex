"""Catalog imports must upsert rows without replacing a populated database."""

import sqlite3
import hashlib
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.config.paths import StoragePaths
from src.db.database import SqliteDatabase
from src.services.backup_service import BackupService


class CatalogMergeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.source = StoragePaths(root / "source")
        self.target = StoragePaths(root / "target")
        for paths, incoming in ((self.source, True), (self.target, False)):
            self.populate(paths, incoming)

    @staticmethod
    def populate(paths, incoming):
        database = SqliteDatabase(paths.catalog_database)
        database.initialize()
        with closing(database.connect()) as connection, connection:
            stamp = "2026-10-01T10:00:00Z" if incoming else "2026-10-28T10:00:00+00:00"
            prefix = "incoming" if incoming else "existing"
            connection.execute("INSERT INTO catalog_setting VALUES ('tcg_price_refresh_seconds', ?)",
                               ("60" if incoming else "300",))
            connection.executemany("INSERT INTO type VALUES (?, ?)",
                                   [(1, "electric"), (2, "grass")] if incoming else [(1, "water"), (2, "electric")])
            connection.execute("INSERT INTO ability VALUES (?, 'static')", (1 if incoming else 7,))
            connection.execute("INSERT INTO stat VALUES (?, 'hp')", (1 if incoming else 8,))
            connection.execute("INSERT INTO evolution_chain VALUES (10, NULL)")
            connection.execute(
                "INSERT INTO pokemon_species (id, name, evolution_chain_id, last_refreshed_at) VALUES (25, 'pikachu', 10, ?)",
                (stamp,),
            )
            connection.execute(
                "INSERT INTO pokemon (id, species_id, name, display_order, height_decimetres, last_refreshed_at) "
                "VALUES (25, 25, 'pikachu', 25, ?, ?)", (9 if incoming else 4, stamp),
            )
            connection.execute("INSERT INTO pokemon_type VALUES (25, ?, 1)", (1 if incoming else 2,))
            connection.execute("INSERT INTO pokemon_ability VALUES (25, ?, 1, 0)", (1 if incoming else 7,))
            connection.execute("INSERT INTO pokemon_stat VALUES (25, ?, ?, 0)", (1 if incoming else 8, 99 if incoming else 35))
            connection.execute("INSERT INTO evolution_node VALUES (?, 10, 25, NULL, 0)", (1 if incoming else 70,))
            connection.execute(
                "INSERT INTO tcg_set (id, name, api_updated_at) VALUES ('test', ?, ?)",
                (f"{prefix} set", "2026/10/01" if incoming else "2026/10/28"),
            )
            connection.execute(
                "INSERT INTO tcg_card (id, set_id, name, number, last_refreshed_at) VALUES ('test-1', 'test', ?, '1', ?)",
                (f"{prefix} card", stamp),
            )
            connection.execute("INSERT INTO card_type VALUES ('test-1', ?, 1)", (1 if incoming else 2,))
            connection.execute("INSERT INTO card_pokemon VALUES ('test-1', 25)")
            connection.execute(
                "INSERT INTO card_attack (id, card_id, name, sort_order) VALUES (?, 'test-1', ?, 0)",
                (1 if incoming else 90, f"{prefix} attack"),
            )
            connection.execute("INSERT INTO card_attack_cost VALUES (?, ?, 1)",
                               (1 if incoming else 90, "Grass" if incoming else "Lightning"))
            connection.execute(
                "INSERT INTO card_market_listing VALUES (?, 'test-1', 'tcgplayer', NULL, ?)",
                (99 if incoming else 1, "2026/10/01" if incoming else "2026/10/28"),
            )
            connection.execute("INSERT INTO card_price VALUES (?, 'normal', 'market', ?, 'USD')",
                               (99 if incoming else 1, 5 if incoming else 50))
            connection.execute(
                "INSERT INTO card_asset (id, card_id, asset_kind, source_url, local_path) VALUES (1, 'test-1', 'large', ?, ?)",
                (f"https://example.test/{prefix}.png", f"data/assets/tcg/{prefix}.png"),
            )
            connection.execute(
                "INSERT INTO import_run VALUES (1, ?, ?, 'completed', 'fixture', 3, NULL)", (prefix, prefix),
            )
            connection.execute(
                "INSERT INTO import_file VALUES (1, 1, 'tcg', 'cards', 'seeds/tcg/cards.json', 'hash', NULL, ?, 1)",
                (prefix,),
            )
            if incoming:
                connection.execute(
                    "INSERT INTO pokemon_species (id, name, evolution_chain_id) VALUES (26, 'raichu', 10)"
                )
                connection.execute("INSERT INTO evolution_node VALUES (2, 10, 26, 1, 1)")
                connection.execute("INSERT INTO evolution_condition (id, node_id, trigger_name) VALUES (1, 2, 'use-item')")
                connection.execute(
                    "INSERT INTO tcg_card (id, set_id, name, number) VALUES ('new-card', 'test', 'New card', '2')"
                )
                connection.execute(
                    "INSERT INTO card_market_listing VALUES (1, 'test-1', 'cardmarket', NULL, '2026/10/28')"
                )
                connection.execute("INSERT INTO card_price VALUES (1, 'default', 'trendPrice', 7, 'EUR')")
            else:
                connection.execute(
                    "INSERT INTO tcg_card (id, set_id, name, number) VALUES ('local-only', 'test', 'Local card', '9')"
                )
                connection.execute(
                    "INSERT INTO card_market_listing VALUES (99, 'local-only', 'tcgplayer', NULL, '2026/10/28')"
                )
                connection.execute("CREATE TABLE local_marker (value TEXT)")
                connection.execute("INSERT INTO local_marker VALUES ('must survive')")
        paths.tcg_images.mkdir(parents=True, exist_ok=True)
        (paths.tcg_images / f"{prefix}.png").write_bytes(f"{prefix} asset".encode())

    def restore(self):
        bundle = BackupService(self.source).create_backup(["catalog_database"])
        return BackupService(self.target).restore_backup(bundle)["catalog_merge"]

    def query(self, sql, parameters=()):
        with closing(sqlite3.connect(self.target.catalog_database)) as connection:
            return connection.execute(sql, parameters).fetchall()

    def make_source_newer(self):
        with closing(sqlite3.connect(self.source.catalog_database)) as connection, connection:
            for table in ("pokemon_species", "pokemon", "tcg_card"):
                connection.execute(f"UPDATE {table} SET last_refreshed_at = '2026-10-29T10:00:00Z'")
            connection.execute("UPDATE tcg_set SET api_updated_at = '2026/10/29'")
            connection.execute("UPDATE card_market_listing SET source_updated_at = '2026/10/29'")

    def test_merge_retains_newer_rows_local_settings_and_destination_only_content(self):
        inode = self.target.catalog_database.stat().st_ino
        result = self.restore()
        self.assertGreater(result["inserted"], 0)
        self.assertEqual(self.target.catalog_database.stat().st_ino, inode)
        self.assertEqual(self.query("SELECT value FROM local_marker"), [("must survive",)])
        self.assertEqual(self.query("SELECT name FROM tcg_card WHERE id='test-1'"), [("existing card",)])
        self.assertEqual(self.query("SELECT name FROM tcg_card WHERE id='local-only'"), [("Local card",)])
        self.assertEqual(self.query("SELECT name FROM tcg_card WHERE id='new-card'"), [("New card",)])
        self.assertEqual(self.query("SELECT value FROM catalog_setting"), [("300",)])
        self.assertEqual(self.query("SELECT amount FROM card_price WHERE listing_id=1"), [(50.0,)])
        self.assertEqual(self.query("SELECT energy_type FROM card_attack_cost WHERE attack_id=90"), [("Lightning",)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_lookup_and_surrogate_ids_are_remapped_without_reassigning_local_identities(self):
        self.make_source_newer()
        self.restore()
        self.assertEqual(self.query("SELECT name FROM type WHERE id=1"), [("water",)])
        self.assertEqual(self.query(
            "SELECT t.name FROM pokemon_type pt JOIN type t ON t.id=pt.type_id WHERE pt.pokemon_id=25"
        ), [("electric",)])
        self.assertEqual(self.query("SELECT stat_id, base_stat FROM pokemon_stat"), [(8, 99)])
        self.assertEqual(self.query("SELECT ability_id FROM pokemon_ability"), [(7,)])
        self.assertEqual(self.query("SELECT name FROM card_attack WHERE id=90"), [("incoming attack",)])
        self.assertEqual(self.query("SELECT attack_id, energy_type FROM card_attack_cost"), [(90, "Grass")])
        self.assertEqual(self.query(
            "SELECT c.species_id, p.species_id FROM evolution_node c "
            "JOIN evolution_node p ON c.parent_node_id=p.id"
        ), [(26, 25)])
        self.assertEqual(self.query(
            "SELECT n.species_id FROM evolution_condition c JOIN evolution_node n ON c.node_id=n.id"
        ), [(26,)])
        self.assertEqual(self.query(
            "SELECT l.provider, p.amount FROM card_market_listing l JOIN card_price p ON p.listing_id=l.id "
            "WHERE l.card_id='test-1' ORDER BY l.provider"
        ), [("cardmarket", 7.0), ("tcgplayer", 5.0)])
        self.assertEqual(self.query(
            "SELECT r.started_at FROM import_file f JOIN import_run r ON f.import_run_id=r.id ORDER BY r.started_at"
        ), [("existing",), ("incoming",)])

    def test_newer_metadata_does_not_discard_a_valid_existing_local_asset(self):
        self.make_source_newer()
        self.restore()
        self.assertEqual(self.query("SELECT name FROM tcg_card WHERE id='test-1'"), [("incoming card",)])
        self.assertEqual(self.query("SELECT local_path, source_url FROM card_asset"), [
            ("data/assets/tcg/existing.png", "https://example.test/existing.png"),
        ])
        self.assertEqual((self.target.tcg_images / "existing.png").read_bytes(), b"existing asset")

    def test_newer_slot_relations_update_in_place_instead_of_adding_duplicate_types_and_abilities(self):
        self.make_source_newer()
        with closing(sqlite3.connect(self.source.catalog_database)) as connection, connection:
            connection.execute("UPDATE pokemon_type SET type_id=2")
            connection.execute("UPDATE card_type SET type_id=2")
            connection.execute("UPDATE ability SET name='lightning-rod'")
        self.restore()
        self.assertEqual(self.query(
            "SELECT t.name, p.slot FROM pokemon_type p JOIN type t ON p.type_id=t.id"
        ), [("grass", 1)])
        self.assertEqual(self.query(
            "SELECT t.name, c.slot FROM card_type c JOIN type t ON c.type_id=t.id"
        ), [("grass", 1)])
        self.assertEqual(self.query(
            "SELECT a.name, p.slot FROM pokemon_ability p JOIN ability a ON p.ability_id=a.id"
        ), [("lightning-rod", 1)])
        self.assertEqual(self.query("SELECT name FROM ability WHERE id=7"), [("static",)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_type_slot_swaps_and_replacements_do_not_violate_unique_constraints(self):
        self.make_source_newer()
        with closing(sqlite3.connect(self.target.catalog_database)) as connection, connection:
            connection.execute("INSERT INTO pokemon_type VALUES (25, 1, 2)")
            connection.execute("INSERT INTO card_type VALUES ('test-1', 1, 2)")
        with closing(sqlite3.connect(self.source.catalog_database)) as connection, connection:
            connection.execute("UPDATE pokemon_type SET slot=2")
            connection.execute("INSERT INTO pokemon_type VALUES (25, 2, 1)")
            connection.execute("INSERT INTO type VALUES (3, 'water')")
            connection.execute("UPDATE card_type SET slot=2")
            connection.execute("INSERT INTO card_type VALUES ('test-1', 3, 1)")
        self.restore()
        self.assertEqual(self.query(
            "SELECT t.name, p.slot FROM pokemon_type p JOIN type t ON p.type_id=t.id ORDER BY p.slot"
        ), [("grass", 1), ("electric", 2)])
        self.assertEqual(self.query(
            "SELECT t.name, c.slot FROM card_type c JOIN type t ON c.type_id=t.id ORDER BY c.slot"
        ), [("water", 1), ("electric", 2)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_unknown_dates_preserve_matches_and_missing_local_paths_are_not_imported(self):
        with closing(sqlite3.connect(self.source.catalog_database)) as connection, connection:
            connection.execute("UPDATE tcg_card SET last_refreshed_at=NULL")
            connection.execute(
                "INSERT INTO card_asset (card_id, asset_kind, local_path) VALUES ('new-card', 'large', 'data/assets/tcg/missing.png')"
            )
        self.restore()
        self.assertEqual(self.query("SELECT name FROM tcg_card WHERE id='test-1'"), [("existing card",)])
        self.assertEqual(self.query("SELECT local_path FROM card_asset WHERE card_id='new-card'"), [(None,)])

    def test_repeated_import_is_idempotent_and_missing_database_is_initialized_by_sql(self):
        empty = StoragePaths(self.target.data_root / "empty")
        bundle = BackupService(self.source).create_backup(["catalog_database"])
        service = BackupService(empty)
        self.assertGreater(service.restore_backup(bundle)["catalog_merge"]["inserted"], 0)
        result = service.restore_backup(bundle)["catalog_merge"]
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["updated"], 0)
        with closing(sqlite3.connect(empty.catalog_database)) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_same_provider_date_fills_missing_metrics_without_overwriting_existing_prices(self):
        with closing(sqlite3.connect(self.source.catalog_database)) as connection, connection:
            connection.execute("UPDATE card_market_listing SET source_updated_at='2026/10/28'")
            connection.execute("INSERT INTO card_price VALUES (99, 'normal', 'low', 3, 'USD')")
        self.restore()
        self.assertEqual(self.query("SELECT metric, amount FROM card_price WHERE listing_id=1 ORDER BY metric"),
                         [("low", 3.0), ("market", 50.0)])

    def test_price_freshness_is_independent_of_newer_card_metadata(self):
        self.make_source_newer()
        with closing(sqlite3.connect(self.source.catalog_database)) as connection, connection:
            connection.execute(
                "UPDATE card_market_listing SET source_updated_at='2026/10/01' WHERE provider='tcgplayer'"
            )
        self.restore()
        self.assertEqual(self.query("SELECT name FROM tcg_card WHERE id='test-1'"), [("incoming card",)])
        self.assertEqual(self.query("SELECT amount FROM card_price WHERE listing_id=1"), [(50.0,)])

    def test_invalid_freshness_date_rejects_and_rolls_back_the_import(self):
        with closing(sqlite3.connect(self.source.catalog_database)) as connection, connection:
            connection.execute("UPDATE pokemon SET last_refreshed_at='not a timestamp'")
        with self.assertRaisesRegex(ValueError, "Invalid catalog timestamp"):
            self.restore()
        self.assertEqual(self.query("SELECT name FROM type WHERE name='grass'"), [])
        self.assertEqual(self.query("SELECT height_decimetres FROM pokemon WHERE id=25"), [(4,)])

    def test_identical_existing_evolution_details_are_preserved_not_deleted_or_rejected(self):
        with closing(sqlite3.connect(self.target.catalog_database)) as connection, connection:
            connection.executemany(
                "INSERT INTO evolution_condition (id, node_id, trigger_name) VALUES (?, 70, 'level-up')",
                [(1,), (2,)],
            )
        self.restore()
        self.assertEqual(self.query("SELECT COUNT(*) FROM evolution_condition WHERE node_id=70"), [(2,)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_sql_failure_rolls_back_the_whole_catalog_merge_without_replacing_the_file(self):
        self.make_source_newer()
        with closing(sqlite3.connect(self.target.catalog_database)) as connection, connection:
            connection.execute(
                "CREATE TRIGGER reject_new_card BEFORE INSERT ON tcg_card WHEN NEW.id='new-card' "
                "BEGIN SELECT RAISE(ABORT, 'fixture rejected import'); END"
            )
        inode = self.target.catalog_database.stat().st_ino
        with self.assertRaisesRegex(sqlite3.IntegrityError, "fixture rejected"):
            self.restore()
        self.assertEqual(self.target.catalog_database.stat().st_ino, inode)
        self.assertEqual(self.query("SELECT name FROM tcg_card WHERE id='test-1'"), [("existing card",)])
        self.assertEqual(self.query("SELECT name FROM type WHERE name='grass'"), [])
        self.assertEqual(self.query("SELECT value FROM local_marker"), [("must survive",)])

    def test_asset_and_combined_bundles_preserve_registered_files_even_when_archive_paths_match(self):
        source_image = self.source.tcg_images / "incoming.png"
        source_image.unlink()
        (self.source.tcg_images / "existing.png").write_bytes(b"older archived content")
        for paths, content in ((self.source, b"older archived content"), (self.target, b"existing asset")):
            with closing(sqlite3.connect(paths.catalog_database)) as connection, connection:
                connection.execute(
                    "UPDATE card_asset SET local_path='data/assets/tcg/existing.png', "
                    "source_url='https://example.test/existing.png', sha256=?",
                    (hashlib.sha256(content).hexdigest(),),
                )
        self.make_source_newer()
        for components in (["tcg_images"], ["catalog_database", "tcg_images"]):
            with self.subTest(components=components):
                bundle = BackupService(self.source).create_backup(components)
                BackupService(self.target).restore_backup(bundle)
                self.assertEqual((self.target.tcg_images / "existing.png").read_bytes(), b"existing asset")
                self.assertEqual(self.query("SELECT sha256 FROM card_asset"), [
                    (hashlib.sha256(b"existing asset").hexdigest(),),
                ])


if __name__ == "__main__":
    unittest.main()
