#!/usr/bin/env python3
import json, os, sys
from urllib.parse import urljoin
import requests

base=os.environ["WP_BASE_URL"].rstrip("/")+"/"
auth=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
pages={"one_hectare_basket":145233,"product_comparator":145234}
checks={}
for name,pid in pages.items():
    r=requests.get(urljoin(base,f"wp-json/wp/v2/pages/{pid}"),params={"context":"edit"},auth=auth,timeout=90)
    r.raise_for_status(); o=r.json(); raw=((o.get("content") or {}).get("raw") or "")
    checks[name]={
      "id":pid,"status":o.get("status"),"slug":o.get("slug"),"chars":len(raw),
      "has_script":"<script" in raw.lower(),
      "has_h1":"<h1" in raw.lower(),
      "has_safety_copy":("طراحی هیدرولیکی" in raw or "حدس نمی" in raw),
      "marker_ok":(("k20-area" in raw and "k20-calc" in raw) if name=="one_hectare_basket" else ("wc/store/v1/products" in raw and "k20-compare" in raw))
    }

store={"ok":False}
try:
    r=requests.get(urljoin(base,"wp-json/wc/store/v1/products"),params={"per_page":1},timeout=90)
    body=r.json() if r.ok else None
    store={"ok":r.ok and isinstance(body,list),"http_status":r.status_code,"items":len(body) if isinstance(body,list) else 0}
except Exception as e:
    store={"ok":False,"error":type(e).__name__}

# Formula unit test: 10,000 m2, 100m rows, 1m spacing, 5% reserve, 1000m roll.
area=10000; length=100; spacing=1; waste=5; roll=1000
width=area/length; rows=max(1,int(width//spacing)); base_tape=rows*length; total=base_tape*(1+waste/100); rolls=-(-int(total*1000)//int(roll*1000))
formula={"rows":rows,"base_tape_m":base_tape,"total_tape_m":total,"rolls":rolls,
         "expected":{"rows":100,"base_tape_m":10000,"total_tape_m":10500,"rolls":11}}
formula["ok"]=all(formula[k]==v for k,v in formula["expected"].items())
record={"ok":all(x["status"]=="draft" and x["has_script"] and x["has_h1"] and x["marker_ok"] for x in checks.values()) and store["ok"] and formula["ok"],
        "mode":"read-only-qa","pages":checks,"store_api":store,"basket_formula_test":formula}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
with open(sys.argv[1],"w",encoding="utf-8") as f:json.dump(record,f,ensure_ascii=False,indent=2)
print("PHASE2_TOOL_QA",record["ok"],record)
