import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "p6", ROOT / "scripts" / "k20_seogod2_phase6_basket.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Phase6BasketTests(unittest.TestCase):
    def setUp(self):
        self.graph = m.load_graph()

    def test_current_tier_a_is_fail_closed(self):
        r = m.build(self.graph)
        self.assertEqual(r["metrics"]["tier_a_products"], 20)
        self.assertEqual(r["metrics"]["random_recommendations"], 0)
        self.assertEqual(r["metrics"]["same_size_only_recommendations"], 0)
        self.assertEqual(r["metrics"]["verified_exact_recommendations"], 0)
        self.assertFalse(r["runtime"]["exact_sku_cards_enabled"])

    def test_incompatible_edges_never_recommend(self):
        r = m.build(self.graph)
        exact_pairs = {
            tuple(sorted((x["from"], x["to"])))
            for p in r["products"]
            for x in p["exact_sku_recommendations"]
        }
        blocked_pairs = {
            tuple(sorted((x["from"], x["to"])))
            for p in r["products"]
            for x in p["blocked_pairs"]
        }
        self.assertTrue(blocked_pairs)
        self.assertTrue(exact_pairs.isdisjoint(blocked_pairs))

    def test_needs_review_routes_to_expert(self):
        r = m.build(self.graph)
        self.assertGreater(r["metrics"]["expert_review_pairs"], 0)
        for p in r["products"]:
            for edge in p["expert_review_pairs"]:
                self.assertEqual(edge["label"], "نیازمند تأیید کارشناس")

    def test_verified_edge_requires_approved_label(self):
        graph = {
            "nodes": [{"id": i, "family": "valve"} for i in range(1, 21)],
            "edges": [
                {"from": 1, "to": 2, "status": "VERIFIED", "relation": "x"}
            ],
        }
        r = m.build(graph)
        self.assertEqual(r["metrics"]["verified_exact_recommendations"], 0)
        self.assertEqual(r["metrics"]["expert_review_pairs"], 1)

        graph["edges"][0]["recommendation_type"] = "مکمل ضروری"
        r2 = m.build(graph)
        self.assertEqual(r2["metrics"]["verified_exact_recommendations"], 1)
        self.assertTrue(r2["runtime"]["exact_sku_cards_enabled"])


if __name__ == "__main__":
    unittest.main()
