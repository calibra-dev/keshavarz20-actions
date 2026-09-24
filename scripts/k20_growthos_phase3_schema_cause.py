#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
FULL=Path("growthos-phase3-results/html-schema-feed-parity.json")
OUT=Path("growthos-phase3-results/schema-missing-cause.json")
j=json.loads(FULL.read_text(encoding="utf-8"))
missing={int(x["product_id"]) for x in (j.get("products") or []) if (x.get("checks") or {}).get("product_schema_present") is False}

s=requests.Session(); s.auth=AUTH; s.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-schema-cause/1.0"})
products={}
for page in range(1,30):
    r=s.get(urljoin(BASE,"wp-json/wc/v3/products"),params={"status":"publish","per_page":100,"page":page},timeout=120)
    if r.status_code==400 and page>1: break
    r.raise_for_status()
    rows=r.json()
    if not rows: break
    for p in rows: products[int(p["id"])]=p
    if len(rows)<100: break

rows=[]
for pid in sorted(missing):
    p=products.get(pid) or {}
    def nonempty(k):
        v=p.get(k)
        return v is not None and str(v).strip()!=""
    rows.append({
      "product_id":pid,
      "name":p.get("name"),
      "type":p.get("type"),
      "status":p.get("status"),
      "catalog_visibility":p.get("catalog_visibility"),
      "has_price_value":nonempty("price"),
      "has_regular_price_value":nonempty("regular_price"),
      "has_sale_price_value":nonempty("sale_price"),
      "purchasable":bool(p.get("purchasable")),
      "stock_status":p.get("stock_status"),
    })

summary={
 "schema_missing_products":len(missing),
 "api_products_found":sum(1 for r in rows if r.get("name")),
 "has_price_value":sum(1 for r in rows if r["has_price_value"]),
 "missing_price_value":sum(1 for r in rows if not r["has_price_value"]),
 "has_regular_price_value":sum(1 for r in rows if r["has_regular_price_value"]),
 "purchasable_true":sum(1 for r in rows if r["purchasable"]),
 "published":sum(1 for r in rows if r["status"]=="publish"),
 "visible_catalog":sum(1 for r in rows if r["catalog_visibility"] in ("visible","catalog","search")),
}
classification={
 "all_schema_missing_are_price_empty": bool(rows) and all(not r["has_price_value"] for r in rows),
 "all_schema_missing_are_non_purchasable": bool(rows) and all(not r["purchasable"] for r in rows),
 "safe_conclusion": "No price values are emitted. If all missing-schema products are price-empty/non-purchasable, Offer markup must not be fabricated under the Product Truth policy."
}
out={
 "phase":3,"version":"growthos-schema-missing-cause-v1",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "read_only":True,
 "summary":summary,"classification":classification,
 "sample":rows[:30]
}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print("GROWTHOS_SCHEMA_CAUSE",json.dumps({"summary":summary,"classification":classification},ensure_ascii=False))
