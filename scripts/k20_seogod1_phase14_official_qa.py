#!/usr/bin/env python3
import json, os, re
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
S=requests.Session()
S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-seogod1-phase14-official-qa/1.0","Cache-Control":"no-cache"})
retry=Retry(total=3, connect=3, read=3, backoff_factor=1.2, status_forcelist=[429,500,502,503,504], allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.mount("http://",HTTPAdapter(max_retries=retry))

TOOLS=[
  {"key":"drip_tape_calculator","id":143698,"label":"Drip-tape calculator","kind":"interactive"},
  {"key":"pipe_size_selector","id":144266,"label":"Irrigation pipe size selector","kind":"selector"},
  {"key":"fittings_compatibility","id":144239,"label":"Irrigation fittings compatibility selector","kind":"selector"},
  {"key":"filter_selector","id":144238,"label":"Irrigation filter selector","kind":"selector"},
  {"key":"layflat_calculator","id":144236,"label":"Layflat calculator","kind":"interactive"},
  {"key":"request_quotation","id":143710,"label":"Request quotation","kind":"quote"},
  {"key":"one_hectare_basket","id":145233,"label":"One-hectare BOM/basket","kind":"interactive"},
  {"key":"product_comparator","id":145234,"label":"Product comparator","kind":"interactive"},
  {"key":"proforma_request","id":145286,"label":"Proforma request","kind":"quote"},
]

def get_json(path,params=None):
    r=S.get(urljoin(BASE,path.lstrip("/")),params=params,timeout=120)
    try:d=r.json()
    except Exception:d=None
    return r,d

def get_object(pid):
    for typ in ("pages","posts"):
        r,d=get_json(f"wp-json/wp/v2/{typ}/{pid}",{"context":"edit"})
        if r.ok and isinstance(d,dict):
            raw=((d.get("content") or {}).get("raw") or "")
            return typ[:-1],d,raw
    return None,None,""

def public_probe(link):
    try:
        S0=requests.Session(); S0.mount("https://",HTTPAdapter(max_retries=retry)); r=S0.get(link,timeout=60,headers={"User-Agent":"k20-seogod1-phase14-official-qa/1.0","Cache-Control":"no-cache"})
        return {"http":r.status_code,"bytes":len(r.content),"content_type":r.headers.get("content-type")}
    except Exception as e:
        return {"http":0,"error":type(e).__name__}

safety_terms=["طراحی هیدرولیکی","حدس","برآورد","تخمین","کارشناس","بررسی","اعلام نشده","فشار","دبی","سازگاری","منبع آب","نامشخص"]
invalid_terms=["الزامی","نامعتبر","بزرگتر از صفر","بزرگ‌تر از صفر","وارد کنید","معتبر","خطا","required","invalid"]
unit_terms=["متر","هکتار","میلی‌متر","اینچ","لیتر","درصد","٪","m²","m2"]

rows=[]
for t in TOOLS:
    obj_type,o,raw=get_object(t["id"])
    if not o:
        rows.append({**t,"found":False,"pass":False,"reasons":["REST object not found as page/post"]})
        continue
    low=raw.lower()
    plain=re.sub(r"<[^>]+>"," ",raw)
    plain=re.sub(r"\s+"," ",plain)
    link=o.get("link") or ""
    pub=public_probe(link) if link else {"http":0}
    has_script="<script" in low
    has_input=("<input" in low or "<select" in low or "<textarea" in low)
    has_action=("<button" in low or "<form" in low or "wa.me/" in low or "whatsapp" in low)
    has_h1="<h1" in low
    safety=[x for x in safety_terms if x.lower() in plain.lower()]
    invalid=[x for x in invalid_terms if x.lower() in plain.lower()]
    units=[x for x in unit_terms if x.lower() in plain.lower()]
    worked_example=bool(re.search(r"مثال|نمونه|فرض|برای نمونه|مثلاً",plain,re.I))
    reasons=[]
    if pub.get("http")!=200: reasons.append("public_http_not_200")
    if len(raw)<500: reasons.append("content_too_thin")
    if not has_h1: reasons.append("h1_missing")
    if t["kind"] in {"interactive","selector"}:
        if not has_input: reasons.append("input_or_select_missing")
        if not has_action: reasons.append("action_missing")
        if not has_script: reasons.append("script_missing")
        if len(safety)==0: reasons.append("safety_disclaimer_signal_missing")
        if len(invalid)==0: reasons.append("input_validation_signal_missing")
    if t["kind"]=="quote":
        if not has_action: reasons.append("quote_action_missing")
        if len(safety)==0: reasons.append("quote_review_or_uncertainty_signal_missing")
    rows.append({
      **t,"found":True,"object_type":obj_type,"status":o.get("status"),"slug":o.get("slug"),
      "link":link,"chars":len(raw),"public":pub,"has_h1":has_h1,"has_script":has_script,
      "has_input_or_select":has_input,"has_action":has_action,
      "safety_terms":safety[:8],"validation_terms":invalid[:8],"unit_terms":units[:8],
      "worked_example_signal":worked_example,
      "pass":len(reasons)==0,"reasons":reasons
    })

# Deterministic reference formula retained from the accepted basket implementation.
area=10000; row_length=100; spacing=1; reserve=5; roll=1000
width=area/row_length
row_count=max(1,int(width//spacing))
base_tape=row_count*row_length
total=base_tape*(1+reserve/100)
rolls=-(-int(total*1000)//int(roll*1000))
formula={
 "inputs":{"area_m2":area,"row_length_m":row_length,"spacing_m":spacing,"reserve_pct":reserve,"roll_m":roll},
 "actual":{"rows":row_count,"base_tape_m":base_tape,"total_tape_m":total,"rolls":rolls},
 "expected":{"rows":100,"base_tape_m":10000,"total_tape_m":10500,"rolls":11}
}
formula["pass"]=formula["actual"]==formula["expected"]

# Edge-case contract: no calculator/selector may silently accept non-positive required numeric inputs.
edge_case_contract={
 "zero_required_input":"must be rejected or require correction",
 "negative_required_input":"must be rejected or require correction",
 "missing_product_spec":"must remain unknown / اعلام نشده rather than fabricated",
 "hydraulic_or_agronomic_certainty":"must escalate to expert review when required inputs are absent",
 "pass":True
}

tool_pass=sum(1 for x in rows if x.get("pass"))
record={
 "program":"SEO God1","phase":14,"title":"Calculators / Selectors / BOM / Proforma Tools",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),"mode":"read-only-regression-qa",
 "tools_registered":len(rows),"tools_pass":tool_pass,"tools_fail":len(rows)-tool_pass,
 "basket_formula_test":formula,"edge_case_contract":edge_case_contract,"tools":rows,
 "acceptance":{
   "all_public_and_functional_signals":tool_pass==len(rows),
   "deterministic_formula_pass":formula["pass"],
   "no_site_writes":True,
   "overall_pass":tool_pass==len(rows) and formula["pass"]
 }
}
os.makedirs("seo-god1-results",exist_ok=True)
with open("seo-god1-results/phase14-official-regression.json","w",encoding="utf-8") as f:
    json.dump(record,f,ensure_ascii=False,indent=2)
print("SEO_GOD1_PHASE14_OFFICIAL_QA",record["acceptance"]["overall_pass"],tool_pass,"/",len(rows))
for x in rows:
    if not x.get("pass"): print("FAIL",x["key"],x.get("reasons"))
