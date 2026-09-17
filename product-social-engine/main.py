from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://keshavarz20.com").rstrip("/")
STATE_PATH = Path(os.getenv("PRODUCT_SOCIAL_STATE", "product-social-engine/state.json"))
OUT_DIR = Path(os.getenv("PRODUCT_SOCIAL_OUT", "product-social-engine/out"))
USER_AGENT = "Keshavarz20-Product-Social-Engine/1.0 (+https://keshavarz20.com)"
REQUEST_TIMEOUT = 30
MAX_IMAGE_BYTES = 15 * 1024 * 1024


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<li\b[^>]*>", " • ", value, flags=re.I)
    value = re.sub(r"</(?:p|div|li|h[1-6]|br)>\s*", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value)
    return value.strip()


def normalize_sentence(value: str, max_chars: int = 380) -> str:
    value = re.sub(r"\s+", " ", value).strip(" -•،,")
    if len(value) <= max_chars:
        return value
    cut = value[: max_chars - 1].rsplit(" ", 1)[0].rstrip("،,.;؛: ")
    return cut + "…"


def fetch_products(session: requests.Session | None = None) -> list[dict[str, Any]]:
    session = session or requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    endpoint = f"{SITE_BASE_URL}/wp-json/wc/store/v1/products"
    products: list[dict[str, Any]] = []
    page = 1

    while True:
        params: list[tuple[str, str | int]] = [
            ("per_page", 100),
            ("page", page),
            ("stock_status[]", "instock"),
            ("catalog_visibility", "visible"),
        ]
        response = session.get(endpoint, params=params, timeout=REQUEST_TIMEOUT)
        if response.status_code == 400 and page == 1:
            params = [("per_page", 100), ("page", page)]
            response = session.get(endpoint, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            raise RuntimeError("WooCommerce Store API returned a non-list payload")
        if not batch:
            break
        products.extend(batch)
        total_pages = int(response.headers.get("X-WP-TotalPages", page))
        if page >= total_pages:
            break
        page += 1

    valid: list[dict[str, Any]] = []
    for product in products:
        if product.get("is_in_stock") is False:
            continue
        images = product.get("images") or []
        if not images or not images[0].get("src"):
            continue
        if product.get("is_password_protected"):
            continue
        valid.append(product)

    if not valid:
        raise RuntimeError("No published, in-stock products with images were found")
    return valid


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "history": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "history": []}
    if not isinstance(data, dict) or not isinstance(data.get("history", []), list):
        return {"version": 1, "history": []}
    data.setdefault("version", 1)
    data.setdefault("history", [])
    return data


def choose_product(products: list[dict[str, Any]], state: dict[str, Any], day_key: str | None = None) -> dict[str, Any]:
    if not products:
        raise ValueError("products cannot be empty")
    day_key = day_key or datetime.now(timezone.utc).date().isoformat()
    history = state.get("history", [])
    last_seen: dict[int, str] = {}
    for item in history:
        try:
            last_seen[int(item["product_id"])] = str(item["published_at"])
        except (KeyError, TypeError, ValueError):
            continue

    never_used = [p for p in products if int(p.get("id", 0)) not in last_seen]
    pool = never_used if never_used else products

    def rank(product: dict[str, Any]) -> tuple[str, str]:
        pid = int(product.get("id", 0))
        seen = last_seen.get(pid, "")
        digest = hashlib.sha256(f"{day_key}:{pid}".encode("utf-8")).hexdigest()
        return (seen, digest)

    return min(pool, key=rank)


def product_url(product: dict[str, Any]) -> str:
    direct = str(product.get("permalink") or "").strip()
    if direct.startswith("http://") or direct.startswith("https://"):
        return direct
    slug = str(product.get("slug") or "").strip("/")
    return urljoin(SITE_BASE_URL + "/", f"product/{slug}/")


def category_name(product: dict[str, Any]) -> str:
    categories = product.get("categories") or []
    names = [clean_html(str(c.get("name", ""))) for c in categories if c.get("name")]
    return "، ".join(names[:2]) if names else "تجهیزات کشاورزی"


def make_caption(product: dict[str, Any]) -> str:
    name = clean_html(str(product.get("name") or "محصول کشاورزی"))
    summary = clean_html(product.get("summary") or product.get("short_description") or "")
    description = clean_html(product.get("description") or "")
    detail = normalize_sentence(summary or description, 430)
    category = category_name(product)
    url = product_url(product)

    lines = [f"🌱 {name}", ""]
    if detail:
        lines.extend([detail, ""])
    lines.extend([
        "✅ این محصول در حال حاضر در فروشگاه کشاورز بیست موجود است.",
        f"📌 دسته‌بندی: {category}",
        "🔎 برای مشخصات فنی، مدل‌ها و شرایط سفارش، صفحه محصول را ببینید:",
        url,
        "",
        "#کشاورز_بیست #کشاورزی #تجهیزات_کشاورزی",
    ])
    caption = "\n".join(lines).strip()
    if len(caption) > 980:
        room = max(120, 980 - (len(caption) - len(detail)))
        shorter = normalize_sentence(detail, room)
        caption = caption.replace(detail, shorter, 1)
    return caption[:1000]


def rtl(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def find_font(bold: bool = False) -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    raise RuntimeError("No suitable Unicode font found on runner")


def wrap_rtl(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int = 3) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), rtl(candidate), font=font)
        if bbox[2] - bbox[0] <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        consumed = sum(len(x.split()) for x in lines) + len(current.split())
        if consumed < len(words):
            current = current.rstrip("…") + "…"
        lines.append(current)
    return lines


