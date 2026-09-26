#!/usr/bin/env python3
import os,json,re,requests
from concurrent.futures import ThreadPoolExecutor,as_completed

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
r=S.get(BASE+"/wp-json/code-snippets/v1/snippets",params={"per_page":100},timeout=30)
r.raise_for_status()
payload=r.json()
items=payload if isinstance(payload,list) else (payload.get("snippets") or payload.get("data") or [])
items=items if isinstance(items,list) else []
active=[x for x in items if x.get("active")]
needles=[
 "the_content","rest_prepare_post","wp_insert_post_data","content.rendered","post_content",
 "نظر کارشناسی کشاورز بیست","box-shadow","145235","phase16","k20",
 "render_block","the_posts","posts_results","pre_get_posts","wp_update_post","save_post"
]

def fetch(x):
 sid=x.get("id")
 try:
  rr=requests.get(f"{BASE}/wp-json/code-snippets/v1/snippets/{sid}",auth=AUTH,timeout=20)
  rr.raise_for_status(); y=rr.json(); code=str(y.get("code") or "")
  matched=[n for n in needles if n.lower() in code.lower()]
  if not matched:return None
  lines=code.splitlines(); ex=[]
  for i,line in enumerate(lines):
   if any(n.lower() in line.lower() for n in matched):
    ex.append({"line":i+1,"context":"\n".join(lines[max(0,i-2):min(len(lines),i+3)])[:2200]})
  return {"id":sid,"name":y.get("name"),"scope":y.get("scope"),"priority":y.get("priority"),"matched":matched,"excerpts":ex[:50]}
 except Exception as e:
  return {"id":sid,"error":str(e)[:250]}

rows=[]
with ThreadPoolExecutor(max_workers=12) as ex:
 futs=[ex.submit(fetch,x) for x in active]
 for f in as_completed(futs):
  v=f.result()
  if v: rows.append(v)
rows.sort(key=lambda x:int(x.get("id") or 0))
print(json.dumps({"active_count":len(active),"rows":rows},ensure_ascii=False))
