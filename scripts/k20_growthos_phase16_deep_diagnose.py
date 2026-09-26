#!/usr/bin/env python3
import json, os, time, requests
from pathlib import Path
from datetime import datetime, timezone
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
IDS=[142587,145235,145237,145238,145251,145253,145259,145263,145281,145330,145775]
MARK="k20-phase16-deep-review-v1"
rows=[]
for pid in IDS:
    r=requests.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit","_fields":"id,slug,link,status,title,content,modified_gmt"},auth=AUTH,timeout=90)
    r.raise_for_status(); p=r.json()
    raw=((p.get("content") or {}).get("raw") or "")
    rendered=((p.get("content") or {}).get("rendered") or "")
    url=p.get("link") or ""
    pub=requests.get(url+("?k20_p16_diag="+str(int(time.time()*1000))),headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-diagnose/1.0"},timeout=60)
    txt=pub.text
    row={
      "id":pid,"slug":p.get("slug"),"url":url,"status":p.get("status"),"modified_gmt":p.get("modified_gmt"),
      "raw_marker_count":raw.count(MARK),
      "rendered_marker_count":rendered.count(MARK),
      "public_marker_count":txt.count(MARK),
      "raw_review_method_count":raw.count("روش تهیه و بازبینی"),
      "rendered_review_method_count":rendered.count("روش تهیه و بازبینی"),
      "public_review_method_count":txt.count("روش تهیه و بازبینی"),
      "raw_policy_count":raw.count("/editorial-policy/"),
      "rendered_policy_count":rendered.count("/editorial-policy/"),
      "public_policy_count":txt.count("/editorial-policy/"),
      "raw_editorial_count":raw.count("نظر کارشناسی کشاورز بیست"),
      "rendered_editorial_count":rendered.count("نظر کارشناسی کشاورز بیست"),
      "public_editorial_count":txt.count("نظر کارشناسی کشاورز بیست"),
      "public_http":pub.status_code,
    }
    rows.append(row)
out={
 "phase":16,
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "read_only":True,
 "target_count":len(rows),
 "rows":rows,
 "summary":{
   "raw_marker_exactly_one":sum(1 for x in rows if x["raw_marker_count"]==1),
   "raw_marker_duplicates":sum(1 for x in rows if x["raw_marker_count"]>1),
   "raw_marker_missing":sum(1 for x in rows if x["raw_marker_count"]==0),
   "public_review_method_present":sum(1 for x in rows if x["public_review_method_count"]>0),
   "public_policy_present":sum(1 for x in rows if x["public_policy_count"]>0),
   "public_editorial_present":sum(1 for x in rows if x["public_editorial_count"]>0)
 }}
Path("growthos-phase16-results/deep-diagnostic.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out["summary"],ensure_ascii=False))
