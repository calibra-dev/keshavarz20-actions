#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import textwrap
import time
from pathlib import Path

import arabic_reshaper
import requests
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine-gallery-product-creator"
RULES_PATH = ENGINE / "config" / "category-rules.json"
PREVIEWS = ENGINE / "previews"

SITE = os.environ.get("WP_BASE_URL", "https://keshavarz20.com").rstrip("/")
USER = os.environ.get("WP_USERNAME")
PASSWORD = os.environ.get("WP_APP_PASSWORD")

BG = (7, 27, 34)
TEAL = (9, 72, 70)
GREEN = (93, 214, 90)
LIME = (188, 242, 112)
GOLD = (245, 204, 83)
WHITE = (246, 250, 249)
MUTED = (185, 208, 207)


def rtl(value: str) -> str:
    return get_display(arabic_reshaper.reshape(value or ""))


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def req_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def wp_get(path: str):
    auth = (USER, PASSWORD) if USER and PASSWORD else None
    r = requests.get(SITE + "/wp-json" + path, auth=auth, timeout=90, headers={"User-Agent": "K20-gallery-creator/1.0"})
    r.raise_for_status()
    return r.json()


def download_image(url: str) -> Image.Image:
    r = requests.get(url, timeout=90, headers={"User-Agent": "K20-gallery-creator/1.0"})
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGBA")


def normalize_text(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "")).strip()


def extract_verified_specs(product: dict) -> list[tuple[str, str]]:
    out = []
    for a in product.get("attributes") or []:
        name = normalize_text(str(a.get("name") or ""))
        opts = [normalize_text(str(x)) for x in (a.get("options") or []) if normalize_text(str(x))]
        if name and opts:
            out.append((name, "، ".join(opts)))
    return out[:6]


def background(w: int, h: int) -> Image.Image:
    c = Image.new("RGBA", (w, h), BG + (255,))
    px = c.load()
    for y in range(h):
        t = y / max(1, h - 1)
        col = (
            int(BG[0] * (1 - t) + TEAL[0] * t),
            int(BG[1] * (1 - t) + TEAL[1] * t),
            int(BG[2] * (1 - t) + TEAL[2] * t),
            255,
        )
        for x in range(w):
            px[x, y] = col
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((130, 110, w - 130, h - 160), fill=(88, 210, 126, 36))
    gd.ellipse((-180, h // 2, 480, h + 250), fill=(20, 160, 170, 36))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    c.alpha_composite(glow)
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, w, 16), fill=GREEN)
    d.rectangle((0, h - 16, w, h), fill=GREEN)
    return c


def center_text(d, text: str, y: int, fnt, fill=WHITE, width_chars=27, gap=8):
    lines = textwrap.wrap(text, width=width_chars, break_long_words=False) or [text]
    for line in lines:
        shaped = rtl(line)
        box = d.textbbox((0, 0), shaped, font=fnt)
        d.text(((1000 - (box[2] - box[0])) / 2, y), shaped, font=fnt, fill=fill)
        y += (box[3] - box[1]) + gap
    return y


