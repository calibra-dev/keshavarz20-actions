#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import mimetypes
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "phase15-video-engine"
OUT = ENGINE / "out"
RESULTS = ROOT / "phase15-video-results"

_spec = importlib.util.spec_from_file_location("k20_video_engine", ENGINE / "k20_video_engine.py")
engine = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = engine
_spec.loader.exec_module(engine)


def _norm(text: str) -> str:
    text = (text or "").lower().replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"[^0-9a-z\u0600-\u06ff]+", " ", text)
    return " ".join(text.split())


def resolve_product_id(search: str) -> int:
    products = engine.store_products(search)
    if not products:
        raise RuntimeError(f"No product found for search={search!r}")
    wanted = [t for t in _norm(search).split() if len(t) > 1]
    ranked = []
    for p in products:
        name = _norm(str(p.get("name") or ""))
        score = sum(1 for t in wanted if t in name)
        ranked.append((score, int(p["id"]), str(p.get("name") or "")))
    ranked.sort(reverse=True)
    if not ranked or ranked[0][0] == 0:
        raise RuntimeError(f"No sufficiently matching product found for search={search!r}")
    return ranked[0][1]


def upload_media(path: Path, title: str) -> dict:
    base = os.environ["WP_BASE_URL"].rstrip("/")
    username = os.environ["WP_USERNAME"]
    password = os.environ["WP_APP_PASSWORD"]
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Disposition": f'attachment; filename="{path.name}"',
        "Content-Type": mime,
        "Accept": "application/json",
    }
    response = requests.post(
        f"{base}/wp-json/wp/v2/media",
        headers=headers,
        data=path.read_bytes(),
        timeout=240,
    )
    response.raise_for_status()
    item = response.json()
    media_id = int(item["id"])
    patch = requests.post(
        f"{base}/wp-json/wp/v2/media/{media_id}",
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
        json={"title": title},
        timeout=120,
    )
    patch.raise_for_status()
    item = patch.json()
    return {
        "id": media_id,
        "source_url": item.get("source_url"),
        "mime_type": item.get("mime_type"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    args = parser.parse_args()

    request_path = ROOT / args.request
    req = json.loads(request_path.read_text(encoding="utf-8"))
    product_id = int(req["product_id"]) if req.get("product_id") else resolve_product_id(str(req["product_search"]))
    if product_id < 1:
        raise SystemExit("Invalid product_id")

    custom = req.get("custom_video")
    if custom:
        metadata = engine.render_custom_product_video(
            product_id=product_id,
            title=str(custom["title"]),
            hook=str(custom["hook"]),
            body=str(custom["body"]),
            cta=str(custom["cta"]),
            target_seconds=float(custom.get("duration_seconds", 15)),
            voice=str(custom.get("voice", "fa-IR-FaridNeural")),
        )
        episode = None
        episode_dir = OUT / f"product-{product_id}-{int(round(float(custom.get('duration_seconds', 15))))}s"
    else:
        episode = int(req.get("episode", 7))
        if not 1 <= episode <= 20:
            raise SystemExit("Invalid episode")
        subprocess.run(
            [
                sys.executable,
                str(ENGINE / "k20_video_engine.py"),
                "render",
                "--episode",
                str(episode),
                "--product-id",
                str(product_id),
            ],
            check=True,
        )
        episode_dir = OUT / f"episode-{episode:02d}"
        metadata = json.loads((episode_dir / "metadata.json").read_text(encoding="utf-8"))
    if int(metadata.get("source_product_id") or 0) != product_id:
        raise RuntimeError("Rendered source product does not match request")

    video = upload_media(
        episode_dir / "video.mp4",
        f"راهنمای ویدئویی محصول {product_id} - کشاورز بیست",
    )
    thumbnail = upload_media(
        episode_dir / "thumbnail.jpg",
        f"تصویر ویدئوی محصول {product_id} - کشاورز بیست",
    )

    result = {
        "ok": True,
        "mode": "render-and-upload-media-only",
        "product_id": product_id,
        "episode": episode,
        "custom_video": bool(custom),
        "source_product_id": metadata.get("source_product_id"),
        "source_product_url": metadata.get("source_product_url"),
        "source_image_url": metadata.get("source_image_url"),
        "video_sha256": metadata.get("video_sha256"),
        "duration_seconds": metadata.get("duration_seconds"),
        "video": video,
        "thumbnail": thumbnail,
        "embed_applied": False,
        "policy": "Real Keshavarz20 product image only; no fabricated product result or review.",
    }
    RESULTS.mkdir(exist_ok=True)
    out_path = RESULTS / f"{request_path.stem}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
