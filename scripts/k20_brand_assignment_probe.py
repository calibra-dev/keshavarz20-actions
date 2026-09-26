#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
r=requests.get(BASE+"/wp-json/wc/v3/products/brands",params={"per_page":100,"page":1},auth=AUTH,timeout=90)
out={"ok":r.ok,"status":r.status_code,"count":0,"brands":[]}
if r.ok:
    rows=r.json(); out["count"]=len(rows); out["brands"]=[{"id":x.get("id"),"name":x.get("name"),"slug":x.get("slug"),"count":x.get("count")} for x in rows]
else:
    try: out["error"]=r.json()
    except Exception: out["error"]=r.text[:500]
Path("brand-assignment-results").mkdir(exist_ok=True)
Path("brand-assignment-results/probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":out["ok"],"status":out["status"],"count":out["count"]},ensure_ascii=False))
if not r.ok: raise SystemExit(2)