def fit_product(im: Image.Image, maxw=700, maxh=560) -> Image.Image:
    src = im.copy()
    src.thumbnail((maxw, maxh), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    x = (1000 - src.width) // 2
    y = 0
    sh = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.ellipse((x + 35, src.height - 28, x + src.width - 35, src.height + 42), fill=(0, 0, 0, 82))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    layer.alpha_composite(sh)
    layer.alpha_composite(src, (x, y))
    return layer


def card(c: Image.Image, box, title: str, body: str, accent=GREEN):
    x0, y0, x1, y1 = box
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle((x0 + 8, y0 + 12, x1 + 8, y1 + 12), radius=30, fill=(0, 0, 0, 60))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    c.alpha_composite(sh)
    d = ImageDraw.Draw(c)
    d.rounded_rectangle(box, radius=30, fill=(3, 52, 54, 235), outline=accent, width=3)
    tf = font(34, True)
    bf = font(24, False)
    t = rtl(title)
    bb = d.textbbox((0, 0), t, font=tf)
    d.text((x1 - 28 - (bb[2] - bb[0]), y0 + 24), t, font=tf, fill=GOLD)
    yy = y0 + 82
    for line in textwrap.wrap(body, width=29, break_long_words=False):
        s = rtl(line)
        b = d.textbbox((0, 0), s, font=bf)
        d.text((x1 - 28 - (b[2] - b[0]), yy), s, font=bf, fill=WHITE)
        yy += 38


def save_webp(im: Image.Image, path: Path, quality: int):
    im.convert("RGB").save(path, "WEBP", quality=quality, method=6)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_slides(product: dict, rules: dict, request: dict, product_im: Image.Image, ref_im: Image.Image | None):
    out_cfg = rules["output"]
    cat = rules["categories"].get(request.get("category_key"), rules["categories"]["default"])
    batch_id = request["batch_id"]
    outdir = PREVIEWS / batch_id
    outdir.mkdir(parents=True, exist_ok=True)

    name = normalize_text(product.get("name", ""))
    sku = normalize_text(product.get("sku", ""))
    specs = extract_verified_specs(product)
    safe_copy = list(cat.get("safe_copy") or [])

    # Slide 1: Hero
    c = background(1000, 1000); d = ImageDraw.Draw(c)
    center_text(d, "معرفی محصول", 52, font(32, True), MUTED)
    center_text(d, name, 112, font(48, True), WHITE, width_chars=24)
    hero = ref_im if ref_im is not None else product_im
    c.alpha_composite(fit_product(hero, 720, 520), (0, 315))
    d.rounded_rectangle((115, 820, 885, 925), radius=34, fill=(4, 67, 62, 240), outline=GREEN, width=3)
    center_text(d, f"SKU: {sku}" if sku else "محصول کشاورز بیست", 845, font(27, True), GOLD)
    p1 = outdir / "slide-01.webp"; save_webp(c, p1, out_cfg["quality"])

    # Slide 2: Verified specs
    c = background(1000, 1000); d = ImageDraw.Draw(c)
    center_text(d, "مشخصات تاییدشده", 55, font(48, True), WHITE)
    y = 180
    if specs:
        for i, (k, v) in enumerate(specs[:4]):
            card(c, (65, y, 935, y + 145), k, v, GREEN if i % 2 == 0 else GOLD)
            y += 170
    else:
        card(c, (65, 260, 935, 470), "داده محصول", "برای این محصول مشخصات ساختاریافته کافی ثبت نشده؛ موتور عدد فنی را حدس نمی‌زند.", GOLD)
    center_text(d, "فقط داده‌ای که روی محصول یا منبع معتبر ثبت شده نمایش داده می‌شود", 890, font(25, True), MUTED, width_chars=38)
    p2 = outdir / "slide-02.webp"; save_webp(c, p2, out_cfg["quality"])

    # Slide 3: Use/field concept
    c = background(1000, 1000); d = ImageDraw.Draw(c)
    center_text(d, "کاربرد و شرایط اجرا", 55, font(48, True), WHITE)
    c.alpha_composite(fit_product(product_im, 610, 440), (0, 175))
    body = safe_copy[0] if safe_copy else "کاربرد واقعی باید با شرایط پروژه، سایز، اتصال و محدودیت‌های فنی همان محصول تطبیق داده شود."
    card(c, (80, 650, 920, 875), "راهنمای کاربرد", body, GREEN)
    p3 = outdir / "slide-03.webp"; save_webp(c, p3, out_cfg["quality"])

    # Slide 4: checklist
    c = background(1000, 1000); d = ImageDraw.Draw(c)
    center_text(d, "قبل از خرید بررسی کنید", 55, font(48, True), LIME)
    checks = [
        ("۱", "سایز و نوع اتصال را با قطعه واقعی پروژه تطبیق دهید."),
        ("۲", "طول مسیر، شرایط نصب و محدودیت‌های اجرایی را مشخص کنید."),
        ("۳", "اگر فشار، دبی یا عملکرد برای تصمیم مهم است فقط مقدار تاییدشده همان مدل را ملاک قرار دهید."),
    ]
    y = 210
    for n, b in checks:
        card(c, (70, y, 930, y + 185), n, b, GOLD if n == "۲" else GREEN)
        y += 215
    p4 = outdir / "slide-04.webp"; save_webp(c, p4, out_cfg["quality"])

    # Slide 5: summary/CTA
    c = background(1000, 1000); d = ImageDraw.Draw(c)
    center_text(d, "جمع‌بندی انتخاب", 55, font(46, True), WHITE)
    c.alpha_composite(fit_product(product_im, 650, 480), (0, 185))
    summary = safe_copy[-1] if safe_copy else "برای انتخاب نهایی، مشخصات ثبت‌شده همین محصول را با نیاز پروژه مقایسه کنید."
    card(c, (85, 665, 915, 835), "تصمیم مطمئن‌تر", summary, GREEN)
    d.rounded_rectangle((170, 865, 830, 950), radius=35, fill=GOLD)
    center_text(d, "keshavarz20.com", 887, font(30, True), (10, 42, 48))
    p5 = outdir / "slide-05.webp"; save_webp(c, p5, out_cfg["quality"])

    files = [p1, p2, p3, p4, p5]
    return outdir, files, cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    args = ap.parse_args()

    request = req_json(args.request)
    if request.get("engine") != "engine-gallery-product-creator":
        raise SystemExit("wrong engine")
    if request.get("mode") != "preview":
        raise SystemExit("preview renderer accepts mode=preview only")
    if not re.fullmatch(r"[a-zA-Z0-9._-]{4,120}", request.get("batch_id", "")):
        raise SystemExit("invalid batch_id")

    rules = req_json(RULES_PATH)
    product_id = int(request["product_id"])
    product = wp_get(f"/wc/v3/products/{product_id}")
    if int(product.get("id")) != product_id:
        raise RuntimeError("product readback mismatch")
    images = product.get("images") or []
    if not images:
        raise RuntimeError("product has no source image")

    product_im = download_image(images[0]["src"])
    ref_im = download_image(request["reference_image_url"]) if request.get("reference_image_url") else None

    outdir, files, cat = build_slides(product, rules, request, product_im, ref_im)
    assets = []
    for p in files:
        with Image.open(p) as im:
            if im.size != (rules["output"]["width"], rules["output"]["height"]):
                raise RuntimeError(f"invalid dimensions for {p.name}: {im.size}")
            if im.format != "WEBP":
                raise RuntimeError(f"invalid format for {p.name}: {im.format}")
        assets.append({"file": p.name, "sha256": sha256(p), "bytes": p.stat().st_size})

    manifest = {
        "engine": "engine-gallery-product-creator",
        "version": "1.0.0",
        "batch_id": request["batch_id"],
        "product_id": product_id,
        "product_name": product.get("name"),
        "product_sku": product.get("sku"),
        "category_key": request.get("category_key", "default"),
        "category_label": cat.get("label_fa"),
        "reference_image_url": request.get("reference_image_url"),
        "preview_only": True,
        "approval_required": True,
        "publish_ready": False,
        "gallery_write_performed": False,
        "asset_count": len(assets),
        "assets": assets,
        "created_at_epoch": int(time.time()),
        "source_product_image": images[0]["src"],
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
