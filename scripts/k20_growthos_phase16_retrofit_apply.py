#!/usr/bin/env python3
from __future__ import annotations
import hashlib, html, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
BACKLOG=Path("growthos-phase16-results/legacy-backlog.json")
OUT=Path("growthos-phase16-results/legacy-retrofit-apply.json")
MARKER="k20-phase16-editorial-trust-start"
POLICY_URL="https://keshavarz20.com/editorial-policy/"
NOW=datetime.now(timezone.utc).isoformat()
BRIDGE="/wp-json/keshavarz20-ops/v3/execute"

S=requests.Session(); S.auth=AUTH
retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=0.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase16-direct-repair/1.0","Cache-Control":"no-cache"})

def get_post(post_id:int):
    url=urljoin(BASE+"/",f"wp-json/wp/v2/posts/{post_id}")
    r=S.get(url,params={"context":"edit","_fields":"id,status,type,slug,link,title,content,modified_gmt"},timeout=90)
    r.raise_for_status()
    return r.json()

def bridge(action:str, request_id:str, payload:dict|None=None):
    body={"action":action,"request_id":request_id,"payload":payload or {}}
    r=S.post(urljoin(BASE+"/",BRIDGE.lstrip("/")),json=body,timeout=120)
    data={}
    try: data=r.json()
    except Exception:
        raise RuntimeError(f"{action}: non-json HTTP {r.status_code}: {(r.text or '')[:180]}")
    if not r.ok or data.get("ok") is not True:
        raise RuntimeError(f"{action}: HTTP {r.status_code} code={data.get('code')} message={data.get('message')}")
    return data.get("result") or {}

def choose_anchors(content:str):
    seen=set()
    for size in (700,1000,1400,2200,3500,5000,8000,12000):
        n=min(size,len(content))
        anchor=content[-n:]
        if anchor and anchor not in seen and content.count(anchor)==1:
            seen.add(anchor); yield anchor

def trust_block(needs_editorial_note:bool):
    note=""
    if needs_editorial_note:
        note="""
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

def title_text(post):
    t=(post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or ""
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",t))).strip()

backlog=json.loads(BACKLOG.read_text(encoding="utf-8"))
ids=[int(x["id"]) for x in (backlog.get("posts") or [])]
results=[]
placeholder_candidates=[]
failures=[]

for pos,post_id in enumerate(ids,1):
    try:
        post=get_post(post_id)
        if post.get("type")!="post" or post.get("status")!="publish":
            results.append({"id":post_id,"status":"skipped_nonpublished","type":post.get("type"),"post_status":post.get("status")})
            continue
        raw=((post.get("content") or {}).get("raw") or "")
        if not raw:
            raise RuntimeError("empty raw post content")

        # Audit obvious unresolved editorial placeholders without rewriting them silently.
        for pat in [
            r"نام واقعی کارشناس[^<\n]{0,180}",
            r"\[\s*نام\s+(?:کارشناس|نویسنده|بازبین)[^\]]*\]",
            r"نام\s+(?:کارشناس|بازبین)\s+را\s+پیش\s+از\s+انتشار[^<\n]{0,120}",
        ]:
            for m in re.finditer(pat,raw,re.I):
                placeholder_candidates.append({"id":post_id,"pattern":pat,"match":m.group(0)[:240]})

        if MARKER in raw:
            results.append({"id":post_id,"status":"already_present","title":title_text(post),"verified_marker":True})
            continue

        needs_editorial=("نظر کارشناسی کشاورز بیست" not in raw and "یادداشت تحریریه کشاورز بیست" not in raw)
        block=trust_block(needs_editorial)
        patched=False
        last_error=None

        for attempt in range(1,4):
            if attempt>1:
                time.sleep(1.0*attempt)
                post=get_post(post_id)
                raw=((post.get("content") or {}).get("raw") or "")
                if MARKER in raw:
                    results.append({"id":post_id,"status":"became_present_during_retry","title":title_text(post),"verified_marker":True})
                    patched=True
                    break

            for anchor in choose_anchors(raw):
                try:
                    sr=bridge("content.search",f"growthos-phase16-search-{post_id}-{attempt}",{
                        "target_type":"post","post_id":post_id,"field":"post_content","pattern":anchor,"context":40
                    })
                    if int(sr.get("matches") or 0)!=1 or not sr.get("sha256"):
                        continue
                    pr=bridge("content.patch",f"growthos-phase16-patch-{post_id}-{attempt}",{
                        "target_type":"post","post_id":post_id,"field":"post_content",
                        "old_content":anchor,"new_content":anchor+block,
                        "expected_sha256":sr["sha256"]
                    })
                    verify=get_post(post_id)
                    vraw=((verify.get("content") or {}).get("raw") or "")
                    if MARKER not in vraw or POLICY_URL not in vraw or "روش تهیه و بازبینی" not in vraw:
                        raise RuntimeError("readback missing Phase16 provenance block")
                    results.append({
                      "id":post_id,"status":"patched","title":title_text(post),
                      "editorial_note_added":needs_editorial,
                      "changed":pr.get("changed"),"before_sha256":pr.get("before_sha256"),
                      "after_sha256":pr.get("after_sha256"),"verified_marker":True
                    })
                    patched=True
                    break
                except Exception as exc:
                    last_error=str(exc)
                    continue
            if patched: break

        if not patched:
            raise RuntimeError(last_error or "no unique Bridge-matching anchor could be patched")
    except Exception as exc:
        failures.append({"id":post_id,"error":str(exc)[:500]})

cache=None
try:
    cache=bridge("cache.purge","growthos-phase16-cache-purge-after-retrofit",{})
except Exception as exc:
    cache={"error":str(exc)[:300]}

OUT.parent.mkdir(exist_ok=True)
report={
  "ok":not failures,
  "phase":16,
  "title":"Human Expertise & Editorial Trust — direct Bridge legacy repair",
  "generated_at_utc":NOW,
  "target_count":len(ids),
  "patched_count":sum(1 for x in results if x.get("status")=="patched"),
  "already_present_count":sum(1 for x in results if x.get("status") in {"already_present","became_present_during_retry"}),
  "failure_count":len(failures),
  "failures":failures,
  "placeholder_candidates":placeholder_candidates,
  "results":results,
  "cache_purge":cache,
  "safety":{
    "bridge_route":True,
    "snapshots_created_by_content_patch":True,
    "fake_authors_created":0,
    "fake_reviewers_created":0,
    "named_human_experts_created":0,
    "technical_claims_rewritten":0,
    "price_stock_discount_mutations":0,
    "orders_created":0,
    "messages_sent":0
  }
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ["ok","target_count","patched_count","already_present_count","failure_count"]},ensure_ascii=False))
if failures:
    raise SystemExit(2)
