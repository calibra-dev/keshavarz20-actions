#!/usr/bin/env python3
import json, re, html, time
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests
from xml.etree import ElementTree as ET

REQ=Path("phase6-ops/20260918-indexability-closure-v1.json")
OUT=Path("phase6-results/indexability-closure.json")
cfg=json.load(open(REQ,encoding="utf-8"))
targets=cfg["targets"]
UA={"User-Agent":"k20-phase6-indexability/1.0","Cache-Control":"no-cache"}

def norm(u):
    p=urlparse(u or "")
    return (p.scheme.lower(),p.netloc.lower(),unquote(p.path).rstrip("/").lower()+"/")

def get(url,tries=4):
    last=None
    for i in range(tries):
        try:
            return requests.get(url,timeout=120,allow_redirects=True,headers=UA)
        except Exception as e:
            last=e; time.sleep(1.5*(i+1))
    raise last

idx=get("https://keshavarz20.com/sitemap_index.xml"); idx.raise_for_status()
root=ET.fromstring(idx.content)
maps=[(e.text or "").strip() for e in root.iter() if e.tag.endswith("loc") and (e.text or "").strip()]
sitemap_urls=set(); sm_errors=[]
for sm in maps:
    try:
        r=get(sm); r.raise_for_status()
        rr=ET.fromstring(r.content)
        for e in rr.iter():
            if e.tag.endswith("loc") and e.text:
                sitemap_urls.add(norm(e.text.strip()))
    except Exception as e:
        sm_errors.append({"sitemap":sm,"error":type(e).__name__})

robots=get("https://keshavarz20.com/robots.txt")
robots_text=robots.text if robots.ok else ""
rows=[]
for u in targets:
    r=get(u); body=r.text[:1800000] if r.ok else ""
    cm=re.search(r'<link[^>]+rel=["\'][^"\']*canonical[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',body,re.I)
    if not cm:
        cm=re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'][^"\']*canonical[^"\']*["\']',body,re.I)
    canonical=html.unescape(cm.group(1)).strip() if cm else None
    metas=[m.group(1).lower() for m in re.finditer(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)["\']',body,re.I)]
    noindex=any("noindex" in x for x in metas)
    selfcanon=bool(canonical) and norm(canonical)==norm(u)
    in_sm=norm(u) in sitemap_urls
    rows.append({
      "url":u,"http_status":r.status_code,"final_url":r.url,
      "canonical":canonical,"self_canonical":selfcanon,
      "robots_meta":metas,"noindex":noindex,
      "in_sitemap":in_sm,
      "technical_indexable":r.status_code==200 and selfcanon and not noindex
    })
summary={
  "targets":len(rows),
  "http_200":sum(x["http_status"]==200 for x in rows),
  "self_canonical":sum(x["self_canonical"] for x in rows),
  "noindex":sum(x["noindex"] for x in rows),
  "in_sitemap":sum(x["in_sitemap"] for x in rows),
  "robots_txt_http":robots.status_code,
  "sitemaps_found":len(maps),
  "sitemap_parse_errors":len(sm_errors)
}
ok=summary["http_200"]==len(rows) and summary["self_canonical"]==len(rows) and summary["noindex"]==0 and summary["in_sitemap"]==len(rows) and robots.status_code==200
OUT.parent.mkdir(exist_ok=True)
json.dump({"ok":ok,"version":"phase6-indexability-closure-v1","summary":summary,"sitemap_errors":sm_errors,"targets":rows},open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE6_INDEXABILITY_CLOSURE",summary,"ok=",ok)
