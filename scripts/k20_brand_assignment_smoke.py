#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-brand-smoke/1.0"})

def get(path,params=None):
    r=S.get(BASE+path,params=params,timeout=60); r.raise_for_status(); return r.json()
def post(path,payload):
    r=S.post(BASE+path,json=payload,timeout=60); r.raise_for_status(); return r.json()

terms=get("/wp-json/wp/v2/product_brand",{"per_page":100,"page":1,"context":"edit"})
matches=[t for t in terms if str(t.get("name") or "").strip().startswith("ویسپار")]
if len(matches)!=1:
    raise SystemExit("Expected exactly one Vispar brand term, got "+str([(x.get("id"),x.get("name")) for x in matches]))
term=matches[0]
pid=140429
before=get(f"/wp-json/wp/v2/product/{pid}",{"context":"edit"})
before_brands=before.get("product_brand") or []
if before_brands:
    raise SystemExit(f"Smoke target {pid} is no longer unbranded: {before_brands}")
updated=post(f"/wp-json/wp/v2/product/{pid}",{"product_brand":[int(term["id"])]})
after=get(f"/wp-json/wp/v2/product/{pid}",{"context":"edit"})
after_brands=after.get("product_brand") or []
ok=(after_brands==[int(term["id"])])
out={
  "ok":ok,"product_id":pid,"brand_id":int(term["id"]),"brand_name":term.get("name"),
  "before_product_brand":before_brands,"after_product_brand":after_brands,
  "only_field_requested":"product_brand"
}
Path("brand-assignment-results").mkdir(exist_ok=True)
Path("brand-assignment-results/smoke-vispar.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
if not ok: raise SystemExit(2)
