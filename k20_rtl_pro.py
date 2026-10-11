"""Deterministic Persian RTL text checks and libraqm image lettering for K20."""
from __future__ import annotations
import unicodedata
from pathlib import Path
from typing import Any, Iterable

VERSION = "1.0.0"
_BAD = frozenset({0x200B, 0x200D, 0x200E, 0x200F, 0x061C, 0x2060, 0xFEFF, 0xFFFD})
_FA_CHARS = frozenset("آأإءابتثجچحخدذرزژسشصضطظعغفقکگلمنوهیپ")

class RTLQualityError(ValueError):
    """Refuse invalid copy or unshaped Persian rather than publishing it."""


def normalize_visible(value: str) -> str:
    """Opt-in normalization for visible prose, never identifiers or URLs."""
    return unicodedata.normalize("NFC", str(value)).replace("ي", "ی").replace("ك", "ک")


def assert_public_text(value: str, *, field: str, require_persian: bool = False) -> None:
    text = str(value or "")
    if not text.strip():
        raise RTLQualityError(f"{field}: empty public text")
    for character in text:
        cp = ord(character)
        if (cp in _BAD or 0x202A <= cp <= 0x202E or 0x2066 <= cp <= 0x2069
                or 0xE0000 <= cp <= 0xE007F):
            raise RTLQualityError(f"{field}: unsafe invisible/replacement U+{cp:04X}")
    if require_persian and not any(c in _FA_CHARS for c in normalize_visible(text)):
        raise RTLQualityError(f"{field}: expected Persian letters")
    # Real Persian ZWNJ U+200C is explicitly preserved.


_PUBLIC_FIELDS = (
    "title", "excerpt", "content_html", "seo_title", "meta_description",
    "cover_title", "cover_subtitle", "image_title", "alt_text",
    "focus_keyphrase", "editorial_disclosure",
)


def audit_payload_text(payload: dict[str, Any], *, fields: Iterable[str] = _PUBLIC_FIELDS) -> dict[str, Any]:
    checked = []
    for field in fields:
        value = payload.get(field)
        if value is None or value == "":
            continue
        assert_public_text(str(value), field=field)
        checked.append(field)
    for key in ("faq_items", "tags", "related_keyphrases"):
        def walk(node: Any) -> None:
            if isinstance(node, str):
                assert_public_text(node, field=key)
            elif isinstance(node, list):
                for x in node:
                    walk(x)
            elif isinstance(node, dict):
                for x in node.values():
                    walk(x)
        if payload.get(key):
            walk(payload[key])
            checked.append(key)
    return {"version": VERSION, "verified_fields": checked, "content_clean": True}


def _require_raqm() -> None:
    from PIL import features
    if not features.check_feature("raqm"):
        raise RTLQualityError("Pillow lacks libraqm: no Persian image text output")


def load_font(size: int, candidates: Iterable[str]):
    from PIL import ImageFont
    _require_raqm()
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size, layout_engine=ImageFont.Layout.RAQM), path
            except (OSError, ValueError):
                continue
    raise RTLQualityError("No approved Persian font could be loaded")


def text_width(draw, value: str, font) -> int:
    assert_public_text(value, field="cover_line")
    _require_raqm()
    box = draw.textbbox((0, 0), value, font=font, direction="rtl", language="fa")
    return max(0, box[2] - box[0])


def draw_text(draw, position, value: str, font, **kwargs) -> None:
    assert_public_text(value, field="cover_line")
    _require_raqm()
    draw.text(position, value, font=font, direction="rtl", language="fa", **kwargs)
