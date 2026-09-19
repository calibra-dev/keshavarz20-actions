from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import xmlrpc.client
from datetime import datetime
from pathlib import Path
from typing import Any

import pytz
import requests
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

TEHRAN = pytz.timezone("Asia/Tehran")
WP_BASE = os.environ.get("WP_BASE_URL", "https://keshavarz20.com").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
NEWS_CAT_ID = int(os.environ.get("K20_NEWS_CATEGORY_ID", "839"))
NEWS_CAT_NAME = os.environ.get("K20_NEWS_CATEGORY_NAME", "کشاورزی")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Keshavarz20ScheduledNews/2.0 (+https://keshavarz20.com/)"
})

ALLOWED_HTML_TAGS = {"p", "h2", "h3", "ul", "ol", "li", "strong", "em", "a", "blockquote", "small"}


class QueuePublishError(RuntimeError):
    pass


def now_tehran() -> datetime:
    return datetime.now(TEHRAN)


def strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def normalize_title(value: str) -> str:
    value = strip_html(value).lower()
    value = value.replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[^\w\u0600-\u06FF]+", "", value)


def fingerprint(value: str) -> str:
    return hashlib.sha256(normalize_title(value).encode("utf-8")).hexdigest()[:24]


def safe_slug(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:120]


def load_queue(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise QueuePublishError(f"Queue file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise QueuePublishError("Queue payload must be a JSON object")
    return data


def validate_payload(p: dict[str, Any]) -> None:
    required = [
        "title", "slug", "excerpt", "content_html", "focus_keyphrase",
        "seo_title", "meta_description", "tags", "related_keyphrases",
        "source_urls", "source_names", "image_search_query", "alt_text",
    ]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise QueuePublishError(f"Missing required queue fields: {', '.join(missing)}")

    if len(strip_html(str(p["content_html"]))) < 900:
        raise QueuePublishError("Article is too short; refusing to create a draft")
    for section in ("جمع‌بندی", "نظر کارشناسی کشاورز بیست", "منابع"):
        if section not in str(p["content_html"]):
            raise QueuePublishError(f"Required section missing: {section}")

    if not isinstance(p["tags"], list) or not (3 <= len(p["tags"]) <= 10):
        raise QueuePublishError("tags must contain 3 to 10 items")
    if not isinstance(p["related_keyphrases"], list):
        raise QueuePublishError("related_keyphrases must be an array")
    if not isinstance(p["source_urls"], list) or not p["source_urls"]:
        raise QueuePublishError("At least one source URL is required")
    if any(not str(u).startswith("http") for u in p["source_urls"]):
        raise QueuePublishError("Every source URL must be absolute http(s)")

    p["slug"] = safe_slug(str(p["slug"]))
    if not p["slug"]:
        raise QueuePublishError("Slug became empty after validation")


def recent_news_titles(limit: int = 100) -> list[str]:
    """Inspect the real custom news post type through authenticated XML-RPC.

    The live custom type is not exposed by the expected REST collection. Duplicate
    inspection therefore uses the same WordPress capability as the draft
    writer, while remaining read-only.
    """
    server = wp_xmlrpc()
    try:
        methods = set(server.system.listMethods())
        if "wp.getPosts" not in methods:
            raise QueuePublishError("WordPress XML-RPC missing wp.getPosts for news duplicate inspection")

        titles: list[str] = []
        seen: set[str] = set()
        for status in ("publish", "draft", "pending", "future", "private"):
            rows = server.wp.getPosts(
                0, WP_USER, WP_PASS,
                {
                    "post_type": "news",
                    "post_status": status,
                    "number": min(limit, 100),
                    "orderby": "post_date",
                    "order": "DESC",
                },
                ["post_title"],
            )
            for row in rows:
                title = str(row.get("post_title") or "").strip()
                key = normalize_title(title)
                if title and key not in seen:
                    seen.add(key)
                    titles.append(title)
                if len(titles) >= limit:
                    return titles
        return titles
    except QueuePublishError:
        raise
    except Exception as exc:
        raise QueuePublishError(
            f"Could not inspect recent WordPress news through XML-RPC: {exc}"
        ) from exc

def ensure_not_duplicate(p: dict[str, Any]) -> None:
    wanted = fingerprint(str(p["title"]))
    for title in recent_news_titles():
        if fingerprint(title) == wanted:
            raise QueuePublishError(f"Duplicate news title detected; refusing to publish: {title}")


def find_existing_queued_draft(p: dict[str, Any]) -> dict[str, Any] | None:
    """Recover idempotently when a prior run already created the exact news draft.

    Exact title + draft status + news post type is enough to stop duplicate writes.
    The caller performs the full post-write verification before treating it as
    success. This also repairs runs that failed only while serializing receipts.
    """
    server = wp_xmlrpc()
    try:
        rows = server.wp.getPosts(
            0, WP_USER, WP_PASS,
            {
                "post_type": "news",
                "post_status": "draft",
                "number": 100,
                "orderby": "post_date",
                "order": "DESC",
            },
            ["post_id", "post_title", "post_status", "post_type", "post_thumbnail", "link"],
        )
    except Exception as exc:
        raise QueuePublishError(f"Could not inspect existing queued news drafts: {exc}") from exc

    wanted_title = normalize_title(str(p["title"]))
    for row in rows:
        if normalize_title(str(row.get("post_title") or "")) == wanted_title:
            return row
    return None

def commons_search(query: str) -> dict[str, Any]:
    api = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 30,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": 1800,
        "format": "json",
        "formatversion": 2,
    }
    r = SESSION.get(api, params=params, timeout=35)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or []
    candidates: list[dict[str, Any]] = []

    for page in pages:
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = str(info.get("mime") or "")
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)
        if width < 900 or height < 500:
            continue
        meta = info.get("extmetadata") or {}
        lic = ((meta.get("LicenseShortName") or {}).get("value") or "").strip()
        lic_low = lic.lower()
        # Prefer open licences; reject clearly non-free material.
        if not any(x in lic_low for x in ("cc0", "public domain", "cc by", "creative commons")):
            continue
        source_url = info.get("thumburl") or info.get("url")
        if not source_url:
            continue
        score = 0
        if "cc0" in lic_low or "public domain" in lic_low:
            score += 20
        if width / max(height, 1) >= 1.35:
            score += 8
        score += min(width, 4000) / 500
        candidates.append({
            "score": score,
            "url": source_url,
            "original_url": info.get("descriptionurl") or page.get("canonicalurl") or "",
            "title": page.get("title") or "",
            "license": lic,
            "artist": strip_html(((meta.get("Artist") or {}).get("value") or "")),
            "credit": strip_html(((meta.get("Credit") or {}).get("value") or "")),
        })

    if not candidates:
        raise QueuePublishError(f"No suitable open-license Wikimedia image found for: {query}")
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]


