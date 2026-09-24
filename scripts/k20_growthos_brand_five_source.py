#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone

IDS={135383,139231,139232,140406,140407}
BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
TRUTH=Path("growthos-phase2-results/product-truth-registry.json")
OUT=Path("growthos-phase3-results/remaining-brand-five-source.json")

truth=json.loads(TRUTH.read_text(encoding="utf-8"))
tmap={int(x["product_id"]):x for x in truth.get("records",[]) if int(x.get("product_id") or 0) in IDS}
s=requests.Session();s.auth=AUTH;s.headers.update({"Accept":"application/json","User-Agent":"k20-brand-five-source/1.0"})
rows=[]
for pid in sorted(IDS):
    r=s.get(urljoin(BASE,f"wp-json/wc/v3/products/{pid}"),timeout=120);r.raise_for_status();p=r.json()
    attrs=[]
    for a in p.get("attributes") or []:
        attrs.append({"id":a.get("id"),"name":a.get("name"),"options":a.get("options")})
    tf=((tmap.get(pid) or {}).get("fields") or {}).get("brand") or {}
    rows.append({
      "product_id":pid,"name":p.get("name"),"sku":p.get("sku"),
      "truth_brand":tf,
      "woocommerce_brands":p.get("brands") or [],
      "attributes":attrs
    })
out={"phase":3,"version":"growthos-brand-five-source-v1","generated_at_utc":datetime.now(timezone.utc).isoformat(),"rows":rows}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
