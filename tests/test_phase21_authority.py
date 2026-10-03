import importlib.util
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
    def test_real_repo_snapshot_passes_v3(self):
        s = mod.build_snapshot()
        self.assertEqual(s["version"], "phase21-iran-authority-network-v3")
        self.assertEqual(s["status"], "PASS_IRAN_FIRST_AUTHORITY_V3_GUARDED")
        self.assertGreaterEqual(s["evidence"]["verified_grade_a_cards"], 7)
        self.assertEqual(s["full_catalog"]["candidate_rows"], 652)
        self.assertEqual(s["identifier_truth"]["published_products"], 652)
        self.assertEqual(s["brand_truth"]["published_products"], 652)
        self.assertEqual(s["product_truth"]["hard_fabrications"], 0)
        self.assertGreater(s["search_demand"]["rows"], 0)
        self.assertGreater(s["intent_graph"]["active_intents"], 0)
        self.assertEqual(s["acceptance"]["passed_checks"], s["acceptance"]["check_count"])
        self.assertEqual(s["acceptance"]["failed_checks"], [])

    def test_generated_questions_are_not_customer_evidence(self):
        s = mod.build_snapshot()
        q = s["question_engine"]
        self.assertEqual(
            q["classification"],
            "synthetic_editorial_question_generator_not_customer_evidence",
        )
        self.assertFalse(q["may_count_as_customer_review"])
        self.assertFalse(q["may_count_as_customer_question"])
        self.assertFalse(q["may_count_as_testimonial"])

    def test_currency_mapping_is_denomination_not_fx(self):
        s = mod.build_snapshot()
        c = s["currency_truth"]
        self.assertEqual(c["source_currency"], "IRT")
        self.assertEqual(c["target_currency"], "IRR")
        self.assertEqual(c["multiplier"], 10)
        self.assertFalse(c["fx_conversion_used"])
        self.assertEqual(c["site_price_mutations"], 0)

    def test_full_wcag_is_not_falsely_claimed(self):
        s = mod.build_snapshot()
        self.assertFalse(s["agent_usable_surfaces"]["full_wcag_automated_pass"])
        self.assertGreaterEqual(len(s["agent_usable_surfaces"]["guarded_residuals"]), 1)

    def test_fabrication_fails_closed(self):
        s = mod.build_snapshot()
        s["product_truth"]["hard_fabrications"] = 1
        s["acceptance"] = mod.build_acceptance(s)
        with self.assertRaises(mod.Phase21Error):
            mod.validate_snapshot(s)

    def test_unsupported_compatibility_fails_closed(self):
        s = mod.build_snapshot()
        s["product_truth"]["unsupported_compatibility_promoted"] = True
        s["acceptance"] = mod.build_acceptance(s)
        with self.assertRaises(mod.Phase21Error):
            mod.validate_snapshot(s)

    def test_gtin_fabrication_fails_closed(self):
        s = mod.build_snapshot()
        s["identifier_truth"]["gtins_fabricated"] = 1
        s["acceptance"] = mod.build_acceptance(s)
        with self.assertRaises(mod.Phase21Error):
            mod.validate_snapshot(s)

    def test_fake_question_evidence_fails_closed(self):
        s = mod.build_snapshot()
        s["question_engine"]["may_count_as_customer_question"] = True
        s["acceptance"] = mod.build_acceptance(s)
        with self.assertRaises(mod.Phase21Error):
            mod.validate_snapshot(s)


if __name__ == "__main__":
    unittest.main()
