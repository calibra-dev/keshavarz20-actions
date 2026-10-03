#!/usr/bin/env python3
import json, os, re, time
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-brand-remediation/2.0","Cache-Control":"no-cache"})
M=json.loads(Path("brand-remediation/verified-map-20261003.json").read_text(encoding="utf-8"))
SN=json.loads(Path("brand-remediation-results/snapshot-87.json").read_text(encoding="utf-8"))
OUT=Path("brand-remediation-results/apply-verified-latest.json")
VER={int(k):v for k,v in M["verified"].items()}
MULTI={int(k):set(v) for k,v in M["resolved_multibrand_expected"].items()}
PSEUDO=int(M["pseudo_brand_id"])

def call(method,path,**kw):
    for n in range(5):
        r=S.request(method,BASE+path,timeout=90,**kw)
        if r.status_code in (429,500,502,503,504):
            time.sleep(1.5*(n+1)); continue
        if not r.ok: raise RuntimeError(f"{method} {path} {r.status_code}: {r.text[:500]}")
        return r.json()
    raise RuntimeError("retry exhausted")

def norm(s):
    s=str(s or "").casefold().replace("\u200c"," ")
    s=re.sub(r"\([^)]*\)","",s)
    return re.sub(r"[^0-9a-zآ-ی]+","",s)

def terms():
    out=[]
    for page in range(1,10):
        rows=call("GET","/wp-json/wp/v2/product_brand",params={"per_page":100,"page":page,"context":"edit"})
        out+=rows
        if len(rows)<100: break
    return out

def product(pid):
    return call("GET",f"/wp-json/wp/v2/product/{pid}",params={"context":"edit"})

by_norm={}
for t in terms(): by_norm.setdefault(norm(t.get("name")),[]).append(t)
term_ids={}; created=[]
for name in sorted(set(VER.values())):
    rows=by_norm.get(norm(name),[])
    if len(rows)>1: raise RuntimeError(f"ambiguous term {name}")
    if rows:
        term_ids[name]=int(rows[0]["id"]); continue
    r=S.post(BASE+"/wp-json/wp/v2/product_brand",json={"name":name},timeout=90)
    if r.ok:
        tid=int(r.json()["id"])
    else:
        e=r.json() if r.text else {}
        if r.status_code!=400 or e.get("code")!="term_exists": raise RuntimeError(f"term create {name}: {r.status_code} {r.text[:300]}")
        tid=int((e.get("data") or {}).get("term_id") or 0)
    if not tid: raise RuntimeError(f"no term id for {name}")
    term_ids[name]=tid; created.append({"name":name,"id":tid})

rows={int(x["product_id"]):x for x in SN["rows"]}
results=[]; failures=[]
for pid,row in sorted(rows.items()):
    before=product(pid); current=[int(x) for x in (before.get("product_brand") or [])]
    if pid in VER:
        desired=[term_ids[VER[pid]]]
        valid=(set(current)==MULTI[pid]) if pid in MULTI else (current==[PSEUDO])
        if not valid:
            failures.append({"product_id":pid,"error":"stale_state","current":current}); continue
        action="verified_assignment"
    elif current==[PSEUDO]:
        desired=[]; action="remove_pseudo"
    else:
        results.append({"product_id":pid,"name":row.get("name"),"before":current,"after":current,"action":"leave_unresolved_multi","ok":True})
        continue
    call("POST",f"/wp-json/wp/v2/product/{pid}",json={"product_brand":desired})
    after=[int(x) for x in (product(pid).get("product_brand") or [])]
    rec={"product_id":pid,"name":row.get("name"),"before":current,"after":after,"action":action,"brand":VER.get(pid),"ok":after==desired}
    results.append(rec)
    if not rec["ok"]: failures.append(rec)

report={
 "ok":not failures,"scope":87,
 "verified_assignments":sum(x.get("action")=="verified_assignment" and x.get("ok") for x in results),
 "pseudo_removed":sum(x.get("action")=="remove_pseudo" and x.get("ok") for x in results),
 "unresolved_multi":sum(x.get("action")=="leave_unresolved_multi" for x in results),
 "created_terms":created,"term_ids":term_ids,"failures":failures,"results":results,
 "safety":{"only_field":"product_brand","price_mutations":0,"stock_mutations":0,"content_mutations":0,"sku_mutations":0}
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ("ok","verified_assignments","pseudo_removed","unresolved_multi")},ensure_ascii=False))
if failures: raise SystemExit(2)
