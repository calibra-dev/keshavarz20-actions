import unittest
from pathlib import Path

import content_growth_runtime


ROOT = Path(__file__).resolve().parents[1]


class ContentGrowthPromptV3Tests(unittest.TestCase):
    def test_master_prompt_v3_is_active(self):
        self.assertEqual(
            content_growth_runtime.MASTER_PROMPT_PATH.name,
            "K20_CONTENT_GROWTH_MASTER_PROMPT_V3.md",
        )
        prompt = content_growth_runtime.load_master_prompt()
        for marker in (
            "Answer First Architecture",
            "Truth & Evidence",
            "GEO / AEO / AI Extractability",
            "Performance-safe Content",
            "Human Editing Pass",
            "Final Content Gate",
        ):
            self.assertIn(marker, prompt)

    def test_article_profile_is_mounted(self):
        prompt = content_growth_runtime.load_master_prompt("article")
        self.assertIn("ARTICLE PROFILE", prompt)
        self.assertIn("FACT / ESTIMATE / ENGINEERING CALCULATION", prompt)
        source = (ROOT / "daily-agri-articles" / "publish_queue_v6.py").read_text(encoding="utf-8")
        self.assertIn('load_master_prompt("article")', source)

    def test_article_recovery_uses_canonical_queue_ingress(self):
        scheduled = (ROOT / "daily-agri-articles" / "SCHEDULED_TASK_PROMPT.md").read_text(encoding="utf-8")
        readme = (ROOT / "daily-agri-articles" / "README.md").read_text(encoding="utf-8")
        for marker in (
            "Canonical queue ingress",
            "GitHub Contents API",
            "Do **not** route queue creation through Bridge",
            "already-existing allow-listed queue file",
        ):
            self.assertIn(marker, scheduled)
        self.assertIn("scheduled task -> GitHub Contents API", readme)
        self.assertIn("must not fall back to Bridge/`engine.run`", readme)

    def test_news_profile_is_mounted(self):
        prompt = content_growth_runtime.load_master_prompt("news")
        self.assertIn("NEWS PROFILE", prompt)
        self.assertIn("این خبر برای کشاورزان چه معنایی دارد؟", prompt)
        source = (ROOT / "daily-agri-news" / "main.py").read_text(encoding="utf-8")
        self.assertIn('load_master_prompt("news")', source)

    def test_profile_rejects_unknown_engine(self):
        with self.assertRaises(ValueError):
            content_growth_runtime.load_master_prompt("invalid")


if __name__ == "__main__":
    unittest.main()
