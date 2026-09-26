#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

spec = importlib.util.spec_from_file_location("news_base", ROOT / "publish_queue.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

POLICY = json.loads((REPO_ROOT / "automation-policy" / "seo-god-2026.json").read_text(encoding="utf-8"))
EDITORIAL_POLICY = json.loads((REPO_ROOT / "automation-policy" / "editorial-trust-2026.json").read_text(encoding="utf-8"))


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def _title_tokens(value: str) -> set[str]:
    raw = base.strip_html(value).replace("ي", "ی").replace("ك", "ک").lower()
    tokens = re.findall(r"[\u0600-\u06FFA-Za-z0-9]{3,}", raw)
    stop = {"برای", "های", "این", "است", "خبر", "کشاورزی", "کشاورز", "ایران"}
    return {t for t in tokens if t not in stop}


def validate_payload_v2(p):
    required = [
        "content_type", "title", "slug", "excerpt", "content_html", "focus_keyphrase",
        "seo_title", "meta_description", "tags", "related_keyphrases",
        "source_urls", "source_names", "selection_reason", "fact_check_notes",
        "editorial_disclosure", "review_status", "image_search_query", "alt_text",
    ]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise base.QueuePublishError(f"Missing required queue fields: {', '.join(missing)}")

    if str(p.get("content_type") or "").strip().lower() != "news":
        raise base.QueuePublishError("Routing guard: daily-agri-news queue must declare content_type=news")

    text = base.strip_html(str(p["content_html"]))
    if len(text) < 900:
        raise base.QueuePublishError("News draft is too short; refusing to create a draft")
    for section in ("جمع‌بندی", "نظر کارشناسی کشاورز بیست", "منابع", "روش تهیه و بازبینی"):
        if section not in str(p["content_html"]):
            raise base.QueuePublishError(f"Required section missing: {section}")

    if "/editorial-policy/" not in str(p["content_html"]):
        raise base.QueuePublishError("Phase 16 requires a visible link to the Keshavarz20 editorial policy")

    expected_review = str(EDITORIAL_POLICY["publication_gate"]["required_review_status"])
    if str(p.get("review_status") or "").strip() != expected_review:
        raise base.QueuePublishError(f"review_status must be {expected_review}")

    disclosure = base.strip_html(str(p.get("editorial_disclosure") or "")).strip()
    if len(disclosure) < 60:
        raise base.QueuePublishError("editorial_disclosure is too thin for the Phase 16 provenance gate")

    if not isinstance(p["tags"], list) or not (3 <= len(p["tags"]) <= 10):
        raise base.QueuePublishError("tags must contain 3 to 10 items")
    if not isinstance(p["related_keyphrases"], list) or not (1 <= len(p["related_keyphrases"]) <= 8):
        raise base.QueuePublishError("related_keyphrases must contain 1 to 8 useful items")

    urls = p.get("source_urls")
    if not isinstance(urls, list) or len(urls) < 2:
        raise base.QueuePublishError("At least two direct research source URLs are required")
    if any(not str(u).startswith(("http://", "https://")) for u in urls):
        raise base.QueuePublishError("Every source URL must be absolute http(s)")
    hosts = {_host(str(u)) for u in urls if _host(str(u))}
    min_domains = int(POLICY["research"]["minimum_independent_domains"]["news"])
    if len(hosts) < min_domains:
        raise base.QueuePublishError(f"News verification needs at least {min_domains} independent source domains")

    names = p.get("source_names")
    if not isinstance(names, list) or len(names) != len(urls):
        raise base.QueuePublishError("source_names must be an array matching source_urls length")

    p["slug"] = base.safe_slug(str(p["slug"]))
    if not p["slug"]:
        raise base.QueuePublishError("Slug became empty after validation")

    if p.get("fact_check_notes") is not None and len(base.strip_html(str(p.get("fact_check_notes") or ""))) < 30:
        raise base.QueuePublishError("fact_check_notes is present but too thin")
    if p.get("selection_reason") is not None and len(base.strip_html(str(p.get("selection_reason") or ""))) < 30:
        raise base.QueuePublishError("selection_reason is present but too thin")


def ensure_not_duplicate_v2(p):
    wanted_fp = base.fingerprint(str(p["title"]))
    wanted_tokens = _title_tokens(str(p["title"]))
    for title in base.recent_news_titles():
        if base.fingerprint(title) == wanted_fp:
            raise base.QueuePublishError(f"Duplicate news title detected; refusing to publish: {title}")
        other = _title_tokens(title)
        if wanted_tokens and other:
            overlap = len(wanted_tokens & other) / max(1, len(wanted_tokens | other))
            if overlap >= 0.72:
                raise base.QueuePublishError(f"Near-duplicate news topic detected; refusing to publish: {title}")


base.validate_payload = validate_payload_v2
base.ensure_not_duplicate = ensure_not_duplicate_v2

if __name__ == "__main__":
    base.main()
