#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, time
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-brand-assignment/1.0","Cache-Control":"no-cache"})

REG=Path("growthos-phase15-results/brand-entity-registry.json")
OUT=Path("brand-assignment-results/apply-all-158.json")

def req(method,path,**kwargs):
    for attempt in range(1,6):
        try:
            r=S.request(method,BASE+path,timeout=90,**kwargs)
            if r.status_code in (429,500,502,503,504):
                time.sleep(attempt*1.5); continue
            if not r.ok:
                raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:700]}")
            return r.json()
        except requests.RequestException:
            if attempt==5: raise
            time.sleep(attempt*1.5)
    raise RuntimeError("request retry exhausted")

def norm(v):
    s=str(v or "").strip().casefold().replace("\u200c"," ").replace("\u200f"," ")
    s=re.sub(r"\([^)]*\)","",s)
    s=re.sub(r"[^0-9a-zآ-ی]+","",s)
    return s

def all_terms():
    rows=[]
    for page in range(1,20):
        got=req("GET","/wp-json/wp/v2/product_brand",params={"per_page":100,"page":page,"context":"edit"})
        if not got: break
        rows.extend(got)
        if len(got)<100: break
    return rows

def product(pid):
    return req("GET",f"/wp-json/wp/v2/product/{pid}",params={"context":"edit"})

data=json.loads(REG.read_text(encoding="utf-8"))
unbranded=data.get("unbranded_products") or []
if len(unbranded)!=158:
    raise SystemExit(f"Expected 158 source rows, got {len(unbranded)}")
ids=[int(x["product_id"]) for x in unbranded]
if len(set(ids))!=158:
    raise SystemExit("Duplicate product IDs in source list")

# User-confirmed row mapping, 1-based.
row_brand={}
def set_range(a,b,brand):
    for i in range(a,b+1):
        if i in row_brand: raise RuntimeError(f"row {i} assigned twice")
        row_brand[i]=brand
def set_rows(rows,brand):
    for i in rows:
        if i in row_brand: raise RuntimeError(f"row {i} assigned twice")
        row_brand[i]=brand

set_range(1,8,"پلیمر پارس"); set_rows([100],"پلیمر پارس")
set_range(9,51,"متفرقه"); set_rows([56,97],"متفرقه"); set_range(101,103,"متفرقه"); set_range(105,125,"متفرقه"); set_range(152,154,"متفرقه"); set_range(156,158,"متفرقه")
set_range(52,55,"زلال رود"); set_rows([99],"زلال رود")
set_range(57,85,"بنیز")
set_range(86,88,"تک ستاره نگین گلپایگان"); set_range(94,96,"تک ستاره نگین گلپایگان")
set_range(89,93,"ویسپار")
set_rows([98,104],"باران"); set_range(137,139,"باران")
set_range(126,127,"باغبان تاک")
set_range(128,136,"سازگان شیمی"); set_rows([140,141],"سازگان شیمی")
set_rows([142,150,151],"فلایژن")
set_range(143,149,"کمل")
set_rows([155],"ایکس گرین")

if set(row_brand)!=set(range(1,159)):
    missing=sorted(set(range(1,159))-set(row_brand)); extra=sorted(set(row_brand)-set(range(1,159)))
    raise SystemExit(f"Mapping coverage error missing={missing} extra={extra}")

expected_counts={}
for b in row_brand.values(): expected_counts[b]=expected_counts.get(b,0)+1
if sum(expected_counts.values())!=158:
    raise SystemExit("Mapping total is not 158")

terms=all_terms()
by_norm={}
for t in terms:
    by_norm.setdefault(norm(t.get("name")),[]).append(t)

# Reuse canonical existing bilingual terms for these known brands.
aliases={
 "ویسپار":["ویسپار","ویسپار (Vispar)"],
 "باران":["باران","باران (baran)"],
 "فلایژن":["فلایژن","فلایژن (FLYGEN)"],
 "ایکس گرین":["ایکس گرین","ایکس گرین (XGreen)"],
}
requested=sorted(set(row_brand.values()))
brand_terms={}
created=[]
reused=[]

