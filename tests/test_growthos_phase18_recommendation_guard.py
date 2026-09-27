import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p18",ROOT/"scripts"/"k20_growthos_phase18_recommendation_guard.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class T(unittest.TestCase):
    def test_fail_closed_without_verified_edges(self):
        r=m.build()
        self.assertTrue(r["policy"]["exact_sku_recommendation_requires_verified_technical_edge"])
        self.assertTrue(r["policy"]["same_size_candidate_is_not_compatibility"])
        if r["verified_technical_compatibility_edges"] == 0:
            self.assertFalse(r["automatic_exact_sku_recommendation_enabled"])
            self.assertEqual(r["runtime_mode"],"GUARDED_EXPERT_REVIEW_ONLY")

if __name__=="__main__": unittest.main()
