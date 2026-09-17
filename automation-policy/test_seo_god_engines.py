#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "automation-policy" / "seo-god-2026.json").read_text(encoding="utf-8"))
assert POLICY["policy_version"] == "seo-god-2026.09.18"
assert POLICY["automation"]["news_status"] == "draft"
assert POLICY["automation"]["article_status"] == "draft"
assert POLICY["automation"]["question_status"] == "hold"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


article = load("article_v2", ROOT / "daily-agri-articles" / "publish_queue_v2.py")
news = load("news_v2", ROOT / "daily-agri-news" / "publish_queue_v2.py")

long_body = (
    "<p>این متن آزمایشی درباره تصمیم درست کشاورز، آب، هزینه، سازگاری، نصب و محدودیت‌ها است. "
    "هدف تست کیفیت ساختاری است و هیچ ادعای محصول یا قیمت واقعی ندارد.</p>" * 45
    + '<p><a href="https://keshavarz20.com/a/">راهنمای اول</a> و <a href="https://keshavarz20.com/b/">راهنمای دوم</a></p>'
    + "<h2>جمع‌بندی</h2><p>نتیجه آزمایشی.</p>"
    + "<h2>نظر کارشناسی کشاورز بیست</h2><p>این بخش صرفاً تحلیل تحریریه آزمایشی است.</p>"
)

article_payload = {
    "title": "آزمون ساختاری موتور مقاله کشاورز بیست",
    "slug": "seo-god-article-smoke",
    "excerpt": "این فقط payload ساختاری برای تست اعتبارسنج موتور مقاله است و وارد وردپرس نمی‌شود.",
    "content_html": long_body,
    "focus_keyphrase": "آزمون موتور مقاله",
    "seo_title": "آزمون ساختاری موتور مقاله کشاورز بیست",
    "meta_description": "این توضیح متا فقط برای آزمون ساختاری موتور مقاله کشاورز بیست ساخته شده و هیچ محتوای واقعی یا ادعای تجاری را منتشر نمی‌کند.",
    "related_keyphrases": ["کیفیت محتوا", "تصمیم کشاورز", "اعتبار منبع"],
    "category_name": "کشاورزی",
    "category_id": 0,
    "tags": ["کشاورزی", "آبیاری", "آموزش", "تست"],
    "source_urls": ["https://example.org/a", "https://example.edu/b", "https://example.org/c"],
    "source_names": ["Example Org", "Example EDU", "Example Org 2"],
    "research_summary": "این payload فقط برای اثبات گیت‌های ساختاری است: چند منبع، دامنه مستقل، لینک داخلی، طول محتوا و FAQ تطبیقی بررسی می‌شوند و هیچ نوشته‌ای منتشر نمی‌شود.",
    "image_search_query": "agriculture irrigation field factual editorial photo",
    "image_title": "آزمون کاور",
    "alt_text": "تصویر آزمایشی مزرعه و آبیاری",
    "faq_items": [],
}
article.validate_payload_v2(dict(article_payload))

faq_payload = dict(article_payload)
faq_payload["slug"] = "seo-god-article-faq-smoke"
faq_payload["faq_items"] = [
    {"question": "این تست چه چیزی را بررسی می‌کند؟", "answer": "گیت ساختاری را بررسی می‌کند."},
    {"question": "آیا چیزی منتشر می‌شود؟", "answer": "خیر."},
    {"question": "آیا FAQ اجباری است؟", "answer": "خیر."},
]
faq_payload["content_html"] = long_body + "<h2>این تست چه چیزی را بررسی می‌کند؟</h2><p>گیت ساختاری.</p><h2>آیا چیزی منتشر می‌شود؟</h2><p>خیر.</p><h2>آیا FAQ اجباری است؟</h2><p>خیر.</p>"
article.validate_payload_v2(faq_payload)

bad_faq = dict(faq_payload)
bad_faq["faq_items"] = bad_faq["faq_items"] * 3
try:
    article.validate_payload_v2(bad_faq)
    raise AssertionError("9 FAQ items must be rejected")
except article.base.QueuePublishError:
    pass

bad_domains = dict(article_payload)
bad_domains["source_urls"] = ["https://same.example/a", "https://same.example/b", "https://same.example/c"]
bad_domains["source_names"] = ["Same", "Same", "Same"]
try:
    article.validate_payload_v2(bad_domains)
    raise AssertionError("single-domain article evidence must be rejected")
except article.base.QueuePublishError:
    pass

news_body = (
    "<p>این متن آزمایشی برای تست خبر است و هیچ ادعای واقعی ندارد. کشاورزان باید خبرهای مهم را با منبع مستقیم بررسی کنند.</p>" * 12
    + "<h2>جمع‌بندی</h2><p>جمع‌بندی آزمایشی.</p>"
    + "<h2>نظر کارشناسی کشاورز بیست</h2><p>تحلیل تحریریه آزمایشی.</p>"
    + '<h2>منابع</h2><p><a href="https://example.org/news">منبع اول</a> <a href="https://example.edu/news">منبع دوم</a></p>'
)
news_payload = {
    "title": "آزمون ساختاری موتور خبر کشاورز بیست",
    "slug": "seo-god-news-smoke",
    "excerpt": "payload تست خبر",
    "content_html": news_body,
    "focus_keyphrase": "آزمون خبر کشاورزی",
    "seo_title": "آزمون ساختاری موتور خبر کشاورز بیست",
    "meta_description": "توضیح آزمایشی خبر",
    "tags": ["کشاورزی", "خبر", "آبیاری"],
    "related_keyphrases": ["خبر کشاورزی", "آب"],
    "source_urls": ["https://example.org/news", "https://example.edu/news"],
    "source_names": ["Example Org", "Example EDU"],
    "image_search_query": "agriculture field factual editorial",
    "alt_text": "تصویر آزمایشی کشاورزی",
    "selection_reason": "این متن فقط برای تست ساختاری است و نشان می‌دهد دلیل انتخاب باید مستند و بیش از یک عبارت کوتاه باشد.",
    "fact_check_notes": "این تست هیچ ادعای خبری واقعی ندارد و فقط کنترل چندمنبعی بودن و ساختار payload را بررسی می‌کند.",
}
news.validate_payload_v2(dict(news_payload))

bad_news = dict(news_payload)
bad_news["source_urls"] = ["https://same.example/a", "https://same.example/b"]
bad_news["source_names"] = ["Same", "Same"]
try:
    news.validate_payload_v2(bad_news)
    raise AssertionError("single-domain news verification must be rejected")
except news.base.QueuePublishError:
    pass

api_workflow = (ROOT / ".github" / "workflows" / "k20-daily-agri-news.yml").read_text(encoding="utf-8")
assert "schedule:" not in api_workflow, "API fallback must not have a second daily cron"
assert "workflow_dispatch:" in api_workflow

article_workflow = (ROOT / ".github" / "workflows" / "k20-article-queue-publisher.yml").read_text(encoding="utf-8")
news_workflow = (ROOT / ".github" / "workflows" / "k20-news-queue-publisher.yml").read_text(encoding="utf-8")
question_workflow = (ROOT / ".github" / "workflows" / "k20-customer-question-engine.yml").read_text(encoding="utf-8")
scheduler_workflow = (ROOT / ".github" / "workflows" / "k20-question-scheduler.yml").read_text(encoding="utf-8")
assert "publish_queue_v2.py" in article_workflow
assert "publish_queue_v2.py" in news_workflow
assert "engine_v18.py" in question_workflow
assert "test_engine_v18.py" in question_workflow
assert "engine_v18.py" in scheduler_workflow

print("PASS SEO-God cross-engine smoke tests")
