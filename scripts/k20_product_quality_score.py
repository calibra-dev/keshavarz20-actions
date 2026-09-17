#!/usr/bin/env python3
import json, os, re, sys, html, math
from urllib.parse import urljoin
from collections import defaultdict
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-product-quality-score/1.0"})

def paged(path, params=None, cap=50):
    out=[]; params=dict(params or {})
    for page in range(1,cap+1):
        p=dict(params); p.update({"per_page":100,"page":page})
        r=S.get(urljoin(BASE,path.lstrip("/")),params=p,timeout=120)
        if r.status_code==400 and page>1: break
        r.raise_for_status(); rows=r.json()
        if not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

def textify(v):
    v=html.unescape(v or "")
    v=re.sub(r"<[^>]+>"," ",v)
    return re.sub(r"\s+"," ",v).strip()

def has_any(t, words):
    return any(w in t for w in words)

products=paged("wp-json/wc/v3/products",{"status":"publish"})
schema_template_points=0
schema_probe={}
if products:
    try:
        sample_url=products[0].get("permalink")
        htmlr=requests.get(sample_url,timeout=30,headers={"User-Agent":"k20-product-quality-score/1.0","Cache-Control":"no-cache"}).text[:500000]
        has_product=bool(re.search(r'"@type"\s*:\s*"Product"',htmlr,re.I))
        has_offer=bool(re.search(r'"@type"\s*:\s*"Offer"',htmlr,re.I))
        schema_template_points=(5 if has_product else 0)+(2 if has_offer else 0)
        schema_probe={"sample_url":sample_url,"product_schema":has_product,"offer_schema":has_offer,"points":schema_template_points}
    except Exception as e:
        schema_probe={"error":type(e).__name__,"points":0}
reviews=[]
try:
    reviews=paged("wp-json/wc/v3/products/reviews",{"status":"approved"},cap=20)
except Exception:
    pass
rv=defaultdict(lambda:{"total":0,"verified":0})
for r in reviews:
    b=rv[int(r.get("product_id") or 0)]; b["total"]+=1
    if r.get("verified"): b["verified"]+=1

rows=[]
for p in products:
    title=(p.get("name") or "").strip()
    desc=textify(p.get("description") or "")
    short=textify(p.get("short_description") or "")
    corpus=(title+" "+short+" "+desc).lower()
    attrs=p.get("attributes") or []
    imgs=p.get("images") or []
    score=0; gaps=[]; detail={}

    v=5 if len(title)>=5 else 0; score+=v; detail["title"]=v
    if v<5:gaps.append("عنوان استاندارد/کامل")

    v=5 if len(short)>=40 else (2 if short else 0); score+=v; detail["short_decision"]=v
    if v<5:gaps.append("توضیح کوتاه تصمیم‌ساز")

    spec_points=min(15, len(attrs)*3)
    if len(desc)>800: spec_points=max(spec_points,8)
    score+=spec_points; detail["specifications"]=spec_points
    if spec_points<12:gaps.append("مشخصات ساختاریافته/کامل")

    suitable=has_any(corpus,["مناسب","کاربرد","برای چه","انتخاب"])
    unsuitable=has_any(corpus,["نامناسب","مناسب نیست","نخرید","محدودیت","قبل از خرید"])
    v=(5 if suitable else 0)+(5 if unsuitable else 0); score+=v; detail["suitable_unsuitable"]=v
    if v<10:gaps.append("مناسب/نامناسب و محدودیت")

    img_points=0
    if len(imgs)>=4: img_points=7
    elif len(imgs)>=2: img_points=5
    elif len(imgs)==1: img_points=3
    if imgs and all(bool((i.get("alt") or "").strip()) for i in imgs): img_points=min(10,img_points+3)
    score+=img_points; detail["images"]=img_points
    if img_points<8:gaps.append("تصاویر واقعی/ALT")

    video=has_any(corpus,["<video","youtube","aparat","آپارات","ویدئو"])
    v=5 if video else 0; score+=v; detail["video"]=v
    if not video:gaps.append("ویدئو")

    price_present=bool(str(p.get("price") or "").strip())
    stock_known=(p.get("stock_status") in ("instock","outofstock","onbackorder"))
    v=(5 if price_present else 0)+(5 if stock_known else 0); score+=v; detail["price_stock"]=v
    if v<10:gaps.append("قیمت/موجودی معتبر")

    shipping=has_any(corpus,["ارسال","باربری","تحویل"])
    returns=has_any(corpus,["مرجوع","بازگشت","مغایرت","ضمانت"])
    v=(3 if shipping else 0)+(2 if returns else 0); score+=v; detail["shipping_returns"]=v
    if v<5:gaps.append("ارسال/مرجوعی/ضمانت نزدیک تصمیم خرید")

    compat=has_any(corpus,["سازگار","اتصال","سایز","واشر","مته","بست","نیازمند"])
    v=10 if compat else 0; score+=v; detail["compatibility"]=v
    if not compat:gaps.append("سازگاری")

    altcomp=has_any(corpus,["جایگزین","محصولات مرتبط","مکمل","همراه"])
    v=5 if altcomp else 0; score+=v; detail["alternatives_complements"]=v
    if not altcomp:gaps.append("جایگزین/مکمل")

    rstat=rv[int(p.get("id"))]
    qa=has_any(corpus,["پرسش","سوالات رایج","سؤالات رایج","faq"])
    v=(6 if rstat["verified"]>0 else (3 if rstat["total"]>0 else 0))+(4 if qa else 0)
    v=min(10,v); score+=v; detail["reviews_qa"]=v
    if v<8:gaps.append("Verified Review/Q&A")

    schema_points=schema_template_points
    # Product feed is Phase 3; keep its 3 points explicitly unearned in Phase 2.
    score+=schema_points; detail["schema_feed"]=schema_points
    if schema_points<7:gaps.append("Schema قابل‌مشاهده")
    gaps.append("Feed (فاز ۳)") if schema_points>=5 else None

    rows.append({
      "id":p.get("id"),"name":title,"sku":p.get("sku"),"permalink":p.get("permalink"),
      "score":int(score),"promote_ready":score>=85,"verified_reviews":rstat["verified"],
      "review_count":rstat["total"],"gaps":gaps,"breakdown":detail,"modified_gmt":p.get("date_modified_gmt")
    })

rows.sort(key=lambda x:(x["score"],x["id"] or 0))
scores=[x["score"] for x in rows]
summary={
  "product_count":len(rows),
  "average_score":round(sum(scores)/len(scores),2) if scores else 0,
  "promote_ready_85_plus":sum(1 for x in rows if x["score"]>=85),
  "below_85":sum(1 for x in rows if x["score"]<85),
  "verified_review_products":sum(1 for x in rows if x["verified_reviews"]>0),
  "distribution":{"90_100":sum(1 for s in scores if s>=90),"85_89":sum(1 for s in scores if 85<=s<90),"70_84":sum(1 for s in scores if 70<=s<85),"below_70":sum(1 for s in scores if s<70)}
}
record={"ok":True,"mode":"read-only","version":"phase2-pqs-v2","weights_total":100,"feed_points_reserved_for_phase3":3,
        "schema_template_probe":schema_probe,"generated_at_utc":__import__("datetime").datetime.utcnow().isoformat()+"Z","summary":summary,"products":rows}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
with open(sys.argv[1],"w",encoding="utf-8") as f:json.dump(record,f,ensure_ascii=False,indent=2)
print("PQS_OK",summary)
