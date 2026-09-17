#!/usr/bin/env python3
import json, os, re, sys, html
from collections import defaultdict
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-phase2-inventory/1.0"})

def get_json(path, params=None, timeout=120):
    u=urljoin(BASE,path.lstrip("/"))
    r=S.get(u,params=params,timeout=timeout)
    r.raise_for_status()
    return r.json()

def paged(path, params=None, cap=50):
    params=dict(params or {})
    out=[]
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

def strip_markup(s):
    s=html.unescape(s or "")
    s=re.sub(r"<script\b[^>]*>.*?</script>"," ",s,flags=re.I|re.S)
    s=re.sub(r"<style\b[^>]*>.*?</style>"," ",s,flags=re.I|re.S)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def post_row(o, typ):
    rendered=((o.get("content") or {}).get("rendered") or "")
    plain=strip_markup(rendered)
    title=strip_markup((o.get("title") or {}).get("rendered") or "")
    return {
      "id":o.get("id"),"type":typ,"title":title,"slug":o.get("slug"),"status":o.get("status"),
      "link":o.get("link"),"modified_gmt":o.get("modified_gmt"),"word_count":len(plain.split()),
      "h2_count":len(re.findall(r"<h2\b",rendered,re.I)),"h3_count":len(re.findall(r"<h3\b",rendered,re.I)),
      "has_table":bool(re.search(r"<table\b",rendered,re.I)),"has_faq_details":bool(re.search(r"<details\b",rendered,re.I)),
      "has_video":bool(re.search(r"<(?:video|iframe)\b",rendered,re.I)),
      "categories":o.get("categories",[]),"tags":o.get("tags",[]),"featured_media":o.get("featured_media",0)
    }

posts=[]
for typ,path in [("post","wp-json/wp/v2/posts"),("page","wp-json/wp/v2/pages")]:
    rows=paged(path,{"status":"publish","context":"view","_fields":"id,slug,status,link,modified_gmt,title,content,categories,tags,featured_media"})
    posts.extend(post_row(x,typ) for x in rows)

cats=paged("wp-json/wc/v3/products/categories",{"hide_empty":"false","_fields":"id,name,slug,parent,count,description"})
products=paged("wp-json/wc/v3/products",{"status":"publish","_fields":"id,name,slug,permalink,sku,stock_status,short_description,description,categories,tags,images,attributes,reviews_allowed,date_modified_gmt"})

product_rows=[]
for p in products:
    product_rows.append({
      "id":p.get("id"),"name":p.get("name"),"slug":p.get("slug"),"permalink":p.get("permalink"),"sku":p.get("sku"),
      "stock_status":p.get("stock_status"),"categories":p.get("categories",[]),"tags":p.get("tags",[]),
      "image_count":len(p.get("images",[])),"alt_complete":all(bool((i.get("alt") or "").strip()) for i in p.get("images",[])) if p.get("images") else False,
      "attribute_count":len(p.get("attributes",[])),"has_short_description":bool(strip_markup(p.get("short_description") or "")),
      "has_description":bool(strip_markup(p.get("description") or "")),"reviews_allowed":bool(p.get("reviews_allowed")),
      "modified_gmt":p.get("date_modified_gmt")
    })

review_stats={"endpoint_ok":False,"total":0,"verified":0,"unverified":0,"by_product":{}}
try:
    reviews=paged("wp-json/wc/v3/products/reviews",{"status":"approved","_fields":"id,product_id,rating,verified,date_created_gmt"},cap=20)
    by=defaultdict(lambda:{"total":0,"verified":0,"unverified":0})
    for rv in reviews:
        pid=str(rv.get("product_id") or 0); b=by[pid]; b["total"]+=1
        if rv.get("verified"): b["verified"]+=1
        else: b["unverified"]+=1
    review_stats={"endpoint_ok":True,"total":len(reviews),"verified":sum(1 for x in reviews if x.get("verified")),"unverified":sum(1 for x in reviews if not x.get("verified")),"by_product":dict(by)}
except Exception as e:
    review_stats={"endpoint_ok":False,"error":type(e).__name__}

media_videos=[]
try:
    vids=paged("wp-json/wp/v2/media",{"media_type":"video","status":"inherit","context":"edit","_fields":"id,slug,source_url,mime_type,caption,date_gmt,modified_gmt"})
    media_videos=[{"id":v.get("id"),"slug":v.get("slug"),"source_url":v.get("source_url"),"mime_type":v.get("mime_type"),"date_gmt":v.get("date_gmt"),"modified_gmt":v.get("modified_gmt")} for v in vids]
except Exception:
    pass

def sitemap_probe(path):
    u=urljoin(BASE,path)
    try:
        r=requests.get(u,timeout=60,allow_redirects=True,headers={"User-Agent":"k20-phase2-inventory/1.0"})
        text=r.text[:500000] if r.ok else ""
        return {"url":u,"status":r.status_code,"content_type":r.headers.get("content-type",""),"bytes":len(r.content),
                "has_image_ns":"xmlns:image" in text,"has_video_ns":"xmlns:video" in text,"url_count":text.count("<url>"),"sitemap_count":text.count("<sitemap>")}
    except Exception as e:
        return {"url":u,"status":0,"error":type(e).__name__}

probes=[sitemap_probe(x) for x in ["sitemap_index.xml","wp-sitemap.xml","image-sitemap.xml","video-sitemap.xml"]]

groups={
 "decision_guides":["راهنما","خرید","انتخاب","مقایسه","تفاوت","طراحی"],
 "problem_content":["گرفتگی","نشتی","پارگی","افت فشار","خرابی","تعمیر","شستشو","شست‌وشو","عیب"],
 "case_studies":["مطالعه موردی","پروژه","Case Study","اجرای واقعی"],
 "transcripts":["ترنسکریپت","Transcript","متن ویدئو","رونویسی"],
}
classed={k:[] for k in groups}
for p in posts:
    hay=(p["title"]+" "+(p["slug"] or "")).lower()
    for k,terms in groups.items():
        if any(t.lower() in hay for t in terms):
            classed[k].append({x:p[x] for x in ["id","type","title","slug","status","link","modified_gmt","word_count"]})

record={
 "ok":True,"mode":"read-only","generated_at_utc":__import__("datetime").datetime.utcnow().isoformat()+"Z",
 "counts":{"posts_pages":len(posts),"products":len(product_rows),"product_categories":len(cats),"media_videos":len(media_videos)},
 "content_classification":classed,
 "posts_pages":posts,
 "product_categories":cats,
 "products":product_rows,
 "reviews":review_stats,
 "media_videos":media_videos,
 "sitemaps":probes
}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
with open(sys.argv[1],"w",encoding="utf-8") as f: json.dump(record,f,ensure_ascii=False,indent=2)
print("PHASE2_INVENTORY_OK",record["counts"],"reviews",review_stats.get("total"))
