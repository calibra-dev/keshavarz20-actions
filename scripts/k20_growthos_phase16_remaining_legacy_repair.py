#!/usr/bin/env python3
from __future__ import annotations
import html, json, os, re, time, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
BACKLOG=Path("growthos-phase16-results/legacy-backlog.json")
OUT=Path("growthos-phase16-results/remaining-legacy-repair.json")
POLICY_URL="https://keshavarz20.com/editorial-policy/"
MARKER="k20-phase16-editorial-trust-v3"
NOW=datetime.now(timezone.utc).isoformat()

S=requests.Session()
S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=0.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase16-remaining-repair/1.0","Cache-Control":"no-cache"})

def bridge(action,request_id,payload=None,dry_run=False):
    body={"action":action,"request_id":request_id,"payload":payload or {}}
    if dry_run:
        body["dry_run"]=True
    r=S.post(BASE+"/wp-json/keshavarz20-ops/v3/execute",json=body,timeout=120)
    try:
        data=r.json()
    except Exception:
        raise RuntimeError(f"{action}: non-json HTTP {r.status_code}: {(r.text or '')[:180]}")
    if not r.ok or data.get("ok") is not True:
        raise RuntimeError(f"{action}: HTTP {r.status_code} code={data.get('code')} message={data.get('message')}")
    return data.get("result") or {}

def get_post(post_id):
    r=S.get(f"{BASE}/wp-json/wp/v2/posts/{post_id}",params={"context":"edit","_fields":"id,status,type,slug,link,title,content,modified_gmt"},timeout=90)
    r.raise_for_status()
    return r.json()

def get_public(url):
    sep="&" if "?" in url else "?"
    bust=f"{sep}k20_phase16_verify={int(time.time()*1000)}"
    r=requests.get(url+bust,timeout=60,headers={"User-Agent":"k20-growthos-phase16-remaining-repair/1.0","Cache-Control":"no-cache, no-store","Pragma":"no-cache"})
    r.raise_for_status()
    return r.text

