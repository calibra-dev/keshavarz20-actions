#!/usr/bin/env python3
from __future__ import annotations
import hashlib, html, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
BACKLOG=Path("growthos-phase16-results/legacy-backlog.json")
OUT=Path("bridge-v3-ops/20260926-growthos-phase16-legacy-retrofit-job-create.json")
MANIFEST=Path("growthos-phase16-results/legacy-retrofit-prepare.json")
MARKER="k20-phase16-editorial-trust-start"
POLICY_URL="https://keshavarz20.com/editorial-policy/"
NOW=datetime.now(timezone.utc).isoformat()

S=requests.Session(); S.auth=AUTH
retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=1.0,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase16-retrofit/1.0","Cache-Control":"no-cache"})

def get_json(path,params=None,tries=5):
    url=urljoin(BASE+"/",path.lstrip("/"))
    last=None
    for attempt in range(1,tries+1):
        try:
            r=S.get(url,params=params,timeout=90)
            r.raise_for_status()
            ctype=(r.headers.get("Content-Type") or "").lower()
            if "json" not in ctype:
                raise ValueError("non-json response "+ctype+" sample="+repr((r.text or "")[:80]))
            return r.json()
        except Exception as exc:
            last=exc
            if attempt<tries: time.sleep(attempt*2)
    raise RuntimeError(f"GET failed after retries: {path}: {last}")

def strip_tags(value):
    s=re.sub(r"<script[\s\S]*?</script>"," ",str(value or ""),flags=re.I)
    s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",html.unescape(s)).strip()

def choose_anchor(content):
    # Use a unique suffix so content.patch appends without replacing the body.
    for size in (900,1400,2200,3500,5000):
        n=min(size,len(content))
        anchor=content[-n:]
        if anchor and content.count(anchor)==1:
            return anchor
    raise RuntimeError("could not derive unique content suffix anchor")

def trust_block(needs_editorial_note):
    note=""
    if needs_editorial_note:
        note=f"""
<h2>نظر کارشناسی کشاورز بیست <span style="font-size:.72em;font-weight:500">(تحلیل تحریریه)</span></h2>
<p>این بخش یک جمع‌بندی تحریریه برای کمک به تصمیم‌گیری است و به معنی تأیید یک کارشناس نام‌دار یا توصیه اختصاصی برای مزرعه شما نیست. برای تصمیم‌های وابسته به دوز، فشار، دبی، سازگاری، آب، خاک یا مرحله رشد، داده واقعی پروژه و منبع مستقیم همان محصول یا موضوع را ملاک قرار دهید.</p>"""
    return f"""
<!-- {MARKER} -->
<section class="k20-phase16-editorial-trust" dir="rtl" style="direction:rtl;text-align:right;line-height:2;border:1px solid #dfe8e2;border-radius:16px;padding:18px;margin:28px 0;background:#f8fbf9">
{note}
<h2>روش تهیه و بازبینی</h2>
<p><strong>مسئول محتوا:</strong> تحریریه کشاورز بیست. منابع مستقیم و ارجاعات درج‌شده در همین صفحه مبنای ادعاهای قابل بررسی هستند. برای این نسخه، بازبین نام‌دار یا متخصص مستقلِ قابل‌تأیید ثبت نشده است؛ بنابراین نام شخص، مدرک تخصصی یا تجربه میدانی ساختگی به محتوا اضافه نمی‌شود.</p>
<p>در صورت مشاهده عدد، مشخصه فنی یا توضیحی که نیاز به اصلاح دارد، آن مورد باید با منبع مستقیم بررسی شود. جزئیات روش منبع‌سنجی، استفاده از ابزارهای خودکار و سیاست اصلاح محتوا در <a href="{POLICY_URL}">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> توضیح داده شده است.</p>
</section>
<!-- k20-phase16-editorial-trust-end -->
"""

if not BACKLOG.exists():
    raise SystemExit("Missing Phase 16 legacy backlog")
backlog=json.loads(BACKLOG.read_text(encoding="utf-8"))
rows=backlog.get("posts") or []
items=[]; prepared=[]; skipped=[]

for row in rows:
    post_id=int(row["id"])
    post=get_json(f"wp-json/wp/v2/posts/{post_id}",{"context":"edit","_fields":"id,status,type,slug,link,title,content,modified_gmt"})
    if post.get("type")!="post" or post.get("status")!="publish":
        skipped.append({"id":post_id,"reason":"not_published_normal_post","status":post.get("status"),"type":post.get("type")})
        continue
    content=((post.get("content") or {}).get("raw") or "")
    if not content:
        raise RuntimeError(f"post {post_id} returned empty raw content")
    if MARKER in content:
        skipped.append({"id":post_id,"reason":"marker_already_present"})
        continue

    has_editorial=("نظر کارشناسی کشاورز بیست" in content) or ("یادداشت تحریریه کشاورز بیست" in content)
    block=trust_block(not has_editorial)
    anchor=choose_anchor(content)
    expected=hashlib.sha256(content.encode("utf-8")).hexdigest()
    items.append({
      "action":"content.patch",
      "request_id":f"growthos-phase16-retrofit-post-{post_id}-20260926",
      "payload":{
        "target_type":"post",
        "post_id":post_id,
        "field":"post_content",
        "old_content":anchor,
        "new_content":anchor+block,
        "expected_sha256":expected
      }
    })
    prepared.append({
      "id":post_id,
      "slug":post.get("slug"),
      "link":post.get("link"),
      "title":strip_tags((post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or ""),
      "expected_sha256":expected,
      "editorial_note_added":not has_editorial,
      "method_block_added":True,
      "policy_link_added":True
    })

payload={
  "action":"job.create",
  "request_id":"growthos-phase16-legacy-retrofit-job-create-20260926",
  "payload":{
    "items":items,
    "max_retries":2,
    "backoff_seconds":20
  }
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
MANIFEST.write_text(json.dumps({
  "ok":True,
  "phase":16,
  "title":"Human Expertise & Editorial Trust — legacy provenance retrofit prepare",
  "generated_at_utc":NOW,
  "backlog_rows":len(rows),
  "prepared_items":len(items),
  "skipped":skipped,
  "prepared":prepared,
  "safety":{
    "fake_authors_created":0,
    "fake_reviewers_created":0,
    "named_human_experts_created":0,
    "price_stock_discount_mutations":0,
    "orders_created":0,
    "messages_sent":0,
    "content_claims_rewritten":0,
    "technical_facts_rewritten":0
  }
},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"prepared_items":len(items),"skipped":len(skipped),"request":str(OUT)},ensure_ascii=False))
if not items and rows:
    print("No new patches needed; all current backlog rows already contain the Phase 16 marker.")
