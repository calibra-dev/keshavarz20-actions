#!/usr/bin/env python3
import os, requests, json
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
pid=145235
r=requests.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit","_fields":"id,link,content"},auth=AUTH,timeout=90)
r.raise_for_status(); p=r.json()
raw=((p.get("content") or {}).get("raw") or "")
rendered=((p.get("content") or {}).get("rendered") or "")
pub=requests.get(p["link"],headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-diagnostic/1.0"},timeout=90)
checks={}
for name,text in [("raw",raw),("rendered",rendered),("public",pub.text)]:
    checks[name]={
      "deep_marker":"k20-phase16-deep-review-v1" in text,
      "review_method":"روش تهیه و بازبینی" in text,
      "policy":"/editorial-policy/" in text,
      "editorial":"نظر کارشناسی کشاورز بیست" in text,
      "okstate":"https://extension.okstate.edu/fact-sheets/drip-irrigation-systems" in text,
      "itrc":"https://itrc.org/projects/evals.htm" in text
    }
checks["public_http"]=pub.status_code
for term in ["نظر کارشناسی کشاورز بیست","k20-phase16-deep-review-v1","k20-phase16-gutenberg-test-v1"]:
    i=raw.find(term)
    checks["snippet_"+term]=raw[max(0,i-1500):i+3000] if i>=0 else None
print(json.dumps(checks,ensure_ascii=False))
