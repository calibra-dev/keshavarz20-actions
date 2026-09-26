#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
paths=[
  "/wp-json/wp/v2/product_brand",
  "/wp-json/wp/v2/product-brands",
  "/wp-json/wp/v2/product_brand?per_page=100",
  "/wp-json/wp/v2/product-brands?per_page=100"
]
rows=[]
for p in paths:
    r=requests.get(BASE+p,auth=AUTH,timeout=60)
    rec={"path":p,"status":r.status_code,"ok":r.ok}
    if r.ok:
        try:
            data=r.json()
            rec["count"]=len(data) if isinstance(data,list) else None
            rec["sample"]=data[:5] if isinstance(data,list) else data
        except Exception:
            rec["body"]=r.text[:500]
    else:
        try: rec["error"]=r.json()
        except Exception: rec["error"]=r.text[:500]
    rows.append(rec)
Path("brand-assignment-results").mkdir(exist_ok=True)
Path("brand-assignment-results/taxonomy-probe.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps([{"path":x["path"],"status":x["status"],"ok":x["ok"],"count":x.get("count")} for x in rows],ensure_ascii=False))
if not any(x["ok"] for x in rows): raise SystemExit(2)
