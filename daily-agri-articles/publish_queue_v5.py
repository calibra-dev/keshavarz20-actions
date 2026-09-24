#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("article_v4", ROOT / "publish_queue_v4.py")
v4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)
base = v4.base

RENDERER_VERSION = "k20-cover-v5-cinematic-deterministic-persian"
TITLE_MAX_WORDS = 8
SUBTITLE_MAX_WORDS = 12
TITLE_MAX_LINES = 2
SUBTITLE_MAX_LINES = 2
MAX_TEXT_WIDTH = 1080


def _word_count(value: str) -> int:
    return len([x for x in re.split(r"\s+", str(value or "").strip()) if x])


def _copy(p: dict[str, Any]) -> tuple[str, str, str]:
    explicit = str(p.get("cover_title") or p.get("image_overlay_title") or "").strip()
    title = v4._normalize_fa_text(explicit or p.get("image_title") or p.get("title") or "")
    subtitle = v4._normalize_fa_text(str(p.get("cover_subtitle") or ""))

    if not title:
        raise base.QueuePublishError("cover_title/image_title/title cannot all be empty")

    source = "explicit" if explicit else "fallback"
    if _word_count(title) > TITLE_MAX_WORDS:
        if explicit:
            raise base.QueuePublishError(f"cover_title is too dense: maximum {TITLE_MAX_WORDS} words")
        title = " ".join(title.split()[:TITLE_MAX_WORDS])
        source = "fallback-trimmed"

    if len(title) > 92:
        raise base.QueuePublishError("cover_title is too long for a safe editorial cover")
    if _word_count(subtitle) > SUBTITLE_MAX_WORDS or len(subtitle) > 132:
        raise base.QueuePublishError(f"cover_subtitle is too dense: maximum {SUBTITLE_MAX_WORDS} words")
    return title, subtitle, source


def _wrap_all(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int):
    words = v4._normalize_fa_text(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if not current or v4._text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    if not lines or len(lines) > max_lines:
        return None
    if any(v4._text_width(draw, line, font) > max_width for line in lines):
        return None
    return lines


def _fit(draw: ImageDraw.ImageDraw, text: str, start: int, minimum: int, max_lines: int):
    for size in range(start, minimum - 1, -2):
        font, path = v4._font(size)
        lines = _wrap_all(draw, text, font, MAX_TEXT_WIDTH, max_lines)
        if lines:
            return font, path, lines
    raise base.QueuePublishError("Persian cover copy cannot fit safe margins without becoming unreadable")


def _cinematic_base(im: Image.Image) -> Image.Image:
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
    im = ImageEnhance.Contrast(im).enhance(1.09)
    im = ImageEnhance.Color(im).enhance(1.06)
    im = ImageEnhance.Brightness(im).enhance(0.99)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.25, percent=88, threshold=3))

    rgba = im.convert("RGBA")
    grade = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grade)
    for y in range(250, 720):
        t = (y - 250) / 470
        alpha = int(92 * (t ** 1.65))
        gd.line((0, y, 1280, y), fill=(4, 24, 15, alpha))
    for inset, alpha in ((0, 14), (18, 11), (36, 8)):
        gd.rounded_rectangle((inset, inset, 1279 - inset, 719 - inset), radius=42, outline=(0, 0, 0, alpha), width=24)
    return Image.alpha_composite(rgba, grade)


def make_editorial_cover_v5(source: dict[str, Any], p: dict[str, Any]) -> Path:
    r = base.SESSION.get(source["url"], timeout=60)
    r.raise_for_status()
    raw = base.OUT / "article-image-source"
    raw.write_bytes(r.content)
    target = base.OUT / "featured-article.webp"

    title, subtitle, copy_source = _copy(p)

    with Image.open(raw) as source_im:
        im = _cinematic_base(source_im)
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        draw.rounded_rectangle((38, 402, 1242, 684), radius=32, fill=(7, 28, 19, 214))
        draw.rounded_rectangle((62, 426, 296, 492), radius=23, fill=(246, 248, 240, 246))
        brand_font, brand_font_path = v4._font(27)
        draw.text((179, 459), v4._rtl("کشاورز بیست"), font=brand_font, fill=(17, 71, 43, 255), anchor="mm")
        draw.rounded_rectangle((315, 439, 1197, 445), radius=3, fill=(114, 196, 139, 220))

        title_font, title_font_path, title_lines = _fit(draw, title, 54, 42, TITLE_MAX_LINES)
        y = 520
        for line in title_lines:
            draw.text((1195, y), v4._rtl(line), font=title_font, fill=(255, 255, 255, 255), anchor="ra")
            y += title_font.size + 10

        subtitle_lines: list[str] = []
        subtitle_font_path = ""
        if subtitle:
            subtitle_font, subtitle_font_path, subtitle_lines = _fit(draw, subtitle, 32, 26, SUBTITLE_MAX_LINES)
            y = max(y + 2, 618)
            for line in subtitle_lines:
                if y > 660:
                    raise base.QueuePublishError("cover_subtitle exceeds safe vertical space")
                draw.text((1195, y), v4._rtl(line), font=subtitle_font, fill=(226, 238, 230, 255), anchor="ra")
                y += subtitle_font.size + 7

        final = Image.alpha_composite(im, overlay).convert("RGB")
        final.save(target, "WEBP", quality=88, method=6)

    raw.unlink(missing_ok=True)
    manifest = {
        "renderer": RENDERER_VERSION,
        "background_profile": "factual-realistic-controlled-cinematic",
        "brand": "کشاورز بیست",
        "cover_title": title,
        "cover_subtitle": subtitle,
        "copy_source": copy_source,
        "title_words": _word_count(title),
        "title_lines": len(title_lines),
        "subtitle_words": _word_count(subtitle),
        "subtitle_lines": len(subtitle_lines),
        "safe_margin_px": 38,
        "output_size": "1280x720",
        "brand_font": brand_font_path,
        "title_font": title_font_path,
        "subtitle_font": subtitle_font_path,
        "source_url": source.get("original_url") or source.get("url") or "",
        "text_rendering": "deterministic-pillow-arabic-reshaper-python-bidi",
        "ai_text_rendering": False,
        "fail_closed_on_missing_persian_stack": True,
        "fail_closed_on_copy_overflow": True,
        "qa_passed": True,
    }
    (base.OUT / "cover-render-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


base.make_editorial_cover = make_editorial_cover_v5

if __name__ == "__main__":
    base.main()
