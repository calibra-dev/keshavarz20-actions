#!/usr/bin/env python3
import json, os, sys
from collections import defaultdict
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-verified-reviews-audit/1.0"})

def paged(path,params=None,cap=30):
    out=[]; params=dict(params or {})
    for page in range(1,cap+1):
        p=dict(params); p.update({"per_page":100,"page":page})
        r=S.get(urljoin(BASE,path.lstrip("/")),params=p,timeout=120,headers={"Cache-Control":"no-cache"})
        if r.status_code==400 and page>1: break
        r.raise_for_status(); rows=r.json()
        if not isinstance(rows,list) or not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

reviews=paged("wp-json/wc/v3/products/reviews",{"status":"approved","_fields":"id,product_id,rating,verified,date_created_gmt"})
by=defaultdict(lambda:{"approved":0,"verified":0,"unverified":0,"ratings":[]})
for x in reviews:
    b=by[str(x.get("product_id") or 0)]
    b["approved"]+=1
    if x.get("verified"): b["verified"]+=1
    else: b["unverified"]+=1
    if x.get("rating") is not None: b["ratings"].append(int(x.get("rating") or 0))
for b in by.values():
    vals=b.pop("ratings")
    b["average_rating"]=round(sum(vals)/len(vals),2) if vals else None

settings={}
try:
    r=S.get(urljoin(BASE,"wp-json/wc/v3/settings/products"),timeout=120,headers={"Cache-Control":"no-cache"})
    r.raise_for_status()
    for x in r.json():
        if x.get("id") in ("woocommerce_enable_reviews","woocommerce_review_rating_verification_label","woocommerce_review_rating_verification_required","woocommerce_enable_review_rating"):
            settings[x.get("id")]={"value":x.get("value"),"default":x.get("default"),"type":x.get("type")}
except Exception as e:
    settings={"error":type(e).__name__}

record={
 "ok":True,"mode":"read-only","policy":"Never create, relabel, or imply a verified review unless WooCommerce marks it verified.",
 "generated_at_utc":__import__("datetime").datetime.utcnow().isoformat()+"Z",
 "summary":{"approved":len(reviews),"verified":sum(1 for x in reviews if x.get("verified")),"unverified":sum(1 for x in reviews if not x.get("verified")),
            "products_with_verified_reviews":sum(1 for b in by.values() if b["verified"]>0)},
 "settings":settings,"by_product":dict(by)
}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
with open(sys.argv[1],"w",encoding="utf-8") as f:json.dump(record,f,ensure_ascii=False,indent=2)
print("VERIFIED_REVIEWS_AUDIT_OK",record["summary"])
