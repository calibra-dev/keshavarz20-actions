#!/usr/bin/env python3
import json, os, re, html, time
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests
from xml.etree import ElementTree as ET

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
UA={"User-Agent":"k20-phase3-indexability/1.0","Cache-Control":"no-cache"}

def norm(u):
    p=urlparse(u or "")
    return (p.scheme.lower(),p.netloc.lower(),unquote(p.path).rstrip("/").lower()+"/")

def get_retry(url,tries=4):
    last=None
    for i in range(tries):
        try:
            r=requests.get(url,timeout=120,allow_redirects=True,headers=UA)
            return r
        except Exception as e:
            last=e;time.sleep(1.5*(i+1))
    raise last

# Discover product sitemap URLs from sitemap index.
sitemap_index=get_retry("https://keshavarz20.com/sitemap_index.xml")
sitemap_index.raise_for_status()
root=ET.fromstring(sitemap_index.content)
locs=[(e.text or "").strip() for e in root.iter() if e.tag.endswith("loc")]
product_maps=[u for u in locs if "product" in u.lower() and "product_cat" not in u.lower() and "product-tag" not in u.lower()]
sitemap_urls=set()
sitemap_errors=[]
for sm in product_maps:
    try:
        r=get_retry(sm);r.raise_for_status()
        rr=ET.fromstring(r.content)
        for e in rr.iter():
            if e.tag.endswith("loc") and e.text: sitemap_urls.add(norm(e.text.strip()))
    except Exception as e:
        sitemap_errors.append({"sitemap":sm,"error":type(e).__name__})

rows=[]
for x in pim.get("products",[]):
    u=x["permalink"]; r=get_retry(u)
    body=r.text[:1800000] if r.ok else ""
    cm=re.search(r'<link[^>]+rel=["\'][^"\']*canonical[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',body,re.I)
    if not cm:
        cm=re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'][^"\']*canonical[^"\']*["\']',body,re.I)
    canonical=html.unescape(cm.group(1)).strip() if cm else None
    robots=[]
    for m in re.finditer(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)["\']',body,re.I):
        robots.append(m.group(1).lower())
    noindex=any("noindex" in z for z in robots)
    selfcanon=bool(canonical) and norm(canonical)==norm(u)
    in_sitemap=norm(u) in sitemap_urls
    rows.append({
      "rank":x["rank"],"product_id":x["product_id"],"url":u,
      "http_status":r.status_code,"final_url":r.url,
      "canonical":canonical,"self_canonical":selfcanon,
      "robots_meta":robots,"noindex":noindex,
      "in_product_sitemap":in_sitemap,
      "technical_indexable":r.status_code==200 and selfcanon and not noindex
    })

summary={
 "products":len(rows),
 "http_200":sum(1 for x in rows if x["http_status"]==200),
 "self_canonical":sum(1 for x in rows if x["self_canonical"]),
 "noindex":sum(1 for x in rows if x["noindex"]),
 "in_product_sitemap":sum(1 for x in rows if x["in_product_sitemap"]),
 "technical_indexable":sum(1 for x in rows if x["technical_indexable"]),
 "product_sitemaps_found":len(product_maps),
 "sitemap_parse_errors":len(sitemap_errors)
}
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":summary["technical_indexable"]==30,"version":"phase3-top30-indexability-v1",
           "summary":summary,"product_sitemaps":product_maps,"sitemap_errors":sitemap_errors,"products":rows},
          open("phase3-results/top30-indexability.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_INDEXABILITY_OK",summary)
