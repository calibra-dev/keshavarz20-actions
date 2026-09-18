#!/usr/bin/env python3
import json, os
from datetime import datetime, timezone
import requests
base=os.environ["WP_BASE_URL"].rstrip("/")
auth=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
r=requests.get(base+"/wp-json/",auth=auth,timeout=60)
r.raise_for_status()
routes=r.json().get("routes",{})
targets={}
for path,meta in routes.items():
    if path.startswith("/wpvibe/v1/file/"):
        clean={"namespace":meta.get("namespace"),"methods":meta.get("methods"),"endpoints":[]}
        for ep in meta.get("endpoints",[]):
            clean["endpoints"].append({
                "methods":ep.get("methods"),
                "args":{k:{"required":v.get("required"),"type":v.get("type"),"enum":v.get("enum")} for k,v in (ep.get("args") or {}).items()}
            })
        targets[path]=clean
out={"captured_at_utc":datetime.now(timezone.utc).isoformat(),"routes":targets}
os.makedirs("phase7-results",exist_ok=True)
with open("phase7-results/wpvibe-file-route-schema.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
print(json.dumps({"ok":True,"count":len(targets)}))
