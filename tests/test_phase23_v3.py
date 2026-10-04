import datetime as dt
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase23v3", ROOT / "phase23" / "lifecycle_governance_v3.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
policy = json.loads((ROOT / "phase23" / "lifecycle-governance-policy-v3.json").read_text(encoding="utf-8"))


class Phase23V3Tests(unittest.TestCase):
    def now(self):
        return dt.datetime(2026, 10, 5, tzinfo=dt.timezone.utc)

    def test_dependencies_are_current_phase_stack(self):
        deps = mod.dependency_snapshot()
        self.assertTrue(str(deps["phase20"]["status"]).startswith("PASS"))
        self.assertEqual(deps["phase20"]["passed_checks"], deps["phase20"]["check_count"])
        self.assertEqual(deps["phase21"]["version"], "phase21-iran-authority-network-v3")
        self.assertEqual(deps["phase21"]["status"], "PASS_IRAN_FIRST_AUTHORITY_V3_GUARDED")
        self.assertEqual(deps["phase22"]["version"], "phase22-farmer-decision-v3")
        self.assertEqual(deps["phase22"]["status"], "PASS_PHASE22_FARMER_DECISION_V3_GUARDED")

    def test_published_outofstock_never_means_discontinued(self):
        r = mod.classify("products", {
            "id": 1, "status": "publish", "date_modified_gmt": "2026-10-01T00:00:00",
            "stock_status": "outofstock"
        }, policy, self.now())
        self.assertIn("verify_supply_state_keep_url", r["actions"])
        self.assertFalse(r["discontinued_inferred"])
        self.assertFalse(r["redirect_inferred"])
        self.assertFalse(r["canonical_change_allowed"])
        self.assertFalse(r["deletion_allowed"])

    def test_draft_outofstock_gets_no_public_url_action(self):
        r = mod.classify("products", {
            "id": 2, "status": "draft", "date_modified_gmt": "2026-10-01T00:00:00",
            "stock_status": "outofstock"
        }, policy, self.now())
        self.assertIn("internal_lifecycle_only", r["actions"])
        self.assertNotIn("verify_supply_state_keep_url", r["actions"])
        self.assertNotIn("verify_backorder_copy_and_schema", r["actions"])

    def test_old_content_queues_review_without_fake_date_write(self):
        r = mod.classify("posts", {
            "id": 3, "status": "publish", "modified_gmt": "2025-01-01T00:00:00"
        }, policy, self.now())
        self.assertIn("substantive_review", r["actions"])
        self.assertFalse(r["dateModified_mutation_allowed"])

    def test_backorder_is_not_instock(self):
        r = mod.classify("products", {
            "id": 4, "status": "publish", "date_modified_gmt": "2026-10-01T00:00:00",
            "stock_status": "onbackorder"
        }, policy, self.now())
        self.assertIn("verify_backorder_copy_and_schema", r["actions"])

    def test_state_snapshot_contains_no_price_or_customer_data(self):
        state = mod.build_state_snapshot(
            [{"id":1,"slug":"p","status":"publish","modified_gmt":"2026-10-01T00:00:00"}],
            [{"id":2,"slug":"pg","status":"publish","modified_gmt":"2026-10-01T00:00:00"}],
            [{"id":3,"slug":"x","status":"publish","date_modified_gmt":"2026-10-01T00:00:00","stock_status":"instock","price":"SECRET"}],
            self.now(),
        )
        self.assertFalse(state["contains_price"])
        self.assertFalse(state["contains_stock_quantity"])
        self.assertFalse(state["contains_customer_data"])
        self.assertNotIn("price", state["fields"])
        self.assertTrue(all("price" not in x for x in state["rows"]))

    def test_stock_transition_creates_review_not_mutation(self):
        previous = {
            "version":"phase23-lifecycle-state-v3",
            "rows":[{"kind":"products","id":10,"slug":"x","status":"publish","modified_gmt":"2026-10-01T00:00:00","stock_status":"instock"}]
        }
        current = {
            "version":"phase23-lifecycle-state-v3",
            "rows":[{"kind":"products","id":10,"slug":"x","status":"publish","modified_gmt":"2026-10-01T00:00:00","stock_status":"outofstock"}]
        }
        diff = mod.detect_transitions(previous, current)
        self.assertEqual(diff["transition_count"], 1)
        t = diff["transitions"][0]
        self.assertIn("stock_state_changed_review_availability_parity", t["actions"])
        self.assertFalse(t["dateModified_mutation_allowed"])
        self.assertFalse(t["redirect_inferred"])
        self.assertFalse(t["canonical_change_allowed"])

    def test_build_report_passes_read_only_with_catalog_parity(self):
        now = self.now()
        products = [
            {"id":i,"slug":f"p-{i}","status":"publish","date_modified_gmt":"2026-10-01T00:00:00","stock_status":"instock"}
            for i in range(1, 653)
        ]
        report, state = mod.build_report(
            [{"id":1,"slug":"post","status":"publish","modified_gmt":"2026-10-01T00:00:00"}],
            [{"id":2,"slug":"page","status":"publish","modified_gmt":"2026-10-01T00:00:00"}],
            products,
            policy,
            previous_state=None,
            now=now,
        )
        self.assertEqual(report["status"], "PASS_PHASE23_LIFECYCLE_FRESHNESS_V3_GUARDED")
        self.assertEqual(report["passed_checks"], report["check_count"])
        self.assertEqual(report["failed_checks"], [])
        self.assertEqual(report["inventory"]["products_published"], 652)
        self.assertTrue(all(v == 0 for v in report["mutations"].values()))
        self.assertEqual(state["row_count"], 654)

    def test_governance_assets_are_current(self):
        deps = mod.dependency_snapshot()
        assets = mod.governance_assets(policy, self.now(), deps)
        self.assertEqual(len(assets), 3)
        self.assertTrue(all(not x["review_due"] for x in assets))
        self.assertTrue(all(not x["dateModified_mutation_allowed"] for x in assets))


if __name__ == "__main__":
    unittest.main()
