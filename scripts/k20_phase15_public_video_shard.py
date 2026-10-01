#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "phase15-video-engine"
sys.path.insert(0, str(ENGINE))

import k20_video_engine as engine
from run_product_video_request import upload_media

PRODUCT_IDS = {
    1: 135235, 2: 135235, 3: 135235, 4: 135235,
    5: 141504, 6: 135235,
    7: 135311, 8: 135311, 9: 135311, 10: 135311,
    11: 135221,
    12: 140610, 13: 140610,
    14: 141504, 15: 141504, 16: 141504,
    17: 135349,
    18: 141523,
    19: 135235,
    20: 140407,
}

def verify_public(url: str, expected_prefix: str) -> dict:
    r = requests.get(url, stream=True, timeout=60, headers={"User-Agent": "Keshavarz20-Phase15-Publication/1.0"})
    status = r.status_code
    ctype = (r.headers.get("content-type") or "").lower()
    ok = status == 200 and ctype.startswith(expected_prefix)
    r.close()
    if not ok:
        raise RuntimeError(f"public verification failed: {status} {ctype} {url}")
    return {"http_status": status, "content_type": ctype}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    numbers = [int(x) for x in args.episodes.split(",") if x.strip()]
    if not numbers:
        raise SystemExit("no episodes")
    parsed = engine.parse_episodes()
    rows = []

    for number in numbers:
        if number not in PRODUCT_IDS or number not in parsed:
            raise RuntimeError(f"unsupported episode {number}")
        product_id = PRODUCT_IDS[number]
        meta = engine.render_episode(number, product_id=product_id)
        out_dir = ENGINE / "out" / f"episode-{number:02d}"
        transcript = (out_dir / "transcript-fa.txt").read_text(encoding="utf-8").strip()
        expected_transcript = parsed[number].narration.strip()
        if transcript != expected_transcript:
            raise RuntimeError(f"transcript mismatch for episode {number}")

        title = f"{parsed[number].title} | کشاورز بیست"
        video = upload_media(out_dir / "video.mp4", title)
        thumb = upload_media(out_dir / "thumbnail.jpg", f"کاور ویدئو: {parsed[number].title}")

        video_probe = verify_public(str(video["source_url"]), "video/")
        thumb_probe = verify_public(str(thumb["source_url"]), "image/")

        rows.append({
            "episode": number,
            "status": "public_ready",
            "product_id": product_id,
            "source_product_id": meta.get("source_product_id"),
            "source_product_url": meta.get("source_product_url"),
            "source_image_url": meta.get("source_image_url"),
            "video_media_id": video.get("id"),
            "video_url": video.get("source_url"),
            "thumbnail_media_id": thumb.get("id"),
            "thumbnail_url": thumb.get("source_url"),
            "duration_seconds": meta.get("duration_seconds"),
            "video_sha256": meta.get("video_sha256"),
            "publication_date": datetime.now(timezone.utc).date().isoformat(),
            "title": parsed[number].title,
            "description": " ".join([parsed[number].hook, parsed[number].body]).strip(),
            "transcript": expected_transcript,
            "video_probe": video_probe,
            "thumbnail_probe": thumb_probe,
        })

    out = {
        "ok": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "episodes": rows,
    }
    p = ROOT / args.output
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "episodes": [x["episode"] for x in rows]}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
