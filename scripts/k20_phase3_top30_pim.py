#!/usr/bin/env python3
import json, os, re, html, math, sys
from collections import defaultdict
from urllib.parse import urljoin, urlparse, unquote
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase3-pim/1.0","Cache-Control":"no-cache"})

def paged(path, params=None, cap=20):
    out=[]; params=dict(params or {})
    for page in range(1,cap+1):
        p=dict(params); p.update({"per_page":100,"page":page})
        r=S.get(urljoin(BASE,path.lstrip("/")),params=p,timeout=120)
        if r.status_code==400 and page>1: break
        r.raise_for_status()
        rows=r.json()
        if not isinstance(rows,list) or not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

def textify(v):
    v=html.unescape(v or "")
    v=re.sub(r"<script\b[^>]*>.*?</script>"," ",v,flags=re.I|re.S)
    v=re.sub(r"<style\b[^>]*>.*?</style>"," ",v,flags=re.I|re.S)
    v=re.sub(r"<[^>]+>"," ",v)
    return re.sub(r"\s+"," ",v).strip()

def norm_url(u):
    p=urlparse(u or "")
    path=unquote(p.path or "/").rstrip("/")+"/"
    return (p.scheme.lower(),p.netloc.lower(),path.lower())

def attr_map(p):
    out={}
    for a in p.get("attributes") or []:
        name=(a.get("name") or "").strip()
        opts=a.get("options") or []
        if name: out[name]="، ".join(str(x) for x in opts if str(x).strip())
    return out

def find_attr(attrs, needles):
    for k,v in attrs.items():
        kl=k.lower()
        if any(n in kl for n in needles) and str(v).strip():
            return {"value":v,"source":"woocommerce_attribute","field":k,"confidence":"high"}
    return None

def classify(p):
    t=((p.get("name") or "")+" "+" ".join((c.get("name") or "") for c in p.get("categories") or [])).lower()
    if any(x in t for x in ["فیلتر","هیدروسیکلون"]): return "filter"
    if any(x in t for x in ["نخدار","لی فلت","لی‌فلت","مه پاش","بارانی"]): return "layflat_rain"
    if any(x in t for x in ["نوار تیپ","نوار آبیاری","تیپ به تیپ"]): return "drip_tape"
    if any(x in t for x in ["مخزن تزریق کود","تانک کود"]): return "fertigation"
    if any(x in t for x in ["شیر توپی","شیرتوپی","شیر پروانه","شیر ویفری","شیر انشعاب","سوپاپ"]): return "valve"
    if any(x in t for x in ["رابط","زانو","سه راه","سه‌راه","فلنج","فلنچ","کمربند","درپوش","بوشن","تبدیل","سر شلنگ","سر شيلنگ"]): return "fitting"
    return "other_irrigation"

