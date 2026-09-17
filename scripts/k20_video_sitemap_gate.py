#!/usr/bin/env python3
import json, os
from xml.sax.saxutils import escape

assets=json.load(open("phase2/video-program/assets.json",encoding="utf-8"))
rows=assets.get("episodes",[])
required=["landing_page","video_url","thumbnail_url","duration_seconds","publication_date","title","description"]
ready=[]; blocked=[]
for x in rows:
    missing=[k for k in required if not x.get(k)]
    if missing: blocked.append({"episode":x.get("episode"),"missing":missing})
    else: ready.append(x)

os.makedirs("phase2-results",exist_ok=True)
gate={"ok":True,"required":20,"registered":len(rows),"ready":len(ready),"blocked":len(blocked),
      "status":"PASS" if len(ready)>=20 else "BLOCKED_PUBLIC_VIDEO_ASSETS","blocked_items":blocked}
json.dump(gate,open("phase2-results/video-sitemap-gate.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)

if len(ready)>=20:
    lines=['<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">']
    for x in ready:
        lines+=['<url>',f'<loc>{escape(str(x["landing_page"]))}</loc>','<video:video>',
          f'<video:thumbnail_loc>{escape(str(x["thumbnail_url"]))}</video:thumbnail_loc>',
          f'<video:title>{escape(str(x["title"]))}</video:title>',
          f'<video:description>{escape(str(x["description"]))}</video:description>',
          f'<video:content_loc>{escape(str(x["video_url"]))}</video:content_loc>',
          f'<video:duration>{int(x["duration_seconds"])}</video:duration>',
          f'<video:publication_date>{escape(str(x["publication_date"]))}</video:publication_date>',
          '</video:video>','</url>']
    lines.append('</urlset>')
    open("phase2-results/video-sitemap.xml","w",encoding="utf-8").write("\n".join(lines))
print("VIDEO_SITEMAP_GATE",gate["status"],gate["ready"],"/",gate["required"])
