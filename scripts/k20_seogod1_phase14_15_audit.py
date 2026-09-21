#!/usr/bin/env python3
import os, json, re, hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-seogod1-phase14-15-audit/1.0","Cache-Control":"no-cache"})

def get(path,params=None):
    r=S.get(urljoin(BASE+"/",path.lstrip("/")),params=params,timeout=120)
    try: data=r.json()
    except Exception: data=None
    return r,data

def paged(path, params=None, cap=50):
    out=[]
    params=dict(params or {})
    for page in range(1,cap+1):
        p=dict(params); p.update({"per_page":100,"page":page})
        r,d=get(path,p)
        if r.status_code==400 and page>1: break
        r.raise_for_status()
        if not isinstance(d,list) or not d: break
        out.extend(d)
        if len(d)<100: break
    return out

def host_public(path):
    try:
        r=requests.get(BASE.rstrip("/")+"/"+path.lstrip("/"),timeout=45,headers={"User-Agent":"k20-seogod1-phase14-15-audit/1.0","Cache-Control":"no-cache"})
        return {"http":r.status_code,"content_type":r.headers.get("content-type"),"bytes":len(r.content)}
    except Exception as e:
        return {"http":0,"error":type(e).__name__}

# Plugins: persist only integration-relevant slugs/names, not full admin inventory.
rp,plugins=get("wp-json/wp/v2/plugins",{"status":"active","per_page":100,"_fields":"plugin,name,status"})
plugin_rows=plugins if rp.ok and isinstance(plugins,list) else []
kw=re.compile(r"torob|emalls|feed|merchant|product.?feed|recommend|related|cross.?sell|up.?sell|discovery|personal",re.I)
relevant_plugins=[{"plugin":x.get("plugin"),"name":x.get("name"),"status":x.get("status")} for x in plugin_rows if kw.search(str(x.get("plugin",""))+" "+str(x.get("name","")))]

# REST routes relevant to phase 14/15.
ri,index=get("wp-json/")
routes=list((index or {}).get("routes",{}).keys()) if isinstance(index,dict) else []
route_hits=sorted([x for x in routes if kw.search(x)])[:300]

# Full published catalog.
products=paged("wp-json/wc/v3/products",{"status":"publish","orderby":"id","order":"asc"})
def brand_names(p):
    b=p.get("brands") or []
    vals=[]
    if isinstance(b,list):
        for x in b:
            if isinstance(x,dict) and x.get("name"): vals.append(str(x["name"]))
    return vals

rows=[]
for p in products:
    images=p.get("images") or []
    cats=p.get("categories") or []
    attrs=p.get("attributes") or []
    desc=re.sub(r"<[^>]+>"," ",str(p.get("description") or ""))
    desc=re.sub(r"\s+"," ",desc).strip()
    related=p.get("related_ids") or []
    upsell=p.get("upsell_ids") or []
    cross=p.get("cross_sell_ids") or []
    rows.append({
      "id":p.get("id"),
      "sku":bool(str(p.get("sku") or "").strip()),
      "title":bool(str(p.get("name") or "").strip()),
      "url":bool(str(p.get("permalink") or "").startswith("http")),
      "image":bool(images and str((images[0] or {}).get("src") or "").startswith("http")),
      "image_count":len(images),
      "price":bool(str(p.get("price") or "").strip()),
      "stock_status":str(p.get("stock_status") or ""),
      "in_stock":str(p.get("stock_status") or "")=="instock",
      "catalog_visible":str(p.get("catalog_visibility") or "")!="hidden",
      "category":bool(cats),
      "brand":bool(brand_names(p)),
      "description_chars":len(desc),
      "attributes_count":len(attrs),
      "related_count":len(related),
      "upsell_count":len(upsell),
      "cross_sell_count":len(cross),
      "reviews_allowed":bool(p.get("reviews_allowed")),
    })

n=len(rows)
def count(k,pred=lambda v:bool(v)): return sum(1 for x in rows if pred(x.get(k)))
def pct(v): return round((100*v/n),2) if n else 0

