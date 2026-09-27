import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("intent_graph", ROOT / "daily-agri-articles" / "intent_graph.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Phase20IntentTests(unittest.TestCase):
    def test_score_passes_only_at_85_without_blocker(self):
        c = {"scores": {
            "farmer_decision_value": 20, "independent_intent": 15, "evidence_strength": 15,
            "demand_signal": 15, "seasonal_relevance": 10, "business_relevance": 5,
            "original_value_potential": 5, "cannibalization_safety": 5,
        }, "blockers": []}
        self.assertEqual(mod.score_candidate(c)["decision"], "PASS")
        c["blockers"] = ["existing_intent_overlap"]
        self.assertEqual(mod.score_candidate(c)["decision"], "SKIP")

    def test_routing(self):
        self.assertEqual(mod.route_signal("news"), "news")
        self.assertEqual(mod.route_signal("compatibility_gap"), "product_data_backlog")
        self.assertEqual(mod.route_signal("recurring decision"), "article")
        self.assertEqual(mod.route_signal("recurring decision", True), "update_existing")

    def test_phase20_faq_gate(self):
        p = {
            "phase20_schema_version": "1", "canonical_intent_id": "ir-intent-x", "parent_hub": "irrigation",
            "scenario_dimensions": {"crop": "گوجه", "decision": "انتخاب نوار تیپ"},
            "source_strength": "primary+independent", "question_engine_intents_covered": [],
            "compatibility_rules_referenced": [], "membership_cta_type": "save_project", "update_triggers": [],
            "topic_score": {"total": 90, "blockers": []}, "faq_items": [{"question":"q","answer":"a"}] * 9,
        }
        with self.assertRaises(ValueError):
            mod.validate_phase20_metadata(p)

    def test_ten_draft_dry_runs_validate_without_wordpress_write(self):
        data = json.loads((ROOT / "growth-os" / "phase20-dry-run-drafts.json").read_text(encoding="utf-8"))
        self.assertEqual(data["mode"], "draft-dry-run-no-wordpress-write")
        self.assertEqual(len(data["drafts"]), 10)
        for draft in data["drafts"]:
            mod.validate_phase20_metadata(draft, registry={"intents": []})

    def test_existing_draft_intent_requires_update_path(self):
        p = {
            "phase20_schema_version": "1", "canonical_intent_id": "ir-intent-draft", "parent_hub": "irrigation",
            "scenario_dimensions": {"decision": "انتخاب فیلتر"},
            "source_strength": "primary+independent", "question_engine_intents_covered": [],
            "compatibility_rules_referenced": [], "membership_cta_type": "save_project", "update_triggers": [],
            "topic_score": {"total": 90, "blockers": []}, "faq_items": []
        }
        registry = {"intents": [{"canonical_intent_id": "ir-intent-draft", "status": "draft-covered", "wordpress_post_id": 146227}]}
        with self.assertRaises(ValueError):
            mod.validate_phase20_metadata(p, registry=registry)
        p["update_post_id"] = 146227
        mod.validate_phase20_metadata(p, registry=registry)

    def test_shadow_pack_has_30_candidates(self):
        data = json.loads((ROOT / "growth-os" / "phase20-shadow-topics.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["candidates"]), 30)
        self.assertTrue(any(mod.score_candidate(x)["decision"] == "SKIP" for x in data["candidates"]))
        self.assertTrue(any(mod.score_candidate(x)["decision"] == "PASS" for x in data["candidates"]))


if __name__ == "__main__":
    unittest.main()
