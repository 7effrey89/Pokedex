import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from src.db.database import SqliteDatabase
from src.db.tcg_repository import SqliteTcgRepository
from src.services.tcg_print_matching import match_print_text


class PrintMatchingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = SqliteDatabase(Path(temporary.name) / "catalog.sqlite3")
        database.initialize()
        with closing(database.connect()) as connection, connection:
            connection.executemany(
                "INSERT INTO tcg_set(id, name, printed_total, ptcgo_code) VALUES (?, ?, ?, ?)",
                [("set1", "Set 1", 182, "DRI"), ("set2", "Set 2", 100, "ALT"),
                 ("set3", "Set 3", None, None)],
            )
            connection.executemany(
                "INSERT INTO tcg_card(id, set_id, name, number, artist) VALUES (?, ?, ?, ?, ?)",
                [
                    ("standard", "set1", "Shaymin", "10", "tono"),
                    ("full-art", "set1", "Shaymin", "185", "Heisuke Kitazawa"),
                    ("missing", "set1", "Shaymin", "186", None),
                    ("other-set", "set2", "Shaymin", "185", "Other Artist"),
                    ("unknown-total", "set3", "Shaymin", "185", None),
                ],
            )
            connection.executemany(
                "INSERT INTO card_attack(card_id, name) VALUES (?, ?)",
                [(card_id, "Smash Kick") for card_id in ("standard", "full-art", "missing", "other-set")],
            )
        self.repository = SqliteTcgRepository(database)

    def test_collector_and_illustrator_distinguish_prints_with_the_same_attack(self):
        lines = [
            {"region": "body", "text": "Smash Kick", "confidence": 0.99},
            {"region": "footer", "text": "185/182", "confidence": 0.98,
             "verification_text": "185/182", "verification_confidence": 0.97},
            {"region": "footer", "text": "Illus. Heisuke Kitazawa", "confidence": 0.96},
            {"region": "footer", "text": "DRIEN", "confidence": 0.95},
        ]
        matches = match_print_text(
            self.repository, {"standard", "full-art", "missing", "other-set", "unknown-total"}, lines,
        )
        self.assertEqual(["Smash Kick"], matches["standard"]["attacks"])
        self.assertEqual(["Smash Kick"], matches["full-art"]["attacks"])
        self.assertEqual("185/182", matches["full-art"]["collector_number"])
        self.assertEqual("Heisuke Kitazawa", matches["full-art"]["artist"])
        self.assertEqual("DRI", matches["full-art"]["set_code"])
        self.assertIsNone(matches["standard"]["collector_number"])
        self.assertIsNone(matches["other-set"]["collector_number"])
        self.assertIsNone(matches["missing"]["artist"])
        self.assertNotIn("unknown-total", matches)
        self.assertGreater(matches["full-art"]["strength"], matches["standard"]["strength"])

    def test_attack_and_collector_discover_candidates_without_a_title(self):
        attack_matches = match_print_text(self.repository, set(), [
            {"region": "body", "text": "Smash Kick 30", "confidence": 0.99},
        ])
        self.assertIn("standard", attack_matches)
        self.assertIn("full-art", attack_matches)
        number_matches = match_print_text(self.repository, set(), [
            {"region": "footer", "text": "010/182", "confidence": 0.99,
             "verification_text": "010/182", "verification_confidence": 0.98},
        ])
        self.assertEqual({"standard"}, set(number_matches))
        self.assertEqual("010/182", number_matches["standard"]["collector_number"])

    def test_one_observed_line_cannot_count_as_two_similar_attacks(self):
        with closing(self.repository.database.connect()) as connection, connection:
            connection.execute("INSERT INTO card_attack(card_id, name) VALUES ('full-art', 'Smash Kicks')")
        matches = match_print_text(self.repository, {"full-art"}, [
            {"region": "body", "text": "Smash Kick", "confidence": 0.99},
        ])
        self.assertEqual(["Smash Kick"], matches["full-art"]["attacks"])
        self.assertAlmostEqual(0.30 * 0.75 * 0.99, matches["full-art"]["strength"])

    def test_weak_or_invalid_collector_reads_do_not_boost_any_card(self):
        with mock.patch.object(self.repository, "get_print_metadata") as lookup:
            for text, confidence in (("185/182", 0.89), ("185/000", 0.99)):
                self.assertEqual({}, match_print_text(self.repository, {"full-art"}, [
                    {"region": "footer", "text": text, "confidence": confidence,
                     "verification_text": text, "verification_confidence": 0.99},
                ]))
            for verified in (None, "185/162"):
                self.assertEqual({}, match_print_text(self.repository, {"full-art"}, [
                    {"region": "footer", "text": "185/182", "confidence": 0.99,
                     "verification_text": verified, "verification_confidence": 0.98},
                ]))
            lookup.assert_not_called()

    def test_fuzzy_artist_matching_never_penalizes_missing_metadata(self):
        matches = match_print_text(self.repository, {"full-art", "missing"}, [
            {"region": "footer", "text": "Illus. Heisuke Kitazaw", "confidence": 0.95},
        ])
        self.assertIn("full-art", matches)
        self.assertNotIn("missing", matches)

    def test_illustrator_above_the_footer_is_recognized_with_an_explicit_label(self):
        matches = match_print_text(self.repository, set(), [
            {"region": "body", "text": "Illus. Heisuke Kitazawa", "confidence": 0.96},
        ])
        self.assertEqual({"full-art"}, set(matches))
        self.assertEqual("Heisuke Kitazawa", matches["full-art"]["artist"])

    def test_repository_batches_candidate_ids_and_reads_multiple_evidence_types(self):
        ids = {f"not-in-catalog-{i}" for i in range(410)}
        ids.add("unknown-total")
        metadata = self.repository.get_print_metadata(
            candidate_ids=ids, attack_names=["smash kick"],
            artists=["HEISUKE KITAZAWA"], printed_totals=[182], set_codes=["alt"],
        )
        self.assertEqual({"standard", "full-art", "missing", "other-set", "unknown-total"}, set(metadata))
        self.assertEqual(["Smash Kick"], metadata["full-art"]["attacks"])
        self.assertIsNone(metadata["unknown-total"]["printed_total"])


if __name__ == "__main__":
    unittest.main()
