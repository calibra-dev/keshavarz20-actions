#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
r=requests.get(BASE+"/wp-json/",auth=AUTH,timeout=30)
r.raise_for_status()
data=r.json()
routes=data.get("routes") or {}
hits=[]
for route,meta in routes.items():
    if "brand" in route.lower():
        methods=[]
        for ep in (meta.get("endpoints") or []):
            methods.extend(ep.get("methods") or [])
        hits.append({"route":route,"methods":sorted(set(methods))})
out={"ok":True,"brand_routes":sorted(hits,key=lambda x:x["route"])}
Path("brand-assignment-results").mkdir(exist_ok=True)
Path("brand-assignment-results/rest-index-brand-routes.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
if not hits: raise SystemExit(2)
