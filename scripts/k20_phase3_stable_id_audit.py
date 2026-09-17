#!/usr/bin/env python3
import json, os
from collections import defaultdict
from urllib.parse import urljoin
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session();S.auth=AUTH;S.headers.update({"Accept":"application/json","User-Agent":"k20-phase3-id-audit/1.0","Cache-Control":"no-cache"})

def paged(path,params=None,cap=30):
    out=[];params=dict(params or {})
    for page in range(1,cap+1):
        p=dict(params);p.update({"per_page":100,"page":page})
        r=S.get(urljoin(BASE,path.lstrip("/")),params=p,timeout=120)
        if r.status_code==400 and page>1:break
        r.raise_for_status();rows=r.json()
        if not isinstance(rows,list) or not rows:break
        out.extend(rows)
        if len(rows)<100:break
    return out

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
top={int(x["product_id"]):x for x in pim.get("products",[])}
products=paged("wp-json/wc/v3/products",{"status":"any","_fields":"id,name,status,sku,global_unique_id"})
skus=defaultdict(list)
for p in products:
    s=(p.get("sku") or "").strip()
    if s: skus[s].append(int(p["id"]))
duplicates={s:ids for s,ids in skus.items() if len(ids)>1}
rows=[]
for pid,x in top.items():
    p=next((z for z in products if int(z["id"])==pid),None)
    if not p:
        rows.append({"product_id":pid,"status":"missing_from_catalog"});continue
    sku=(p.get("sku") or "").strip()
    gtin=(p.get("global_unique_id") or "").strip() if isinstance(p.get("global_unique_id"),str) else ""
    rows.append({
      "product_id":pid,"rank":x["rank"],"name":p.get("name"),
      "wp_id_stable":True,"sku":sku or None,"sku_present":bool(sku),
      "sku_unique_catalog_wide":bool(sku) and len(skus.get(sku,[]))==1,
      "sku_conflicts":skus.get(sku,[]) if sku else [],
      "gtin":gtin or None,
      "mpn":(((x.get("stable_identifiers") or {}).get("mpn") or {}).get("value") if isinstance((x.get("stable_identifiers") or {}).get("mpn"),dict) else None)
    })
summary={
 "catalog_products":len(products),"top30":len(rows),
 "top30_wp_id_present":sum(1 for x in rows if x.get("wp_id_stable")),
 "top30_sku_present":sum(1 for x in rows if x.get("sku_present")),
 "top30_sku_unique_catalog_wide":sum(1 for x in rows if x.get("sku_unique_catalog_wide")),
 "top30_gtin_present":sum(1 for x in rows if x.get("gtin")),
 "top30_mpn_present":sum(1 for x in rows if x.get("mpn")),
 "catalog_duplicate_sku_values":len(duplicates)
}
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":summary["top30_sku_present"]==30 and summary["top30_sku_unique_catalog_wide"]==30,
           "version":"phase3-stable-id-audit-v1","summary":summary,"catalog_duplicate_skus":duplicates,"top30":rows},
          open("phase3-results/stable-id-audit.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_STABLE_ID_AUDIT",summary)