DECISION_LINKS={
 "valve":[
   {"label":"راهنمای خرید شیرآلات آبیاری","url":"https://keshavarz20.com/irrigation-valves-buying-guide/"},
   {"label":"راهنمای سازگاری و سبد اتصالات","url":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/"}],
 "fitting":[
   {"label":"راهنمای اتصالات پلی‌اتیلن","url":"https://keshavarz20.com/polyethylene-compression-fittings-guide/"},
   {"label":"راهنمای سازگاری و سبد اتصالات","url":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/"}],
 "layflat_rain":[
   {"label":"راهنمای سایز لی‌فلت و نخدار","url":"https://keshavarz20.com/layflat-hose-size-inch-mm-guide/"},
   {"label":"ماشین حساب لی‌فلت و اتصالات","url":"https://keshavarz20.com/layflat-length-fittings-calculator/"}],
 "drip_tape":[
   {"label":"راهنمای خرید نوار تیپ","url":"https://keshavarz20.com/drip-tape-buying-guide/"},
   {"label":"محاسبه متراژ نوار تیپ و اتصالات","url":"https://keshavarz20.com/drip-tape-length-fittings-calculator/"}],
 "filter":[
   {"label":"راهنمای انتخاب فیلتر آبیاری","url":"https://keshavarz20.com/irrigation-filter-selection-guide/"},
   {"label":"انتخاب‌گر فیلتر آبیاری","url":"https://keshavarz20.com/irrigation-filter-selector/"}],
 "fertigation":[
   {"label":"راهنمای طراحی و خرید تجهیزات آبیاری قطره‌ای","url":"https://keshavarz20.com/complete-drip-irrigation-system-guide/"},
   {"label":"انتخاب‌گر فیلتر آبیاری","url":"https://keshavarz20.com/irrigation-filter-selector/"}],
 "other_irrigation":[
   {"label":"راهنمای طراحی و خرید تجهیزات آبیاری قطره‌ای","url":"https://keshavarz20.com/complete-drip-irrigation-system-guide/"}]
}
REQ={
 "valve":["nominal_size","connection_type","pressure_class"],
 "fitting":["nominal_size","connection_type","material","pressure_class"],
 "layflat_rain":["nominal_size","length","connection_type","pressure_class"],
 "drip_tape":["nominal_size","length","emitter_spacing","filtration_requirement"],
 "filter":["connection_size","flow_rate","filtration_grade"],
 "fertigation":["capacity","connection_size","pressure_requirement"],
 "other_irrigation":["nominal_size","connection_type"]
}

snap=json.load(open("phase3/gsc-irrigation-product-candidates.json",encoding="utf-8"))
quality_map={}
try:
    q=json.load(open("phase2-results/product-quality-score.json",encoding="utf-8"))
    quality_map={int(x.get("id")):x for x in q.get("products",[]) if x.get("id")}
except Exception:
    quality_map={}
products=paged("wp-json/wc/v3/products",{"status":"publish"})
by_url={norm_url(p.get("permalink")):p for p in products}

rows=[]
unmapped=[]
for g in snap["candidates"]:
    p=by_url.get(norm_url(g["url"]))
    if not p:
        unmapped.append(g); continue
    family=classify(p)
    stock=p.get("stock_status") or ""
    priority=(int(g.get("clicks") or 0)*1000)+(int(g.get("impressions") or 0))
    if stock=="instock": priority+=100
    elif stock=="outofstock": priority-=5000
    if family in ("drip_tape","filter","layflat_rain"): priority+=50
    rows.append({"gsc":g,"product":p,"family":family,"priority":priority})

rows.sort(key=lambda x:(x["priority"],x["gsc"].get("clicks",0),x["gsc"].get("impressions",0)),reverse=True)
selected=rows[:30]
selected_ids={x["product"]["id"] for x in selected}
selected_urls={norm_url(x["product"].get("permalink")):x["product"]["id"] for x in selected}

pim=[]
explicit_edges=[]
by_size=defaultdict(list)
for rank,x in enumerate(selected,1):
    p=x["product"]; attrs=attr_map(p); family=x["family"]
    desc=p.get("description") or ""; short=p.get("short_description") or ""
    plain=textify(desc); splain=textify(short)
    brand=None
    brands=p.get("brands") or []
    if brands:
        brand={"value":"، ".join((b.get("name") or "") for b in brands if b.get("name")),"source":"woocommerce_brand","confidence":"high"}
    if not brand: brand=find_attr(attrs,["brand","برند","سازنده"])
    mpn=find_attr(attrs,["mpn","کد سازنده","part number","شماره قطعه"])
    model=find_attr(attrs,["model","مدل"])
    size=find_attr(attrs,["سایز","اندازه","قطر","size","diameter"])
    material=find_attr(attrs,["جنس","material"])
    pressure=find_attr(attrs,["فشار کاری","کلاس فشار","pressure","pn","sdr"])
    pressure_requirement=find_attr(attrs,["الزام فشار","نیاز فشار","pressure requirement"])
    length=find_attr(attrs,["طول","length"])
    capacity=find_attr(attrs,["ظرفیت","capacity"])
    connection=find_attr(attrs,["اتصال","رزوه","connection"])
    flow=find_attr(attrs,["دبی","flow"])
    filtration=find_attr(attrs,["میکرون","mesh","مش","filtration grade"])
    filtration_requirement=find_attr(attrs,["فیلتراسیون","الزام فیلتراسیون","نیاز فیلتراسیون","filtration requirement"])
    emitter=find_attr(attrs,["فاصله قطره","فاصله خروجی","emitter"])
    gtin=(p.get("global_unique_id") or "").strip() if isinstance(p.get("global_unique_id"),str) else ""
    imgs=p.get("images") or []
    alt_ok=bool(imgs) and all(bool((i.get("alt") or "").strip()) for i in imgs)
    links=DECISION_LINKS.get(family,DECISION_LINKS["other_irrigation"])
    current_all=(desc+" "+short).lower()
    has_decision_link=any(l["url"].lower() in current_all for l in links)
    tech=[size,material,pressure,pressure_requirement,length,capacity,connection,flow,filtration,filtration_requirement,emitter,model]
    tech_count=sum(1 for z in tech if z)
    score=0
    score+=10
    score+=10 if (p.get("sku") or "").strip() else 0
    score+=10 if gtin else 0
    score+=5 if mpn else 0
    score+=5 if brand else 0
    score+=min(15,tech_count*5)
    score+=10 if len(splain.split())>=20 else (5 if splain else 0)
    score+=10 if len(plain.split())>=120 else (5 if plain else 0)
    score+=10 if len(imgs)>=4 else (5 if imgs else 0)
    score+=5 if alt_ok else 0
    score+=5 if has_decision_link else 0
    score+=5 if stock in ("instock","outofstock","onbackorder") else 0
    extracted={
      "brand":brand,"mpn":mpn,"model":model,"nominal_size":size,"material":material,
      "pressure_class":pressure,"pressure_requirement":pressure_requirement,
      "length":length,"capacity":capacity,"connection_type":connection,
      "flow_rate":flow,"filtration_grade":filtration,"filtration_requirement":filtration_requirement,
      "emitter_spacing":emitter
    }
    req=REQ.get(family,[])
    missing=[]
    aliases={"connection_size":"nominal_size"}
    for k in req:
        kk=aliases.get(k,k)
        if not extracted.get(kk): missing.append(k)
    # Explicit product-to-product links only. No inferred compatibility is promoted to verified.
    for m in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+',desc+" "+short,re.I):
        target=selected_urls.get(norm_url(m))
        if target and target!=p["id"]:
            explicit_edges.append({"source_product_id":p["id"],"target_product_id":target,"relation":"explicit_internal_reference","confidence":"high","evidence_url":p.get("permalink")})
    # Title size tokens are candidate-only and never treated as verified compatibility.
    title=p.get("name") or ""
    tokens=sorted(set(re.findall(r'(?<!\d)(\d+(?:[./]\d+)?\s*(?:اینچ|میلی ?متر|mm|inch))(?!\d)',title,re.I)))
    for tok in tokens: by_size[tok.lower()].append(p["id"])
    gaps=[]
    if not (p.get("sku") or "").strip(): gaps.append("missing_sku")
    if not gtin: gaps.append("missing_gtin")
    if not mpn: gaps.append("missing_mpn")
    if not brand: gaps.append("missing_brand")
    if missing: gaps.append("compatibility_fields_incomplete")
    if len(splain.split())<20: gaps.append("decision_summary_weak")
    if len(plain.split())<120: gaps.append("long_description_weak")
    if len(imgs)<4 or not alt_ok: gaps.append("image_set_incomplete")
    if not has_decision_link: gaps.append("decision_link_missing")
    pim.append({
      "rank":rank,"product_id":p["id"],"name":p.get("name"),"permalink":p.get("permalink"),
      "family":family,"stock_status":stock,
      "gsc":x["gsc"],"priority_score":x["priority"],
      "stable_identifiers":{
        "wp_product_id":{"value":p["id"],"confidence":"high"},
        "sku":{"value":p.get("sku") or None,"confidence":"high" if (p.get("sku") or "").strip() else "missing",
               "proposed_if_blank":f"K20-{p['id']}"},
        "gtin":{"value":gtin or None,"confidence":"high" if gtin else "missing"},
        "mpn":mpn
      },
      "pim_fields":extracted,
      "compatibility_required_fields":req,
      "compatibility_missing_fields":missing,
      "decision_links":links,"decision_links_present":has_decision_link,
      "content":{"short_words":len(splain.split()),"description_words":len(plain.split()),"image_count":len(imgs),"all_image_alt_present":alt_ok},
      "pim_completeness_score":score,
      "product_quality_score":(quality_map.get(int(p["id"])) or {}).get("score"),
      "product_quality_gaps":(quality_map.get(int(p["id"])) or {}).get("gaps",[]),
      "gaps":gaps
    })

candidate_edges=[]
for token,ids in by_size.items():
    if len(ids)>1:
        for i in range(len(ids)):
            for j in range(i+1,len(ids)):
                candidate_edges.append({"a":ids[i],"b":ids[j],"relation":"same_title_size_token_candidate","size_token":token,
                                        "confidence":"candidate_only","warning":"Same nominal size does not prove compatibility; connection standard/material/pressure must be verified."})

avg=round(sum(x["pim_completeness_score"] for x in pim)/len(pim),2) if pim else 0
summary={
 "selected":len(pim),"mapped_candidates":len(rows),"unmapped_candidates":len(unmapped),
 "average_pim_completeness":avg,
 "scores_85_plus":sum(1 for x in pim if x["pim_completeness_score"]>=85),
 "missing_sku":sum(1 for x in pim if "missing_sku" in x["gaps"]),
 "missing_gtin":sum(1 for x in pim if "missing_gtin" in x["gaps"]),
 "missing_mpn":sum(1 for x in pim if "missing_mpn" in x["gaps"]),
 "missing_brand":sum(1 for x in pim if "missing_brand" in x["gaps"]),
 "compatibility_incomplete":sum(1 for x in pim if x["compatibility_missing_fields"]),
 "decision_link_missing":sum(1 for x in pim if "decision_link_missing" in x["gaps"]),
 "average_product_quality_score":round(sum(x["product_quality_score"] for x in pim if isinstance(x.get("product_quality_score"),(int,float))) / max(1,sum(1 for x in pim if isinstance(x.get("product_quality_score"),(int,float)))),2),
 "product_quality_below_85":sum(1 for x in pim if isinstance(x.get("product_quality_score"),(int,float)) and x["product_quality_score"]<85)
}

owner={
 "missing_sku":"catalog","missing_gtin":"catalog+supplier","missing_mpn":"catalog+supplier","missing_brand":"catalog",
 "compatibility_fields_incomplete":"technical-data","decision_summary_weak":"content","long_description_weak":"content",
 "image_set_incomplete":"media","decision_link_missing":"content+internal-linking"
}
rem=[]
for x in pim:
    for g in x["gaps"]:
        rem.append({"product_id":x["product_id"],"rank":x["rank"],"gap":g,"owner":owner[g],
                    "deadline":"2026-10-18" if x["rank"]<=10 else ("2026-11-01" if x["rank"]<=20 else "2026-11-17"),
                    "write_policy":"Never invent GTIN/MPN/brand/technical specs. SKU may use proposed K20-{id} only after uniqueness check."})

os.makedirs("phase3-results",exist_ok=True)
json.dump({"ok":True,"mode":"read-only","version":"phase3-top30-pim-v2","generated_at_utc":__import__("datetime").datetime.utcnow().isoformat()+"Z",
           "selection_rule":"GSC irrigation/fertigation candidate cohort; published Woo products; organic demand dominates priority; in-stock bonus; out-of-stock penalty. This is commercial-priority, not a profit/margin claim.",
           "summary":summary,"products":pim,"unmapped_candidates":unmapped},
          open("phase3-results/top30-pim.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
json.dump({"ok":True,"version":"phase3-compatibility-graph-v1","nodes":[{"product_id":x["product_id"],"name":x["name"],"family":x["family"],"required_fields":x["compatibility_required_fields"],"missing_fields":x["compatibility_missing_fields"]} for x in pim],
           "verified_edges":explicit_edges,"candidate_edges":candidate_edges,
           "policy":"Only explicit evidence is verified. Same-size candidate edges are never presented as compatible without connection/material/pressure verification."},
          open("phase3-results/compatibility-graph.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
json.dump({"ok":True,"version":"phase3-top30-remediation-v1","summary":summary,"actions":rem},
          open("phase3-results/top30-remediation.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_TOP30_PIM_OK",summary)
