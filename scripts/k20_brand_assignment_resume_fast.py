#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
REG=Path("growthos-phase15-results/brand-entity-registry.json")
OUT=Path("brand-assignment-results/resume-fast-158.json")
TLS=threading.local()

def session():
    if not hasattr(TLS,"s"):
        s=requests.Session(); s.auth=AUTH
        s.headers.update({"Accept":"application/json","User-Agent":"k20-brand-resume-fast/1.0","Cache-Control":"no-cache"})
        TLS.s=s
    return TLS.s

def call(method,path,**kwargs):
    last=None
    for attempt in range(1,5):
        try:
            r=session().request(method,BASE+path,timeout=45,**kwargs)
            if r.status_code in (429,500,502,503,504):
                last=f"{r.status_code} {r.text[:200]}"; time.sleep(attempt); continue
            if not r.ok:
                raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
            try: return r.json()
            except Exception:
                last=f"non-json success {r.status_code}"; time.sleep(0.8); continue
        except requests.RequestException as e:
            last=str(e); time.sleep(attempt)
    raise RuntimeError(f"{method} {path} failed after retries: {last}")

def norm(v):
    s=str(v or "").strip().casefold().replace("\u200c"," ").replace("\u200f"," ")
    s=re.sub(r"\([^)]*\)","",s)
    s=re.sub(r"[^0-9a-zآ-ی]+","",s)
    return s

def all_terms():
    s=requests.Session(); s.auth=AUTH
    out=[]
    for page in range(1,10):
        r=s.get(BASE+"/wp-json/wp/v2/product_brand",params={"per_page":100,"page":page,"context":"edit"},timeout=45)
        if r.status_code==400 and page>1: break
        r.raise_for_status()
        got=r.json()
        out.extend(got)
        if len(got)<100: break
    return out

data=json.loads(REG.read_text(encoding="utf-8"))
src=data.get("unbranded_products") or []
if len(src)!=158: raise SystemExit(f"source list expected 158 got {len(src)}")
ids=[int(x["product_id"]) for x in src]

row_brand={}
def R(a,b,bn):
    for i in range(a,b+1): row_brand[i]=bn
def X(rows,bn):
    for i in rows: row_brand[i]=bn
R(1,8,"پلیمر پارس"); X([100],"پلیمر پارس")
R(9,51,"متفرقه"); X([56,97],"متفرقه"); R(101,103,"متفرقه"); R(105,125,"متفرقه"); R(152,154,"متفرقه"); R(156,158,"متفرقه")
R(52,55,"زلال رود"); X([99],"زلال رود")
R(57,85,"بنیز")
R(86,88,"تک ستاره نگین گلپایگان"); R(94,96,"تک ستاره نگین گلپایگان")
R(89,93,"ویسپار")
X([98,104],"باران"); R(137,139,"باران")
R(126,127,"باغبان تاک")
R(128,136,"سازگان شیمی"); X([140,141],"سازگان شیمی")
X([142,150,151],"فلایژن")
R(143,149,"کمل")
X([155],"ایکس گرین")
if set(row_brand)!=set(range(1,159)): raise SystemExit("mapping coverage error")

aliases={
 "ویسپار":["ویسپار","ویسپار (Vispar)"],
 "باران":["باران","باران (baran)"],
 "فلایژن":["فلایژن","فلایژن (FLYGEN)"],
 "ایکس گرین":["ایکس گرین","ایکس گرین (XGreen)"],
}
terms=all_terms()
by_norm={}
for t in terms: by_norm.setdefault(norm(t.get("name")),[]).append(t)
brand_terms={}
for brand in sorted(set(row_brand.values())):
    names=aliases.get(brand,[brand])
    found={}
    for nm in names:
        for t in by_norm.get(norm(nm),[]): found[int(t["id"])]=t
    if len(found)!=1:
        raise SystemExit(f"brand term resolution failed for {brand}: {[(x.get('id'),x.get('name')) for x in found.values()]}")
    t=list(found.values())[0]
    brand_terms[brand]={"id":int(t["id"]),"name":t.get("name")}

def worker(row):
    pid=ids[row-1]; brand=row_brand[row]; tid=brand_terms[brand]["id"]
    before=call("GET",f"/wp-json/wp/v2/product/{pid}",params={"context":"edit"})
    current=[int(x) for x in (before.get("product_brand") or [])]
    if current==[tid]:
        action="already_correct"
    elif current:
        return {"row":row,"product_id":pid,"brand":brand,"term_id":tid,"ok":False,"error":f"unexpected existing product_brand={current}"}
    else:
        call("POST",f"/wp-json/wp/v2/product/{pid}",json={"product_brand":[tid]})
        action="assigned"
    after=call("GET",f"/wp-json/wp/v2/product/{pid}",params={"context":"edit"})
    actual=[int(x) for x in (after.get("product_brand") or [])]
    return {"row":row,"product_id":pid,"brand":brand,"term_id":tid,"action":action,"actual":actual,"ok":actual==[tid]}

results=[]
with ThreadPoolExecutor(max_workers=6) as ex:
    futs={ex.submit(worker,row):row for row in range(1,159)}
    for fut in as_completed(futs):
        row=futs[fut]
        try: results.append(fut.result())
        except Exception as e: results.append({"row":row,"product_id":ids[row-1],"brand":row_brand[row],"ok":False,"error":str(e)[:700]})
results.sort(key=lambda x:x["row"])
fails=[x for x in results if not x.get("ok")]
counts={}
for x in results:
    if x.get("ok"): counts[x["brand"]]=counts.get(x["brand"],0)+1
report={"ok":not fails,"verified_count":sum(1 for x in results if x.get("ok")),"failure_count":len(fails),"brand_terms":brand_terms,"verified_counts_by_brand":counts,"failures":fails,"results":results,"safety":{"only_product_field_written":"product_brand","other_fields_changed":False}}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":report["ok"],"verified":report["verified_count"],"failures":len(fails),"counts":counts,"brand_terms":brand_terms},ensure_ascii=False))
if fails: raise SystemExit(2)
