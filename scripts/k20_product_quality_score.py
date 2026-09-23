#!/usr/bin/env python3
import json, os, re, sys, html, math
from pathlib import Path
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

review_collection_global=False
try:
    settings=S.get(urljoin(BASE,"wp-json/wc/v3/settings/products"),timeout=120).json()
    setting_values={x.get("id"):x.get("value") for x in settings if isinstance(x,dict)}
    review_collection_global=(
        setting_values.get("woocommerce_enable_reviews")=="yes"
        and setting_values.get("woocommerce_review_rating_verification_label")=="yes"
    )
except Exception:
    pass

feed_ready_ids=set()
try:
    feed_path=Path(__file__).resolve().parents[1]/"geo-aeo-results"/"k21-openai-discovery-feed-draft.json"
    if feed_path.exists():
        feed_obj=json.loads(feed_path.read_text(encoding="utf-8"))
        feed_ready_ids={
            int(x.get("wp_product_id"))
            for x in feed_obj.get("valid_rows",[])
            if x.get("wp_product_id")
        }
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

    raw_media=((p.get("description") or "")+" "+(p.get("short_description") or ""))
    video=bool(re.search(r"<video\b|youtube\.com|youtu\.be|aparat\.com",raw_media,re.I))
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
    review_collection_ready=review_collection_global and bool(p.get("reviews_allowed"))
    review_points=6 if rstat["verified"]>0 else (3 if rstat["total"]>0 else (2 if review_collection_ready else 0))
    v=min(10,review_points+(4 if qa else 0)); score+=v
    detail["reviews_qa"]=v
    detail["review_collection_ready"]=review_collection_ready
    if v<6:gaps.append("Verified Review/Q&A")

    feed_ready=int(p.get("id") or 0) in feed_ready_ids
    schema_points=schema_template_points+(3 if feed_ready else 0)
    score+=schema_points
    detail["schema_feed"]=schema_points
    detail["feed_ready"]=feed_ready
    if schema_template_points<7:gaps.append("Schema قابل‌مشاهده")
    if not feed_ready:gaps.append("Feed (فاز ۳)")

    owner_map={
      "عنوان استاندارد/کامل":"catalog",
      "توضیح کوتاه تصمیم‌ساز":"content",
      "مشخصات ساختاریافته/کامل":"catalog+technical",
      "مناسب/نامناسب و محدودیت":"content+technical",
      "تصاویر واقعی/ALT":"media",
      "ویدئو":"media",
      "قیمت/موجودی معتبر":"catalog",
      "ارسال/مرجوعی/ضمانت نزدیک تصمیم خرید":"commerce-content",
      "سازگاری":"technical-data",
      "جایگزین/مکمل":"merchandising",
      "Verified Review/Q&A":"customer-evidence",
      "Schema قابل‌مشاهده":"seo-technical",
      "Feed (فاز ۳)":"phase3-feed"
    }
    deadline="2026-10-18" if score<70 else ("2026-11-17" if score<85 else None)
    remediation=[{"gap":g,"owner":owner_map.get(g,"content-ops"),"deadline":deadline if g!="Feed (فاز ۳)" else "Phase 3"} for g in gaps]
    rows.append({
      "id":p.get("id"),"name":title,"sku":p.get("sku"),"permalink":p.get("permalink"),
      "score":int(score),"promote_ready":score>=85,"verified_reviews":rstat["verified"],
      "review_count":rstat["total"],"gaps":gaps,"remediation":remediation,
      "deadline":deadline,"breakdown":detail,"modified_gmt":p.get("date_modified_gmt")
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
record={"ok":True,"mode":"read-only","version":"phase2-pqs-v5","weights_total":100,"feed_points_reserved_for_phase3":3,
        "schema_template_probe":schema_probe,"generated_at_utc":__import__("datetime").datetime.utcnow().isoformat()+"Z","summary":summary,"products":rows}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
with open(sys.argv[1],"w",encoding="utf-8") as f:json.dump(record,f,ensure_ascii=False,indent=2)
print("PQS_OK",summary)
