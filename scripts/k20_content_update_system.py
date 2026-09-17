#!/usr/bin/env python3
import json, os, re, sys, html
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-content-update-system/1.0"})

def paged(path, params=None, cap=50):
    params=dict(params or {}); out=[]
    for page in range(1,cap+1):
        p=dict(params); p.update({"per_page":50,"page":page})
        rows=None
        for attempt in range(3):
            r=S.get(urljoin(BASE,path.lstrip("/")),params=p,timeout=120,headers={"Cache-Control":"no-cache"})
            if r.status_code==400 and page>1: return out
            r.raise_for_status()
            try:
                rows=r.json()
                break
            except Exception:
                if attempt==2:
                    raise RuntimeError(f"Non-JSON response for {path} page={page} status={r.status_code} content_type={r.headers.get('content-type','')} prefix={r.text[:80]!r}")
        if not isinstance(rows,list) or not rows: break
        out.extend(rows)
        if len(rows)<50: break
    return out

def clean(x):
    x=html.unescape(x or ""); x=re.sub(r"<[^>]+>"," ",x)
    return re.sub(r"\s+"," ",x).strip()

now=datetime.now(timezone.utc)
assets=[]
def add_content_asset(o, typ):
    mod=o.get("modified_gmt")
    age=None
    if mod:
        try: age=(now-datetime.fromisoformat(mod.replace("Z","+00:00"))).days
        except: pass
    content=((o.get("content") or {}).get("rendered") or "")
    plain=clean(content)
    state=[]; triggers=[]
    if age is not None and age>=180: state.append("قدیمی"); triggers.append("age>=180d")
    elif age is not None and age>=90: state.append("نیازمند بررسی"); triggers.append("age>=90d")
    else: state.append("تازه")
    if len(plain.split())<250: triggers.append("thin-content-check")
    if "href=" not in content.lower(): triggers.append("internal-link-review")
    assets.append({"id":o.get("id"),"type":typ,"title":clean((o.get("title") or {}).get("rendered") or ""),"url":o.get("link"),"modified_gmt":mod,"age_days":age,"state":state,"triggers":triggers})

for o in paged("wp-json/wp/v2/posts",{"status":"publish","context":"view","_fields":"id,slug,status,link,modified_gmt,title,content"}):
    add_content_asset(o,"post")

# The live /wp/v2/pages collection is cache-contaminated. Tool/page URLs are monitored through
# the explicit GSC watchlist rather than bulk-reading potentially corrupted page responses.

products=paged("wp-json/wc/v3/products",{"status":"publish","_fields":"id,name,permalink,stock_status,date_modified_gmt,images,description,short_description"})
for p in products:
    mod=p.get("date_modified_gmt"); age=None
    if mod:
        try: age=(now-datetime.fromisoformat(mod.replace("Z","+00:00"))).days
        except: pass
    state=[]; triggers=[]
    if p.get("stock_status")=="outofstock": state.append("دارای محصول ناموجود"); triggers.append("out-of-stock")
    if age is not None and age>=180: state.append("قدیمی"); triggers.append("age>=180d")
    elif age is not None and age>=90: state.append("نیازمند بررسی"); triggers.append("age>=90d")
    if not state: state=["تازه"]
    imgs=p.get("images") or []
    if not imgs: triggers.append("missing-image")
    elif any(not (i.get("alt") or "").strip() for i in imgs): triggers.append("missing-alt")
    assets.append({"id":p.get("id"),"type":"product","title":p.get("name"),"url":p.get("permalink"),"modified_gmt":mod,"age_days":age,"state":state,"triggers":triggers})

watch=[]
try:
    with open("phase2/gsc-watchlist.json",encoding="utf-8") as f: g=json.load(f)
    for x in g.get("pages",[]):
        flags=[]
        if x.get("impressions",0)>=20 and x.get("clicks",0)==0: flags.append("CTR/ranking review")
        if x.get("position") is not None and x["position"]>15 and x.get("impressions",0)>=20: flags.append("ranking-gap")
        if x.get("role")=="money-category" and x.get("position",999)>20: flags.append("money-page-priority")
        watch.append(dict(x,flags=flags))
except FileNotFoundError:
    pass

needs=[a for a in assets if a["triggers"]]
needs.sort(key=lambda x:(0 if "out-of-stock" in x["triggers"] else 1, -(x["age_days"] or 0)))
record={"ok":True,"mode":"read-only","version":"phase2-content-lifecycle-v1","generated_at_utc":now.isoformat(),
 "rules":{"fresh":"<90 days unless another trigger fires","review":"90-179 days","old":">=180 days",
 "triggers":["price/stock/catalog/replacement/warranty","rank/CTR/sales/intent","new customer question/season","shipping/broken link/out-of-stock","schema error/competitor"]},
 "summary":{"assets":len(assets),"needs_review":len(needs),"gsc_watch_flags":sum(1 for x in watch if x["flags"])},
 "gsc_watchlist":watch,"needs_review":needs[:500]}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
with open(sys.argv[1],"w",encoding="utf-8") as f:json.dump(record,f,ensure_ascii=False,indent=2)
print("CONTENT_LIFECYCLE_OK",record["summary"])
