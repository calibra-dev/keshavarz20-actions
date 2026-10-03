#!/usr/bin/env python3
import json, os, re, time
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-brand-remediation-snapshot/1.0","Cache-Control":"no-cache"})

pseudo=json.loads(Path("brand-assignment-results/apply-all-158.json").read_text(encoding="utf-8"))
ids=[int(x["product_id"]) for x in pseudo.get("results",[]) if x.get("requested_brand")=="متفرقه"]
multi=json.loads(Path("refresh-results/multibrand-audit.json").read_text(encoding="utf-8"))
ids += [int(x["product_id"]) for x in multi.get("rows",[])]
ids=sorted(set(ids))
if len(ids)!=87: raise SystemExit(f"expected 87 targets, got {len(ids)}")

def clean(s):
    s=re.sub(r"<[^>]+>"," ",str(s or ""))
    return re.sub(r"\s+"," ",s).strip()

rows=[]
chunks=[ids[i:i+50] for i in range(0,len(ids),50)]
products=[]
for chunk in chunks:
    for attempt in range(5):
        r=S.get(BASE+"/wp-json/wc/v3/products",params={"include":",".join(str(x) for x in chunk),"per_page":100},timeout=120)
        if r.status_code in (429,500,502,503,504):
            time.sleep((attempt+1)*1.5); continue
        r.raise_for_status(); break
    products.extend(r.json())
by_id={int(p["id"]):p for p in products}
missing=[x for x in ids if x not in by_id]
if missing: raise SystemExit(f"missing target products: {missing}")
for pid in ids:
    p=by_id[pid]
    rows.append({
      "product_id":pid,
      "name":p.get("name"),
      "sku":p.get("sku"),
      "permalink":p.get("permalink"),
      "status":p.get("status"),
      "brands":[{"id":int(x.get("id") or 0),"name":x.get("name")} for x in (p.get("brands") or [])],
      "categories":[{"id":int(x.get("id") or 0),"name":x.get("name")} for x in (p.get("categories") or [])],
      "attributes":[{"name":a.get("name"),"options":a.get("options")} for a in (p.get("attributes") or [])],
      "short_description":clean(p.get("short_description"))[:4000],
      "description":clean(p.get("description"))[:12000],
      "image_alts":[str(x.get("alt") or "") for x in (p.get("images") or [])],
    })
Path("brand-remediation-results").mkdir(exist_ok=True)
out={"ok":True,"target_count":len(ids),"rows":rows,"writes_performed":0}
Path("brand-remediation-results/snapshot-87.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":True,"target_count":len(ids),"rows":len(rows)},ensure_ascii=False))
