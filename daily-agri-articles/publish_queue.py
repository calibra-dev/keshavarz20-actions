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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover
    arabic_reshaper = None
    get_display = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

TEHRAN = pytz.timezone("Asia/Tehran")
WP_BASE = os.environ.get("WP_BASE_URL", "https://keshavarz20.com").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Keshavarz20ScheduledArticles/1.0 (+https://keshavarz20.com/)"})


class QueuePublishError(RuntimeError):
    pass


def now_tehran() -> datetime:
    return datetime.now(TEHRAN)


def strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def normalize_fa(value: str) -> str:
    value = strip_html(value).lower().replace("ي", "ی").replace("ك", "ک")
    value = re.sub(r"[\u200c\u200f\u202a-\u202e]", "", value)
    return re.sub(r"[^\w\u0600-\u06FF]+", "", value)


def fingerprint(value: str) -> str:
    return hashlib.sha256(normalize_fa(value).encode("utf-8")).hexdigest()[:24]


def safe_slug(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")[:120]


def load_queue(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise QueuePublishError(f"Queue file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise QueuePublishError("Queue payload must be a JSON object")
    return data


def validate_payload(p: dict[str, Any]) -> None:
    required = [
        "title", "slug", "excerpt", "content_html", "focus_keyphrase", "seo_title",
        "meta_description", "related_keyphrases", "category_name", "tags", "source_urls",
        "source_names", "research_summary", "image_search_query", "image_title", "alt_text", "faq_items",
    ]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise QueuePublishError(f"Missing required queue fields: {', '.join(missing)}")

    p["slug"] = safe_slug(str(p["slug"]))
    if not p["slug"]:
        raise QueuePublishError("Slug must be English ASCII and non-empty")

    text = strip_html(str(p["content_html"]))
    if len(text) < 4500:
        raise QueuePublishError("Article is too short for the K20 long-form article engine")

    for section in ("جمع‌بندی", "نظر کارشناسی کشاورز بیست"):
        if section not in str(p["content_html"]):
            raise QueuePublishError(f"Required section missing: {section}")

    faq = p.get("faq_items")
    if not isinstance(faq, list) or len(faq) != 15:
        raise QueuePublishError("faq_items must contain exactly 15 question/answer objects")
    for i, item in enumerate(faq, 1):
        if not isinstance(item, dict) or not item.get("question") or not item.get("answer"):
            raise QueuePublishError(f"FAQ item {i} is incomplete")
        if normalize_fa(str(item["question"])) not in normalize_fa(text):
            raise QueuePublishError(f"FAQ question {i} is not present in content_html")

    tags = p.get("tags")
    if not isinstance(tags, list) or not (4 <= len(tags) <= 10):
        raise QueuePublishError("tags must contain 4 to 10 useful items")

    related = p.get("related_keyphrases")
    if not isinstance(related, list) or not (3 <= len(related) <= 8):
        raise QueuePublishError("related_keyphrases must contain 3 to 8 items")

    urls = p.get("source_urls")
    if not isinstance(urls, list) or len(urls) < 3:
        raise QueuePublishError("At least three credible research source URLs are required")
    if any(not str(u).startswith(("http://", "https://")) for u in urls):
        raise QueuePublishError("Every source URL must be absolute http(s)")

    if len(str(p["meta_description"]).strip()) < 80 or len(str(p["meta_description"]).strip()) > 185:
        raise QueuePublishError("meta_description must be 80 to 185 characters")

    internal_links = re.findall(
        r"href=['\"](https?://(?:www\.)?keshavarz20\.com/[^'\"]+)['\"]",
        str(p["content_html"]),
        flags=re.I,
    )
    if len(set(internal_links)) < 2:
        raise QueuePublishError("Article must contain at least two useful internal Keshavarz20 links")


def recent_posts(limit: int = 100) -> list[dict[str, str]]:
    r = SESSION.get(
        f"{WP_BASE}/wp-json/wp/v2/posts",
        params={"per_page": min(limit, 100), "orderby": "date", "order": "desc", "status": "publish,draft,pending,future,private"},
        auth=(WP_USER, WP_PASS),
        timeout=30,
    )
    if not r.ok:
        raise QueuePublishError(f"Could not inspect recent WordPress posts: HTTP {r.status_code}")
    rows = []
    for row in r.json():
        title = row.get("title", {})
        if isinstance(title, dict):
            title = title.get("rendered", "")
        rows.append({"title": strip_html(str(title or "")), "slug": str(row.get("slug") or "")})
    return rows


def title_token_set(value: str) -> set[str]:
    raw = strip_html(value).replace("ي", "ی").replace("ك", "ک").lower()
    tokens = re.findall(r"[\u0600-\u06FFA-Za-z0-9]{3,}", raw)
    stop = {"برای", "های", "این", "است", "راهنمای", "چگونه", "بهترین", "کشاورزی", "کشاورز"}
    return {t for t in tokens if t not in stop}


def ensure_not_duplicate(p: dict[str, Any]) -> None:
    wanted_fp = fingerprint(str(p["title"]))
    wanted_slug = str(p["slug"])
    wanted_tokens = title_token_set(str(p["title"]))
    for row in recent_posts():
        if fingerprint(row["title"]) == wanted_fp or row["slug"] == wanted_slug:
            raise QueuePublishError(f"Duplicate article detected: {row['title']}")
        other = title_token_set(row["title"])
        if wanted_tokens and other:
            overlap = len(wanted_tokens & other) / max(1, len(wanted_tokens | other))
            if overlap >= 0.72:
                raise QueuePublishError(f"Near-duplicate article title detected: {row['title']}")


def resolve_category(p: dict[str, Any]) -> tuple[int, str]:
    requested_id = int(p.get("category_id") or 0)
    requested_name = str(p["category_name"]).strip()
    params: dict[str, Any] = {"per_page": 100, "hide_empty": False}
    if requested_id:
        r = SESSION.get(f"{WP_BASE}/wp-json/wp/v2/categories/{requested_id}", auth=(WP_USER, WP_PASS), timeout=30)
        if r.ok:
            row = r.json()
            if normalize_fa(str(row.get("name") or "")) == normalize_fa(requested_name):
                return int(row["id"]), str(row["name"])
    r = SESSION.get(f"{WP_BASE}/wp-json/wp/v2/categories", params=params, auth=(WP_USER, WP_PASS), timeout=30)
    if not r.ok:
        raise QueuePublishError(f"Could not inspect WordPress categories: HTTP {r.status_code}")
    for row in r.json():
        if normalize_fa(str(row.get("name") or "")) == normalize_fa(requested_name):
            return int(row["id"]), str(row["name"])
    raise QueuePublishError(f"Requested category does not already exist: {requested_name}")


def commons_search(query: str) -> dict[str, Any]:
    api = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 35,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1800,
        "format": "json", "formatversion": 2,
    }
    r = SESSION.get(api, params=params, timeout=40)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or []
    candidates: list[dict[str, Any]] = []
    for page in pages:
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        if str(info.get("mime") or "") not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        width, height = int(info.get("width") or 0), int(info.get("height") or 0)
        if width < 1000 or height < 600:
            continue
        meta = info.get("extmetadata") or {}
        lic = ((meta.get("LicenseShortName") or {}).get("value") or "").strip()
        lic_low = lic.lower()
        if not any(x in lic_low for x in ("cc0", "public domain", "cc by", "creative commons")):
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        score = min(width, 5000) / 600
        if width / max(height, 1) >= 1.4:
            score += 10
        if "cc0" in lic_low or "public domain" in lic_low:
            score += 15
        candidates.append({
            "score": score, "url": url,
            "original_url": info.get("descriptionurl") or page.get("canonicalurl") or "",
            "title": page.get("title") or "", "license": lic,
            "artist": strip_html(((meta.get("Artist") or {}).get("value") or "")),
        })
    if not candidates:
        raise QueuePublishError(f"No suitable open-license Wikimedia image found for: {query}")
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def rtl(text: str) -> str:
    if arabic_reshaper and get_display:
        return get_display(arabic_reshaper.reshape(text))
    return text


def make_editorial_cover(source: dict[str, Any], p: dict[str, Any]) -> Path:
    r = SESSION.get(source["url"], timeout=60)
    r.raise_for_status()
    raw = OUT / "article-image-source"
    raw.write_bytes(r.content)
    target = OUT / "featured-article.webp"
    with Image.open(raw) as im:
        im = im.convert("RGB")
        w, h = im.size
        desired = 16 / 9
        current = w / max(h, 1)
        if current > desired:
            nw = int(h * desired)
            left = max(0, (w - nw) // 2)
            im = im.crop((left, 0, left + nw, h))
        else:
            nh = int(w / desired)
            top = max(0, (h - nh) // 2)
            im = im.crop((0, top, w, top + nh))
        im = im.resize((1280, 720), Image.Resampling.LANCZOS)
        im = ImageEnhance.Contrast(im).enhance(1.07)
        im = ImageEnhance.Color(im).enhance(1.04)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=85, threshold=3))

        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle((40, 430, 1240, 680), radius=28, fill=(10, 20, 18, 190))
        od.rounded_rectangle((52, 442, 250, 500), radius=20, fill=(240, 240, 230, 235))
        small_font = find_font(26)
        title_font = find_font(48)
        od.text((230, 470), rtl("کشاورز بیست"), font=small_font, fill=(20, 35, 28, 255), anchor="mm")

        title = str(p.get("image_title") or p["title"]).strip()
        words = title.split()
        lines: list[str] = []
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            bbox = od.textbbox((0, 0), rtl(test), font=title_font)
            if bbox[2] - bbox[0] <= 1080:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        lines = lines[:2]
        y = 545
        for ln in lines:
            od.text((1200, y), rtl(ln), font=title_font, fill=(255, 255, 255, 255), anchor="ra")
            y += 62
        im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
        im.save(target, "WEBP", quality=88, method=6)
    raw.unlink(missing_ok=True)
    return target


def wp_xmlrpc() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(f"{WP_BASE}/xmlrpc.php", allow_none=True)


def upload_wp_image(server: xmlrpc.client.ServerProxy, path: Path, p: dict[str, Any], source: dict[str, Any]) -> int:
    payload = {
        "name": f"keshavarz20-article-{now_tehran().strftime('%Y%m%d-%H%M%S')}.webp",
        "type": "image/webp", "bits": xmlrpc.client.Binary(path.read_bytes()), "overwrite": False, "post_id": 0,
    }
    media = server.wp.uploadFile(0, WP_USER, WP_PASS, payload)
    media_id = int(media["id"])
    description = " | ".join(x for x in [source.get("title", ""), source.get("artist", ""), source.get("license", ""), source.get("original_url", "")] if x)
    try:
        server.wp.editPost(0, WP_USER, WP_PASS, media_id, {
            "post_title": p.get("image_title") or p["title"], "post_excerpt": "", "post_content": description,
        })
    except Exception:
        pass
    rr = SESSION.post(
        f"{WP_BASE}/wp-json/wp/v2/media/{media_id}",
        json={"alt_text": p["alt_text"], "caption": "", "description": description},
        auth=(WP_USER, WP_PASS), timeout=30,
    )
    if not rr.ok:
        print(f"Warning: media metadata update returned HTTP {rr.status_code}", file=sys.stderr)
    return media_id


def create_draft(server: xmlrpc.client.ServerProxy, p: dict[str, Any], media_id: int, category_id: int, category_name: str, image_source: dict[str, Any]) -> int:
    related = [str(x).strip() for x in p.get("related_keyphrases", []) if str(x).strip()][:8]
    tags = [str(x).strip() for x in p.get("tags", []) if str(x).strip()][:10]
    custom_fields = [
        {"key": "_yoast_wpseo_title", "value": p["seo_title"]},
        {"key": "_yoast_wpseo_metadesc", "value": p["meta_description"]},
        {"key": "_yoast_wpseo_focuskw", "value": p["focus_keyphrase"]},
        {"key": "_yoast_wpseo_primary_category", "value": str(category_id)},
        {"key": "_yoast_wpseo_focuskeywords", "value": json.dumps([{"keyword": p["focus_keyphrase"], "score": 0}], ensure_ascii=False)},
        {"key": "_yoast_wpseo_keywordsynonyms", "value": json.dumps([", ".join(related)], ensure_ascii=False)},
        {"key": "_k20_article_engine", "value": "chatgpt-pro-scheduled-v1"},
        {"key": "_k20_article_generated_at", "value": str(p.get("generated_at") or now_tehran().isoformat())},
        {"key": "_k20_article_sources", "value": json.dumps(p["source_urls"], ensure_ascii=False)},
        {"key": "_k20_article_research_summary", "value": str(p["research_summary"])[:5000]},
        {"key": "_k20_article_fingerprint", "value": fingerprint(str(p["title"]) + " " + " ".join(p["source_urls"]))},
        {"key": "_k20_article_image_source", "value": str(image_source.get("original_url") or "")},
        {"key": "_k20_article_image_license", "value": str(image_source.get("license") or "")},
    ]
    content = {
        "post_type": "post", "post_status": "draft", "post_title": p["title"], "post_name": p["slug"],
        "post_excerpt": p["excerpt"], "post_content": p["content_html"], "post_thumbnail": media_id,
        "terms_names": {"category": [category_name], "post_tag": tags},
        "custom_fields": custom_fields, "comment_status": "open",
    }
    return int(server.wp.newPost(0, WP_USER, WP_PASS, content))


def verify(server: xmlrpc.client.ServerProxy, post_id: int, category_id: int) -> dict[str, Any]:
    post = server.wp.getPost(0, WP_USER, WP_PASS, post_id, [
        "post_id", "post_title", "post_status", "post_type", "post_thumbnail", "terms", "custom_fields", "link"
    ])
    if post.get("post_status") != "draft" or post.get("post_type") != "post":
        raise QueuePublishError("Created item is not a normal WordPress post draft")
    if not post.get("post_thumbnail"):
        raise QueuePublishError("Created draft has no featured image")
    keys = {x.get("key") for x in post.get("custom_fields", [])}
    required = {"_yoast_wpseo_title", "_yoast_wpseo_metadesc", "_yoast_wpseo_focuskw", "_yoast_wpseo_primary_category", "_k20_article_engine"}
    missing = sorted(required - keys)
    if missing:
        raise QueuePublishError(f"Required SEO/audit fields missing after write: {missing}")
    category_ids = {int(t.get("term_id")) for t in post.get("terms", []) if t.get("taxonomy") == "category" and t.get("term_id")}
    if category_id not in category_ids:
        raise QueuePublishError("Requested category is missing after write")
    return post


def save_result(result: dict[str, Any]) -> None:
    (OUT / "queue-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "## Keshavarz20 scheduled article publisher", "",
        f"- Status: **{result.get('status')}**", f"- Title: {result.get('title', '-')}",
        f"- Draft ID: `{result.get('post_id', '-')}`", f"- Tehran time: `{now_tehran().isoformat()}`",
        f"- Category: {result.get('category', '-')}", f"- Image license: {result.get('image_license', '-')}",
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
    ensure_not_duplicate(p)
    category_id, category_name = resolve_category(p)
    image_source = commons_search(str(p["image_search_query"]))
    image_path = make_editorial_cover(image_source, p)

    server = wp_xmlrpc()
    methods = set(server.system.listMethods())
    needed = {"wp.newPost", "wp.uploadFile", "wp.getPost"}
    if not needed.issubset(methods):
        raise QueuePublishError(f"WordPress XML-RPC missing methods: {sorted(needed - methods)}")

    media_id = upload_wp_image(server, image_path, p, image_source)
    post_id = create_draft(server, p, media_id, category_id, category_name, image_source)
    verified = verify(server, post_id, category_id)
    result = {
        "status": "draft-created", "post_id": post_id, "title": p["title"], "media_id": media_id,
        "category": category_name, "category_id": category_id, "image_source": image_source.get("original_url"),
        "image_license": image_source.get("license"), "edit_url": f"{WP_BASE}/wp-admin/post.php?post={post_id}&action=edit",
        "wp_status": verified.get("post_status"), "wp_type": verified.get("post_type"), "queue_file": str(queue_path),
    }
    save_result(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        save_result({"status": "failed", "error": str(exc)})
        raise