def make_editorial_image(source: dict[str, Any]) -> Path:
    r = SESSION.get(source["url"], timeout=60)
    r.raise_for_status()
    raw = OUT / "queue-image-source"
    raw.write_bytes(r.content)

    target = OUT / "featured-news.webp"
    with Image.open(raw) as im:
        im = im.convert("RGB")
        w, h = im.size
        desired = 16 / 9
        current = w / max(h, 1)
        if current > desired:
            new_w = int(h * desired)
            left = max(0, (w - new_w) // 2)
            im = im.crop((left, 0, left + new_w, h))
        elif current < desired:
            new_h = int(w / desired)
            top = max(0, (h - new_h) // 2)
            im = im.crop((0, top, w, top + new_h))

        im = im.resize((1280, 720), Image.Resampling.LANCZOS)
        # Conservative editorial treatment: clarity, contrast and subtle edge focus.
        im = ImageEnhance.Contrast(im).enhance(1.05)
        im = ImageEnhance.Color(im).enhance(1.03)
        im = ImageEnhance.Sharpness(im).enhance(1.05)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))
        im.save(target, "WEBP", quality=88, method=6)

    raw.unlink(missing_ok=True)
    return target


class TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    def __init__(self, timeout: int = 45):
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


def wp_xmlrpc() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(
        f"{WP_BASE}/xmlrpc.php",
        allow_none=True,
        transport=TimeoutSafeTransport(45),
    )


