#!/usr/bin/env python3
import json, os
from urllib.parse import urljoin
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session();S.auth=AUTH;S.headers.update({"Accept":"application/json","User-Agent":"k20-phase3-live-verify/1.0","Cache-Control":"no-cache"})
pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
marker="<!-- k20-phase3-decision-links -->"
rows=[]
for x in pim.get("products",[]):
    pid=int(x["product_id"])
    r=S.get(urljoin(BASE,f"wp-json/wc/v3/products/{pid}"),timeout=120);r.raise_for_status();p=r.json()
    d=p.get("description") or ""
    expected=[z.get("url") for z in x.get("decision_links") or [] if z.get("url")]
    links_ok=all(u in d for u in expected)
    marker_count=d.count(marker)
    ok=marker_count==1 and links_ok
    rows.append({"product_id":pid,"rank":x["rank"],"ok":ok,"marker_count":marker_count,"decision_links_expected":len(expected),"decision_links_present":sum(1 for u in expected if u in d),"modified_gmt":p.get("date_modified_gmt")})
summary={"products":len(rows),"pass":sum(1 for x in rows if x["ok"]),"fail":sum(1 for x in rows if not x["ok"]),"duplicate_marker":sum(1 for x in rows if x["marker_count"]>1)}
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":summary["fail"]==0,"version":"phase3-decision-link-live-verify-v1","summary":summary,"products":rows},open("phase3-results/decision-link-live-verify.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_DECISION_LINK_VERIFY",summary)
if summary["fail"]>0: raise SystemExit(2)