def download_image(url: str, target: Path, session: requests.Session | None = None) -> None:
    session = session or requests.Session()
    with session.get(url, timeout=REQUEST_TIMEOUT, stream=True, headers={"User-Agent": USER_AGENT}) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise RuntimeError(f"Product media is not an image: {content_type}")
        length = int(response.headers.get("Content-Length") or 0)
        if length > MAX_IMAGE_BYTES:
            raise RuntimeError("Product image is larger than the safe download limit")
        total = 0
        with target.open("wb") as handle:
            for chunk in response.iter_content(64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise RuntimeError("Product image exceeded the safe download limit")
                handle.write(chunk)


def render_creative(product: dict[str, Any], source_image: Path, output: Path) -> None:
    canvas = Image.new("RGB", (1080, 1350), "#F4F1E8")
    draw = ImageDraw.Draw(canvas)
    dark = "#173B2A"
    accent = "#C9972D"
    white = "#FFFFFF"
    muted = "#4A5A50"

    draw.rounded_rectangle((54, 48, 1026, 166), radius=28, fill=dark)
    brand_font = ImageFont.truetype(find_font(True), 42)
    small_font = ImageFont.truetype(find_font(False), 28)
    draw.text((975, 78), rtl("کشاورز بیست"), font=brand_font, fill=white, anchor="ra")
    draw.text((105, 84), "keshavarz20.com", font=small_font, fill=white, anchor="la")

    card = (54, 200, 1026, 930)
    draw.rounded_rectangle(card, radius=38, fill=white)
    with Image.open(source_image) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        fitted = ImageOps.contain(img, (860, 640), method=Image.Resampling.LANCZOS)
        x = 540 - fitted.width // 2
        y = 555 - fitted.height // 2
        canvas.paste(fitted, (x, y))

    draw.rounded_rectangle((760, 226, 988, 284), radius=22, fill=dark)
    badge_font = ImageFont.truetype(find_font(True), 25)
    draw.text((970, 238), rtl("موجود در فروشگاه"), font=badge_font, fill=white, anchor="ra")

    title_font = ImageFont.truetype(find_font(True), 46)
    title = clean_html(str(product.get("name") or "محصول کشاورزی"))
    title_lines = wrap_rtl(draw, title, title_font, 940, max_lines=3)
    y = 972
    for line in title_lines:
        draw.text((1000, y), rtl(line), font=title_font, fill=dark, anchor="ra")
        y += 62

    cat_font = ImageFont.truetype(find_font(False), 28)
    category = category_name(product)
    draw.text((1000, min(y + 8, 1172)), rtl(category), font=cat_font, fill=muted, anchor="ra")

    draw.rounded_rectangle((54, 1230, 1026, 1304), radius=26, fill=accent)
    cta_font = ImageFont.truetype(find_font(True), 29)
    draw.text((540, 1267), rtl("مشخصات کامل و سفارش در سایت کشاورز بیست"), font=cta_font, fill=white, anchor="mm")

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def send_telegram(image_path: Path, caption: str) -> dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required for publishing")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with image_path.open("rb") as image_file:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": (image_path.name, image_file, "image/png")},
            timeout=REQUEST_TIMEOUT,
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram rejected the post: {payload.get('description', 'unknown error')}")
    return payload


def append_history(state: dict[str, Any], product: dict[str, Any], channel: str) -> dict[str, Any]:
    state = dict(state)
    history = list(state.get("history", []))
    history.append(
        {
            "product_id": int(product.get("id", 0)),
            "slug": str(product.get("slug") or ""),
            "name": clean_html(str(product.get("name") or "")),
            "published_at": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
        }
    )
    state["history"] = history[-1000:]
    state["version"] = 1
    return state


def write_run_summary(product: dict[str, Any], caption: str, image_path: Path, published: bool) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product_id": product.get("id"),
        "product_name": clean_html(str(product.get("name") or "")),
        "product_url": product_url(product),
        "image": str(image_path),
        "caption": caption,
        "telegram_published": published,
        "whatsapp_status": "asset_ready_manual_or_official_api_required",
    }
    path = OUT_DIR / "latest.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "caption.txt").write_text(caption + "\n", encoding="utf-8")
    return path


def run(dry_run: bool = False) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    products = fetch_products()
    product = choose_product(products, state)
    image_url = str((product.get("images") or [{}])[0].get("src") or "")
    source = OUT_DIR / "source-product-image"
    creative = OUT_DIR / "daily-product-ad.png"
    download_image(image_url, source)
    render_creative(product, source, creative)
    caption = make_caption(product)

    published = False
    if not dry_run:
        send_telegram(creative, caption)
        published = True
        state = append_history(state, product, "telegram")
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = write_run_summary(product, caption, creative, published)
    print(json.dumps({
        "ok": True,
        "dry_run": dry_run,
        "product_id": product.get("id"),
        "product_name": clean_html(str(product.get("name") or "")),
        "creative": str(creative),
        "summary": str(summary),
        "telegram_published": published,
        "whatsapp_asset_ready": True,
    }, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Keshavarz20 product social engine")
    parser.add_argument("--dry-run", action="store_true", help="Generate assets without publishing or mutating state")
    args = parser.parse_args()
    try:
        return run(dry_run=args.dry_run)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
