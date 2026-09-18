#!/usr/bin/env python3
import json, os
from datetime import datetime, timezone
import requests

base=os.environ["WP_BASE_URL"].rstrip("/")
auth=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
ids=[135349,140407,135339]
records=[]
for pid in ids:
    r=requests.get(f"{base}/wp-json/wc/v3/products/{pid}",auth=auth,timeout=60)
    r.raise_for_status()
    p=r.json()
    records.append({
      "id":p.get("id"),"name":p.get("name"),"slug":p.get("slug"),"status":p.get("status"),
      "sku":p.get("sku"),"description":p.get("description") or "","short_description":p.get("short_description") or "",
      "attributes":p.get("attributes") or [],"categories":p.get("categories") or [],"tags":p.get("tags") or [],
      "permalink":p.get("permalink"),"modified_gmt":p.get("date_modified_gmt")
    })
out={"phase":11,"captured_at_utc":datetime.now(timezone.utc).isoformat(),"products":records}
os.makedirs("phase11-results",exist_ok=True)
with open("phase11-results/product-snapshot.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
print(json.dumps({"ok":True,"count":len(records)}))
