#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
p="/wp-json/wp/v2/product_brand"
try:
    r=requests.get(BASE+p,params={"per_page":100,"page":1},auth=AUTH,timeout=20)
    out={"path":p,"status":r.status_code,"ok":r.ok}
    try: data=r.json()
    except Exception: data=None
    if r.ok and isinstance(data,list):
        out["count"]=len(data)
        out["brands"]=[{"id":x.get("id"),"name":x.get("name"),"slug":x.get("slug"),"count":x.get("count")} for x in data]
    else:
        out["error"]=data if data is not None else r.text[:500]
except Exception as e:
    out={"path":p,"status":0,"ok":False,"error":str(e)}
Path("brand-assignment-results").mkdir(exist_ok=True)
Path("brand-assignment-results/taxonomy-probe-fast.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":out["ok"],"status":out["status"],"count":out.get("count")},ensure_ascii=False))
if not out["ok"]: raise SystemExit(2)