feed_ready_core=sum(1 for x in rows if x["sku"] and x["title"] and x["url"] and x["image"] and x["price"] and x["stock_status"] and x["category"] and x["catalog_visible"])
rec_any=sum(1 for x in rows if x["related_count"] or x["upsell_count"] or x["cross_sell_count"])
desc_rec_signal=0
for p in products:
    html=str(p.get("description") or "")
    if re.search(r"محصولات مرتبط|محصولات پیشنهادی|محصولات مکمل|برای تکمیل خرید|همراه این محصول|پیشنهاد خرید",html,re.I):
        desc_rec_signal+=1

# Common public Torob route guesses only; no auth/token interaction.
probes={}
for path in ["torob_api/v3/products","wp-json/torob/v1","wp-json/torob","torob/products"]:
    probes[path]=host_public(path)

# Existing phase-10 tools for contextual merchandising.
for path in ["drip-tape-length-fittings-calculator/","one-hectare-drip-irrigation-basket/","irrigation-product-comparator/","request-proforma/"]:
    probes[path]=host_public(path)

out={
 "program":"SEO God1","phases":[14,15],"generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "privacy":{"customer_pii_persisted":False,"orders_read":False},
 "phase14":{
   "title":"Torob / Emalls / Feeds / Distribution",
   "active_plugin_endpoint_http":rp.status_code,
   "relevant_active_plugins":relevant_plugins,
   "relevant_rest_routes":route_hits,
   "published_products":n,
   "core_feed_ready_products":feed_ready_core,
   "core_feed_ready_percent":pct(feed_ready_core),
   "field_coverage":{
      "sku":{"count":count("sku"),"percent":pct(count("sku"))},
      "absolute_url":{"count":count("url"),"percent":pct(count("url"))},
      "main_image":{"count":count("image"),"percent":pct(count("image"))},
      "price":{"count":count("price"),"percent":pct(count("price"))},
      "stock_status":{"count":count("stock_status"),"percent":pct(count("stock_status"))},
      "category":{"count":count("category"),"percent":pct(count("category"))},
      "brand":{"count":count("brand"),"percent":pct(count("brand"))},
      "description_ge_200_chars":{"count":count("description_chars",lambda v:(v or 0)>=200),"percent":pct(count("description_chars",lambda v:(v or 0)>=200))},
      "image_count_ge_1":{"count":count("image_count",lambda v:(v or 0)>=1),"percent":pct(count("image_count",lambda v:(v or 0)>=1))},
   },
   "public_probes":{k:v for k,v in probes.items() if "torob" in k},
 },
 "phase15":{
   "title":"Personalization / Recommendations / Intelligent Merchandising",
   "products_with_wc_related_or_up_cross_sell":rec_any,
   "products_with_wc_related_or_up_cross_sell_percent":pct(rec_any),
   "products_with_description_recommendation_signal":desc_rec_signal,
   "products_with_description_recommendation_signal_percent":pct(desc_rec_signal),
   "coverage":{
      "related_ids":{"count":count("related_count",lambda v:(v or 0)>0),"percent":pct(count("related_count",lambda v:(v or 0)>0))},
      "upsell_ids":{"count":count("upsell_count",lambda v:(v or 0)>0),"percent":pct(count("upsell_count",lambda v:(v or 0)>0))},
      "cross_sell_ids":{"count":count("cross_sell_count",lambda v:(v or 0)>0),"percent":pct(count("cross_sell_count",lambda v:(v or 0)>0))},
      "recommendation_block":{"count":desc_rec_signal,"percent":pct(desc_rec_signal)},
   },
   "decision_tools":{k:v for k,v in probes.items() if "torob" not in k},
 },
 "sample_safe_counts_only":{
   "products_with_brand_missing": n-count("brand"),
   "products_with_description_lt_200": n-count("description_chars",lambda v:(v or 0)>=200),
   "products_with_no_explicit_merch_signal": n-rec_any if n>=rec_any else 0
 }
}
os.makedirs("seo-god1-results",exist_ok=True)
with open("seo-god1-results/phase14-15-baseline.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
print("SEO_GOD1_PHASE14_15_BASELINE_OK",json.dumps({
 "published":n,"feed_ready":feed_ready_core,"plugins":relevant_plugins,
 "route_hits":route_hits[:20],"rec_any":rec_any,"desc_rec_signal":desc_rec_signal
},ensure_ascii=False))
