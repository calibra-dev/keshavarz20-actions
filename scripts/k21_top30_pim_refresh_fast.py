#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures, datetime, html, json, os, re
from pathlib import Path
from urllib.parse import urljoin
import requests

ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
HEAD={"Accept":"application/json","User-Agent":"k21-top30-fast-pim/1.0","Cache-Control":"no-cache"}

REQ={
 "valve":["nominal_size","connection_type","pressure_class"],
 "fitting":["nominal_size","connection_type","material","pressure_class"],
 "layflat_rain":["nominal_size","length","connection_type","pressure_class"],
 "drip_tape":["nominal_size","length","emitter_spacing","filtration_requirement"],
 "filter":["connection_size","flow_rate","filtration_grade"],
 "fertigation":["capacity","connection_size","pressure_requirement"],
 "other_irrigation":["nominal_size","connection_type"]
}
ALIASES={"connection_size":"nominal_size","pressure_requirement":"pressure_class","filtration_requirement":"filtration_grade"}

def textify(v):
    v=html.unescape(v or "")
    v=re.sub(r"<script\b[^>]*>.*?</script>"," ",v,flags=re.I|re.S)
    v=re.sub(r"<style\b[^>]*>.*?</style>"," ",v,flags=re.I|re.S)
    v=re.sub(r"<[^>]+>"," ",v)
    return re.sub(r"\s+"," ",v).strip()

def amap(p):
    out={}
    for a in p.get("attributes") or []:
        n=(a.get("name") or "").strip().lower()
        vals=a.get("options") or []
        if n and vals: out[n]={"value":"، ".join(str(x) for x in vals),"source":"woocommerce_attribute","confidence":"high"}
    return out

def find_attr(attrs,names):
    for want in names:
        wl=want.lower()
        for k,v in attrs.items():
            if wl in k: return v
    return None

def fetch(pid):
    r=requests.get(urljoin(BASE,f"wp-json/wc/v3/products/{pid}"),auth=AUTH,headers=HEAD,timeout=45)
    r.raise_for_status(); return pid,r.json()

old=json.loads((ROOT/"phase3-results/top30-pim.json").read_text(encoding="utf-8"))
pq={}
try:
    q=json.loads((ROOT/"phase2-results/product-quality-score.json").read_text(encoding="utf-8"))
    pq={int(x["id"]):x for x in q.get("products",[]) if x.get("id")}
except Exception: pass

base_rows=old.get("products",[])
ids=[int(x["product_id"]) for x in base_rows]
live={}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    for pid,p in ex.map(lambda x:fetch(x),ids): live[pid]=p