for brand in requested:
    candidates=[]
    lookup_names=aliases.get(brand,[brand])
    for name in lookup_names:
        candidates.extend(by_norm.get(norm(name),[]))
    # Deduplicate term IDs.
    uniq={int(x["id"]):x for x in candidates}
    candidates=list(uniq.values())
    if len(candidates)>1:
        raise SystemExit(f"Ambiguous brand term for {brand}: {[(x['id'],x['name']) for x in candidates]}")
    if len(candidates)==1:
        t=candidates[0]
        brand_terms[brand]={"id":int(t["id"]),"name":t.get("name"),"created":False}
        reused.append({"requested":brand,"id":int(t["id"]),"name":t.get("name")})
        continue
    # Create exact requested brand name. If WordPress reports term_exists,
    # reuse that exact existing term instead of creating a duplicate.
    rr=S.post(BASE+"/wp-json/wp/v2/product_brand",json={"name":brand},timeout=90)
    if rr.ok:
        t=rr.json()
        brand_terms[brand]={"id":int(t["id"]),"name":t.get("name"),"created":True}
        created.append({"requested":brand,"id":int(t["id"]),"name":t.get("name")})
        by_norm.setdefault(norm(t.get("name")),[]).append(t)
    elif rr.status_code==400:
        err=rr.json()
        if err.get("code")!="term_exists":
            raise RuntimeError(f"POST product_brand {brand} -> {rr.status_code}: {rr.text[:700]}")
        term_id=int(((err.get("data") or {}).get("term_id")) or (err.get("additional_data") or [0])[0])
        if not term_id:
            raise RuntimeError(f"term_exists without term_id for {brand}")
        t=req("GET",f"/wp-json/wp/v2/product_brand/{term_id}",params={"context":"edit"})
        brand_terms[brand]={"id":term_id,"name":t.get("name"),"created":False}
        reused.append({"requested":brand,"id":term_id,"name":t.get("name"),"source":"term_exists"})
        by_norm.setdefault(norm(t.get("name")),[]).append(t)
    else:
        raise RuntimeError(f"POST product_brand {brand} -> {rr.status_code}: {rr.text[:700]}")

results=[]
failures=[]
for row in range(1,159):
    pid=ids[row-1]
    title=unbranded[row-1].get("title")
    brand=row_brand[row]
    term_id=brand_terms[brand]["id"]
    try:
        before=product(pid)
        current=[int(x) for x in (before.get("product_brand") or [])]
        if current==[term_id]:
            action="already_correct"
        elif current:
            raise RuntimeError(f"refusing overwrite; current product_brand={current}, expected={term_id}")
        else:
            req("POST",f"/wp-json/wp/v2/product/{pid}",json={"product_brand":[term_id]})
            action="assigned"
        after=product(pid)
        actual=[int(x) for x in (after.get("product_brand") or [])]
        ok=(actual==[term_id])
        rec={"row":row,"product_id":pid,"title":title,"requested_brand":brand,"brand_term_id":term_id,"action":action,"verified_product_brand":actual,"ok":ok}
        results.append(rec)
        if not ok: failures.append(rec)
    except Exception as exc:
        rec={"row":row,"product_id":pid,"title":title,"requested_brand":brand,"brand_term_id":term_id,"ok":False,"error":str(exc)[:700]}
        results.append(rec); failures.append(rec)

report={
 "ok":not failures,
 "source_count":158,
 "mapping_count":len(row_brand),
 "expected_counts":expected_counts,
 "brand_terms":brand_terms,
 "created_terms":created,
 "reused_terms":reused,
 "assigned_or_already_correct":sum(1 for x in results if x.get("ok")),
 "failures":failures,
 "results":results,
 "safety":{
   "only_product_field_written":"product_brand",
   "price_changed":False,"stock_changed":False,"categories_changed":False,
   "content_changed":False,"sku_changed":False
 }
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
 "ok":report["ok"],"verified":report["assigned_or_already_correct"],
 "created_terms":created,"reused_terms":reused,"failures":len(failures),
 "counts":expected_counts
},ensure_ascii=False))
if failures: raise SystemExit(2)
