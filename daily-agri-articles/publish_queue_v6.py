#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import k20_sanitizer
import content_growth_runtime
spec = importlib.util.spec_from_file_location("article_v5", ROOT / "publish_queue_v5.py")
v5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v5)
base = v5.base

intent_spec = importlib.util.spec_from_file_location("intent_graph", ROOT / "intent_graph.py")
intent_graph = importlib.util.module_from_spec(intent_spec)
intent_spec.loader.exec_module(intent_graph)

previous_validate = base.validate_payload

previous_load_queue = base.load_queue


def _upgrade_queue_payload_with_growth_prompt(p: dict) -> dict:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    enabled = os.environ.get("K20_CONTENT_GROWTH_ENABLED", "false").lower() in {"1", "true", "yes"}
    if not key or not enabled:
        k20_sanitizer.sanitize_payload_inplace(p)
        return p

    try:
        master = content_growth_runtime.load_master_prompt("article")
        model = os.environ.get("OPENAI_TEXT_MODEL", "gpt-5.6")
        client = OpenAI(api_key=key)
    except Exception as exc:
        print(
            f"Optional content-growth enhancer unavailable ({type(exc).__name__}); "
            "continuing with the original queue payload and deterministic validators.",
            file=sys.stderr,
        )
        k20_sanitizer.sanitize_payload_inplace(p)
        return p
    protected = {
        "slug": p.get("slug"),
        "content_type": p.get("content_type"),
        "category_name": p.get("category_name"),
        "category_id": p.get("category_id"),
        "source_urls": p.get("source_urls"),
        "source_names": p.get("source_names"),
        "research_summary": p.get("research_summary"),
        "editorial_disclosure": p.get("editorial_disclosure"),
        "review_status": p.get("review_status"),
        "generated_at": p.get("generated_at"),
        "phase20_schema_version": p.get("phase20_schema_version"),
        "intent_id": p.get("intent_id"),
        "intent_family": p.get("intent_family"),
        "rebuild_of_post_id": p.get("rebuild_of_post_id"),
        "update_post_id": p.get("update_post_id"),
    }
    source = {
        "title": p.get("title"),
        "excerpt": p.get("excerpt"),
        "content_html": p.get("content_html"),
        "focus_keyphrase": p.get("focus_keyphrase"),
        "related_keyphrases": p.get("related_keyphrases"),
        "seo_title": p.get("seo_title"),
        "meta_description": p.get("meta_description"),
        "tags": p.get("tags"),
        "faq_items": p.get("faq_items"),
        "cover_title": p.get("cover_title"),
        "cover_subtitle": p.get("cover_subtitle"),
        "image_title": p.get("image_title"),
        "alt_text": p.get("alt_text"),
        "internal_link_allowlist": sorted(set(
            __import__("re").findall(
                r"https?://(?:www\.)?keshavarz20\.com/[^\s'\"<>]+",
                str(p.get("content_html") or ""),
                flags=__import__("re").I,
            )
        )),
    }
    prompt = f"""
{master}

این یک پیش‌نویس آماده انتشار از موتور نوشته‌های کشاورز بیست است. آن را با استاندارد بالا بازبینی و بهینه کن، اما هیچ claim، منبع، لینک داخلی یا داده‌ای خارج از ورودی نساز.

قواعد این مرحله:
- source_urls/source_names/research_summary و داده‌های intent را تغییر نده.
- slug را تغییر نده.
- فقط لینک‌های داخلی موجود در internal_link_allowlist را نگه دار/استفاده کن؛ URL جدید نساز.
- منابع بیرونی جدید نساز؛ ادعاهای متن باید در محدوده research موجود بمانند.
- content_html باید حداقل همان عمق مفید فعلی را حفظ کند؛ کوتاه‌سازی صرفاً برای سبک نوشتار ممنوع.
- بخش‌های «جمع‌بندی»، «نظر کارشناسی کشاورز بیست»، «منابع» و «روش تهیه و بازبینی» را حفظ کن.
- لینک editorial-policy موجود را حذف نکن.
- خروجی فقط JSON با این کلیدها باشد:
  title, excerpt, content_html, focus_keyphrase, related_keyphrases, seo_title,
  meta_description, tags, faq_items, cover_title, cover_subtitle, image_title, alt_text.

ورودی:
{json.dumps(source, ensure_ascii=False)}
"""
    try:
        response = client.responses.create(model=model, input=prompt)
        data = content_growth_runtime.safe_json_from_text(response.output_text)
    except Exception as exc:
        print(
            f"Optional content-growth enhancer failed ({type(exc).__name__}); "
            "continuing with the original queue payload and deterministic validators.",
            file=sys.stderr,
        )
        k20_sanitizer.sanitize_payload_inplace(p)
        return p
    allowed = {
        "title", "excerpt", "content_html", "focus_keyphrase", "related_keyphrases",
        "seo_title", "meta_description", "tags", "faq_items", "cover_title",
        "cover_subtitle", "image_title", "alt_text",
    }
    for k in allowed:
        if k in data and data[k] not in (None, "", []):
            p[k] = data[k]
    for k, v in protected.items():
        if v is not None:
            p[k] = v

    content_growth_runtime.clean_user_facing_fields(
        p,
        [
            "title", "excerpt", "content_html", "focus_keyphrase", "related_keyphrases",
            "seo_title", "meta_description", "tags", "faq_items", "cover_title",
            "cover_subtitle", "image_title", "alt_text",
        ],
    )
    content_growth_runtime.assert_safe_content_html(str(p.get("content_html") or ""))
    return p


def load_queue_growth(path: Path) -> dict:
    p = previous_load_queue(path)
    return _upgrade_queue_payload_with_growth_prompt(p)


base.load_queue = load_queue_growth

ROLLOUT_DATE = "2026-09-27"


def _is_phase20_payload(p: dict) -> bool:
    if str(p.get("phase20_schema_version") or "").strip():
        return True
    generated = str(p.get("generated_at") or "")
    return generated[:10] >= ROLLOUT_DATE if len(generated) >= 10 else False


def validate_payload_v6(p):
    k20_sanitizer.sanitize_payload_inplace(p)
    previous_validate(p)
    if not _is_phase20_payload(p):
        return
    registry_path = REPO_ROOT / "growth-os" / "intent-registry.json"
    registry = intent_graph.load_json(registry_path) if registry_path.exists() else {"intents": []}
    try:
        intent_graph.validate_phase20_metadata(p, registry=registry)
    except ValueError as exc:
        raise base.QueuePublishError(f"Phase 20 intent gate: {exc}") from exc


base.validate_payload = validate_payload_v6

if __name__ == "__main__":
    base.main()
