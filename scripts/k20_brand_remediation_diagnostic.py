#!/usr/bin/env python3
import json, os, time, re
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session();S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-brand-remediation-diagnostic/1.0","Cache-Control":"no-cache"})
M=json.loads(Path("brand-remediation/verified-map-20261003.json").read_text(encoding="utf-8"))
SN=json.loads(Path("brand-remediation-results/snapshot-87.json").read_text(encoding="utf-8"))
ids=sorted(int(x["product_id"]) for x in SN["rows"])

def req(path,params=None):
  for n in range(5):
    r=S.get(BASE+path,params=params,timeout=90)
    if r.status_code in (429,500,502,503,504):
      time.sleep(1.5*(n+1));continue
    r.raise_for_status();return r.json()
  raise RuntimeError("retry exhausted")

terms=[]
for page in range(1,10):
  got=req("/wp-json/wp/v2/product_brand",{"per_page":100,"page":page,"context":"edit"})
  terms+=got
  if len(got)<100:break

products=[]
for i in range(0,len(ids),50):
  chunk=ids[i:i+50]
  got=req("/wp-json/wc/v3/products",{"include":",".join(map(str,chunk)),"per_page":100})
  products+=got

out={
  "ok":True,
  "terms":[{"id":int(x["id"]),"name":x.get("name")} for x in terms],
  "targets":[{"product_id":int(p["id"]),"name":p.get("name"),"brands":[{"id":int(b["id"]),"name":b.get("name")} for b in (p.get("brands") or [])]} for p in products],
  "writes_performed":0
}
Path("brand-remediation-results").mkdir(exist_ok=True)
Path("brand-remediation-results/diagnostic-latest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"terms":len(terms),"targets":len(products)},ensure_ascii=False))
