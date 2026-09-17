#!/usr/bin/env python3
import json, os, re, html as htmlmod
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase3-feed-parity/1.0","Cache-Control":"no-cache"})

def get(path,params=None,auth=True):
    r=(S if auth else requests).get(urljoin(BASE,path.lstrip("/")),params=params,timeout=120,headers={"User-Agent":"k20-phase3-feed-parity/1.0","Cache-Control":"no-cache"})
    r.raise_for_status(); return r

def setting_value(group,key):
    try:
        rows=get(f"wp-json/wc/v3/settings/{group}").json()
        for x in rows:
            if x.get("id")==key: return x.get("value")
    except Exception:
        return None
    return None

def walk_jsonld(x):
    out=[]
    if isinstance(x,dict):
        out.append(x)
        for v in x.values():
            if isinstance(v,(dict,list)): out.extend(walk_jsonld(v))
    elif isinstance(x,list):
        for v in x: out.extend(walk_jsonld(v))
    return out

def extract_products(page):
    objs=[]
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',page,re.I|re.S):
        raw=htmlmod.unescape(m.group(1)).strip()
        try: data=json.loads(raw)
        except Exception: continue
        for o in walk_jsonld(data):
            t=o.get("@type")
            types=t if isinstance(t,list) else [t]
            if "Product" in types: objs.append(o)
    return objs

def offer_obj(p):
    o=p.get("offers")
    if isinstance(o,list): return o[0] if o else {}
    return o if isinstance(o,dict) else {}

def num(v):
    try:return float(str(v).replace(",","").strip())
    except:return None

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
currency=setting_value("general","woocommerce_currency") or setting_value("general","currency") or "UNKNOWN"
feed=[]; parity=[]
for item in pim.get("products",[]):
    pid=int(item["product_id"])
    p=get(f"wp-json/wc/v3/products/{pid}").json()
    public=requests.get(p.get("permalink"),timeout=120,headers={"User-Agent":"k20-phase3-feed-parity/1.0","Cache-Control":"no-cache"})
    public.raise_for_status()
    plist=extract_products(public.text[:1500000])
    sku=(p.get("sku") or "").strip()
    schema=None
    for z in plist:
        if sku and str(z.get("sku") or "").strip()==sku: schema=z; break
    if schema is None and plist: schema=plist[0]
    off=offer_obj(schema or {})
    schema_price=num(off.get("price") if off else None)
    schema_currency=(off.get("priceCurrency") if off else None)
    schema_avail=(off.get("availability") if off else None)
    raw_price=num(p.get("price"))
    if p.get("stock_status")=="instock": feed_avail="in_stock"; expected_schema_avail="https://schema.org/InStock"
    elif p.get("stock_status")=="outofstock": feed_avail="out_of_stock"; expected_schema_avail="https://schema.org/OutOfStock"
    else: feed_avail="backorder"; expected_schema_avail=None

    price_parity="not_evaluated"
    expected_schema_price=None
    if raw_price is not None and schema_price is not None:
        cur=str(currency).upper()
        sc=str(schema_currency or "").upper()
        if cur==sc:
            expected_schema_price=raw_price
            price_parity="pass" if abs(schema_price-raw_price)<0.01 else "fail"
        elif cur in ("IRT","TMN","TOMAN") and sc=="IRR":
            expected_schema_price=raw_price*10
            price_parity="pass" if abs(schema_price-expected_schema_price)<0.01 else "fail"
        else:
            price_parity="currency_rule_unknown"

    schema_sku=(schema or {}).get("sku")
    schema_name=(schema or {}).get("name")
    schema_brand=(schema or {}).get("brand")
    if isinstance(schema_brand,dict): schema_brand=schema_brand.get("name")
    elif isinstance(schema_brand,list): schema_brand="، ".join(str(x.get("name") if isinstance(x,dict) else x) for x in schema_brand)

    row={
      "id":sku or f"K20-{pid}",
      "wp_product_id":pid,
      "title":p.get("name"),
      "link":p.get("permalink"),
      "image_link":((p.get("images") or [{}])[0].get("src") if p.get("images") else None),
      "availability":feed_avail,
      "store_price_raw":p.get("price"),
      "store_currency":currency,
      "brand":((item.get("pim_fields") or {}).get("brand") or {}).get("value"),
      "gtin":((item.get("stable_identifiers") or {}).get("gtin") or {}).get("value"),
      "mpn":(((item.get("stable_identifiers") or {}).get("mpn") or {}).get("value") if isinstance((item.get("stable_identifiers") or {}).get("mpn"),dict) else None),
      "status":"active" if p.get("status")=="publish" else p.get("status"),
      "feed_scope":"internal_canonical_top30",
      "not_submitted_to_external_merchant":True
    }
    feed.append(row)
    checks={
      "product_schema_present":bool(schema),
      "sku_match":bool(schema) and str(schema_sku or "").strip()==sku,
      "name_present":bool(schema_name),
      "offer_present":bool(off),
      "availability_match":(schema_avail==expected_schema_avail) if expected_schema_avail else None,
      "price_parity":price_parity
    }
    hard_ok=checks["product_schema_present"] and checks["sku_match"] and checks["offer_present"] and checks["availability_match"] is not False and checks["price_parity"]!="fail"
    parity.append({
      "product_id":pid,"rank":item["rank"],"url":p.get("permalink"),"checks":checks,"pass":hard_ok,
      "observed":{"woo_stock_status":p.get("stock_status"),"woo_price_raw":p.get("price"),"woo_currency":currency,
                  "schema_sku":schema_sku,"schema_price":schema_price,"schema_currency":schema_currency,
                  "schema_availability":schema_avail,"schema_brand":schema_brand},
      "expected_schema_price_when_rule_known":expected_schema_price
    })

summary={
 "products":len(feed),"parity_pass":sum(1 for x in parity if x["pass"]),"parity_fail":sum(1 for x in parity if not x["pass"]),
 "schema_missing":sum(1 for x in parity if not x["checks"]["product_schema_present"]),
 "offer_missing":sum(1 for x in parity if not x["checks"]["offer_present"]),
 "sku_mismatch":sum(1 for x in parity if not x["checks"]["sku_match"]),
 "availability_mismatch":sum(1 for x in parity if x["checks"]["availability_match"] is False),
 "price_mismatch":sum(1 for x in parity if x["checks"]["price_parity"]=="fail"),
 "store_currency":currency
}
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":True,"version":"phase3-top30-internal-feed-v1","generated_at_utc":__import__("datetime").datetime.utcnow().isoformat()+"Z",
           "status":"internal_canonical_not_submitted","summary":summary,"products":feed},
          open("phase3-results/top30-product-feed.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
json.dump({"ok":True,"version":"phase3-page-schema-feed-parity-v1","summary":summary,"products":parity},
          open("phase3-results/page-schema-feed-parity.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_FEED_PARITY_OK",summary)