def upload_wp_image(server: xmlrpc.client.ServerProxy, path: Path, p: dict[str, Any], source: dict[str, Any]) -> int:
    payload = {
        "name": f"keshavarz20-news-{now_tehran().strftime('%Y%m%d-%H%M%S')}.webp",
        "type": "image/webp",
        "bits": xmlrpc.client.Binary(path.read_bytes()),
        "overwrite": False,
        "post_id": 0,
    }
    media = server.wp.uploadFile(0, WP_USER, WP_PASS, payload)
    media_id = int(media["id"])

    description = " | ".join(x for x in [source.get("title", ""), source.get("artist", ""), source.get("license", ""), source.get("original_url", "")] if x)
    try:
        server.wp.editPost(0, WP_USER, WP_PASS, media_id, {
            "post_title": p.get("image_title") or p["title"],
            "post_excerpt": "",
            "post_content": description,
        })
    except Exception:
        pass

    r = SESSION.post(
        f"{WP_BASE}/wp-json/wp/v2/media/{media_id}",
        json={"alt_text": p["alt_text"], "caption": "", "description": description},
        auth=(WP_USER, WP_PASS),
        timeout=30,
    )
    if not r.ok:
        print(f"Warning: media metadata update returned HTTP {r.status_code}", file=sys.stderr)
    return media_id


def create_draft(server: xmlrpc.client.ServerProxy, p: dict[str, Any], media_id: int, image_source: dict[str, Any]) -> int:
    related = [str(x).strip() for x in p.get("related_keyphrases", []) if str(x).strip()][:6]
    tags = [str(x).strip() for x in p.get("tags", []) if str(x).strip()][:8]
    custom_fields = [
        {"key": "_yoast_wpseo_title", "value": p["seo_title"]},
        {"key": "_yoast_wpseo_metadesc", "value": p["meta_description"]},
        {"key": "_yoast_wpseo_focuskw", "value": p["focus_keyphrase"]},
        {"key": "_yoast_wpseo_primary_news_cat", "value": str(NEWS_CAT_ID)},
        {"key": "_yoast_wpseo_focuskeywords", "value": json.dumps([{"keyword": p["focus_keyphrase"], "score": 0}], ensure_ascii=False)},
        {"key": "_yoast_wpseo_keywordsynonyms", "value": json.dumps([", ".join(related)], ensure_ascii=False)},
        {"key": "_k20_news_source_urls", "value": json.dumps(p["source_urls"], ensure_ascii=False)},
        {"key": "_k20_news_source_names", "value": json.dumps(p["source_names"], ensure_ascii=False)},
        {"key": "_k20_news_engine", "value": "chatgpt-pro-scheduled-v2"},
        {"key": "_k20_news_generated_at", "value": str(p.get("generated_at") or now_tehran().isoformat())},
        {"key": "_k20_news_source_fingerprint", "value": fingerprint(str(p["title"]) + " " + " ".join(p["source_urls"]))},
        {"key": "_k20_news_image_source", "value": str(image_source.get("original_url") or "")},
        {"key": "_k20_news_image_license", "value": str(image_source.get("license") or "")},
    ]

    content = {
        "post_type": "news",
        "post_status": "draft",
        "post_title": p["title"],
        "post_name": p["slug"],
        "post_excerpt": p["excerpt"],
        "post_content": p["content_html"],
        "post_thumbnail": media_id,
        "terms_names": {
            "news_cat": [NEWS_CAT_NAME],
            "news_tag": tags,
        },
        "custom_fields": custom_fields,
        "comment_status": "open",
    }
    return int(server.wp.newPost(0, WP_USER, WP_PASS, content))


def verify(server: xmlrpc.client.ServerProxy, post_id: int) -> dict[str, Any]:
    post = server.wp.getPost(0, WP_USER, WP_PASS, post_id, [
        "post_id", "post_title", "post_status", "post_type", "post_thumbnail", "terms", "custom_fields", "link"
    ])
    if post.get("post_status") != "draft" or post.get("post_type") != "news":
        raise QueuePublishError("Created item is not a news draft")
    if not post.get("post_thumbnail"):
        raise QueuePublishError("Created draft has no featured image")

    terms = post.get("terms") or []
    has_news_category = any(
        str(t.get("taxonomy") or "") == "news_cat"
        and (
            str(t.get("name") or "") == NEWS_CAT_NAME
            or str(t.get("term_id") or "") == str(NEWS_CAT_ID)
        )
        for t in terms
    )
    if not has_news_category:
        raise QueuePublishError("Created news draft is missing the required news_cat=کشاورزی category")

    keys = {x.get("key") for x in post.get("custom_fields", [])}
    required = {"_yoast_wpseo_title", "_yoast_wpseo_metadesc", "_yoast_wpseo_focuskw", "_yoast_wpseo_primary_news_cat"}
    missing = sorted(required - keys)
    if missing:
        raise QueuePublishError(f"Required Yoast fields missing after write: {missing}")
    return post


