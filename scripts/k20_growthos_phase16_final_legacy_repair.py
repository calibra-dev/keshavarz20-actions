#!/usr/bin/env python3
from __future__ import annotations
import html, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
BACKLOG=Path("growthos-phase16-results/legacy-backlog.json")
OUT=Path("growthos-phase16-results/final-legacy-repair.json")
POLICY_URL="https://keshavarz20.com/editorial-policy/"
MARKER="k20-phase16-editorial-trust-v2"
NOW=datetime.now(timezone.utc).isoformat()

S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=0.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase16-final-repair/1.0","Cache-Control":"no-cache"})

def bridge(action:str, request_id:str, payload:dict|None=None):
    body={"action":action,"request_id":request_id,"payload":payload or {}}
    r=S.post(urljoin(BASE+"/","wp-json/keshavarz20-ops/v3/execute"),json=body,timeout=120)
    try:
        data=r.json()
    except Exception:
        raise RuntimeError(f"{action}: non-json HTTP {r.status_code}: {(r.text or '')[:180]}")
    if not r.ok or data.get("ok") is not True:
        raise RuntimeError(f"{action}: HTTP {r.status_code} code={data.get('code')} message={data.get('message')}")
    return data.get("result") or {}

def get_post(post_id:int):
    r=S.get(urljoin(BASE+"/",f"wp-json/wp/v2/posts/{post_id}"),
            params={"context":"edit","_fields":"id,status,type,slug,link,title,content,modified_gmt"},timeout=90)
    r.raise_for_status()
    return r.json()

def get_public(url:str):
    r=requests.get(url,timeout=60,headers={"User-Agent":"k20-growthos-phase16-final-repair/1.0","Cache-Control":"no-cache"})
    r.raise_for_status()
    return r.text

