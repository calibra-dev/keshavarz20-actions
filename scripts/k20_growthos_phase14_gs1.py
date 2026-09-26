#!/usr/bin/env python3
import json, os, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.0,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry)); S.mount("http://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase14-gs1/1.0","Cache-Control":"no-cache"})
NOW=datetime.now(timezone.utc).isoformat()
TRUTH=Path("growthos-phase2-results/product-truth-registry.json")
P13=Path("growthos-phase13-results/summary.json")

def api(path,params=None):
    r=S.get(urljoin(BASE,path.lstrip("/")),params=params,timeout=120); r.raise_for_status(); return r.json()

def all_products():
    out=[]
    for page in range(1,40):
        rows=api("wp-json/wc/v3/products",{"status":"publish","per_page":100,"page":page,"orderby":"id","order":"asc"})
        if not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

def norm_digits(v):
    return re.sub(r"\D","",str(v or ""))

def gtin_checksum_ok(v):
    d=norm_digits(v)
    if len(d) not in (8,12,13,14): return False
    nums=list(map(int,d))
    check=nums[-1]; body=nums[:-1]
    total=0
    for i,n in enumerate(reversed(body)):
        total += n*(3 if i%2==0 else 1)
    return ((10-(total%10))%10)==check

def gtin14(v):
    d=norm_digits(v)
    return d.zfill(14) if len(d) in (8,12,13,14) and gtin_checksum_ok(d) else None

def truth_gtin_map():
    if not TRUTH.exists(): return {}
    try: data=json.loads(TRUTH.read_text(encoding="utf-8"))
    except Exception: return {}
    out={}
    for rec in data.get("records",[]):
        f=(rec.get("fields") or {}).get("gtin") or {}
        if f.get("status") in {"VERIFIED","SOURCE-CONFIRMED","USER-CONFIRMED"} and f.get("value"):
            out[int(rec["product_id"])]=str(f["value"]).strip()
    return out

def woo_candidates(p):
    vals=[]
    for key in ["global_unique_id","gtin","ean","upc","isbn"]:
        v=p.get(key)
        if v: vals.append((key,str(v).strip()))
    for m in p.get("meta_data") or []:
        k=str(m.get("key") or "").lower()
        if any(x in k for x in ["gtin","ean","upc","barcode","isbn","global_unique"]):
            v=m.get("value")
            if isinstance(v,(str,int,float)) and str(v).strip(): vals.append(("meta:"+k,str(v).strip()))
    seen=set(); out=[]
    for src,v in vals:
        z=(src,v)
        if z not in seen: seen.add(z); out.append({"source":src,"value":v})
    return out

def schema_gtins(p):
    url=p.get("permalink") or ""
    if not url: return []
    try:
        r=requests.get(url,timeout=60,headers={"User-Agent":"k20-growthos-phase14-gs1/1.0","Cache-Control":"no-cache"})
        vals=[]
        for m in re.finditer(r'"gtin(?:8|12|13|14)?"\s*:\s*"([^"]+)"',r.text,re.I):
            vals.append(m.group(1).strip())
        return sorted(set(vals))
    except Exception:
        return []

if P13.exists():
    p13=json.loads(P13.read_text(encoding="utf-8"))
    if not p13.get("ok"): raise SystemExit("Phase 13 prerequisite is not PASS")

truth=truth_gtin_map()
products=all_products()
rows=[]
with ThreadPoolExecutor(max_workers=10) as ex:
    futs={ex.submit(schema_gtins,p):p for p in products}
    for fut in as_completed(futs):
        p=futs[fut]; pid=int(p["id"])
        source_gtin=truth.get(pid)
        wc=woo_candidates(p)
        sg=fut.result()
        chosen=source_gtin
        chosen_source="phase2_truth_registry" if source_gtin else None
        normalized=gtin14(chosen) if chosen else None
        authoritative=bool(source_gtin and normalized)
        rows.append({
            "product_id":pid,
            "name":p.get("name"),
            "sku":str(p.get("sku") or "").strip() or None,
            "canonical_url":p.get("permalink"),
            "truth_gtin_status":"VERIFIED" if source_gtin else "UNKNOWN",
            "truth_gtin_value":source_gtin,
            "woo_identifier_candidates":wc,
            "schema_gtin_candidates":sg,
            "gtin_checksum_valid":bool(normalized),
            "gtin14":normalized,
            "gs1_digital_link_eligible":authoritative,
            "digital_link":("https://id.gs1.org/01/"+normalized) if authoritative else None,
            "reason":None if authoritative else ("truth_gtin_invalid_checksum" if source_gtin else "no_source_verified_gtin")
        })
rows.sort(key=lambda x:x["product_id"])
verified=[x for x in rows if x["gs1_digital_link_eligible"]]
woo_candidates_count=sum(1 for x in rows if x["woo_identifier_candidates"])
schema_candidates_count=sum(1 for x in rows if x["schema_gtin_candidates"])
unbacked_schema=sum(1 for x in rows if x["schema_gtin_candidates"] and x["truth_gtin_status"]=="UNKNOWN")

contract={
  "phase":14,
  "version":"growthos-gs1-digital-link-v1",
  "generated_at_utc":NOW,
  "standard":{"uri_syntax":"GS1 Digital Link URI Syntax 1.7.0","gtin_path_ai":"01","gtin_new_implementation_format":"14 digits","canonical_reference_domain":"https://id.gs1.org"},
  "policy":{
    "never_treat_sku_as_gtin":True,
    "never_generate_gtin":True,
    "checksum_is_not_ownership_proof":True,
    "digital_link_requires_source_verified_gtin":True,
    "qr_publication_requires_existing_verified_gtin":True,
    "no_fake_authenticity_claim":True
  },
  "future_resolver_contract":{
    "reference_pattern":"https://id.gs1.org/01/{gtin14}",
    "k20_owned_resolver_pattern":"https://keshavarz20.com/id/01/{gtin14}",
    "create_public_resolver_now":bool(verified),
    "intended_link_targets":["canonical_product","verified_specifications","installation_instructions","warranty_return_policy","traceability_when_source_backed"]
  }
}
summary={
  "ok":True,
  "phase":14,
  "title":"GS1 / GS1 Digital Link",
  "generated_at_utc":NOW,
  "status":"PASS_GS1_DIGITAL_LINK_READY" if verified else "PASS_GUARDED_NO_VERIFIED_GS1_IDS",
  "published_products":len(products),
  "source_verified_gtins":len(verified),
  "woo_identifier_candidate_products":woo_candidates_count,
  "schema_gtin_candidate_products":schema_candidates_count,
  "unbacked_schema_gtin_products":unbacked_schema,
  "digital_links_emitted":len(verified),
  "gtins_fabricated":0,
  "skus_promoted_to_gtin":0,
  "public_resolver_urls_created":0,
  "next_external_gate":None if verified else "Obtain manufacturer/GS1-issued GTIN evidence for products that actually have a GTIN; do not infer identifiers from SKU."
}
Path("growthos-phase14-results").mkdir(exist_ok=True)
for name,obj in [
 ("identifier-registry.json",{"phase":14,"generated_at_utc":NOW,"records":rows}),
 ("digital-link-contract.json",contract),
 ("summary.json",summary)
]:
    Path("growthos-phase14-results",name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
print("GROWTHOS_PHASE14",json.dumps(summary,ensure_ascii=False))
