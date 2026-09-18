#!/usr/bin/env python3
import json, os
from datetime import datetime, timezone
import requests

base=os.environ["WP_BASE_URL"].rstrip("/")
auth=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
r=requests.get(base+"/wp-json/", auth=auth, timeout=60)
r.raise_for_status()
data=r.json()
routes=data.get("routes",{})
out={}
for path,meta in routes.items():
    if "keshavarz20-ops/v2" in path:
        clean={"namespace":meta.get("namespace"),"methods":meta.get("methods"),"endpoints":[]}
        for ep in meta.get("endpoints",[]):
            clean["endpoints"].append({
                "methods":ep.get("methods"),
                "args":{k:{"required":v.get("required"),"type":v.get("type"),"enum":v.get("enum")} for k,v in (ep.get("args") or {}).items()}
            })
        out[path]=clean
record={"captured_at_utc":datetime.now(timezone.utc).isoformat(),"route_count":len(out),"routes":out}
os.makedirs("phase7-results",exist_ok=True)
with open("phase7-results/bridge-capabilities.json","w",encoding="utf-8") as f:
    json.dump(record,f,ensure_ascii=False,indent=2); f.write("\n")
print(json.dumps({"ok":True,"route_count":len(out)}))
