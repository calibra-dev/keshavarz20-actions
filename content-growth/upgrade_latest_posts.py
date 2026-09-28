#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import content_growth_runtime

WP_BASE = os.environ.get("WP_BASE_URL", "https://keshavarz20.com").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-5.6")
LIMIT = int(os.environ.get("K20_UPGRADE_LIMIT", "10"))

OUT = ROOT / "output"
BACKUPS = OUT / "backups"
OUT.mkdir(parents=True, exist_ok=True)
BACKUPS.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.auth = (WP_USER, WP_PASS)
SESSION.headers.update({"User-Agent": "Keshavarz20ContentGrowth/2.0 (+https://keshavarz20.com/)"})
CLIENT = OpenAI(api_key=OPENAI_API_KEY)


class GrowthError(RuntimeError):
    pass


def wp(method: str, route: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 70)
    r = SESSION.request(method, f"{WP_BASE}/wp-json{route}", **kwargs)
    if not r.ok:
        detail = ""
        try:
            body = r.json()
            detail = str(body.get("message") or body.get("code") or "")
        except Exception:
            detail = (r.text or "")[:500]
        raise GrowthError(f"WordPress REST {method} {route} failed: HTTP {r.status_code} {detail}".strip())
    return r


def strip_html(value: str) -> str:
    txt = re.sub(r"<script\b[^>]*>.*?</script>", " ", value or "", flags=re.I | re.S)
    txt = re.sub(r"<style\b[^>]*>.*?</style>", " ", txt, flags=re.I | re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return html.unescape(re.sub(r"\s+", " ", txt)).strip()


def hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def field_value(obj: Any, prefer_raw: bool = True) -> str:
    if isinstance(obj, dict):
        if prefer_raw and obj.get("raw") is not None:
            return str(obj.get("raw") or "")
        return str(obj.get("rendered") or obj.get("raw") or "")
    return str(obj or "")


def normalize_tokens(value: str) -> set[str]:
    raw = strip_html(value).replace("ي", "ی").replace("ك", "ک").lower()
    tokens = re.findall(r"[\u0600-\u06FFA-Za-z0-9]{3,}", raw)
    stop = {
        "برای","این","آن","است","هست","های","راهنمای","چگونه","چیست","شود","کنیم","کردن",
        "کشاورزی","کشاورز","بیست","در","از","به","با","یا","که","روی","یک","را","و",
    }
    return {x for x in tokens if x not in stop}


def internal_urls_in_html(value: str) -> list[str]:
    found = re.findall(
        r'href=["\'](https?://(?:www\.)?keshavarz20\.com/[^"\']+)["\']',
        value or "", flags=re.I,
    )
    out = []
    for u in found:
        u = u.split("#")[0]
        if u not in out:
            out.append(u)
    return out


def fetch_latest_posts() -> list[dict[str, Any]]:
    r = wp("GET", "/wp/v2/posts", params={
        "per_page": LIMIT,
        "status": "publish",
        "orderby": "date",
        "order": "desc",
        "context": "edit",
    })
    rows = r.json()
    if len(rows) != LIMIT:
        raise GrowthError(f"Expected {LIMIT} published posts, got {len(rows)}")
    return rows


def fetch_link_corpus() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for route in ("/wp/v2/posts", "/wp/v2/pages"):
        try:
            r = wp("GET", route, params={
                "per_page": 100,
                "status": "publish",
                "orderby": "modified",
                "order": "desc",
                "_fields": "id,link,title,slug",
            })
        except Exception:
            continue
        for x in r.json():
            title = field_value(x.get("title"), prefer_raw=False)
            link = str(x.get("link") or "").strip()
            if title and link:
                rows.append({"title": strip_html(title), "url": link})
    fixed = [
        {
            "title": "ماشین حساب نوار تیپ؛ محاسبه متراژ، رول و اتصالات",
            "url": f"{WP_BASE}/drip-tape-length-fittings-calculator/",
        },
        {"title": "درباره کشاورز بیست", "url": f"{WP_BASE}/about-us/"},
        {"title": "تماس با کشاورز بیست", "url": f"{WP_BASE}/contact-us/"},
        {"title": "سیاست تحریریه کشاورز بیست", "url": f"{WP_BASE}/editorial-policy/"},
    ]
    seen = {x["url"] for x in rows}
    for x in fixed:
        if x["url"] not in seen:
            rows.append(x)
    return rows


def rank_internal_links(post: dict[str, Any], corpus: list[dict[str, str]], max_items: int = 24) -> list[dict[str, str]]:
    title = field_value(post.get("title"))
    content = field_value(post.get("content"))
    wanted = normalize_tokens(title + " " + strip_html(content)[:6000])
    current_url = str(post.get("link") or "")
    scored = []
    for row in corpus:
        if not row["url"] or row["url"] == current_url:
            continue
        tokens = normalize_tokens(row["title"])
        overlap = len(tokens & wanted)
        if overlap == 0:
            continue
        score = overlap / max(1, len(tokens))
        if "calculator" in row["url"] and any(x in wanted for x in {"نوار","تیپ","آبیاری","قطره‌ای","قطره"}):
            score += 2
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    seen = set()
    for _, row in scored:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        out.append(row)
        if len(out) >= max_items:
            break
    return out


def load_gsc() -> dict[str, Any]:
    path = ROOT / "gsc-latest10.json"
    if not path.exists():
        return {"pages": [], "note": "No GSC snapshot file found."}
    return json.loads(path.read_text(encoding="utf-8"))


def gsc_for_url(gsc: dict[str, Any], url: str) -> dict[str, Any]:
    for row in gsc.get("pages", []):
        if str(row.get("page") or "").rstrip("/") == url.rstrip("/"):
            return row
    return {"page": url, "queries": [], "note": gsc.get("note")}


def source_url_usable(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc.lower().endswith("keshavarz20.com"):
            return False
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 K20SourceVerifier/1.0"},
            timeout=20,
            allow_redirects=True,
            stream=True,
        )
        return r.status_code < 500
    except Exception:
        return False


def research_and_rewrite(
    post: dict[str, Any],
    internal_candidates: list[dict[str, str]],
    gsc_row: dict[str, Any],
) -> dict[str, Any]:
    master = content_growth_runtime.load_master_prompt()
    title = field_value(post.get("title"))
    excerpt = field_value(post.get("excerpt"))
    content_html = field_value(post.get("content"))
    slug = str(post.get("slug") or "")
    link = str(post.get("link") or "")

    current_internal = internal_urls_in_html(content_html)
    allowlist = []
    for u in current_internal + [x["url"] for x in internal_candidates]:
        if u not in allowlist and u.rstrip("/") != link.rstrip("/"):
            allowlist.append(u)

    current_meta = post.get("meta") or {}
    payload = {
        "id": post.get("id"),
        "url": link,
        "slug": slug,
        "title": title,
        "excerpt": excerpt,
        "content_html": content_html,
        "current_yoast_title": current_meta.get("_yoast_wpseo_title"),
        "current_yoast_description": current_meta.get("_yoast_wpseo_metadesc"),
        "current_focus_keyphrase": current_meta.get("_yoast_wpseo_focuskw"),
        "gsc": gsc_row,
        "internal_link_allowlist": allowlist,
        "internal_link_candidates": internal_candidates,
    }

    prompt = f"""
{master}

اکنون یک نوشته منتشرشده کشاورز بیست را ارتقا بده. این عملیات روی URL زنده انجام می‌شود و باید fail-closed باشد.

قواعد ویژه:
- slug، URL، وضعیت publish، تاریخ انتشار، نویسنده، دسته‌ها، تگ‌های فعلی و featured image را تغییر نده.
- اگر GSC query خالی است، هیچ impression/CTR/position نساز و صریحاً بر intent و research تکیه کن.
- با ابزار web_search، قبل از بازنویسی حداقل 3 منبع معتبر مستقل و مرتبط پیدا کن. ترجیح با منابع رسمی، دانشگاهی، استاندارد، FAO/نهادهای تخصصی یا سازنده معتبر است.
- هیچ ادعایی که در منابع معتبر قابل پشتیبانی نیست اضافه نکن.
- متن اصلی را از نظر عمق ضعیف نکن؛ اطلاعات خوب فعلی را حفظ و ساختاردهی کن.
- برای موضوعات مهندسی، مرز «برآورد اولیه» و «طراحی مهندسی» را روشن کن.
- دست‌کم 2 و حداکثر 7 لینک داخلی مفید استفاده کن و فقط URLهایی را استفاده کن که در internal_link_allowlist هستند.
- هیچ لینک داخلی جدیدی نساز.
- از <script>، <style>، iframe، JSON-LD خام و shortcode ناشناخته استفاده نکن.
- شیت‌بندی با HTML سبک: h2/h3, p, ul/ol/li, blockquote, table کم‌ستون، details/summary و strong در حد نیاز.
- FAQ فقط اگر به intent واقعی کمک می‌کند؛ تکراری و نمایشی ممنوع.
- عنوان را فقط اگر واقعاً دقیق‌تر و جذاب‌تر می‌شود تغییر بده؛ clickbait ممنوع.
- SEO title و meta را برای CTR و intent واقعی تنظیم کن.
- یک alt_text کوتاه و دقیق برای featured image پیشنهاد بده، بدون ادعای اینکه محتوای تصویر را دیده‌ای؛ alt باید موضوع صفحه را توصیف کند نه جزئیات بصری ساختگی.
- خروجی نهایی فارسی طبیعی، انسان‌نویس و حرفه‌ای باشد.

نوشته:
{json.dumps(payload, ensure_ascii=False)}

فقط JSON معتبر با این کلیدها:
{{
  "title":"...",
  "excerpt":"...",
  "content_html":"...",
  "focus_keyphrase":"...",
  "related_keyphrases":["..."],
  "seo_title":"...",
  "meta_description":"...",
  "faq_items":[{{"question":"...","answer":"..."}}],
  "source_urls":["https://..."],
  "source_names":["..."],
  "research_summary":"...",
  "internal_links_used":["https://..."],
  "change_summary":["..."],
  "risk_notes":["..."],
  "image_alt_text":"..."
}}
"""
    response = CLIENT.responses.create(
        model=TEXT_MODEL,
        tools=[{"type": "web_search"}],
        input=prompt,
    )
    data = content_growth_runtime.safe_json_from_text(response.output_text)

    content_growth_runtime.clean_user_facing_fields(
        data,
        [
            "title", "excerpt", "content_html", "focus_keyphrase",
            "related_keyphrases", "seo_title", "meta_description",
            "faq_items", "research_summary", "change_summary",
            "risk_notes", "source_names", "image_alt_text",
        ],
    )
    content_growth_runtime.assert_safe_content_html(str(data.get("content_html") or ""))

    if not str(data.get("title") or "").strip():
        raise GrowthError("Model returned empty title")
    if len(strip_html(str(data.get("content_html") or ""))) < 3500:
        raise GrowthError("Rewritten article is too short; refusing to reduce content depth")
    if not (80 <= len(str(data.get("meta_description") or "").strip()) <= 185):
        raise GrowthError("Meta description outside safe 80..185 character range")

    used = [str(x).strip() for x in data.get("internal_links_used") or [] if str(x).strip()]
    allow = set(allowlist)
    if len(set(used)) < 2:
        raise GrowthError("Fewer than two useful internal links were used")
    illegal = sorted(set(used) - allow)
    if illegal:
        raise GrowthError("Model invented non-allowlisted internal URLs: " + ", ".join(illegal))

    html_internal = set(internal_urls_in_html(str(data.get("content_html") or "")))
    if len(html_internal & allow) < 2:
        raise GrowthError("content_html does not visibly contain at least two allowlisted internal links")

    source_urls = [str(x).strip() for x in data.get("source_urls") or [] if str(x).strip()]
    source_names = [str(x).strip() for x in data.get("source_names") or []]
    if len(source_urls) < 3 or len(source_names) != len(source_urls):
        raise GrowthError("At least three named external sources are required")
    usable = [u for u in source_urls if source_url_usable(u)]
    if len(usable) < 3:
        raise GrowthError("Fewer than three external source URLs passed reachability verification")

    if str(post.get("slug") or "") != slug:
        raise GrowthError("Unexpected slug mutation before write")

    data["source_urls"] = source_urls
    data["source_names"] = source_names
    return data


def backup_post(post: dict[str, Any]) -> Path:
    post_id = int(post["id"])
    keep = {
        "id": post_id,
        "date": post.get("date"),
        "modified": post.get("modified"),
        "slug": post.get("slug"),
        "status": post.get("status"),
        "link": post.get("link"),
        "title": field_value(post.get("title")),
        "excerpt": field_value(post.get("excerpt")),
        "content": field_value(post.get("content")),
        "featured_media": post.get("featured_media"),
        "categories": post.get("categories"),
        "tags": post.get("tags"),
        "author": post.get("author"),
        "meta": post.get("meta"),
    }
    path = BACKUPS / f"{post_id}.json"
    path.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def update_featured_alt(media_id: int, alt_text: str) -> None:
    if not media_id or not alt_text.strip():
        return
    try:
        wp("POST", f"/wp/v2/media/{media_id}", json={"alt_text": alt_text.strip()})
    except Exception as exc:
        print(f"Warning: media alt update failed for {media_id}: {exc}", file=sys.stderr)


def write_post(post: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    post_id = int(post["id"])
    old_slug = str(post.get("slug") or "")
    old_status = str(post.get("status") or "")
    old_featured = int(post.get("featured_media") or 0)
    old_categories = [int(x) for x in post.get("categories") or []]
    old_tags = [int(x) for x in post.get("tags") or []]
    old_author = int(post.get("author") or 0)

    meta = dict(post.get("meta") or {})
    meta["_yoast_wpseo_title"] = str(data["seo_title"]).strip()
    meta["_yoast_wpseo_metadesc"] = str(data["meta_description"]).strip()
    meta["_yoast_wpseo_focuskw"] = str(data["focus_keyphrase"]).strip()

    payload = {
        "title": str(data["title"]).strip(),
        "excerpt": str(data["excerpt"]).strip(),
        "content": str(data["content_html"]).strip(),
        "meta": meta,
    }
    r = wp("POST", f"/wp/v2/posts/{post_id}", json=payload, timeout=120)
    updated = r.json()

    # Readback is authoritative.
    readback = wp("GET", f"/wp/v2/posts/{post_id}", params={"context": "edit"}, timeout=70).json()
    if str(readback.get("status") or "") != old_status or old_status != "publish":
        raise GrowthError(f"Post {post_id} publication status changed unexpectedly")
    if str(readback.get("slug") or "") != old_slug:
        raise GrowthError(f"Post {post_id} slug changed unexpectedly")
    if int(readback.get("featured_media") or 0) != old_featured:
        raise GrowthError(f"Post {post_id} featured image changed unexpectedly")
    if [int(x) for x in readback.get("categories") or []] != old_categories:
        raise GrowthError(f"Post {post_id} categories changed unexpectedly")
    if [int(x) for x in readback.get("tags") or []] != old_tags:
        raise GrowthError(f"Post {post_id} tags changed unexpectedly")
    if int(readback.get("author") or 0) != old_author:
        raise GrowthError(f"Post {post_id} author changed unexpectedly")

    rb_content = field_value(readback.get("content"))
    if hash_text(rb_content) != hash_text(str(data["content_html"]).strip()):
        raise GrowthError(f"Post {post_id} content readback hash mismatch")

    update_featured_alt(old_featured, str(data.get("image_alt_text") or ""))

    return {
        "id": post_id,
        "url": readback.get("link") or post.get("link"),
        "slug": old_slug,
        "status": readback.get("status"),
        "title": field_value(readback.get("title")),
        "content_sha256": hash_text(rb_content),
        "featured_media": old_featured,
        "changed_fields": ["title", "excerpt", "content", "yoast_title", "yoast_meta_description", "yoast_focus_keyphrase", "featured_alt"],
    }


def main() -> None:
    if not WP_USER or not WP_PASS:
        raise GrowthError("WordPress credentials are missing")
    if not OPENAI_API_KEY:
        raise GrowthError("OPENAI_API_KEY is missing")

    posts = fetch_latest_posts()
    corpus = fetch_link_corpus()
    gsc = load_gsc()

    results = []
    for idx, post in enumerate(posts, start=1):
        post_id = int(post["id"])
        before_title = field_value(post.get("title"))
        before_content = field_value(post.get("content"))
        print(f"[{idx}/{len(posts)}] upgrading post {post_id}: {before_title}")
        backup_post(post)
        try:
            candidates = rank_internal_links(post, corpus)
            data = research_and_rewrite(post, candidates, gsc_for_url(gsc, str(post.get("link") or "")))
            readback = write_post(post, data)
            results.append({
                "id": post_id,
                "url": readback["url"],
                "status": "updated",
                "before_title": before_title,
                "after_title": readback["title"],
                "before_content_sha256": hash_text(before_content),
                "after_content_sha256": readback["content_sha256"],
                "gsc_queries_used": len(gsc_for_url(gsc, str(post.get("link") or "")).get("queries") or []),
                "internal_links_used": data.get("internal_links_used") or [],
                "source_urls": data.get("source_urls") or [],
                "change_summary": data.get("change_summary") or [],
                "risk_notes": data.get("risk_notes") or [],
                "featured_media": readback["featured_media"],
                "changed_fields": readback["changed_fields"],
            })
        except Exception as exc:
            results.append({
                "id": post_id,
                "url": post.get("link"),
                "status": "failed",
                "before_title": before_title,
                "error": str(exc),
            })
            print(f"ERROR post {post_id}: {exc}", file=sys.stderr)
        time.sleep(1)

    report = {
        "engine": "K20 Content Growth v2",
        "requested_count": LIMIT,
        "processed_count": len(posts),
        "updated_count": sum(1 for x in results if x["status"] == "updated"),
        "failed_count": sum(1 for x in results if x["status"] == "failed"),
        "watermark_filter": "guillaumemeyer/watermarks-remover v0.7.0 Layer A + K20 sanitizer",
        "gsc_note": gsc.get("note"),
        "results": results,
    }
    report_path = ROOT / "latest10-upgrade-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "latest10-upgrade-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "updated_count": report["updated_count"],
        "failed_count": report["failed_count"],
        "ids": [x["id"] for x in results],
    }, ensure_ascii=False))
    if report["failed_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
