import datetime as dt
import json
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

p22 = load_module("p22", ROOT / "scripts/k20_phase22_farmer_decision.py")
p23 = load_module("p23", ROOT / "scripts/k20_phase23_freshness_governance.py")

class Phase22Tests(unittest.TestCase):
    def test_missing_input_stops_specific_recommendation(self):
        r = p22.evaluate({"crop": "tomato", "area_ha": 1, "water_source": "well", "soil_texture": "loam", "region": "Fars"})
        self.assertEqual(r["state"], "NEEDS_MORE_INPUT")
        self.assertFalse(r["scope"]["specific_product_recommendation"])
        self.assertTrue(r["expert_escalation"])

    def test_complete_case_is_advisory_not_certified_design(self):
        r = p22.evaluate({"crop": "tomato", "area_ha": 1, "water_source": "well", "water_quality": "clear", "pressure_bar": 2, "available_flow_m3h": 10, "soil_texture": "loam", "region": "Fars"})
        self.assertEqual(r["state"], "ADVISORY_ONLY")
        self.assertFalse(r["scope"]["hydraulic_design_claimed"])
        self.assertGreaterEqual(len(r["next_steps"]), 3)

class Phase23Tests(unittest.TestCase):
    def test_outofstock_is_not_discontinued_and_no_date_write(self):
        policy = json.loads((ROOT / "phase23/lifecycle-governance-policy.json").read_text())
        now = dt.datetime(2026, 9, 19, tzinfo=dt.timezone.utc)
        x = p23.classify("products", {"id":1,"slug":"x","status":"publish","date_modified_gmt":"2025-01-01T00:00:00","stock_status":"outofstock"}, policy, now)
        self.assertIn("verify_supply_state_keep_url", x["actions"])
        self.assertFalse(x["discontinued_inferred"])
        self.assertFalse(x["dateModified_mutation_allowed"])

    def test_dependency_blocks_final_pass_without_breaking_functional_gate(self):
        policy = json.loads((ROOT / "phase23/lifecycle-governance-policy.json").read_text())
        now = dt.datetime(2026, 9, 19, tzinfo=dt.timezone.utc)
        r = p23.build_report([], [], [{"id":1,"status":"publish","date_modified_gmt":"2026-09-18T00:00:00","stock_status":"instock"}], policy, "PARTIAL", now)
        self.assertEqual(r["status"], "READY_BLOCKED_BY_PHASE20")
        self.assertEqual(r["mutations"]["dateModified"], 0)

if __name__ == "__main__":
    unittest.main()
