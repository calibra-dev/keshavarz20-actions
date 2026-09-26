#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
reg=json.loads(Path("growthos-phase15-results/brand-entity-registry.json").read_text(encoding="utf-8"))
targets={int(x["product_id"]) for x in reg.get("unbranded_products",[])}
rows=[]
for page in range(1,40):
 r=requests.get(BASE+"/wp-json/wc/v3/products",params={"status":"publish","per_page":100,"page":page,"orderby":"id","order":"asc"},auth=AUTH,timeout=60)
 r.raise_for_status(); got=r.json()
 if not got: break
 rows.extend(got)
 if len(got)<100: break
subset=[p for p in rows if int(p["id"]) in targets]
branded=[p for p in subset if p.get("brands")]
out={"target_count":len(targets),"found_count":len(subset),"branded_count":len(branded),"unbranded_count":len(subset)-len(branded),"sample_branded":[{"id":p["id"],"brands":p.get("brands")} for p in branded[:10]]}
print(json.dumps(out,ensure_ascii=False))
