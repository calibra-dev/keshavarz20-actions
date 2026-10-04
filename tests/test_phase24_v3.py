import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p24v3",ROOT/"phase24"/"measurement_v3.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Phase24V3Tests(unittest.TestCase):
    def test_prompt_bank_exact_and_balanced(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        x=mod.validate_prompt_bank(bank)
        self.assertEqual(x["count"],200)
        self.assertEqual(set(x["by_platform"].values()),{50})
        self.assertEqual(set(x["by_bucket"].values()),{20})

    def test_observation_integrity_and_surface_match(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        reg=json.loads((ROOT/"phase24"/"direct-observations-v2.json").read_text(encoding="utf-8"))
        x=mod.validate_observations(bank,reg)
        self.assertEqual(x["count"],70)
        self.assertEqual(x["unique_observation_ids"],70)
        self.assertEqual(x["unique_prompt_ids"],70)
        self.assertEqual(x["readback_verified_count"],70)

    def test_bad_surface_fails_closed(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        reg=json.loads((ROOT/"phase24"/"direct-observations-v2.json").read_text(encoding="utf-8"))
        bad=json.loads(json.dumps(reg))
        bad["observations"][0]["surface"]="Perplexity"
        with self.assertRaises(mod.Phase24Error):
            mod.validate_observations(bank,bad)

    def test_false_positive_citation_without_domain_url_fails(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        reg=json.loads((ROOT/"phase24"/"direct-observations-v2.json").read_text(encoding="utf-8"))
        bad=json.loads(json.dumps(reg))
        bad["observations"][0]["keshavarz20_cited"]=True
        bad["observations"][0]["citation_urls"]=[]
        with self.assertRaises(mod.Phase24Error):
            mod.validate_observations(bank,bad)

    def test_dependencies_are_current_20_to_23(self):
        d=mod.dependency_snapshot()
        self.assertTrue(mod.dependencies_current(d))
        self.assertEqual(d["phase21"]["version"],"phase21-iran-authority-network-v3")
        self.assertEqual(d["phase22"]["version"],"phase22-farmer-decision-v3")
        self.assertEqual(d["phase23"]["version"],"phase23-lifecycle-freshness-v3")

    def test_current_registry_has_truthful_backlog(self):
        report,queue=mod.build_report()
        self.assertEqual(report["direct_surface_kpis"]["direct_observation_count"],70)
        self.assertEqual(queue["remaining_count"],130)
        self.assertFalse(report["full_direct_surface_measurement_complete"])
        self.assertEqual(
            report["status"],
            "PASS_PHASE24_CONTROL_PLANE_V3_GUARDED_EXTERNAL_CAPTURE_BACKLOG",
        )
        self.assertEqual(queue["by_surface"]["ChatGPT Search"],30)
        self.assertEqual(queue["by_surface"]["Google AI Mode / AI Overviews"],0)
        self.assertEqual(queue["by_surface"]["Microsoft Copilot / Bing"],50)
        self.assertEqual(queue["by_surface"]["Perplexity"],50)

    def test_unobserved_surfaces_remain_null_not_zero(self):
        report,_=mod.build_report()
        for name in ("Microsoft Copilot / Bing","Perplexity"):
            x=report["direct_surface_kpis"]["by_surface"][name]
            self.assertEqual(x["observations"],0)
            self.assertIsNone(x["citation_rate"])
            self.assertIsNone(x["brand_mention_rate"])

    def test_historical_telemetry_is_not_relabelled_current(self):
        report,_=mod.build_report()
        self.assertTrue(report["telemetry"]["historical_baseline_only"])
        self.assertTrue(report["measurement_rules"]["historical_direct_capture_is_not_relabelled_as_current"])

    def test_control_plane_checks_all_pass(self):
        report,_=mod.build_report()
        self.assertEqual(report["passed_checks"],report["check_count"])
        self.assertEqual(report["failed_checks"],[])
        self.assertTrue(report["control_plane_complete"])


if __name__=="__main__":
    unittest.main()