def title_text(post):
    t=(post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or ""
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",t))).strip()

def public_checks(text):
    return {
      "sources_section_visible":"منابع" in text,
      "editorial_analysis_visible":"نظر کارشناسی کشاورز بیست" in text,
      "review_method_visible":"روش تهیه و بازبینی" in text,
      "editorial_policy_link_visible":"/editorial-policy/" in text
    }

def meets(checks,missing):
    return all(checks.get(k,True) for k in missing)

def trust_block(add_editorial):
    editorial=""
    if add_editorial:
        editorial="""
<h2>نظر کارشناسی کشاورز بیست <span style="font-size:.72em;font-weight:500">(تحلیل تحریریه)</span></h2>
<p>این بخش جمع‌بندی تحریریه کشاورز بیست برای کمک به تصمیم‌گیری است و به معنی تأیید یک کارشناس نام‌دار یا توصیه اختصاصی برای مزرعه شما نیست. برای تصمیم‌هایی که به دوز، فشار، دبی، سازگاری، آب، خاک یا مرحله رشد وابسته‌اند، داده واقعی پروژه و منبع مستقیم همان موضوع یا محصول را ملاک قرار دهید.</p>"""
    return f"""
<!-- {MARKER} -->
<section class="k20-phase16-editorial-trust-v3" dir="rtl" style="direction:rtl;text-align:right;line-height:2;border:1px solid #dfe8e2;border-radius:16px;padding:18px;margin:28px 0;background:#f8fbf9">
{editorial}
<h2>روش تهیه و بازبینی</h2>
<p><strong>مسئول محتوا:</strong> تحریریه کشاورز بیست. ادعاهای قابل بررسی باید به منابع مستقیم یا ارجاعات همین صفحه متکی باشند. در این نسخه بازبین نام‌دار یا متخصص مستقلی که هویت و نقش او تأیید شده باشد ثبت نشده است؛ بنابراین نام شخص، مدرک تخصصی یا تجربه میدانی ساختگی به محتوا اضافه نمی‌شود.</p>
<p>اگر عدد، مشخصه فنی یا توضیحی نیاز به اصلاح داشته باشد، باید با منبع مستقیم بازبینی شود. روش منبع‌سنجی، استفاده از ابزارهای خودکار و سیاست اصلاح محتوا در <a href="{POLICY_URL}">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> توضیح داده شده است.</p>
</section>
<!-- /{MARKER} -->
"""

CLOSERS=[
  "<!-- /wp:html -->","<!-- /wp:group -->","<!-- /wp:columns -->","<!-- /wp:column -->",
  "<!-- /wp:paragraph -->","<!-- /wp:list -->","<!-- /wp:table -->","<!-- /wp:details -->",
  "</section>","</article>","</aside>","</details>","</table>","</ul>","</ol>","</div>","</p>"
]

def unique_safe_anchor(post_id):
    search_terms=["منابع","جمع‌بندی","نظر کارشناسی کشاورز بیست"]
    for term_idx,term in enumerate(search_terms):
        sr=bridge("content.search",f"growthos-phase16-find-{post_id}-{term_idx}",{
          "target_type":"post","post_id":post_id,"field":"post_content","pattern":term,"context":300
        })
        snippets=sr.get("snippets") or []
        # Prefer the last occurrence, which is normally nearest the article footer/source block.
        for sn in reversed(snippets):
            snippet=str(sn.get("snippet") or "")
            if not snippet:
                continue
            pos=snippet.rfind(term)
            if pos<0:
                pos=0
            ends=[]
            for closer in CLOSERS:
                p=snippet.find(closer,pos)
                if p>=0:
                    ends.append((p+len(closer),closer))
            if not ends:
                continue
            # Prefer the farthest safe close after the term to avoid inserting mid-section.
            ends.sort(reverse=True)
            for end,closer in ends[:5]:
                for span in (700,900,1100,1400):
                    start=max(0,end-span)
                    candidate=snippet[start:end]
                    if len(candidate)<40:
                        continue
                    chk=bridge("content.search",f"growthos-phase16-anchor-{post_id}-{term_idx}-{end}-{span}",{
                      "target_type":"post","post_id":post_id,"field":"post_content","pattern":candidate,"context":40
                    })
                    if int(chk.get("matches") or 0)==1 and chk.get("sha256"):
                        return {
                          "candidate":candidate,
                          "sha256":chk["sha256"],
                          "term":term,
                          "closer":closer,
                          "source_offset":sn.get("offset")
                        }
    return None

def apply_one(post_id,row):
    post=get_post(post_id)
    url=post.get("link") or row.get("url")
    public=get_public(url)
    before_checks=public_checks(public)
    missing=row.get("missing") or []
    if meets(before_checks,missing):
        return {"id":post_id,"title":title_text(post),"status":"already_complete","before_checks":before_checks}

    anchor=unique_safe_anchor(post_id)
    if not anchor:
        raise RuntimeError("could not derive unique safe visible anchor from Bridge content.search")

    block=trust_block(not before_checks["editorial_analysis_visible"])
    old=anchor["candidate"]
    new=old+"\n"+block

    # Prove exact patchability immediately before the live write.
    dry=bridge("content.patch",f"growthos-phase16-dry-{post_id}",{
      "target_type":"post","post_id":post_id,"field":"post_content",
      "old_content":old,"new_content":new,"expected_sha256":anchor["sha256"]
    },dry_run=True)
    if not dry.get("planned"):
        raise RuntimeError("Bridge dry-run did not return planned=true")

    live=bridge("content.patch",f"growthos-phase16-live-{post_id}",{
      "target_type":"post","post_id":post_id,"field":"post_content",
      "old_content":old,"new_content":new,"expected_sha256":anchor["sha256"]
    })

    raw_verify=bridge("content.search",f"growthos-phase16-rawverify-{post_id}",{
      "target_type":"post","post_id":post_id,"field":"post_content","pattern":MARKER,"context":40
    })
    if int(raw_verify.get("matches") or 0)<1:
        raise RuntimeError("raw Bridge readback missing v3 marker")

    return {
      "id":post_id,"title":title_text(post),"status":"patched_raw_verified",
      "anchor_term":anchor["term"],"anchor_closer":anchor["closer"],
      "changed":live.get("changed"),"before_sha256":live.get("before_sha256"),
      "after_sha256":live.get("after_sha256"),"before_checks":before_checks,
      "url":url
    }

backlog=json.loads(BACKLOG.read_text(encoding="utf-8"))
rows=backlog.get("posts") or []
results=[]; failures=[]

for row in rows:
    pid=int(row["id"])
    try:
        results.append(apply_one(pid,row))
    except Exception as exc:
        failures.append({"id":pid,"title":row.get("title"),"error":str(exc)[:500]})

# Purge after all successful writes so public verification does not race a stale full-page cache.
cache={}
try:
    cache=bridge("cache.purge","growthos-phase16-remaining-cache-purge",{})
except Exception as exc:
    cache={"error":str(exc)[:300]}

time.sleep(3)
public_failures=[]
for item in results:
    if item.get("status")!="patched_raw_verified":
        continue
    try:
        row=next(x for x in rows if int(x["id"])==int(item["id"]))
        text=get_public(item["url"])
        checks=public_checks(text)
        item["public_checks"]=checks
        if not meets(checks,row.get("missing") or []):
            public_failures.append({"id":item["id"],"checks":checks,"missing":row.get("missing")})
        else:
            item["status"]="patched_and_publicly_verified"
    except Exception as exc:
        public_failures.append({"id":item["id"],"error":str(exc)[:300]})

# Verify the four previously repaired fake-reviewer placeholders no longer remain.
placeholder_specs={
  132458:"نام واقعی کارشناس تغذیه گیاه را پیش از انتشار وارد کنید.",
  132461:"نام واقعی کارشناس گیاه‌پزشکی یا سم‌شناسی کشاورزی پیش از انتشار درج شود.",
  143190:"نام واقعی کارشناس تولید گیاهی یا پس از برداشت پیش از انتشار درج شود.",
  143790:"[نام واقعی کارشناس تغذیه گیاه یا مسئول فنی را وارد کنید]"
}
placeholder_remaining=[]
for pid,pat in placeholder_specs.items():
    try:
        sr=bridge("content.search",f"growthos-phase16-placeholder-verify-{pid}",{
          "target_type":"post","post_id":pid,"field":"post_content","pattern":pat,"context":40
        })
        if int(sr.get("matches") or 0)>0:
            placeholder_remaining.append({"id":pid,"matches":int(sr.get("matches") or 0)})
    except Exception as exc:
        placeholder_remaining.append({"id":pid,"error":str(exc)[:200]})

all_failures=failures+public_failures
report={
  "ok":not all_failures and not placeholder_remaining,
  "phase":16,
  "title":"Human Expertise & Editorial Trust — remaining legacy repair",
  "generated_at_utc":NOW,
  "target_count":len(rows),
  "patched_and_publicly_verified":sum(1 for x in results if x.get("status")=="patched_and_publicly_verified"),
  "already_complete":sum(1 for x in results if x.get("status")=="already_complete"),
  "failure_count":len(all_failures),
  "failures":all_failures,
  "placeholder_remaining":placeholder_remaining,
  "results":results,
  "cache_purge":cache,
  "safety":{
    "route":"Bridge v3 content.search -> dry-run exact content.patch -> live content.patch -> raw readback -> cache purge -> public readback",
    "snapshot_per_live_patch":True,
    "technical_claims_rewritten":0,
    "fake_authors_created":0,
    "fake_reviewers_created":0,
    "named_human_experts_created":0,
    "price_stock_discount_mutations":0,
    "orders_created":0,
    "messages_sent":0
  }
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ["ok","target_count","patched_and_publicly_verified","already_complete","failure_count"]},ensure_ascii=False))
if not report["ok"]:
    raise SystemExit(2)