rows=[]
for oldrow in base_rows:
    pid=int(oldrow["product_id"]); p=live[pid]; attrs=amap(p); family=oldrow["family"]
    desc=p.get("description") or ""; short=p.get("short_description") or ""
    plain=textify(desc); splain=textify(short)
    brands=p.get("brands") or []
    brand=None
    if brands:
        names=[b.get("name") for b in brands if b.get("name")]
        if names: brand={"value":"، ".join(names),"source":"woocommerce_brand","confidence":"high"}
    if not brand: brand=find_attr(attrs,["brand","برند","سازنده"])
    mpn=find_attr(attrs,["mpn","کد سازنده","part number","شماره قطعه"])
    model=find_attr(attrs,["model","مدل"])
    size=find_attr(attrs,["سایز","اندازه","قطر","size","diameter"])
    material=find_attr(attrs,["جنس","material"])
    pressure=find_attr(attrs,["فشار","pressure","pn","sdr"])
    length=find_attr(attrs,["طول","length"])
    capacity=find_attr(attrs,["ظرفیت","capacity"])
    connection=find_attr(attrs,["اتصال","رزوه","connection"])
    flow=find_attr(attrs,["دبی","flow"])
    filtration=find_attr(attrs,["میکرون","mesh","مش","filtration"])
    emitter=find_attr(attrs,["فاصله قطره","فاصله خروجی","emitter"])
    gtin=(p.get("global_unique_id") or "").strip() if isinstance(p.get("global_unique_id"),str) else ""
    imgs=p.get("images") or []; alt_ok=bool(imgs) and all(bool((i.get("alt") or "").strip()) for i in imgs)
    links=oldrow.get("decision_links") or []
    current=(desc+" "+short).lower()
    has_links=bool(links) and any((l.get("url") or "").lower() in current for l in links)
    fields={"brand":brand,"mpn":mpn,"model":model,"nominal_size":size,"material":material,"pressure_class":pressure,
            "length":length,"capacity":capacity,"connection_type":connection,"flow_rate":flow,
            "filtration_grade":filtration,"emitter_spacing":emitter}
    req=REQ.get(family,[]); missing=[k for k in req if not fields.get(ALIASES.get(k,k))]
    tech_count=sum(1 for z in [size,material,pressure,length,capacity,connection,flow,filtration,emitter,model] if z)
    score=10+10*(bool((p.get("sku") or "").strip()))+10*bool(gtin)+5*bool(mpn)+5*bool(brand)+min(15,tech_count*5)
    score+=10 if len(splain.split())>=20 else (5 if splain else 0)
    score+=10 if len(plain.split())>=120 else (5 if plain else 0)
    score+=10 if len(imgs)>=4 else (5 if imgs else 0)
    score+=5 if alt_ok else 0
    score+=5 if has_links else 0
    score+=5 if p.get("stock_status") in ("instock","outofstock","onbackorder") else 0
    gaps=[]
    if not (p.get("sku") or "").strip(): gaps.append("missing_sku")
    if not gtin:gaps.append("missing_gtin")
    if not mpn:gaps.append("missing_mpn")
    if not brand:gaps.append("missing_brand")
    if missing:gaps.append("compatibility_fields_incomplete")
    if len(splain.split())<20:gaps.append("decision_summary_weak")
    if len(plain.split())<120:gaps.append("long_description_weak")
    if len(imgs)<4 or not alt_ok:gaps.append("image_set_incomplete")
    if not has_links:gaps.append("decision_link_missing")
    nr={**oldrow,
       "name":p.get("name"),"permalink":p.get("permalink"),"stock_status":p.get("stock_status"),
       "stable_identifiers":{"wp_product_id":{"value":pid,"confidence":"high"},
         "sku":{"value":p.get("sku") or None,"confidence":"high" if (p.get("sku") or "").strip() else "missing","proposed_if_blank":f"K20-{pid}"},
         "gtin":{"value":gtin or None,"confidence":"high" if gtin else "missing"},"mpn":mpn},
       "pim_fields":fields,"compatibility_required_fields":req,"compatibility_missing_fields":missing,
       "decision_links_present":has_links,
       "content":{"short_words":len(splain.split()),"description_words":len(plain.split()),"image_count":len(imgs),"all_image_alt_present":alt_ok},
       "pim_completeness_score":int(score),
       "product_quality_score":(pq.get(pid) or {}).get("score"),
       "product_quality_gaps":(pq.get(pid) or {}).get("gaps",[]),
       "gaps":gaps}
    rows.append(nr)

summary={
 "selected":len(rows),
 "mapped_candidates":old.get("summary",{}).get("mapped_candidates",len(rows)),
 "unmapped_candidates":old.get("summary",{}).get("unmapped_candidates",0),
 "average_pim_completeness":round(sum(x["pim_completeness_score"] for x in rows)/len(rows),2),
 "scores_85_plus":sum(x["pim_completeness_score"]>=85 for x in rows),
 "missing_sku":sum("missing_sku" in x["gaps"] for x in rows),
 "missing_gtin":sum("missing_gtin" in x["gaps"] for x in rows),
 "missing_mpn":sum("missing_mpn" in x["gaps"] for x in rows),
 "missing_brand":sum("missing_brand" in x["gaps"] for x in rows),
 "compatibility_incomplete":sum(bool(x["compatibility_missing_fields"]) for x in rows),
 "decision_link_missing":sum("decision_link_missing" in x["gaps"] for x in rows),
 "average_product_quality_score":round(sum((x.get("product_quality_score") or 0) for x in rows)/len(rows),2),
 "product_quality_below_85":sum((x.get("product_quality_score") or 0)<85 for x in rows)
}
out={**old,"ok":True,"version":"phase3-top30-pim-fast-v1","generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"summary":summary,"products":rows}
(ROOT/"phase3-results/top30-pim.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print("K21_FAST_PIM_OK",json.dumps(summary,ensure_ascii=False))
