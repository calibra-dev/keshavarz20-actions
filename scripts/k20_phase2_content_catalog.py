#!/usr/bin/env python3
import json, os, re, sys
from urllib.parse import urljoin
import requests
BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-phase2-content-catalog/1.0","Cache-Control":"no-cache"})

def paged_search(subtype):
    out=[]
    for page in range(1,30):
        r=S.get(urljoin(BASE,"wp-json/wp/v2/search"),params={"type":"post","subtype":subtype,"per_page":100,"page":page},timeout=120)
        if r.status_code==400 and page>1: break
        r.raise_for_status()
        rows=r.json()
        if not isinstance(rows,list) or not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

posts=paged_search("post")
pages=paged_search("page")
items=[]
for typ,rows in [("post",posts),("page",pages)]:
  for x in rows:
    items.append({"id":x.get("id"),"type":typ,"title":x.get("title") or "","url":x.get("url")})

decision_terms=["راهنما","خرید","انتخاب","مقایسه","تفاوت","کدام","چطور","چگونه","محاسبه","طراحی","قیمت"]
problem_terms=["گرفتگی","نشتی","پارگی","افت فشار","خرابی","تعمیر","شستشو","شست‌وشو","عیب","مشکل","رسوب","بسته شدن","چکه"]
phase2_domains=["نوار تیپ","نوار آبیاری","لی فلت","لی‌فلت","نخدار","پلی اتیلن","پلی‌اتیلن","فیلتر","آبیاری","آبپاش","قطره","شیر"]

def match(title,terms):
    t=(title or "").lower()
    return any(w.lower() in t for w in terms)
def domain(title):
    return match(title,phase2_domains)

decision=[x for x in items if domain(x["title"]) and match(x["title"],decision_terms)]
problem=[x for x in items if domain(x["title"]) and match(x["title"],problem_terms)]
record={"ok":True,"mode":"read-only","generated_at_utc":__import__("datetime").datetime.utcnow().isoformat()+"Z",
        "counts":{"published_posts":len(posts),"published_pages":len(pages),"decision_candidates":len(decision),"problem_candidates":len(problem)},
        "decision_candidates":decision,"problem_candidates":problem,"all_items":items}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
json.dump(record,open(sys.argv[1],"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE2_CONTENT_CATALOG_OK",record["counts"])
