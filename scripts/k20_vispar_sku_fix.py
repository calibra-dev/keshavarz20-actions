#!/usr/bin/env python3
import json, os, requests
from datetime import datetime, timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.0,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","PUT"]))
S.mount("https://",HTTPAdapter(max_retries=retry)); S.mount("http://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-sku-fix-20260926/1.0"})

P1=140654
P2=140655
SKU1="430000300-2"
SKU2="4300003001"

def req(method,path,body=None,params=None):
    r=S.request(method,urljoin(BASE+"/",path.lstrip("/")),json=body,params=params,timeout=90)
    r.raise_for_status()
    return r.json()

before1=req("GET",f"wp-json/wc/v3/products/{P1}")
before2=req("GET",f"wp-json/wc/v3/products/{P2}")

conflicts=req("GET","wp-json/wc/v3/products",params={"sku":SKU2,"per_page":100})
conflict_ids=[int(x["id"]) for x in conflicts if int(x["id"])!=P2]
if conflict_ids:
    raise SystemExit(f"Target SKU {SKU2} already belongs to other product ids: {conflict_ids}")

changes=[]
if str(before1.get("sku") or "")!=SKU1:
    req("PUT",f"wp-json/wc/v3/products/{P1}",{"sku":SKU1})
    changes.append({"id":P1,"sku":SKU1})
if str(before2.get("sku") or "")!=SKU2:
    req("PUT",f"wp-json/wc/v3/products/{P2}",{"sku":SKU2})
    changes.append({"id":P2,"sku":SKU2})

after1=req("GET",f"wp-json/wc/v3/products/{P1}")
after2=req("GET",f"wp-json/wc/v3/products/{P2}")

ok=(str(after1.get("sku") or "")==SKU1 and str(after2.get("sku") or "")==SKU2)
out={
  "ok":ok,
  "generated_at_utc":datetime.now(timezone.utc).isoformat(),
  "products":[
    {"id":P1,"name":after1.get("name"),"sku_before":before1.get("sku"),"sku_after":after1.get("sku"),"status":after1.get("status")},
    {"id":P2,"name":after2.get("name"),"sku_before":before2.get("sku"),"sku_after":after2.get("sku"),"status":after2.get("status")}
  ],
  "changes":changes,
  "price_changed":False,
  "stock_changed":False,
  "other_fields_changed_by_script":False
}
os.makedirs("sku-fix-results",exist_ok=True)
with open("sku-fix-results/20260926-vispar-sku-fix.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False))
if not ok:
    raise SystemExit("SKU readback mismatch")
