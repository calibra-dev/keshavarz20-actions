#!/usr/bin/env python3
import os,json,requests
from datetime import datetime,timezone
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
r=requests.get(BASE+"/wp-json/wp/v2/posts",params={"slug":"drip-tape-length-fittings-calculator","context":"edit","per_page":5},auth=AUTH,timeout=120)
r.raise_for_status(); rows=r.json()
if not rows: raise SystemExit("calculator post not found")
o=rows[0]
out={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"id":o.get("id"),"slug":o.get("slug"),"status":o.get("status"),"link":o.get("link"),
     "title":((o.get("title") or {}).get("raw") or ""),"content":((o.get("content") or {}).get("raw") or ""),"excerpt":((o.get("excerpt") or {}).get("raw") or "")}
os.makedirs("seo-god1-results",exist_ok=True)
with open("seo-god1-results/calculator-current-snapshot.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
print("CALCULATOR_SNAPSHOT_OK",o.get("id"),o.get("status"),len(out["content"]))
