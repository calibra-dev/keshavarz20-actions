import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p24",ROOT/"phase24"/"measurement_v2.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Phase24Tests(unittest.TestCase):
    def test_prompt_bank_is_exactly_200_and_balanced(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        x=mod.validate_prompt_bank(bank)
        self.assertEqual(x["count"],200)
        self.assertEqual(set(x["by_platform"].values()),{50})
        self.assertEqual(set(x["by_bucket"].values()),{20})

    def test_pending_prompts_cannot_contain_results(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        row=bank["records"][0]
        row["keshavarz20_cited"]=True
        with self.assertRaises(mod.Phase24Error):
            mod.validate_prompt_bank(bank)

    def test_empty_direct_registry_keeps_citation_kpis_null(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        k=mod.compute_direct_kpis(bank,{"observations":[]})
        self.assertEqual(k["direct_observation_count"],0)
        self.assertIsNone(k["citation_rate"])
        self.assertIsNone(k["brand_mention_rate"])

    def test_referral_is_not_used_as_citation(self):
        report=mod.build_report()
        self.assertEqual(report["telemetry"]["ga4"]["chatgpt_referral"]["sessions"],3)
        self.assertIsNone(report["direct_surface_kpis"]["citation_rate"])
        self.assertTrue(report["measurement_rules"]["referral_is_not_citation"])

    def test_dependency_stack_20_to_23_is_current(self):
        report=mod.build_report()
        self.assertTrue(report["dependencies_current"])

    def test_direct_observation_requires_matching_k20_url(self):
        bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
        obs={
          "observation_id":"x","prompt_id":bank["records"][0]["prompt_id"],
          "surface":"ChatGPT Search","observed_at_utc":"2026-09-27T00:00:00Z",
          "evidence_type":"DIRECT_SURFACE_CAPTURE","answer_present":True,
          "keshavarz20_cited":True,"brand_mentioned":True,"citation_urls":[]
        }
        with self.assertRaises(mod.Phase24Error):
            mod.validate_observation(obs,{x["prompt_id"] for x in bank["records"]})


if __name__=="__main__":
    unittest.main()
