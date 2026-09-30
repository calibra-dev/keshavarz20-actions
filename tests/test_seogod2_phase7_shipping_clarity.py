import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "k20_seogod2_phase7_shipping_clarity.py"
spec = importlib.util.spec_from_file_location("p7", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Phase7ShippingClarityTests(unittest.TestCase):
    def test_tier_a_scope_is_exactly_20(self):
        self.assertEqual(len(m.TIER_A), 20)
        self.assertEqual(len(set(m.TIER_A)), 20)

    def test_shipping_block_contains_only_evidenced_policy(self):
        block = m.BLOCK
        self.assertIn("باربری یا تیپاکس", block)
        self.assertIn("پس‌کرایه", block)
        self.assertIn("/shipping/", block)
        self.assertNotIn("ارسال رایگان", block)
        self.assertNotRegex(block, r"تحویل\s*[۰-۹0-9]+\s*روزه")

    def test_truth_matches_enabled_shipping_method(self):
        truth = json.loads((ROOT / "seo-god2" / "phase7-shipping-truth-20260930.json").read_text(encoding="utf-8"))
        iran = next(z for z in truth["shipping_zones"] if z.get("name") == "ایران")
        enabled = [x for x in iran["methods"] if x.get("enabled") is True]
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0]["method_id"], "flat_rate")
        self.assertIn("باربری", enabled[0]["title"])
        self.assertIn("تیپاکس", enabled[0]["title"])
        self.assertIn("پس‌کرایه", enabled[0]["title"])
        free = [x for x in iran["methods"] if x.get("method_id") == "free_shipping"]
        self.assertTrue(free and free[0]["enabled"] is False)
        pickup = [x for x in iran["methods"] if x.get("method_id") == "local_pickup"]
        self.assertTrue(pickup and pickup[0]["enabled"] is False)

    def test_no_fixed_cost_or_delivery_promise(self):
        self.assertNotRegex(m.BLOCK, r"[۰-۹0-9]{2,}\s*(?:تومان|ریال)")
        self.assertNotRegex(m.BLOCK, r"(?:۱|۲|۳|1|2|3)\s*روز")


if __name__ == "__main__":
    unittest.main()
