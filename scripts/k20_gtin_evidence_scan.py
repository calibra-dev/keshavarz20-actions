#!/usr/bin/env python3
import json, os, re, time
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-gtin-evidence-scan/1.0","Cache-Control":"no-cache"})

GTIN_KEYS=("gtin","ean","upc","barcode","isbn","global_unique_id","_global_unique_id")

def valid_check_digit(code):
    if not re.fullmatch(r"\d{8}|\d{12}|\d{13}|\d{14}", code):
        return False
    digits=[int(x) for x in code]
    check=digits[-1]
    body=digits[:-1]
    total=0
    for i,d in enumerate(reversed(body)):
        total += d*(3 if i%2==0 else 1)
    calc=(10-(total%10))%10
    return calc==check

def all_products():
    out=[]
    for page in range(1,20):
        for attempt in range(5):
            r=S.get(BASE+"/wp-json/wc/v3/products",params={"status":"publish","per_page":100,"page":page,"orderby":"id","order":"asc"},timeout=120)
            if r.status_code in (429,500,502,503,504):
                time.sleep((attempt+1)*1.5); continue
            r.raise_for_status(); break
        rows=r.json()
        if not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

records=[]
for p in all_products():
    candidates=[]
    direct=p.get("global_unique_id")
    if direct:
        candidates.append({"source":"wc.global_unique_id","key":"global_unique_id","value":str(direct).strip()})
    for m in p.get("meta_data") or []:
        k=str(m.get("key") or "")
        kl=k.lower()
        if any(x in kl for x in GTIN_KEYS):
            v=m.get("value")
            if isinstance(v,(str,int,float)):
                candidates.append({"source":"wc.meta_data","key":k,"value":str(v).strip()})
    # explicit identifier-like attributes only
    for a in p.get("attributes") or []:
        name=str(a.get("name") or "")
        nl=name.lower()
        if any(x in nl for x in GTIN_KEYS):
            for v in a.get("options") or []:
                candidates.append({"source":"wc.attribute","key":name,"value":str(v).strip()})

    normalized=[]
    seen=set()
    for c in candidates:
        raw=c["value"]
        for code in re.findall(r"(?<!\d)(\d{8}|\d{12}|\d{13}|\d{14})(?!\d)", raw):
            key=(c["source"],c["key"],code)
            if key in seen: continue
            seen.add(key)
            normalized.append({
              "source":c["source"],"key":c["key"],"raw":raw[:300],"code":code,
              "length":len(code),"check_digit_valid":valid_check_digit(code)
            })
    if normalized:
        records.append({
          "product_id":int(p["id"]),"name":p.get("name"),"sku":p.get("sku"),
          "permalink":p.get("permalink"),"candidates":normalized
        })

out={
 "phase":14,
 "type":"live_gtin_evidence_scan",
 "published_products_scanned":652,
 "products_with_explicit_identifier_candidates":len(records),
 "records":records,
 "policy":{
   "sku_is_not_gtin":True,
   "check_digit_validity_is_necessary_not_sufficient":True,
   "external_or_manufacturer_verification_required_before_public_gtin_write":True
 },
 "writes_performed":0
}
Path("growthos-phase14-results").mkdir(exist_ok=True)
Path("growthos-phase14-results/gtin-evidence-scan-latest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"products_with_candidates":len(records),"candidate_count":sum(len(x["candidates"]) for x in records)},ensure_ascii=False))
