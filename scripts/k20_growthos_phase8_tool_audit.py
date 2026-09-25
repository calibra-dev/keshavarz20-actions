#!/usr/bin/env python3
import json, os, requests
from datetime import datetime, timezone
from urllib.parse import urljoin

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session()
S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase8-audit/1.0","Cache-Control":"no-cache"})

SLUGS=[
 "drip-tape-length-fittings-calculator",
 "layflat-length-fittings-calculator",
 "irrigation-filter-selector",
 "irrigation-fittings-compatibility-selector",
 "one-hectare-drip-irrigation-basket",
 "irrigation-product-comparator",
 "irrigation-smart-proforma",
 "irrigation-pipe-size-selector"
]

def api(path, params=None):
    r=S.get(urljoin(BASE+"/",path.lstrip("/")),params=params,timeout=120)
    r.raise_for_status()
    return r.json()

def public(url):
    try:
        r=requests.get(url,timeout=60,headers={"User-Agent":"k20-growthos-phase8-audit/1.0","Cache-Control":"no-cache"},allow_redirects=True)
        return {"http":r.status_code,"final_url":r.url,"bytes":len(r.content)}
    except Exception as e:
        return {"http":0,"error":type(e).__name__}

def discover(slug):
    for subtype in ("pages","posts"):
        try:
            rows=api(f"wp-json/wp/v2/{subtype}",{"slug":slug,"context":"edit","per_page":5})
        except Exception:
            rows=[]
        if rows:
            o=rows[0]
            raw=((o.get("content") or {}).get("raw") or "")
            return {
                "found":True,
                "type":subtype[:-1],
                "id":o.get("id"),
                "slug":o.get("slug"),
                "status":o.get("status"),
                "link":o.get("link"),
                "title":((o.get("title") or {}).get("raw") or (o.get("title") or {}).get("rendered")),
                "chars":len(raw),
                "has_script":"<script" in raw.lower(),
                "has_form":"<form" in raw.lower(),
                "has_phase8_marker":"K20-GROWTHOS-PHASE8" in raw,
                "has_phase9_marker":"K20-GROWTHOS-PHASE9" in raw,
                "signals":{
                    "basket":"one-hectare-drip-irrigation-basket" in raw,
                    "comparator":"irrigation-product-comparator" in raw,
                    "compatibility":"irrigation-fittings-compatibility-selector" in raw,
                    "filter_selector":"irrigation-filter-selector" in raw,
                    "layflat_calc":"layflat-length-fittings-calculator" in raw,
                    "proforma":"irrigation-smart-proforma" in raw,
                    "whatsapp":"wa.me/" in raw,
                    "data_layer":"dataLayer" in raw or "gtag(" in raw
                },
                "public":public(o.get("link") or f"{BASE}/{slug}/")
            }
    return {"found":False,"slug":slug,"public":public(f"{BASE}/{slug}/")}

tools={slug:discover(slug) for slug in SLUGS}
search_hits=[]
for subtype in ("pages","posts"):
    try:
        rows=api(f"wp-json/wp/v2/{subtype}",{"search":"پیش فاکتور","context":"edit","per_page":50})
    except Exception:
        rows=[]
    for o in rows:
        raw=((o.get("content") or {}).get("raw") or "")
        search_hits.append({
            "type":subtype[:-1],"id":o.get("id"),"slug":o.get("slug"),
            "status":o.get("status"),"link":o.get("link"),
            "title":((o.get("title") or {}).get("raw") or (o.get("title") or {}).get("rendered")),
            "chars":len(raw),
            "has_form":"<form" in raw.lower(),
            "has_script":"<script" in raw.lower(),
            "has_inputs":"<input" in raw.lower() or "<select" in raw.lower() or "<textarea" in raw.lower(),
            "has_whatsapp":"wa.me/" in raw,
            "has_data_layer":"dataLayer" in raw or "gtag(" in raw,
            "has_phase8_marker":"K20-GROWTHOS-PHASE8" in raw,
            "has_phase9_marker":"K20-GROWTHOS-PHASE9" in raw,
            "public":public(o.get("link"))
        })

try:
    sr=requests.get(BASE+"/wp-json/wc/store/v1/products",params={"per_page":2},timeout=60,headers={"User-Agent":"k20-growthos-phase8-audit/1.0"})
    body=sr.json() if sr.ok else None
    store={"ok":sr.ok and isinstance(body,list),"http":sr.status_code,"items":len(body) if isinstance(body,list) else 0}
except Exception as e:
    store={"ok":False,"error":type(e).__name__}

out={
 "phase":8,
 "version":"growthos-phase8-tool-audit-v1",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "tools":tools,
 "proforma_search_hits":search_hits,
 "store_api":store,
 "summary":{
   "expected_tools":len(SLUGS),
   "found":sum(1 for x in tools.values() if x.get("found")),
   "public_200":sum(1 for x in tools.values() if x.get("public",{}).get("http")==200),
   "missing":[k for k,v in tools.items() if not v.get("found")]
 }
}
os.makedirs("growthos-phase8-results",exist_ok=True)
with open("growthos-phase8-results/tool-audit.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print("GROWTHOS_PHASE8_TOOL_AUDIT",json.dumps(out["summary"],ensure_ascii=False))
