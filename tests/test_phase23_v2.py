import datetime as dt
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p23v2",ROOT/"phase23"/"lifecycle_governance_v2.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
policy=json.loads((ROOT/"phase23"/"lifecycle-governance-policy-v2.json").read_text(encoding="utf-8"))


class Phase23V2Tests(unittest.TestCase):
    def test_outofstock_never_means_discontinued(self):
        now=dt.datetime(2026,9,27,tzinfo=dt.timezone.utc)
        r=mod.classify("products",{"id":1,"status":"publish","date_modified_gmt":"2026-09-01T00:00:00","stock_status":"outofstock"},policy,now)
        self.assertIn("verify_supply_state_keep_url",r["actions"])
        self.assertFalse(r["discontinued_inferred"])
        self.assertFalse(r["redirect_inferred"])

    def test_old_content_queues_review_without_date_write(self):
        now=dt.datetime(2026,9,27,tzinfo=dt.timezone.utc)
        r=mod.classify("posts",{"id":2,"status":"publish","modified_gmt":"2025-01-01T00:00:00"},policy,now)
        self.assertIn("substantive_review",r["actions"])
        self.assertFalse(r["dateModified_mutation_allowed"])

    def test_draft_post_gets_no_public_freshness_action(self):
        now=dt.datetime(2026,9,27,tzinfo=dt.timezone.utc)
        r=mod.classify("posts",{"id":3,"status":"draft","modified_gmt":"2025-01-01T00:00:00"},policy,now)
        self.assertIn("no_public_freshness_action",r["actions"])

    def test_dependencies_are_new_phase_stack(self):
        deps=mod.dependency_snapshot()
        self.assertEqual(deps["phase20_intent_graph"],"PASS_CANARY_DRAFT")
        self.assertEqual(deps["phase21_authority_network"],"PASS_IRAN_FIRST_AUTHORITY_V2")
        self.assertEqual(deps["phase22_decision_model"],"PASS_FUNCTIONAL_V2_GUARDED_DEPLOYMENT")

    def test_build_report_is_read_only(self):
        now=dt.datetime(2026,9,27,tzinfo=dt.timezone.utc)
        r=mod.build_report(
            [{"id":1,"status":"publish","modified_gmt":"2026-09-26T00:00:00"}],
            [{"id":2,"status":"publish","modified_gmt":"2026-09-26T00:00:00"}],
            [{"id":3,"status":"publish","date_modified_gmt":"2026-09-26T00:00:00","stock_status":"instock"}],
            policy,now)
        self.assertEqual(r["status"],"PASS_LIFECYCLE_GOVERNANCE_V2")
        self.assertTrue(all(v==0 for v in r["mutations"].values()))

    def test_governance_assets_have_no_fake_date_write(self):
        now=dt.datetime(2026,9,27,tzinfo=dt.timezone.utc)
        assets=mod.governance_assets(policy,now)
        self.assertEqual(len(assets),3)
        self.assertTrue(all(not x["dateModified_mutation_allowed"] for x in assets))


if __name__=="__main__":
    unittest.main()
