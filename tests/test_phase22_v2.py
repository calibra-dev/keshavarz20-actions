import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase22v2", ROOT / "phase22" / "decision_engine_v2.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Phase22V2Tests(unittest.TestCase):
    def test_case_pack_has_broad_coverage(self):
        cases=json.loads((ROOT/"phase22"/"validation-cases-v2.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 12)

    def test_missing_hydraulics_blocks_hydraulic_track_not_everything(self):
        r=mod.evaluate({"crop":"گوجه","area_ha":1,"water_source":"well","water_quality":"clear","soil_texture":"لومی","region":"فارس"})
        self.assertEqual(r["decision_tracks"]["hydraulic"]["state"],"BLOCKED_MISSING_MEASUREMENT")
        self.assertNotEqual(r["decision_tracks"]["filtration"]["state"],"BLOCKED_MISSING_MEASUREMENT")
        mod.validate(r)

    def test_dirty_water_escalates_filtration(self):
        r=mod.evaluate({"crop":"ذرت","area_ha":2,"water_source":"canal","water_quality":"turbid","pressure_bar":2,"available_flow_m3h":10,"soil_texture":"رسی","region":"خوزستان"})
        self.assertEqual(r["decision_tracks"]["filtration"]["state"],"EXPERT_REVIEW")
        self.assertIn("clogging_risk",r["risk_flags"])

    def test_unverified_compatibility_never_selects_product(self):
        r=mod.evaluate({"crop":"گوجه","area_ha":1,"water_source":"well","water_quality":"clear","pressure_bar":2,"available_flow_m3h":10,"soil_texture":"لومی","region":"فارس"})
        self.assertEqual(r["decision_tracks"]["compatibility"]["state"],"BLOCKED_UNVERIFIED_COMPATIBILITY")
        self.assertFalse(r["scope"]["specific_product_recommendation"])
        self.assertFalse(r["scope"]["sku_recommendation"])

    def test_phase21_authority_is_required(self):
        r=mod.evaluate({"crop":"گوجه","area_ha":1,"water_source":"well","water_quality":"clear","pressure_bar":2,"available_flow_m3h":10,"soil_texture":"لومی","region":"فارس"})
        self.assertEqual(r["authority_basis"]["phase21_status"],"PASS_IRAN_FIRST_AUTHORITY_V2")
        self.assertEqual(r["authority_basis"]["hard_fabrications"],0)
        mod.validate(r)

    def test_personalization_hash_contains_no_identity(self):
        r=mod.evaluate({"crop":"گوجه","area_ha":1,"water_source":"well","water_quality":"clear","pressure_bar":2,"available_flow_m3h":10,"soil_texture":"لومی","region":"فارس","name":"PRIVATE","phone":"PRIVATE"})
        self.assertTrue(r["context_id"].startswith("farmctx-"))
        self.assertFalse(r["privacy"]["stores_identity"])
        self.assertFalse(r["privacy"]["stores_contact_data"])


if __name__=="__main__":
    unittest.main()
