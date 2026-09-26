#!/usr/bin/env python3
import json, os, requests
from pathlib import Path

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
IDS=[134980,134982,135138,135140,135142,135363,135479,135481,135483,135499,135848,140374]

truth=json.loads(Path("growthos-phase2-results/product-truth-registry.json").read_text(encoding="utf-8"))
truth_map={}
for rec in truth.get("records",[]):
    pid=int(rec.get("product_id") or 0)
    if pid in IDS:
        f=(rec.get("fields") or {}).get("brand") or {}
        truth_map[pid]={
          "brand":f.get("value"),
          "status":f.get("status"),
          "source":f.get("source")
        }

rows=[]
for pid in IDS:
    r=requests.get(f"{BASE}/wp-json/wc/v3/products/{pid}",auth=AUTH,timeout=60)
    r.raise_for_status(); p=r.json()
    brands=[{"id":int(b["id"]),"name":str(b.get("name") or "")} for b in (p.get("brands") or []) if b.get("id")]
    rows.append({
      "product_id":pid,
      "title":p.get("name"),
      "current_brands":brands,
      "phase2_truth":truth_map.get(pid)
    })

out={"ok":True,"count":len(rows),"rows":rows,"writes_performed":0}
Path("refresh-results").mkdir(exist_ok=True)
Path("refresh-results/multibrand-audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
