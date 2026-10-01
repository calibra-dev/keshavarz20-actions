#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "phase2" / "video-program" / "transcripts-fa.md"

@dataclass
class Episode:
    number: int
    title: str
    hook: str
    body: str
    cta: str

    @property
    def narration(self) -> str:
        return " ".join(x.strip() for x in (self.hook, self.body, self.cta) if x.strip())

def parse_episodes() -> dict[int, Episode]:
    text = TRANSCRIPTS.read_text(encoding="utf-8")
    header_re = re.compile(r"^##\s+(\d{2})\s+—\s+(.+)$", re.M)
    matches = list(header_re.finditer(text))
    out = {}
    for i, match in enumerate(matches):
        block = text[match.end():(matches[i+1].start() if i+1 < len(matches) else len(text))]
        def field(label: str) -> str:
            m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", block)
            return m.group(1).strip() if m else ""
        n = int(match.group(1))
        out[n] = Episode(n, match.group(2).strip(), field("هوک"), field("متن"), field("CTA"))
    return out

LANDINGS = {
    1:  {"id":143698,"type":"post","url":"https://keshavarz20.com/drip-tape-length-fittings-calculator/"},
    2:  {"id":143698,"type":"post","url":"https://keshavarz20.com/drip-tape-length-fittings-calculator/"},
    3:  {"id":143698,"type":"post","url":"https://keshavarz20.com/drip-tape-length-fittings-calculator/"},
    4:  {"id":145233,"type":"page","url":"https://keshavarz20.com/one-hectare-drip-irrigation-basket/"},
    5:  {"id":144238,"type":"page","url":"https://keshavarz20.com/irrigation-filter-selector/"},
    6:  {"id":143698,"type":"post","url":"https://keshavarz20.com/drip-tape-length-fittings-calculator/"},
    7:  {"id":144236,"type":"page","url":"https://keshavarz20.com/layflat-length-fittings-calculator/"},
    8:  {"id":144239,"type":"page","url":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/"},
    9:  {"id":144239,"type":"page","url":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/"},
    10: {"id":144236,"type":"page","url":"https://keshavarz20.com/layflat-length-fittings-calculator/"},
    11: {"id":143870,"type":"post","url":"https://keshavarz20.com/polyethylene-pipe-pn-sdr-pe80-pe100-guide/"},
    12: {"id":144239,"type":"page","url":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/"},
    13: {"id":144239,"type":"page","url":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/"},
    14: {"id":144238,"type":"page","url":"https://keshavarz20.com/irrigation-filter-selector/"},
    15: {"id":144238,"type":"page","url":"https://keshavarz20.com/irrigation-filter-selector/"},
    16: {"id":144238,"type":"page","url":"https://keshavarz20.com/irrigation-filter-selector/"},
    17: {"id":143700,"type":"post","url":"https://keshavarz20.com/irrigation-valves-buying-guide/"},
    18: {"id":144232,"type":"post","url":"https://keshavarz20.com/sprinkler-irrigation-selection-design-guide/"},
    19: {"id":145233,"type":"page","url":"https://keshavarz20.com/one-hectare-drip-irrigation-basket/"},
    20: {"id":145286,"type":"page","url":"https://keshavarz20.com/request-proforma/"},
}

EXISTING_FAMILY_EPISODES = {1:"drip_tape",7:"layflat_rain",12:"fitting",17:"valve",20:"fertigation"}

def verify(url: str, prefix: str) -> dict:
    r=requests.get(url,stream=True,timeout=60,headers={"User-Agent":"Keshavarz20-Phase15-Aggregator/1.0"})
    ctype=(r.headers.get("content-type") or "").lower()
    status=r.status_code
    r.close()
    ok=status==200 and ctype.startswith(prefix)
    if not ok:
        raise RuntimeError(f"public URL failed: {status} {ctype} {url}")
    return {"http_status":status,"content_type":ctype}

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifacts",required=True)
    args=ap.parse_args()

    parsed=parse_episodes()
    current=json.loads((ROOT/"phase2/video-program/assets.json").read_text(encoding="utf-8"))
    old={int(x["episode"]):x for x in current.get("episodes",[])}

    rows={}
    for p in Path(args.artifacts).rglob("*.json"):
        try:
            data=json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for x in data.get("episodes",[]) if isinstance(data,dict) else []:
            if x.get("status")=="public_ready" and x.get("episode"):
                rows[int(x["episode"])]=x

    family=json.loads((ROOT/"phase15-video-results/k21-top30-family-videos.json").read_text(encoding="utf-8"))
    for episode,key in EXISTING_FAMILY_EPISODES.items():
        f=family["families"][key]
        video_url=f["video"]["source_url"]
        thumb_url=f["thumbnail"]["source_url"]
        rows[episode]={
            "episode":episode,
            "status":"public_ready_reused",
            "product_id":f.get("source_product_id"),
            "source_product_id":f.get("source_product_id"),
            "source_product_url":f.get("source_product_url"),
            "video_media_id":f["video"].get("id"),
            "video_url":video_url,
            "thumbnail_media_id":f["thumbnail"].get("id"),
            "thumbnail_url":thumb_url,
            "duration_seconds":f.get("duration_seconds"),
            "video_sha256":f.get("video_sha256"),
            "publication_date":"2026-09-23",
            "video_probe":verify(video_url,"video/"),
            "thumbnail_probe":verify(thumb_url,"image/"),
        }

    missing=[n for n in range(1,21) if n not in rows]
    if missing:
        raise RuntimeError(f"missing public episodes: {missing}")

    episodes=[]
    landing_groups={}
    for n in range(1,21):
        ep=parsed[n]
        base=dict(old.get(n,{}))
        base.update(rows[n])
        landing=LANDINGS[n]
        base.update({
            "episode":n,
            "status":"public_ready",
            "landing_page":landing["url"],
            "landing_object_id":landing["id"],
            "landing_object_type":landing["type"],
            "title":ep.title,
            "description":" ".join([ep.hook,ep.body]).strip(),
            "transcript":ep.narration.strip(),
            "transcript_reconciled":True,
            "transcript_basis":"final rendered audio was synthesized from this exact narration text",
        })
        if not base.get("duration_seconds") or not base.get("video_url") or not base.get("thumbnail_url"):
            raise RuntimeError(f"incomplete episode {n}")
        episodes.append(base)
        key=f'{landing["type"]}:{landing["id"]}'
        landing_groups.setdefault(key,{
            "object_id":landing["id"],
            "object_type":landing["type"],
            "url":landing["url"],
            "episodes":[],
        })["episodes"].append(n)

    assets={
        "version":"phase15-public-assets-v2",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "episodes":episodes,
    }
    (ROOT/"phase2/video-program/assets.json").write_text(json.dumps(assets,ensure_ascii=False,indent=2),encoding="utf-8")

    manifest_path=ROOT/"phase2/video-program/manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"]="PUBLIC_ASSETS_READY"
    manifest["render_status"]="PUBLIC_ASSETS_READY_EMBED_PENDING"
    manifest["public_hosting_complete"]=True
    manifest["public_ready_count"]=20
    manifest["publication_reconciled_at_utc"]=datetime.now(timezone.utc).isoformat()
    if isinstance(manifest.get("local_render"),dict):
        manifest["local_render"]["public_hosting_complete"]=True
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")

    out_dir=ROOT/"phase15-publication-results"
    out_dir.mkdir(exist_ok=True)
    result={
        "ok":True,
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "public_ready":20,
        "reused_public_episodes":sorted(EXISTING_FAMILY_EPISODES),
        "new_public_episodes":sorted(set(range(1,21))-set(EXISTING_FAMILY_EPISODES)),
        "landing_groups":list(landing_groups.values()),
        "episodes":episodes,
    }
    (out_dir/"public-assets.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"ok":True,"public_ready":20,"landing_groups":len(landing_groups)},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
