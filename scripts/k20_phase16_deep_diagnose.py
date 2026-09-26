#!/usr/bin/env python3
from __future__ import annotations
import json, os, requests, time
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
IDS=[142587,145235,145237,145238,145251,145253,145259,145263,145281,145330,145775]
MARKER="k20-phase16-deep-review-v1"
S=requests.Session(); S.auth=AUTH
rows=[]
for pid in IDS:
    p=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit","_fields":"id,slug,link,title,content,modified_gmt"},timeout=90)
    p.raise_for_status(); j=p.json()
    raw=((j.get("content") or {}).get("raw") or "")
    rendered=((j.get("content") or {}).get("rendered") or "")
    url=j.get("link")
    pub=requests.get(url+("?k20_diag="+str(int(time.time()*1000))),timeout=60,headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-phase16-deep-diagnose/1.0"})
    rows.append({
      "id":pid,"url":url,"modified_gmt":j.get("modified_gmt"),
      "raw_marker":MARKER in raw,
      "rendered_marker":MARKER in rendered,
      "raw_review_method":"روش تهیه و بازبینی" in raw,
      "rendered_review_method":"روش تهیه و بازبینی" in rendered,
      "raw_policy":"/editorial-policy/" in raw,
      "rendered_policy":"/editorial-policy/" in rendered,
      "raw_deep_heading":"بازبینی عمیق فنی" in raw,
      "rendered_deep_heading":"بازبینی عمیق فنی" in rendered,
      "public_http":pub.status_code,
      "public_review_method":"روش تهیه و بازبینی" in pub.text,
      "public_policy":"/editorial-policy/" in pub.text,
      "public_deep_heading":"بازبینی عمیق فنی" in pub.text,
      "raw_len":len(raw),"rendered_len":len(rendered),"public_len":len(pub.text)
    })
out={"phase":16,"mode":"read_only_diagnosis","count":len(rows),"rows":rows}
Path("growthos-phase16-results/deep-diagnosis.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