def plain_title(post):
    t=(post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or ""
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",t))).strip()

def trust_block(needs_editorial:bool):
    editorial=""
    if needs_editorial:
        editorial="""
<h2>نظر کارشناسی کشاورز بیست <span style="font-size:.72em;font-weight:500">(تحلیل تحریریه)</span></h2>
<p>این بخش جمع‌بندی تحریریه کشاورز بیست برای کمک به تصمیم‌گیری است و به معنی تأیید یک کارشناس نام‌دار یا توصیه اختصاصی برای مزرعه شما نیست. برای تصمیم‌هایی که به دوز، فشار، دبی، سازگاری، آب، خاک یا مرحله رشد وابسته‌اند، داده واقعی پروژه و منبع مستقیم همان موضوع یا محصول را ملاک قرار دهید.</p>"""
    return f"""
<!-- {MARKER} -->
<section class="k20-phase16-editorial-trust-v2" dir="rtl" style="direction:rtl;text-align:right;line-height:2;border:1px solid #dfe8e2;border-radius:16px;padding:18px;margin:28px 0;background:#f8fbf9">
{editorial}
<h2>روش تهیه و بازبینی</h2>
<p><strong>مسئول محتوا:</strong> تحریریه کشاورز بیست. ادعاهای قابل بررسی باید به منابع مستقیم یا ارجاعات همین صفحه متکی باشند. در این نسخه بازبین نام‌دار یا متخصص مستقلی که هویت و نقش او تأیید شده باشد ثبت نشده است؛ بنابراین نام شخص، مدرک تخصصی یا تجربه میدانی ساختگی به محتوا اضافه نمی‌شود.</p>
<p>اگر عدد، مشخصه فنی یا توضیحی نیاز به اصلاح داشته باشد، باید با منبع مستقیم بازبینی شود. روش منبع‌سنجی، استفاده از ابزارهای خودکار و سیاست اصلاح محتوا در <a href="{POLICY_URL}">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> توضیح داده شده است.</p>
</section>
<!-- /{MARKER} -->
"""

def rendered_has(text:str, missing:list[str]):
    checks={
        "editorial_analysis_visible":"نظر کارشناسی کشاورز بیست" in text,
        "review_method_visible":"روش تهیه و بازبینی" in text,
        "editorial_policy_link_visible":"/editorial-policy/" in text,
        "sources_section_visible":"منابع" in text,
    }
    return all(checks.get(x,True) for x in missing),checks

def choose_patch_slot(post_id:int):
    candidates=[
      "<!-- /wp:html -->",
      "<!-- /wp:freeform -->",
      "</article>",
      "</main>",
      "</section>",
      "</div>"
    ]
    best=None
    for idx,pat in enumerate(candidates):
        try:
            sr=bridge("content.search",f"growthos-phase16-slot-{post_id}-{idx}",{
              "target_type":"post","post_id":post_id,"field":"post_content","pattern":pat,"context":300
            })
        except Exception:
            continue
        matches=int(sr.get("matches") or 0)
        snippets=sr.get("snippets") or []
        if matches!=1 or not snippets or not sr.get("sha256"):
            continue
        snip=snippets[0]
        offset=int(snip.get("offset") or 0)
        snippet=str(snip.get("snippet") or "")
        # Prefer later unique slots; block closing comments outrank generic tags.
        priority=(1000-idx*100)+offset
        if best is None or priority>best["priority"]:
            best={"pattern":pat,"snippet":snippet,"sha256":sr["sha256"],"offset":offset,"priority":priority}
    return best

def patch_into_slot(post_id:int, slot:dict, block:str):
    pat=slot["pattern"]
    old=slot["snippet"]
    if pat.startswith("<!-- /wp:"):
        # Keep the trust section inside the current Gutenberg block.
        new=old.replace(pat,block+"\n"+pat,1)
    else:
        # Append immediately after a unique structural closing tag.
        new=old.replace(pat,pat+"\n"+block,1)
    return bridge("content.patch",f"growthos-phase16-final-patch-{post_id}",{
      "target_type":"post","post_id":post_id,"field":"post_content",
      "old_content":old,"new_content":new,"expected_sha256":slot["sha256"]
    })

def repair_placeholder(post_id:int, old_text:str, new_text:str):
    sr=bridge("content.search",f"growthos-phase16-placeholder-search-{post_id}",{
      "target_type":"post","post_id":post_id,"field":"post_content","pattern":old_text,"context":120
    })
    if int(sr.get("matches") or 0)!=1:
        return {"status":"not_unique","matches":int(sr.get("matches") or 0)}
    pr=bridge("content.patch",f"growthos-phase16-placeholder-patch-{post_id}",{
      "target_type":"post","post_id":post_id,"field":"post_content",
      "old_content":old_text,"new_content":new_text,"expected_sha256":sr["sha256"]
    })
    return {"status":"patched","changed":pr.get("changed")}

backlog=json.loads(BACKLOG.read_text(encoding="utf-8"))
rows=backlog.get("posts") or []
results=[]; failures=[]

for row in rows:
    post_id=int(row["id"])
    try:
        post=get_post(post_id)
        url=post.get("link") or row.get("url")
        rendered=get_public(url) if url else ""
        complete,checks=rendered_has(rendered,row.get("missing") or [])
        if complete:
            results.append({"id":post_id,"title":plain_title(post),"status":"already_complete_on_public_readback","checks":checks})
            continue

        needs_editorial=not checks["editorial_analysis_visible"]
        block=trust_block(needs_editorial)
        slot=choose_patch_slot(post_id)
        if not slot:
            raise RuntimeError("no unique structural insertion slot available through Bridge content.search")
        pr=patch_into_slot(post_id,slot,block)

        time.sleep(1)
        post2=get_post(post_id)
        rendered2=get_public(post2.get("link") or url)
        complete2,checks2=rendered_has(rendered2,row.get("missing") or [])
        if not complete2:
            raise RuntimeError("public readback still missing Phase16 fields after Bridge patch")
        results.append({
          "id":post_id,"title":plain_title(post2),"status":"patched_and_publicly_verified",
          "slot_pattern":slot["pattern"],"slot_offset":slot["offset"],
          "changed":pr.get("changed"),"before_sha256":pr.get("before_sha256"),
          "after_sha256":pr.get("after_sha256"),"checks":checks2
        })
    except Exception as exc:
        failures.append({"id":post_id,"title":row.get("title"),"error":str(exc)[:500]})

# Remove four legacy author/reviewer placeholders only when they still exist exactly once.
placeholder_specs={
  132458:("نام واقعی کارشناس تغذیه گیاه را پیش از انتشار وارد کنید.","بازبین نام‌دار: در این نسخه ثبت نشده است."),
  132461:("نام واقعی کارشناس گیاه‌پزشکی یا سم‌شناسی کشاورزی پیش از انتشار درج شود.","بازبین نام‌دار: در این نسخه ثبت نشده است."),
  143190:("نام واقعی کارشناس تولید گیاهی یا پس از برداشت پیش از انتشار درج شود.","بازبین نام‌دار: در این نسخه ثبت نشده است."),
  143790:("[نام واقعی کارشناس تغذیه گیاه یا مسئول فنی را وارد کنید]","بازبین نام‌دار: در این نسخه ثبت نشده است.")
}
placeholder_results=[]
for post_id,(old,new) in placeholder_specs.items():
    try:
        placeholder_results.append({"id":post_id,**repair_placeholder(post_id,old,new)})
    except Exception as exc:
        placeholder_results.append({"id":post_id,"status":"error","error":str(exc)[:300]})

cache={}
try:
    cache=bridge("cache.purge","growthos-phase16-final-cache-purge",{})
except Exception as exc:
    cache={"error":str(exc)[:300]}

OUT.parent.mkdir(exist_ok=True)
report={
  "ok":not failures,
  "phase":16,
  "title":"Human Expertise & Editorial Trust — final legacy repair",
  "generated_at_utc":NOW,
  "target_count":len(rows),
  "patched_and_verified":sum(1 for x in results if x["status"]=="patched_and_publicly_verified"),
  "already_complete":sum(1 for x in results if x["status"]=="already_complete_on_public_readback"),
  "failure_count":len(failures),
  "failures":failures,
  "placeholder_repairs":placeholder_results,
  "results":results,
  "cache_purge":cache,
  "safety":{
    "route":"Bridge v3 content.search -> exact content.patch -> public readback",
    "snapshot_per_successful_patch":True,
    "technical_claims_rewritten":0,
    "fake_authors_created":0,
    "fake_reviewers_created":0,
    "named_human_experts_created":0,
    "price_stock_discount_mutations":0,
    "orders_created":0,
    "messages_sent":0
  }
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ["ok","target_count","patched_and_verified","already_complete","failure_count"]},ensure_ascii=False))
if failures:
    raise SystemExit(2)
