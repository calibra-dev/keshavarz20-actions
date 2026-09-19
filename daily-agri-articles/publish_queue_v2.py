#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

spec = importlib.util.spec_from_file_location("article_base", ROOT / "publish_queue.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

POLICY = json.loads((REPO_ROOT / "automation-policy" / "seo-god-2026.json").read_text(encoding="utf-8"))


def _registrableish_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def validate_payload_v2(p):
    required = [
        "content_type", "title", "slug", "excerpt", "content_html", "focus_keyphrase", "seo_title",
        "meta_description", "related_keyphrases", "category_name", "tags", "source_urls",
        "source_names", "research_summary", "image_search_query", "image_title", "alt_text",
    ]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise base.QueuePublishError(f"Missing required queue fields: {', '.join(missing)}")

    if str(p.get("content_type") or "").strip().lower() != "post":
        raise base.QueuePublishError("Routing guard: daily-agri-articles queue must declare content_type=post")

    p["slug"] = base.safe_slug(str(p["slug"]))
    if not p["slug"]:
        raise base.QueuePublishError("Slug must be English ASCII and non-empty")

    text = base.strip_html(str(p["content_html"]))
    if len(text) < 4500:
        raise base.QueuePublishError("Article is too short for the K20 long-form article engine")

    for section in ("جمع‌بندی", "نظر کارشناسی کشاورز بیست"):
        if section not in str(p["content_html"]):
            raise base.QueuePublishError(f"Required section missing: {section}")

    # 2026 SEO-God rule: FAQ is useful content, not a quota. It may be absent.
    # When present, keep it compact and substantive instead of forcing 15 repeated Q&As.
    faq = p.get("faq_items", [])
    if faq is None:
        faq = []
        p["faq_items"] = []
    if not isinstance(faq, list):
        raise base.QueuePublishError("faq_items must be an array when provided")
    if faq and not (3 <= len(faq) <= 8):
        raise base.QueuePublishError("Adaptive FAQ must contain 3 to 8 useful question/answer objects, or be empty")
    for i, item in enumerate(faq, 1):
        if not isinstance(item, dict) or not item.get("question") or not item.get("answer"):
            raise base.QueuePublishError(f"FAQ item {i} is incomplete")
        if base.normalize_fa(str(item["question"])) not in base.normalize_fa(text):
            raise base.QueuePublishError(f"FAQ question {i} is not visibly present in content_html")

    tags = p.get("tags")
    if not isinstance(tags, list) or not (4 <= len(tags) <= 10):
        raise base.QueuePublishError("tags must contain 4 to 10 useful items")

    related = p.get("related_keyphrases")
    if not isinstance(related, list) or not (3 <= len(related) <= 8):
        raise base.QueuePublishError("related_keyphrases must contain 3 to 8 items")

    urls = p.get("source_urls")
    if not isinstance(urls, list) or len(urls) < 3:
        raise base.QueuePublishError("At least three credible research source URLs are required")
    if any(not str(u).startswith(("http://", "https://")) for u in urls):
        raise base.QueuePublishError("Every source URL must be absolute http(s)")
    hosts = {_registrableish_host(str(u)) for u in urls if _registrableish_host(str(u))}
    min_domains = int(POLICY["research"]["minimum_independent_domains"]["article"])
    if len(hosts) < min_domains:
        raise base.QueuePublishError(f"Article research needs at least {min_domains} independent source domains")

    names = p.get("source_names")
    if not isinstance(names, list) or len(names) != len(urls):
        raise base.QueuePublishError("source_names must be an array matching source_urls length")

    if len(str(p["meta_description"]).strip()) < 80 or len(str(p["meta_description"]).strip()) > 185:
        raise base.QueuePublishError("meta_description must be 80 to 185 characters")

    internal_links = re.findall(
        r"href=['\"](https?://(?:www\.)?keshavarz20\.com/[^'\"]+)['\"]",
        str(p["content_html"]), flags=re.I,
    )
    if len(set(internal_links)) < 2:
        raise base.QueuePublishError("Article must contain at least two useful internal Keshavarz20 links")

    # Require explicit research reasoning so weak trend-chasing cannot silently pass.
    if len(base.strip_html(str(p.get("research_summary") or ""))) < 80:
        raise base.QueuePublishError("research_summary is too thin to document the evidence and decision value")


base.validate_payload = validate_payload_v2

if __name__ == "__main__":
    base.main()
