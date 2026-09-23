#!/usr/bin/env python3
from __future__ import annotations

import html
import io
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "text/html,image/avif,image/webp,image/apng,image/*,*/*;q=0.8"})

WP_BASE = os.environ.get("WP_BASE_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
ALLOWED = {"image/jpeg", "image/png", "image/webp"}

class ShareCoverError(RuntimeError):
    pass

def candidate_urls(text: str) -> list[str]:
    text = html.unescape(text)
    out: list[str] = []

    patterns = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]
    for pat in patterns:
        out.extend(re.findall(pat, text, flags=re.I))

    # Fallback for embedded JSON / asset URLs on shared media pages.
    for u in re.findall(r'https:\\/\\/[^"\s<>]+', text):
        out.append(u.replace("\\/", "/"))
    for u in re.findall(r'https://[^"\s<>]+', text):
        out.append(u)

    cleaned: list[str] = []
    seen = set()
    for u in out:
        u = u.replace("\u0026", "&").strip()
        if not u.startswith("https://"):
            continue
        if u in seen:
            continue
        seen.add(u)
        host = (urlparse(u).hostname or "").lower()
        if any(x in host for x in ("openai", "oaistatic", "oaiusercontent", "chatgpt")) or re.search(r'\.(?:png|jpe?g|webp)(?:\?|$)', u, flags=re.I):
            cleaned.append(u)
    return cleaned

def fetch_image_from_share(share_url: str) -> tuple[bytes, str, str]:
    r = SESSION.get(share_url, timeout=45, allow_redirects=True)
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype in ALLOWED:
        return r.content, ctype, r.url

    for url in candidate_urls(r.text):
        try:
            rr = SESSION.get(url, timeout=45, allow_redirects=True)
            if not rr.ok:
                continue
            ctype = (rr.headers.get("content-type") or "").split(";")[0].strip().lower()
            if ctype not in ALLOWED:
                continue
            if len(rr.content) < 10_000:
                continue
            return rr.content, ctype, rr.url
        except Exception:
            continue
    raise ShareCoverError("No downloadable JPEG/PNG/WebP asset found in the ChatGPT share page")

def prepare_webp(raw: bytes) -> bytes:
    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB")
        w, h = im.size
        target_ratio = 16 / 9
        ratio = w / max(h, 1)
        if abs(ratio - target_ratio) > 0.01:
            if ratio > target_ratio:
                nw = int(h * target_ratio)
                left = (w - nw) // 2
                im = im.crop((left, 0, left + nw, h))
            else:
                nh = int(w / target_ratio)
                top = (h - nh) // 2
                im = im.crop((0, top, w, top + nh))
        im = im.resize((1280, 720), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=88, method=6)
        return buf.getvalue()

def wp(method: str, route: str, **kwargs):
    r = SESSION.request(method, f"{WP_BASE}/wp-json{route}", auth=(WP_USER, WP_PASS), timeout=60, **kwargs)
    if not r.ok:
        detail = (r.text or "")[:500]
        raise ShareCoverError(f"WordPress {method} {route} failed: HTTP {r.status_code}: {detail}")
    return r

def main() -> None:
    if len(sys.argv) != 2:
        raise ShareCoverError("Usage: k20_import_chatgpt_share_cover.py <op.json>")
    if not WP_BASE or not WP_USER or not WP_PASS:
        raise ShareCoverError("WordPress credentials are missing")

    op_path = Path(sys.argv[1])
    op = json.loads(op_path.read_text(encoding="utf-8"))
    post_id = int(op["post_id"])
    share_url = str(op["share_url"])
    title = str(op.get("title") or f"Keshavarz20 article cover {post_id}")
    alt_text = str(op.get("alt_text") or title)

    # Verify target exists before any upload.
    target = wp("GET", f"/wp/v2/posts/{post_id}", params={"context": "edit"}).json()
    old_media = int(target.get("featured_media") or 0)

    raw, source_mime, resolved_url = fetch_image_from_share(share_url)
    webp = prepare_webp(raw)

    filename = f"keshavarz20-article-{post_id}-cover.webp"
    headers = {
        "Content-Type": "image/webp",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    media = wp("POST", "/wp/v2/media", data=webp, headers=headers).json()
    media_id = int(media["id"])

    wp("POST", f"/wp/v2/media/{media_id}", json={
        "title": title,
        "alt_text": alt_text,
        "caption": "",
        "description": "",
    })
    wp("POST", f"/wp/v2/posts/{post_id}", json={"featured_media": media_id})
    readback = wp("GET", f"/wp/v2/posts/{post_id}", params={"context": "edit"}).json()
    actual = int(readback.get("featured_media") or 0)
    if actual != media_id:
        raise ShareCoverError(f"Featured image readback mismatch: expected {media_id}, got {actual}")

    result = {
        "ok": True,
        "post_id": post_id,
        "old_featured_media": old_media,
        "new_featured_media": media_id,
        "source_share_url": share_url,
        "resolved_image_url": resolved_url,
        "source_mime": source_mime,
        "output_mime": "image/webp",
        "output_dimensions": [1280, 720],
        "post_status": readback.get("status"),
        "post_title": (readback.get("title") or {}).get("rendered", ""),
    }
    out_dir = Path("chatgpt-share-cover-results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / op_path.name
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        op_name = Path(sys.argv[1]).name if len(sys.argv) > 1 else "unknown.json"
        out_dir = Path("chatgpt-share-cover-results")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / op_name).write_text(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise
