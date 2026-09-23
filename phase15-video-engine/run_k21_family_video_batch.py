#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/"phase15-video-engine"
OUT=ENGINE/"out"
RESULTS=ROOT/"phase15-video-results"

sys.path.insert(0,str(ENGINE))
from run_product_video_request import upload_media

FAMILIES={
    "valve":17,
    "fitting":12,
    "fertigation":20,
    "layflat_rain":7,
    "drip_tape":1,
}

def main()->int:
    result={"ok":True,"generated_at_utc":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"families":{}}
    for family,episode in FAMILIES.items():
        subprocess.run([sys.executable,str(ENGINE/"k20_video_engine.py"),"render","--episode",str(episode)],check=True)
        d=OUT/f"episode-{episode:02d}"
        meta=json.loads((d/"metadata.json").read_text(encoding="utf-8"))
        video=upload_media(d/"video.mp4",f"K21 {family} guide - Keshavarz20")
        thumb=upload_media(d/"thumbnail.jpg",f"K21 {family} video cover - Keshavarz20")
        result["families"][family]={
            "episode":episode,
            "video":video,
            "thumbnail":thumb,
            "duration_seconds":meta.get("duration_seconds"),
            "video_sha256":meta.get("video_sha256"),
            "source_product_id":meta.get("source_product_id"),
            "source_product_url":meta.get("source_product_url"),
            "scope":"family decision-support guide",
        }
    RESULTS.mkdir(exist_ok=True)
    p=RESULTS/"k21-top30-family-videos.json"
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
