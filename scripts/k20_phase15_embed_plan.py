#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from k20_sanitizer import sanitize_text
ASSETS=ROOT/"phase15-publication-results/public-assets.json"
OUT=ROOT/"phase15-publication-results/embed-plan.json"
MARKER="<!-- K20-GROWTHOS-PHASE10-MEASUREMENT-END -->"
START="<!-- K20-SEOGOD2-PHASE15-VIDEO-START -->"
END="<!-- K20-SEOGOD2-PHASE15-VIDEO-END -->"

def iso_duration(seconds) -> str:
    n=max(1,int(round(float(seconds))))
    m,s=divmod(n,60)
    h,m=divmod(m,60)
    if h:
        return f"PT{h}H{m}M{s}S"
    if m:
        return f"PT{m}M{s}S"
    return f"PT{s}S"

def esc(s) -> str:
    return html.escape(sanitize_text(str(s or "")), quote=True)

def video_card(ep: dict) -> str:
    title=sanitize_text(ep["title"])
    desc=sanitize_text(ep["description"])
    transcript=sanitize_text(ep["transcript"])
    upload=str(ep["publication_date"])+"T00:00:00+00:00"
    schema={
        "@context":"https://schema.org",
        "@type":"VideoObject",
        "name":title,
        "description":desc,
        "thumbnailUrl":[ep["thumbnail_url"]],
        "uploadDate":upload,
        "contentUrl":ep["video_url"],
        "duration":iso_duration(ep["duration_seconds"]),
        "creator":{
            "@type":"Organization",
            "name":"کشاورز بیست",
            "url":"https://keshavarz20.com/"
        }
    }
    schema_json=json.dumps(schema,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")
    return (
        '<article class="k20-phase15-video-card" data-k20-video-episode="'+str(ep["episode"])+'">'
        '<h3>'+esc(title)+'</h3>'
        '<video controls preload="none" playsinline poster="'+esc(ep["thumbnail_url"])+'" '
        'style="display:block;width:100%;max-width:720px;height:auto;margin:12px auto;border-radius:14px;background:#111">'
        '<source src="'+esc(ep["video_url"])+'" type="video/mp4">'
        'مرورگر شما پخش ویدئو را پشتیبانی نمی‌کند.'
        '</video>'
        '<p>'+esc(desc)+'</p>'
        '<details><summary>متن ویدئو</summary><p>'+esc(transcript)+'</p></details>'
        '<script type="application/ld+json">'+schema_json+'</script>'
        '</article>'
    )

def main()->int:
    data=json.loads(ASSETS.read_text(encoding="utf-8"))
    episodes={int(x["episode"]):x for x in data["episodes"]}
    groups=[]
    for g in data["landing_groups"]:
        eps=[episodes[int(n)] for n in g["episodes"]]
        block=(
            START+
            '<section class="k20-phase15-video-section" dir="rtl" aria-label="راهنماهای ویدئویی کشاورز بیست">'
            '<h2>راهنماهای ویدئویی مرتبط</h2>'
            '<p>این ویدئوها برای کمک به انتخاب و بررسی اولیه هستند. برای مشخصات فنی نهایی، اطلاعات همان محصول و شرایط واقعی پروژه را مبنا قرار دهید.</p>'
            +''.join(video_card(x) for x in eps)+
            '</section>'+END
        )
        groups.append({
            "object_id":g["object_id"],
            "object_type":g["object_type"],
            "url":g["url"],
            "episodes":g["episodes"],
            "search_marker":MARKER,
            "start_marker":START,
            "end_marker":END,
            "insert_after_marker_html":MARKER+"\n"+block,
            "video_urls":[x["video_url"] for x in eps],
            "thumbnail_urls":[x["thumbnail_url"] for x in eps],
            "schema_count":len(eps),
        })
    result={
        "ok":len(groups)>0 and sum(len(x["episodes"]) for x in groups)==20,
        "marker":MARKER,
        "landing_count":len(groups),
        "episode_count":sum(len(x["episodes"]) for x in groups),
        "groups":groups,
    }
    if not result["ok"]:
        raise RuntimeError("embed plan incomplete")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"landing_count":len(groups),"episode_count":20},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
