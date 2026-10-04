import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase22v3", ROOT / "phase22" / "decision_engine_v3.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Phase22V3Tests(unittest.TestCase):
    def base(self):
        return {
            "crop":"گوجه","area_ha":1,"water_source":"well","water_quality":"clear",
            "pressure_bar":2,"available_flow_m3h":10,"soil_texture":"لومی","region":"فارس"
        }

    def test_case_pack_has_broad_coverage(self):
        cases=json.loads((ROOT/"phase22"/"validation-cases-v3.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 16)

    def test_phase21_v3_current_authority_required(self):
        r=mod.evaluate(self.base())
        self.assertEqual(r["authority_basis"]["phase21_version"],"phase21-iran-authority-network-v3")
        self.assertEqual(r["authority_basis"]["phase21_status"],"PASS_IRAN_FIRST_AUTHORITY_V3_GUARDED")
        self.assertEqual(r["authority_basis"]["phase21_checks_passed"],r["authority_basis"]["phase21_checks_total"])
        self.assertEqual(r["authority_basis"]["hard_fabrications"],0)
        mod.validate(r)

    def test_missing_hydraulics_blocks_only_hydraulic_track(self):
        c=self.base(); c.pop("pressure_bar"); c.pop("available_flow_m3h")
        r=mod.evaluate(c)
        self.assertEqual(r["decision_tracks"]["hydraulic"]["state"],"BLOCKED_MISSING_MEASUREMENT")
        self.assertNotEqual(r["decision_tracks"]["filtration"]["state"],"BLOCKED_MISSING_MEASUREMENT")
        self.assertFalse(r["scope"]["specific_product_recommendation"])

    def test_dirty_water_escalates_filtration(self):
        c=self.base(); c.update({"water_source":"canal","water_quality":"turbid suspended sediment"})
        r=mod.evaluate(c)
        self.assertEqual(r["decision_tracks"]["filtration"]["state"],"EXPERT_REVIEW")
        self.assertIn("clogging_risk",r["risk_flags"])
        self.assertTrue(r["expert_escalation"])

    def test_verified_compatibility_only_opens_selector_not_product(self):
        c=self.base()
        c["verified_compatibility_fields"]={"nominal_size":"63 mm","connection_type":"threaded","evidence_status":"verified"}
        r=mod.evaluate(c)
        self.assertEqual(r["decision_tracks"]["compatibility"]["state"],"READY_FOR_SELECTOR")
        self.assertFalse(r["scope"]["specific_product_recommendation"])
        self.assertFalse(r["scope"]["sku_recommendation"])

    def test_candidate_compatibility_remains_blocked(self):
        c=self.base()
        c["verified_compatibility_fields"]={"nominal_size":"63 mm","connection_type":"threaded","evidence_status":"candidate"}
        r=mod.evaluate(c)
        self.assertEqual(r["decision_tracks"]["compatibility"]["state"],"BLOCKED_UNVERIFIED_COMPATIBILITY")
        self.assertIn("verified_evidence",r["decision_tracks"]["compatibility"]["missing_inputs"])

    def test_pii_does_not_change_context_hash(self):
        a=self.base()
        b=dict(a); b.update({"name":"A","phone":"111","email":"a@example.com","address":"X"})
        c=dict(a); c.update({"name":"B","phone":"222","email":"b@example.com","address":"Y"})
        self.assertEqual(mod.context_id(a),mod.context_id(b))
        self.assertEqual(mod.context_id(b),mod.context_id(c))
        r=mod.evaluate(c)
        self.assertEqual(set(r["privacy"]["ignored_identity_keys"]),{"address","email","name","phone"})
        self.assertFalse(r["privacy"]["stores_identity"])
        self.assertFalse(r["privacy"]["stores_contact_data"])

    def test_draft_intent_is_never_public_route(self):
        c=self.base(); c.update({"water_source":"canal","water_quality":"turbid"})
        r=mod.evaluate(c)
        routes={x["canonical_intent_id"]:x for x in r["intent_routes"]}
        d=routes["ir-intent-well-sand-drip-filtration"]
        self.assertEqual(d["status"],"draft-covered")
        self.assertFalse(d["publicly_routable"])
        self.assertIsNone(d["canonical_url"])

    def test_invalid_numeric_input_is_fail_soft(self):
        c=self.base(); c["pressure_bar"]="bad"
        r=mod.evaluate(c)
        self.assertIn("pressure_bar",r["input_quality"]["invalid"])
        self.assertEqual(r["state"],"NEEDS_MORE_INPUT")
        self.assertFalse(r["scope"]["specific_product_recommendation"])

    def test_no_commerce_or_certified_design_scope(self):
        r=mod.evaluate(self.base())
        self.assertFalse(r["scope"]["price_or_stock_decision"])
        self.assertFalse(r["scope"]["merchant_or_checkout_action"])
        self.assertFalse(r["scope"]["certified_hydraulic_design"])
        self.assertFalse(r["scope"]["agronomic_prescription"])

    def test_full_validation_pack_passes(self):
        cases=json.loads((ROOT/"phase22"/"validation-cases-v3.json").read_text(encoding="utf-8"))
        report=mod.run_cases(cases)
        self.assertEqual(report["status"],"PASS_MODEL_VALIDATION_V3")
        self.assertEqual(report["case_count"],len(cases))
        self.assertTrue(all(report["checks"].values()))


if __name__=="__main__":
    unittest.main()
