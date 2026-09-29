from pathlib import Path

import content_growth_runtime


ROOT = Path(__file__).resolve().parents[1]


def test_master_prompt_v3_is_active():
    assert content_growth_runtime.MASTER_PROMPT_PATH.name == "K20_CONTENT_GROWTH_MASTER_PROMPT_V3.md"
    prompt = content_growth_runtime.load_master_prompt()
    for marker in (
        "Answer First Architecture",
        "Truth & Evidence",
        "GEO / AEO / AI Extractability",
        "Performance-safe Content",
        "Human Editing Pass",
        "Final Content Gate",
    ):
        assert marker in prompt


def test_article_profile_is_mounted():
    prompt = content_growth_runtime.load_master_prompt("article")
    assert "ARTICLE PROFILE" in prompt
    assert "FACT / ESTIMATE / ENGINEERING CALCULATION" in prompt
    source = (ROOT / "daily-agri-articles" / "publish_queue_v6.py").read_text(encoding="utf-8")
    assert 'load_master_prompt("article")' in source


def test_news_profile_is_mounted():
    prompt = content_growth_runtime.load_master_prompt("news")
    assert "NEWS PROFILE" in prompt
    assert "این خبر برای کشاورزان چه معنایی دارد؟" in prompt
    source = (ROOT / "daily-agri-news" / "main.py").read_text(encoding="utf-8")
    assert 'load_master_prompt("news")' in source


def test_profile_rejects_unknown_engine():
    try:
        content_growth_runtime.load_master_prompt("invalid")
    except ValueError:
        return
    raise AssertionError("unknown content-growth profile must be rejected")
