import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase21_authority",
    ROOT / "phase21" / "authority_registry.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Phase21AuthorityTests(unittest.TestCase):
    def test_real_repo_snapshot_passes(self):
        s = mod.build_snapshot()
        self.assertGreaterEqual(s["evidence"]["verified_grade_a_cards"], 7)
        self.assertEqual(s["product_truth"]["hard_fabrications"], 0)
        self.assertGreater(s["search_demand"]["rows"], 0)
        self.assertGreater(s["intent_graph"]["active_intents"], 0)

    def test_generated_questions_are_not_customer_evidence(self):
        s = mod.build_snapshot()
        q = s["question_engine"]
        self.assertEqual(
            q["classification"],
            "synthetic_editorial_question_generator_not_customer_evidence",
        )
        self.assertFalse(q["may_count_as_customer_review"])
        self.assertFalse(q["may_count_as_customer_question"])

    def test_fabrication_fails_closed(self):
        s = mod.build_snapshot()
        s["product_truth"]["hard_fabrications"] = 1
        with self.assertRaises(mod.Phase21Error):
            mod.validate_snapshot(s)

    def test_unsupported_compatibility_fails_closed(self):
        s = mod.build_snapshot()
        s["product_truth"]["unsupported_compatibility_promoted"] = True
        with self.assertRaises(mod.Phase21Error):
            mod.validate_snapshot(s)


if __name__ == "__main__":
    unittest.main()
