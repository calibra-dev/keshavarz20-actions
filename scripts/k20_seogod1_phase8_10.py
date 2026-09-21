#!/usr/bin/env python3
import os,json,re,requests,html
from datetime import datetime,timezone
from urllib.parse import urljoin
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-seogod1-phase8-10/1.0","Cache-Control":"no-cache"})

def wp(path,params=None):
    r=S.get(urljoin(BASE+"/",path.lstrip("/")),params=params,timeout=120)
    r.raise_for_status()
    return r.json()

def pub(url):
    try:
        r=requests.get(url,timeout=45,headers={"User-Agent":"k20-seogod1-phase8-10/1.0","Cache-Control":"no-cache"})
        return {"http":r.status_code,"final_url":r.url,"bytes":len(r.content)}
    except Exception as e:
        return {"http":0,"error":type(e).__name__}

with open("phase45/input/gsc-baseline-2026-09-18.json",encoding="utf-8") as f:
    gsc=json.load(f)
with open("phase9-results/canonical-pim.json",encoding="utf-8") as f:
    pim=json.load(f)

money_terms=re.compile(r"(قیمت|خرید|فروش|نمایندگی|تانک|مخزن|شیر|کمربند|فیلتر|نوار.?تیپ|لوله.?نخدار|پلی.?اتیلن|اتصالات|مه.?پاش|بارانی|فلنج|رابط|زانو)",re.I)
calc_terms=re.compile(r"(ماشین.?حساب|محاسبه)",re.I)
rows=[]
for x in (gsc.get("queries") or {}).get("rows",[]):
    q=str((x.get("keys") or [""])[0])
    if not (money_terms.search(q) or calc_terms.search(q)): continue
    intent="calculator" if calc_terms.search(q) else ("price_purchase" if re.search(r"(قیمت|خرید|فروش)",q) else "commercial_discovery")
    rows.append({"query":q,"clicks":x.get("clicks",0),"impressions":x.get("impressions",0),"ctr":x.get("ctr",0),"position":x.get("position"),"intent":intent})
rows.sort(key=lambda z:(z["impressions"],z["clicks"]),reverse=True)

owner_rules=[
  ("calculator",r"ماشین.?حساب|محاسبه","https://keshavarz20.com/drip-tape-length-fittings-calculator/"),
  ("drip_tape",r"نوار.?تیپ|شیر.?تیپ","https://keshavarz20.com/product-category/agricultural-equipment-supplies/irrigation-pipes/%D9%86%D9%88%D8%A7%D8%B1-%D8%AA%DB%8C%D9%BE/"),
  ("layflat_rain",r"مه.?پاش|لوله.?بارانی|نخدار","https://keshavarz20.com/product-category/agricultural-equipment-supplies/irrigation-pipes/%D9%84%D9%88%D9%84%D9%87-%D9%86%D8%AE%D8%AF%D8%A7%D8%B1/"),
  ("pe_fittings",r"پلی.?اتیلن|کمربند|فلنج|زانو|رابط","https://keshavarz20.com/product-category/agricultural-equipment-supplies/polyethylene-fittings/"),
  ("filters",r"فیلتر","https://keshavarz20.com/product-category/agricultural-equipment-supplies/%D9%81%DB%8C%D9%84%D8%AA%D8%B1-%D9%88-%D9%81%DB%8C%D9%84%D8%AA%D8%B1%D8%A7%D8%B3%DB%8C%D9%88%D9%86/")
]
for r in rows:
    r["cluster"]="other_commercial"; r["owner_url"]=None
    for key,pat,url in owner_rules:
        if re.search(pat,r["query"],re.I):
            r["cluster"]=key; r["owner_url"]=url; break

calculator={}
for subtype in ("posts","pages"):
    try:
        hit=wp(f"wp-json/wp/v2/{subtype}",{"slug":"drip-tape-length-fittings-calculator","context":"edit","per_page":10})
        if hit:
            o=hit[0]; raw=((o.get("content") or {}).get("raw") or "")
            calculator={"found":True,"subtype":subtype[:-1],"id":o.get("id"),"slug":o.get("slug"),"status":o.get("status"),"link":o.get("link"),"chars":len(raw),"has_script":"<script" in raw.lower(),"has_quote_signal":("پیش" in raw and "فاکتور" in raw)}
            break
    except Exception:
        pass
if not calculator:
    calculator={"found":False}

tools={}
for name,pid,slug in [
 ("basket",145233,"one-hectare-drip-irrigation-basket"),
 ("comparator",145234,"irrigation-product-comparator")
]:
    try:
        o=wp(f"wp-json/wp/v2/pages/{pid}",{"context":"edit"})
        raw=((o.get("content") or {}).get("raw") or "")
        tools[name]={"id":pid,"status":o.get("status"),"slug":o.get("slug"),"link":o.get("link"),"chars":len(raw),"has_script":"<script" in raw.lower(),"has_h1":"<h1" in raw.lower(),"has_quote_signal":("پیش" in raw and "فاکتور" in raw),"public_probe":pub(o.get("link") or f"{BASE}/{slug}/")}
    except Exception as e:
        tools[name]={"id":pid,"error":type(e).__name__}

store={}
try:
    r=requests.get(BASE+"/wp-json/wc/store/v1/products",params={"per_page":2},timeout=60,headers={"User-Agent":"k20-seogod1-phase8-10/1.0"})
    body=r.json() if r.ok else None
    store={"ok":r.ok and isinstance(body,list),"http":r.status_code,"items":len(body) if isinstance(body,list) else 0}
except Exception as e:
    store={"ok":False,"error":type(e).__name__}

comp=pim.get("compatibility") or {}
verified=comp.get("verified_edges") or []
candidate=comp.get("candidate_edges") or []
p9={
 "nodes":len(pim.get("records") or []),
 "verified_edges":len(verified),
 "candidate_only_edges":len(candidate),
 "verified_edge_records":verified,
 "rule":"Only evidence-backed edges are promotable. Same-size/title candidates are not compatibility claims.",
 "complete_basket_policy":"Quantities can be calculated from explicit user geometry. Exact filter/mainline/connection recommendations require verified project + product data."
}

out={
 "program":"SEO God1","phases":[8,9,10],"generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "source_freshness":{"gsc_generated_at":gsc.get("generated_at"),"gsc_settled_through":(gsc.get("queries") or {}).get("settledThrough"),"note":"GSC snapshot is the latest repo-backed first-party baseline used; do not represent it as live beyond settledThrough."},
 "phase08":{"status":"executed","commercial_queries":rows[:120],"top_by_impressions":rows[:30],"owner_rule_count":len(owner_rules)},
 "phase09":{"status":"executed_guarded",**p9},
 "phase10":{"status":"executed_guarded","calculator":calculator,"tools":tools,"store_api":store,
   "flow_gate":{"calculator_found":bool(calculator.get("found")),"basket_public":tools.get("basket",{}).get("status")=="publish" and tools.get("basket",{}).get("public_probe",{}).get("http")==200,"comparator_public":tools.get("comparator",{}).get("status")=="publish" and tools.get("comparator",{}).get("public_probe",{}).get("http")==200,"store_api_ok":bool(store.get("ok"))}}
}
os.makedirs("seo-god1-results",exist_ok=True)
with open("seo-god1-results/phase08-10-live-execution.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print("SEO_GOD1_PHASE8_10_OK",json.dumps({"money_queries":len(rows),"verified_edges":len(verified),"candidate_edges":len(candidate),"calculator":calculator,"tools":{k:v.get("status") for k,v in tools.items()},"store":store},ensure_ascii=False))
