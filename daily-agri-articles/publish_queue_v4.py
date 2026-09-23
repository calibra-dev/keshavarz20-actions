#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent

# Load v3 so SEO-God validation and REST transport remain authoritative.
spec = importlib.util.spec_from_file_location("article_v3", ROOT / "publish_queue_v3.py")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)
base = v3.base

RENDERER_VERSION = "k20-cover-v4-deterministic-persian"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf",
]


def _normalize_fa_text(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value or ""))
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _require_text_stack() -> None:
    if base.arabic_reshaper is None or base.get_display is None:
        raise base.QueuePublishError(
            "Persian cover renderer is unavailable: arabic-reshaper/python-bidi must be installed. "
            "Refusing to create a cover with broken Persian text."
        )


def _font(size: int) -> tuple[ImageFont.FreeTypeFont, str]:
    _require_text_stack()
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size), path
    raise base.QueuePublishError(
        "Persian cover renderer is unavailable: no approved Noto Arabic font was found. "
        "Refusing to fall back to a font that may corrupt Persian."
    )


def _rtl(value: str) -> str:
    _require_text_stack()
    value = _normalize_fa_text(value)
    return base.get_display(base.arabic_reshaper.reshape(value))


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), _rtl(text), font=font)
    return max(0, box[2] - box[0])


def _wrap_rtl(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    words = _normalize_fa_text(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if not current or _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        raise base.QueuePublishError("Cover title/subtitle produced no renderable text")
    return lines


def _cover_copy(p: dict[str, Any]) -> tuple[str, str]:
    title = _normalize_fa_text(str(p.get("cover_title") or p.get("image_title") or p.get("title") or ""))
    subtitle = _normalize_fa_text(str(p.get("cover_subtitle") or ""))

    # If the queue did not provide explicit cover copy, split a long article title
    # at the Persian semicolon so the visual never becomes an unreadable wall of text.
    if not subtitle:
        article_title = _normalize_fa_text(str(p.get("title") or ""))
        if "؛" in article_title:
            first, second = article_title.split("؛", 1)
            if not p.get("cover_title"):
                title = first.strip()
            subtitle = second.strip()

    if not title:
        raise base.QueuePublishError("cover_title/image_title/title cannot all be empty")
    return title, subtitle


def make_editorial_cover_v4(source: dict[str, Any], p: dict[str, Any]) -> Path:
    r = base.SESSION.get(source["url"], timeout=60)
    r.raise_for_status()
    raw = base.OUT / "article-image-source"
    raw.write_bytes(r.content)
    target = base.OUT / "featured-article.webp"

    title, subtitle = _cover_copy(p)
    brand_font, font_path = _font(27)
    title_font, _ = _font(52)
    subtitle_font, _ = _font(34)

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
        im = ImageEnhance.Contrast(im).enhance(1.06)
        im = ImageEnhance.Color(im).enhance(1.04)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))

        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Stable Keshavarz20 article-cover layout. No AI/model-generated text is ever used.
        draw.rounded_rectangle((42, 420, 1238, 682), radius=30, fill=(9, 24, 18, 205))
        draw.rounded_rectangle((62, 442, 278, 505), radius=23, fill=(246, 246, 236, 245))
        draw.text((170, 473), _rtl("کشاورز بیست"), font=brand_font, fill=(18, 61, 39, 255), anchor="mm")

        title_lines = _wrap_rtl(draw, title, title_font, 1080, 2)
        y = 535
        for line in title_lines:
            draw.text((1195, y), _rtl(line), font=title_font, fill=(255, 255, 255, 255), anchor="ra")
            y += 62

        if subtitle:
            subtitle_lines = _wrap_rtl(draw, subtitle, subtitle_font, 1080, 2)
            y = min(y + 4, 640)
            for line in subtitle_lines:
                draw.text((1195, y), _rtl(line), font=subtitle_font, fill=(238, 242, 239, 255), anchor="ra")
                y += 45

        im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
        im.save(target, "WEBP", quality=88, method=6)

    raw.unlink(missing_ok=True)
    manifest = {
        "renderer": RENDERER_VERSION,
        "font": font_path,
        "brand": "کشاورز بیست",
        "cover_title": title,
        "cover_subtitle": subtitle,
        "source_url": source.get("original_url") or source.get("url") or "",
        "text_rendering": "deterministic-pillow-arabic-reshaper-python-bidi",
        "ai_text_rendering": False,
        "fail_closed_on_missing_persian_stack": True,
    }
    (base.OUT / "cover-render-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


# Override only the visual renderer. Validation, research gates, WordPress REST writes,
# duplicate protection and verification all remain inherited from v3/v2.
base.make_editorial_cover = make_editorial_cover_v4

if __name__ == "__main__":
    base.main()
