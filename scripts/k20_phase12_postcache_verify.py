#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
src=json.loads((ROOT/"phase12-results/category-decision-execution-20261001.json").read_text(encoding="utf-8"))
rows=[]
for cat in src["categories"]:
    url=cat["link"]
    r=requests.get(url,headers={"User-Agent":"K20-Phase12-PostCacheVerify/1.0"},timeout=60,allow_redirects=True)
    rows.append({
        "id":cat["id"],
        "name":cat["name"],
        "url":url,
        "http":r.status_code,
        "final_url":r.url,
        "heading_present":"راهنمای تصمیم انتخاب در این دسته" in r.text,
        "cache_control":r.headers.get("cache-control"),
        "x_litespeed_cache":r.headers.get("x-litespeed-cache"),
    })
ok=all(x["http"]==200 and x["heading_present"] for x in rows)
out={
    "schema_version":"seo-god2-phase12-post-cache-public-verify-v1",
    "phase":12,
    "verified_at_utc":datetime.now(timezone.utc).isoformat(),
    "status":"PASS" if ok else "FAIL",
    "ok":ok,
    "public_http_200":sum(1 for x in rows if x["http"]==200),
    "heading_present":sum(1 for x in rows if x["heading_present"]),
    "categories":rows
}
p=ROOT/"phase12-results/post-cache-public-verify-20261001.json"
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":ok,"http_200":out["public_http_200"],"heading":out["heading_present"]}))
if not ok:
    raise SystemExit(1)