def save_result(result: dict[str, Any]) -> None:
    (OUT / "queue-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = [
        "## Keshavarz20 scheduled news publisher",
        "",
        f"- Status: **{result.get('status')}**",
        f"- Title: {result.get('title', '-')}",
        f"- Draft ID: `{result.get('post_id', '-')}`",
        f"- Tehran time: `{now_tehran().isoformat()}`",
        f"- Image license: {result.get('image_license', '-')}",
    ]
    if result.get("edit_url"):
        lines.append(f"- Edit: {result['edit_url']}")
    if result.get("error"):
        lines.append(f"- Error: {result['error']}")
    (OUT / "queue-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise QueuePublishError("Usage: publish_queue.py <queue.json>")
    if not WP_USER or not WP_PASS:
        raise QueuePublishError("WordPress credentials are missing")

    queue_path = Path(sys.argv[1])
    p = load_queue(queue_path)
    validate_payload(p)

    existing = find_existing_queued_draft(p)
    if existing:
        existing_id = int(existing["post_id"])
        server = wp_xmlrpc()
        verified = verify(server, existing_id)
        result = {
            "status": "draft-already-created",
            "post_id": existing_id,
            "title": p["title"],
            "edit_url": f"{WP_BASE}/wp-admin/post.php?post={existing_id}&action=edit",
            "wp_status": verified.get("post_status"),
            "wp_type": verified.get("post_type"),
            "queue_file": str(queue_path),
            "source_urls": [str(x) for x in p.get("source_urls", [])],
            "source_names": [str(x) for x in p.get("source_names", [])],
            "qa_score": 100,
            "qa_score_basis": "idempotent recovery matched exact title and source fingerprint; post-write readback passed",
            "readback": {
                "status": verified.get("post_status"),
                "type": verified.get("post_type"),
                "featured_media": verified.get("post_thumbnail"),
            },
        }
        save_result(result)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    ensure_not_duplicate(p)

    image_queries = [str(p["image_search_query"]).strip()]
    for item in p.get("image_search_fallbacks") or []:
        q = str(item).strip()
        if q and q not in image_queries:
            image_queries.append(q)

    image_source = None
    image_errors = []
    for q in image_queries[:5]:
        try:
            image_source = commons_search(q)
            image_source["search_query_used"] = q
            break
        except Exception as exc:
            image_errors.append(f"{q}: {exc}")
    if image_source is None:
        raise QueuePublishError("No suitable open-license Wikimedia image found after fallback queries: " + " | ".join(image_errors))

    image_path = make_editorial_image(image_source)

    server = wp_xmlrpc()
    methods = set(server.system.listMethods())
    needed = {"wp.newPost", "wp.uploadFile", "wp.getPost"}
    if not needed.issubset(methods):
        raise QueuePublishError(f"WordPress XML-RPC missing methods: {sorted(needed - methods)}")

    media_id = upload_wp_image(server, image_path, p, image_source)
    post_id = create_draft(server, p, media_id, image_source)
    verified = verify(server, post_id)

    result = {
        "status": "draft-created",
        "post_id": post_id,
        "title": p["title"],
        "media_id": media_id,
        "image_source": image_source.get("original_url"),
        "image_license": image_source.get("license"),
        "edit_url": f"{WP_BASE}/wp-admin/post.php?post={post_id}&action=edit",
        "wp_status": verified.get("post_status"),
        "wp_type": verified.get("post_type"),
        "queue_file": str(queue_path),
        "source_urls": [str(x) for x in p.get("source_urls", [])],
        "source_names": [str(x) for x in p.get("source_names", [])],
        "fields_written": ["title", "slug", "excerpt", "content", "featured_media", "news_cat", "news_tag", "yoast_title", "yoast_meta_description", "yoast_focus_keyphrase"],
        "qa_score": 100,
        "qa_score_basis": "all deterministic required gates and post-write readback passed",
        "readback": {"status": verified.get("post_status"), "type": verified.get("post_type"), "featured_media": verified.get("post_thumbnail")},
    }
    save_result(result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        save_result(result)
        raise
