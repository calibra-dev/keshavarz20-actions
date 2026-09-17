from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import textwrap
import xmlrpc.client
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser
import pytz
import requests
import trafilatura
from dateutil import parser as dtparser
from openai import OpenAI
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

TEHRAN = pytz.timezone("Asia/Tehran")
WP_BASE = os.environ.get("WP_BASE_URL", "https://keshavarz20.com").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-5.6")
IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
LOOKBACK_HOURS = int(os.environ.get("K20_LOOKBACK_HOURS", "24"))
DRY_RUN = os.environ.get("K20_DRY_RUN", "false").lower() in {"1", "true", "yes"}
NEWS_CAT_ID = int(os.environ.get("K20_NEWS_CATEGORY_ID", "839"))
NEWS_CAT_NAME = os.environ.get("K20_NEWS_CATEGORY_NAME", "کشاورزی")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Keshavarz20DailyNews/1.0 (+https://keshavarz20.com/)"})

SEARCH_TOPICS = [
    "اخبار کشاورزی ایران",
    "وزارت جهاد کشاورزی کشاورزان",
    "گندم خرید تضمینی",
    "برنج تولید واردات",
    "آب کشاورزی خشکسالی آبیاری",
    "کود نهاده کشاورزی",
    "دام طیور نهاده",
    "پسته خرما زعفران باغداری",
    "صادرات محصولات کشاورزی",
    "فناوری کشاورزی گلخانه آبیاری هوشمند",
]

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=fa&gl=IR&ceid=IR:fa"

BLOCKED_DOMAINS = {
    "instagram.com", "facebook.com", "x.com", "twitter.com", "t.me", "telegram.me",
    "youtube.com", "youtu.be", "aparat.com",
}

HIGH_TRUST_HINTS = {
    "irna.ir": 12,
    "isna.ir": 12,
    "mehrnews.com": 10,
    "tasnimnews.com": 10,
    "farsnews.ir": 9,
    "iana.ir": 14,
    "maj.ir": 15,
    "agri-jahad.ir": 12,
    "ilna.ir": 8,
}


@dataclass
class Candidate:
    title: str
    url: str
    source: str = ""
    published_at: str | None = None
    snippet: str = ""
    query: str = ""
    body: str = ""
    score: float = 0.0

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc.lower().removeprefix("www.")


class NewsEngineError(RuntimeError):
    pass


def now_tehran() -> datetime:
    return datetime.now(TEHRAN)


def strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def safe_json_from_text(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(1))


def canonical_url(url: str) -> str:
    return re.sub(r"[?#].*$", "", url.strip()).rstrip("/")


def fingerprint(text: str) -> str:
    compact = re.sub(r"[^\w\u0600-\u06FF]+", "", text.lower())
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()[:24]


def fetch_recent_wordpress_titles(limit: int = 80) -> list[dict[str, Any]]:
    # CPT is public on this site. This read also provides a second duplicate guard.
    try:
        r = SESSION.get(
            f"{WP_BASE}/wp-json/wp/v2/news",
            params={"per_page": min(limit, 100), "orderby": "date", "order": "desc", "status": "publish,draft,pending,future,private"},
            auth=(WP_USER, WP_PASS) if WP_USER and WP_PASS else None,
            timeout=25,
        )
        if r.ok:
            return r.json()
    except Exception:
        pass
    return []


def collect_rss() -> list[Candidate]:
    cutoff = now_tehran() - timedelta(hours=LOOKBACK_HOURS + 3)
    out: list[Candidate] = []
    seen: set[str] = set()

    for query in SEARCH_TOPICS:
        url = GOOGLE_NEWS.format(q=requests.utils.quote(f"{query} when:1d"))
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            link = canonical_url(getattr(entry, "link", ""))
            if not link or link in seen:
                continue
            title = strip_html(getattr(entry, "title", ""))
            if not title:
                continue

            dt = None
            raw_dt = getattr(entry, "published", None) or getattr(entry, "updated", None)
            if raw_dt:
                try:
                    dt = dtparser.parse(raw_dt)
                    if dt.tzinfo is None:
                        dt = pytz.utc.localize(dt)
                    dt = dt.astimezone(TEHRAN)
                except Exception:
                    dt = None
            if dt and dt < cutoff:
                continue

            source = ""
            if getattr(entry, "source", None):
                source = str(getattr(entry.source, "title", "") or "")
            snippet = strip_html(getattr(entry, "summary", ""))
            seen.add(link)
            out.append(Candidate(title, link, source, dt.isoformat() if dt else None, snippet, query))

    return out


def ai_web_research() -> list[Candidate]:
    prompt = f"""
امروز به وقت تهران {now_tehran().strftime('%Y-%m-%d %H:%M')} است.
برای بخش «اخبار کشاورزی» کشاورز بیست، اخبار منتشرشده در {LOOKBACK_HOURS} ساعت گذشته را در وب جست‌وجو کن.
هدف انتخاب خبرهای واقعی، مهم، تازه و اثرگذار برای کشاورز/باغدار/دامدار ایرانی است.

حوزه‌ها: تولید محصولات، آب و آبیاری، خشکسالی، قیمت و خرید تضمینی، نهاده و کود، دام و طیور، صادرات/واردات محصولات کشاورزی، فناوری کشاورزی، گلخانه، باغداری و تصمیم‌های رسمی مرتبط با بخش کشاورزی.

قواعد:
- خبر باید واقعاً در بازه زمانی خواسته‌شده منتشر یا به‌طور معنادار به‌روزرسانی شده باشد.
- از شایعه، شبکه اجتماعی بدون منبع، خبر تبلیغاتی و بازنشر فاقد منبع اصلی دوری کن.
- برای رویداد مهم ترجیحاً دست‌کم دو منبع مستقل یا یک منبع رسمی/اولیه پیدا کن.
- اگر موضوع سیاسی/دولتی است، کاملاً خنثی و مبتنی بر واقعیت بمان.
- فقط URL واقعی صفحه خبر/منبع را بده، نه صفحه نتایج جست‌وجو.

فقط JSON معتبر برگردان، حداکثر 12 مورد:
[
  {{"title":"...","url":"https://...","source":"...","published_at":"ISO-8601 or empty","snippet":"خلاصه واقعیت خبر در یک جمله"}}
]
"""
    try:
        response = client.responses.create(
            model=TEXT_MODEL,
            tools=[{"type": "web_search"}],
            input=prompt,
        )
        data = safe_json_from_text(response.output_text)
        results: list[Candidate] = []
        for row in data if isinstance(data, list) else []:
            url = canonical_url(str(row.get("url", "")))
            if not url.startswith("http"):
                continue
            results.append(Candidate(
                title=str(row.get("title", "")).strip(),
                url=url,
                source=str(row.get("source", "")).strip(),
                published_at=str(row.get("published_at") or "") or None,
                snippet=str(row.get("snippet", "")).strip(),
                query="AI web research",
            ))
        return results
    except Exception as exc:
        print(f"AI web research unavailable: {exc}", file=sys.stderr)
        return []


def merge_candidates(*groups: list[Candidate]) -> list[Candidate]:
    by_key: dict[str, Candidate] = {}
    for group in groups:
        for c in group:
            if not c.title or not c.url:
                continue
            if c.domain in BLOCKED_DOMAINS:
                continue
            # Google News redirect URLs can still be usable, but a direct source URL wins.
            key = fingerprint(c.title)
            old = by_key.get(key)
            if old is None or ("news.google.com" in old.domain and "news.google.com" not in c.domain):
                by_key[key] = c
    return list(by_key.values())


def extract_article(c: Candidate) -> Candidate:
    try:
        downloaded = trafilatura.fetch_url(c.url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                include_links=False,
                favor_precision=True,
            ) or ""
            c.body = re.sub(r"\n{3,}", "\n\n", text).strip()[:20000]
    except Exception:
        pass
    return c


def lexical_score(c: Candidate) -> float:
    hay = f"{c.title} {c.snippet} {c.body[:4000]}".lower()
    score = 0.0
    terms = {
        "کشاورز": 4, "کشاورزی": 5, "گندم": 6, "برنج": 5, "آبیاری": 6,
        "خشکسالی": 5, "آب": 3, "نهاده": 5, "کود": 4, "دام": 4, "طیور": 4,
        "پسته": 4, "زعفران": 4, "خرما": 4, "گلخانه": 4, "صادرات": 4,
        "واردات": 4, "خرید تضمینی": 7, "قیمت": 4, "تولید": 4, "برداشت": 4,
    }
    for term, weight in terms.items():
        if term in hay:
            score += weight
    for domain, bonus in HIGH_TRUST_HINTS.items():
        if c.domain.endswith(domain):
            score += bonus
            break
    if len(c.body) >= 800:
        score += 7
    if len(c.body) >= 1800:
        score += 3
    if c.published_at:
        try:
            dt = dtparser.parse(c.published_at)
            if dt.tzinfo is None:
                dt = TEHRAN.localize(dt)
            age_h = max(0.0, (now_tehran() - dt.astimezone(TEHRAN)).total_seconds() / 3600)
            score += max(0, 12 - age_h / 2)
        except Exception:
            pass
    c.score = round(score, 2)
    return score


def remove_duplicates_against_site(candidates: list[Candidate]) -> list[Candidate]:
    existing = fetch_recent_wordpress_titles()
    existing_titles = []
    for row in existing:
        title = row.get("title", {})
        if isinstance(title, dict):
            title = title.get("rendered", "")
        if title:
            existing_titles.append(strip_html(str(title)))
    existing_fp = {fingerprint(x) for x in existing_titles}
    return [c for c in candidates if fingerprint(c.title) not in existing_fp]


def ai_rank(candidates: list[Candidate]) -> dict[str, Any]:
    compact = []
    for idx, c in enumerate(candidates[:24]):
        compact.append({
            "index": idx,
            "title": c.title,
            "source": c.source,
            "url": c.url,
            "published_at": c.published_at,
            "snippet": c.snippet[:500],
            "lexical_score": c.score,
            "article_excerpt": c.body[:2200],
        })

    prompt = f"""
تو سردبیر کشاورزی کشاورز بیست هستی. از میان کاندیداهای زیر دقیقاً یک خبر را برای پیش‌نویس امروز انتخاب کن.
معیارها به ترتیب: تازگی واقعی در {LOOKBACK_HOURS} ساعت، اثر مستقیم بر کشاورزان ایران، اهمیت ملی/منطقه‌ای، میزان جست‌وجوپذیری و جذابیت خبری، اعتبار و قابلیت راستی‌آزمایی، تازگی نسبت به خبرهای تکراری.
خبر زرد یا صرفاً تبلیغاتی انتخاب نکن. اگر یک ادعای مهم فقط یک منبع ضعیف دارد، امتیاز آن را کم کن.

کاندیداها:
{json.dumps(compact, ensure_ascii=False)}

فقط JSON بده:
{{
  "selected_index": 0,
  "reason": "دلیل کوتاه",
  "importance_score": 0,
  "trend_score": 0,
  "farmer_impact_score": 0,
  "confidence": 0.0,
  "needs_crosscheck": true
}}
"""
    response = client.responses.create(model=TEXT_MODEL, input=prompt)
    return safe_json_from_text(response.output_text)


def crosscheck(selected: Candidate, all_candidates: list[Candidate]) -> dict[str, Any]:
    related = [c for c in all_candidates if c is not selected and (set(selected.title.split()) & set(c.title.split()))]
    evidence = [{"title": selected.title, "url": selected.url, "source": selected.source, "body": selected.body[:5000]}]
    for c in related[:4]:
        evidence.append({"title": c.title, "url": c.url, "source": c.source, "body": c.body[:2200], "snippet": c.snippet})

    prompt = f"""
خبر انتخاب‌شده برای کشاورز بیست را fact-check کن. فقط از شواهد زیر و جست‌وجوی وب استفاده کن. اعداد، تاریخ‌ها، نام اشخاص/نهادها و نسبت دادن اظهارات باید دقیق باشد. اگر بین منابع اختلاف وجود دارد، آن را صریح علامت بزن. از ساختن واقعیت جدید خودداری کن.

شواهد اولیه:
{json.dumps(evidence, ensure_ascii=False)}

فقط JSON:
{{
 "verified": true,
 "core_facts": ["..."],
 "uncertain_claims": ["..."],
 "source_urls": ["https://..."],
 "source_names": ["..."],
 "published_at_best": "ISO-8601 or empty"
}}
"""
    try:
        response = client.responses.create(model=TEXT_MODEL, tools=[{"type": "web_search"}], input=prompt)
        return safe_json_from_text(response.output_text)
    except Exception:
        return {
            "verified": bool(selected.body),
            "core_facts": [selected.snippet or selected.title],
            "uncertain_claims": [],
            "source_urls": [selected.url],
            "source_names": [selected.source],
            "published_at_best": selected.published_at or "",
        }


def author_article(selected: Candidate, verification: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
برای سایت تخصصی کشاورز بیست یک خبر فارسی حرفه‌ای و انسان‌نویس بنویس. این متن «بازنویسی تحریریه» است نه کپی خبر منبع.

خبر انتخاب‌شده:
عنوان منبع: {selected.title}
منبع اولیه: {selected.source}
URL: {selected.url}
متن استخراج‌شده:
{selected.body[:12000]}

Fact-check:
{json.dumps(verification, ensure_ascii=False)}

قواعد تحریریه:
- زبان طبیعی، حرفه‌ای و روان؛ بدون عبارت‌های کلیشه‌ای AI، بدون پرگویی و بدون تکرار مصنوعی کلیدواژه.
- تیتر واضح و جذاب اما غیرکلیک‌بیتی؛ اگر عدد یا ادعا در تیتر است باید fact-check شده باشد.
- لید 2 تا 3 جمله‌ای که اصل خبر را سریع بگوید.
- سپس 3 تا 6 بخش با H2 متناسب با خبر.
- برای ادعاهای مهم، در متن با عبارت «بر اساس گزارش/اعلام ...» منبع را مشخص کن.
- یک بخش «این خبر برای کشاورزان چه معنایی دارد؟» با اثر عملی و محتاطانه.
- یک بخش «جمع‌بندی».
- یک بخش نهایی «نظر کارشناسی کشاورز بیست» که تحلیل تحریریه باشد، از خبر جدا باشد و چیزی را به عنوان واقعیت اثبات‌نشده بیان نکند.
- در پایان «منابع خبر» با لینک‌های اصلی بنویس.
- اگر خبر درباره تصمیم دولتی/سیاسی است، خنثی، توصیفی و مبتنی بر اسناد باش؛ از جانبداری و حدس درباره انگیزه‌ها پرهیز کن.
- HTML تمیز WordPress: فقط p,h2,h3,ul,li,strong,a,blockquote. هیچ style/script/table نده.
- نامک لاتین کوتاه و پایدار باشد.
- تصویر شاخص باید واقع‌گرایانه، خبری، جذاب، بدون متن و بدون لوگوی جعلی باشد؛ برای کارت افقی صفحه اصلی مناسب باشد.

SEO:
- focus_keyphrase فقط یک عبارت اصلی طبیعی.
- related_keyphrases آرایه 3 تا 6 عبارت مرتبط.
- seo_title حدود 45 تا 60 کاراکتر و طبیعی.
- meta_description تقریباً 125 تا 155 کاراکتر، دقیق و جذاب.
- excerpt حدود 25 تا 45 واژه.
- tags بین 4 تا 8 برچسب دقیق.
- alt_text توصیفی و کوتاه.

فقط JSON معتبر:
{{
 "title":"...",
 "slug":"...",
 "excerpt":"...",
 "content_html":"...",
 "focus_keyphrase":"...",
 "related_keyphrases":["..."],
 "seo_title":"...",
 "meta_description":"...",
 "tags":["..."],
 "image_prompt":"...",
 "image_title":"...",
 "alt_text":"..."
}}
"""
    response = client.responses.create(model=TEXT_MODEL, input=prompt)
    data = safe_json_from_text(response.output_text)
    validate_article(data)
    return data


def validate_article(a: dict[str, Any]) -> None:
    required = ["title", "slug", "excerpt", "content_html", "focus_keyphrase", "seo_title", "meta_description", "image_prompt", "alt_text"]
    missing = [k for k in required if not str(a.get(k, "")).strip()]
    if missing:
        raise NewsEngineError(f"Article JSON missing: {', '.join(missing)}")
    if len(strip_html(a["content_html"])) < 900:
        raise NewsEngineError("Generated article is too short")
    if "نظر کارشناسی کشاورز بیست" not in a["content_html"]:
        raise NewsEngineError("Editorial analysis section is missing")
    if "جمع‌بندی" not in a["content_html"]:
        raise NewsEngineError("Conclusion section is missing")
    if "منابع" not in a["content_html"]:
        raise NewsEngineError("Sources section is missing")


def generate_featured_image(article: dict[str, Any]) -> Path:
    prompt = f"""
Create a premium editorial news photograph for Keshavarz20, an Iranian agriculture publication.
Topic: {article['image_prompt']}
Visual requirements: photorealistic, authentic Iranian agricultural context when relevant, natural light, editorial photojournalism, visually clear subject, strong depth, clean composition, no text, no captions, no watermark, no invented brand logo, no UI, no collage. Avoid exaggerated disaster imagery unless factually necessary. Landscape framing optimized for a website news card; keep important subjects inside the central safe area.
"""
    result = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size="1536x1024",
    )
    item = result.data[0]
    target = OUT / "featured-news.webp"
    if getattr(item, "b64_json", None):
        raw = base64.b64decode(item.b64_json)
        temp = OUT / "featured-news-source.png"
        temp.write_bytes(raw)
        with Image.open(temp) as im:
            im = im.convert("RGB")
            # 3:2 source is cropped to 16:9 for the homepage card.
            w, h = im.size
            target_h = int(w * 9 / 16)
            if target_h < h:
                top = (h - target_h) // 2
                im = im.crop((0, top, w, top + target_h))
            im = im.resize((1280, 720), Image.Resampling.LANCZOS)
            im.save(target, "WEBP", quality=88, method=6)
        temp.unlink(missing_ok=True)
        return target
    if getattr(item, "url", None):
        r = SESSION.get(item.url, timeout=90)
        r.raise_for_status()
        temp = OUT / "featured-news-source"
        temp.write_bytes(r.content)
        with Image.open(temp) as im:
            im = im.convert("RGB")
            w, h = im.size
            target_h = int(w * 9 / 16)
            if target_h < h:
                top = (h - target_h) // 2
                im = im.crop((0, top, w, top + target_h))
            im = im.resize((1280, 720), Image.Resampling.LANCZOS)
            im.save(target, "WEBP", quality=88, method=6)
        temp.unlink(missing_ok=True)
        return target
    raise NewsEngineError("Image API returned neither b64_json nor url")


def wp_xmlrpc() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(f"{WP_BASE}/xmlrpc.php", allow_none=True)


def ensure_tags(server: xmlrpc.client.ServerProxy, tags: list[str]) -> list[str]:
    # terms_names on wp.newPost creates missing non-hierarchical terms automatically on normal WP installs.
    return [str(t).strip() for t in tags if str(t).strip()][:8]


def upload_wp_image(server: xmlrpc.client.ServerProxy, path: Path, article: dict[str, Any]) -> int:
    payload = {
        "name": f"keshavarz20-news-{now_tehran().strftime('%Y%m%d')}.webp",
        "type": "image/webp",
        "bits": xmlrpc.client.Binary(path.read_bytes()),
        "overwrite": False,
        "post_id": 0,
    }
    media = server.wp.uploadFile(0, WP_USER, WP_PASS, payload)
    media_id = int(media["id"])
    # wp.editPost can set attachment title/excerpt. Alt text is set by REST below if available.
    try:
        server.wp.editPost(0, WP_USER, WP_PASS, media_id, {
            "post_title": article.get("image_title") or article["title"],
            "post_excerpt": article.get("alt_text", ""),
        })
    except Exception:
        pass
    try:
        r = SESSION.post(
            f"{WP_BASE}/wp-json/wp/v2/media/{media_id}",
            json={"alt_text": article["alt_text"], "caption": ""},
            auth=(WP_USER, WP_PASS), timeout=25,
        )
        if not r.ok:
            print(f"Warning: media alt REST update returned {r.status_code}", file=sys.stderr)
    except Exception as exc:
        print(f"Warning: media alt update failed: {exc}", file=sys.stderr)
    return media_id


def create_wordpress_draft(article: dict[str, Any], media_id: int, verification: dict[str, Any], selected: Candidate) -> int:
    server = wp_xmlrpc()
    sources = verification.get("source_urls") or [selected.url]
    source_names = verification.get("source_names") or [selected.source]
    related = article.get("related_keyphrases") or []

    custom_fields = [
        {"key": "_yoast_wpseo_title", "value": article["seo_title"]},
        {"key": "_yoast_wpseo_metadesc", "value": article["meta_description"]},
        {"key": "_yoast_wpseo_focuskw", "value": article["focus_keyphrase"]},
        {"key": "_yoast_wpseo_primary_news_cat", "value": str(NEWS_CAT_ID)},
        {"key": "_yoast_wpseo_focuskeywords", "value": json.dumps([{"keyword": article["focus_keyphrase"], "score": 0}], ensure_ascii=False)},
        {"key": "_yoast_wpseo_keywordsynonyms", "value": json.dumps([", ".join(related)], ensure_ascii=False)},
        {"key": "_k20_news_source_urls", "value": json.dumps(sources, ensure_ascii=False)},
        {"key": "_k20_news_source_names", "value": json.dumps(source_names, ensure_ascii=False)},
        {"key": "_k20_news_engine", "value": "daily-agri-news-v1"},
        {"key": "_k20_news_generated_at", "value": now_tehran().isoformat()},
        {"key": "_k20_news_source_fingerprint", "value": fingerprint(selected.title + selected.url)},
    ]

    content = {
        "post_type": "news",
        "post_status": "draft",
        "post_title": article["title"],
        "post_name": article["slug"],
        "post_excerpt": article["excerpt"],
        "post_content": article["content_html"],
        "post_thumbnail": media_id,
        "terms_names": {
            "news_cat": [NEWS_CAT_NAME],
            "news_tag": ensure_tags(server, article.get("tags") or []),
        },
        "custom_fields": custom_fields,
        "comment_status": "open",
    }
    post_id = int(server.wp.newPost(0, WP_USER, WP_PASS, content))
    return post_id


def verify_draft(post_id: int) -> dict[str, Any]:
    server = wp_xmlrpc()
    post = server.wp.getPost(0, WP_USER, WP_PASS, post_id, [
        "post_id", "post_title", "post_status", "post_type", "post_thumbnail", "terms", "custom_fields", "link"
    ])
    if post.get("post_status") != "draft" or post.get("post_type") != "news":
        raise NewsEngineError(f"Draft verification failed: {post}")
    keys = {x.get("key") for x in post.get("custom_fields", [])}
    required_meta = {"_yoast_wpseo_title", "_yoast_wpseo_metadesc", "_yoast_wpseo_focuskw", "_yoast_wpseo_primary_news_cat"}
    missing = sorted(required_meta - keys)
    if missing:
        raise NewsEngineError(f"Draft exists but required Yoast meta is missing: {missing}")
    return post


def save_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_summary(result: dict[str, Any]) -> None:
    lines = [
        "## Keshavarz20 Daily Agriculture News",
        "",
        f"- Status: **{result.get('status')}**",
        f"- Tehran time: `{now_tehran().isoformat()}`",
        f"- Selected: {result.get('title', '-')}",
        f"- Source: {result.get('source', '-')}",
        f"- WordPress draft ID: `{result.get('post_id', '-')}`",
        f"- Dry run: `{DRY_RUN}`",
    ]
    if result.get("note"):
        lines.append(f"- Note: {result['note']}")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    print(f"K20 Daily Agriculture News | now={now_tehran().isoformat()} | lookback={LOOKBACK_HOURS}h | dry_run={DRY_RUN}")

    rss = collect_rss()
    web = ai_web_research()
    candidates = merge_candidates(rss, web)
    if not candidates:
        raise NewsEngineError("No news candidates found")

    candidates = remove_duplicates_against_site(candidates)
    if not candidates:
        result = {"status": "skipped", "note": "All discovered stories appear to be duplicates of recent WordPress news."}
        save_json("result.json", result)
        write_summary(result)
        return

    # Only fetch the best-looking subset to avoid hammering publishers.
    for c in candidates:
        lexical_score(c)
    candidates.sort(key=lambda x: x.score, reverse=True)
    enriched = [extract_article(c) for c in candidates[:18]]
    for c in enriched:
        lexical_score(c)
    enriched = [c for c in enriched if c.body or c.snippet]
    enriched.sort(key=lambda x: x.score, reverse=True)
    if not enriched:
        raise NewsEngineError("Candidates were found but none had usable source text")

    rank = ai_rank(enriched)
    idx = int(rank.get("selected_index", 0))
    if idx < 0 or idx >= len(enriched):
        idx = 0
    selected = enriched[idx]

    verification = crosscheck(selected, enriched)
    if not verification.get("verified") and not verification.get("core_facts"):
        raise NewsEngineError("Selected story could not be verified")

    save_json("selected-story.json", {**asdict(selected), "ranking": rank, "verification": verification})

    article = author_article(selected, verification)
    save_json("article.json", article)

    image = generate_featured_image(article)

    if DRY_RUN:
        result = {
            "status": "dry-run-ok",
            "title": article["title"],
            "source": selected.url,
            "post_id": None,
            "image": str(image.relative_to(ROOT)),
        }
        save_json("result.json", result)
        write_summary(result)
        return

    if not all([WP_USER, WP_PASS]):
        raise NewsEngineError("WordPress credentials are missing")

    server = wp_xmlrpc()
    try:
        methods = server.system.listMethods()
        needed = {"wp.newPost", "wp.uploadFile", "wp.getPost"}
        if not needed.issubset(set(methods)):
            raise NewsEngineError(f"WordPress XML-RPC missing methods: {sorted(needed - set(methods))}")
    except xmlrpc.client.ProtocolError as exc:
        raise NewsEngineError(f"XML-RPC unavailable: HTTP {exc.errcode}") from exc

    media_id = upload_wp_image(server, image, article)
    post_id = create_wordpress_draft(article, media_id, verification, selected)
    verified = verify_draft(post_id)

    result = {
        "status": "draft-created",
        "post_id": post_id,
        "title": article["title"],
        "source": selected.url,
        "source_names": verification.get("source_names", []),
        "media_id": media_id,
        "wp_status": verified.get("post_status"),
        "wp_type": verified.get("post_type"),
        "admin_edit_url": f"{WP_BASE}/wp-admin/post.php?post={post_id}&action=edit",
    }
    save_json("result.json", result)
    write_summary(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        save_json("result.json", result)
        write_summary(result)
        raise
