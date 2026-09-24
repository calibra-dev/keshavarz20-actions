#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("news_v2", ROOT / "publish_queue_v2.py")
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
base = v2.base

RENDERER_VERSION = "k20-news-cover-v3-cinematic-deterministic-persian"
TITLE_MAX_WORDS = 8
SUBTITLE_MAX_WORDS = 12
MAX_TEXT_WIDTH = 1080
_CURRENT_PAYLOAD: dict[str, Any] = {}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf",
]


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value or ""))
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _wc(value: str) -> int:
    return len([x for x in _normalize(value).split() if x])


def _font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size), path
    raise base.QueuePublishError("News Persian cover renderer unavailable: approved Noto Arabic font not found")


def _rtl(value: str) -> str:
    value = _normalize(value)
    if not value:
        return ""
    return get_display(arabic_reshaper.reshape(value))


def _width(draw, value: str, font) -> int:
    box = draw.textbbox((0, 0), _rtl(value), font=font)
    return max(0, box[2] - box[0])


def _wrap_all(draw, text: str, font, max_lines: int):
    words = _normalize(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if not current or _width(draw, candidate, font) <= MAX_TEXT_WIDTH:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    if not lines or len(lines) > max_lines:
        return None
    if any(_width(draw, line, font) > MAX_TEXT_WIDTH for line in lines):
        return None
    return lines


def _fit(draw, text: str, start: int, minimum: int, max_lines: int):
    for size in range(start, minimum - 1, -2):
        font, path = _font(size)
        lines = _wrap_all(draw, text, font, max_lines)
        if lines:
            return font, path, lines
    raise base.QueuePublishError("News Persian cover copy cannot fit safe margins without unreadable typography")


def _select_copy(p: dict[str, Any]) -> tuple[str, str, str]:
    explicit = _normalize(str(p.get("cover_title") or p.get("image_overlay_title") or ""))
    title = explicit or _normalize(str(p.get("image_title") or p.get("title") or ""))
    subtitle = _normalize(str(p.get("cover_subtitle") or ""))
    if not title:
        raise base.QueuePublishError("News cover title is empty")

    source = "explicit" if explicit else "fallback"
    if _wc(title) > TITLE_MAX_WORDS:
        if explicit:
            raise base.QueuePublishError(f"News cover_title is too dense: maximum {TITLE_MAX_WORDS} words")
        title = " ".join(title.split()[:TITLE_MAX_WORDS])
        source = "fallback-trimmed"

    if len(title) > 92:
        raise base.QueuePublishError("News cover_title is too long")
    if _wc(subtitle) > SUBTITLE_MAX_WORDS or len(subtitle) > 132:
        raise base.QueuePublishError(f"News cover_subtitle is too dense: maximum {SUBTITLE_MAX_WORDS} words")
    return title, subtitle, source


def validate_payload_v3(p):
    v2.validate_payload_v2(p)
    title, subtitle, _ = _select_copy(p)
    p["cover_title"] = title
    if subtitle:
        p["cover_subtitle"] = subtitle
    _CURRENT_PAYLOAD.clear()
    _CURRENT_PAYLOAD.update(p)


def make_editorial_image_v3(source: dict[str, Any]) -> Path:
    if not _CURRENT_PAYLOAD:
        raise base.QueuePublishError("News visual payload was not initialized")
    p = _CURRENT_PAYLOAD
    title, subtitle, copy_source = _select_copy(p)

    r = base.SESSION.get(source["url"], timeout=60)
    r.raise_for_status()
    raw = base.OUT / "queue-image-source"
    raw.write_bytes(r.content)
    target = base.OUT / "featured-news.webp"

    with Image.open(raw) as source_im:
        im = source_im.convert("RGB")
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
        im = ImageEnhance.Contrast(im).enhance(1.08)
        im = ImageEnhance.Color(im).enhance(1.045)
        im = ImageEnhance.Brightness(im).enhance(0.995)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=84, threshold=3))
        rgba = im.convert("RGBA")

        grade = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(grade)
        for y in range(280, 720):
            t = (y - 280) / 440
            alpha = int(80 * (t ** 1.6))
            gd.line((0, y, 1280, y), fill=(5, 22, 15, alpha))
        rgba = Image.alpha_composite(rgba, grade)

        overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rounded_rectangle((42, 414, 1238, 682), radius=30, fill=(8, 27, 19, 210))
        draw.rounded_rectangle((62, 436, 282, 500), radius=22, fill=(245, 248, 240, 246))
        brand_font, brand_font_path = _font(27)
        draw.text((172, 468), _rtl("کشاورز بیست"), font=brand_font, fill=(18, 69, 43, 255), anchor="mm")
        draw.rounded_rectangle((304, 449, 1195, 455), radius=3, fill=(104, 190, 132, 220))

        title_font, title_font_path, title_lines = _fit(draw, title, 52, 40, 2)
        y = 526
        for line in title_lines:
            draw.text((1195, y), _rtl(line), font=title_font, fill=(255, 255, 255, 255), anchor="ra")
            y += title_font.size + 10

        subtitle_lines: list[str] = []
        subtitle_font_path = ""
        if subtitle:
            subtitle_font, subtitle_font_path, subtitle_lines = _fit(draw, subtitle, 30, 25, 2)
            y = max(y + 2, 620)
            for line in subtitle_lines:
                if y > 661:
                    raise base.QueuePublishError("News cover_subtitle exceeds safe vertical space")
                draw.text((1195, y), _rtl(line), font=subtitle_font, fill=(226, 238, 230, 255), anchor="ra")
                y += subtitle_font.size + 7

        final = Image.alpha_composite(rgba, overlay).convert("RGB")
        final.save(target, "WEBP", quality=88, method=6)

    raw.unlink(missing_ok=True)
    manifest = {
        "renderer": RENDERER_VERSION,
        "background_profile": "factual-news-controlled-cinematic",
        "brand": "کشاورز بیست",
        "cover_title": title,
        "cover_subtitle": subtitle,
        "copy_source": copy_source,
        "title_words": _wc(title),
        "title_lines": len(title_lines),
        "subtitle_words": _wc(subtitle),
        "subtitle_lines": len(subtitle_lines),
        "safe_margin_px": 42,
        "output_size": "1280x720",
        "brand_font": brand_font_path,
        "title_font": title_font_path,
        "subtitle_font": subtitle_font_path,
        "source_url": source.get("original_url") or source.get("url") or "",
        "source_license": source.get("license") or "",
        "text_rendering": "deterministic-pillow-arabic-reshaper-python-bidi",
        "ai_text_rendering": False,
        "fake_documentary_generation": False,
        "fail_closed_on_missing_persian_stack": True,
        "fail_closed_on_copy_overflow": True,
        "qa_passed": True,
    }
    (base.OUT / "cover-render-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


base.validate_payload = validate_payload_v3
base.make_editorial_image = make_editorial_image_v3

if __name__ == "__main__":
    base.main()
