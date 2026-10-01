#!/usr/bin/env python3
import json, os, time
from pathlib import Path
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"phase12-results"/"rich-category-verify-20261001.json"
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
IDS=[846,997,826]
START="<!--k20-phase12-category-decision:start-->"
END="<!--k20-phase12-category-decision:end-->"

s=requests.Session(); s.auth=AUTH
retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
s.mount("https://",HTTPAdapter(max_retries=retry)); s.mount("http://",HTTPAdapter(max_retries=retry))
rows=[]
for cid in IDS:
    r=s.get(f"{BASE}/wp-json/wc/v3/products/categories/{cid}",timeout=45)
    r.raise_for_status(); j=r.json()
    d=j.get("description") or ""
    link=j.get("_links",{}).get("collection",[{}])[0].get("href")
    rows.append({
      "id":cid,"name":j.get("name"),"slug":j.get("slug"),
      "description_chars":len(d),
      "has_h2":"<h2" in d.lower(),
      "has_p":"<p" in d.lower(),
      "has_ul":"<ul" in d.lower(),
      "has_a":"<a " in d.lower(),
      "marker_start_count":d.count(START),
      "marker_end_count":d.count(END),
      "decision_heading":"راهنمای تصمیم انتخاب در این دسته" in d,
    })
out={"phase":12,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"read_only":True,"rows":rows}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
