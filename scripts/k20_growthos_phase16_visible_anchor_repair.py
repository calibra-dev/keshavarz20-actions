#!/usr/bin/env python3
from __future__ import annotations
import html, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
BACKLOG=Path("growthos-phase16-results/legacy-backlog.json")
OUT=Path("growthos-phase16-results/visible-anchor-repair.json")
POLICY_URL="https://keshavarz20.com/editorial-policy/"
MARKER="k20-phase16-editorial-trust-v4"
NOW=datetime.now(timezone.utc).isoformat()

S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=0.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase16-visible-anchor/1.0","Cache-Control":"no-cache"})

def bridge(action,request_id,payload=None,dry_run=False):
    body={"action":action,"request_id":request_id,"payload":payload or {}}
    if dry_run: body["dry_run"]=True
    r=S.post(BASE+"/wp-json/keshavarz20-ops/v3/execute",json=body,timeout=120)
    try: data=r.json()
    except Exception: raise RuntimeError(f"{action}: non-json HTTP {r.status_code}: {(r.text or '')[:180]}")
    if not r.ok or data.get("ok") is not True:
        raise RuntimeError(f"{action}: HTTP {r.status_code} code={data.get('code')} message={data.get('message')}")
    return data.get("result") or {}

def get_post(pid):
    r=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit","_fields":"id,status,type,slug,link,title,content"},timeout=90)
    r.raise_for_status(); return r.json()

def get_public(url):
    sep="&" if "?" in url else "?"
    r=requests.get(url+sep+"k20_phase16_v4="+str(int(time.time()*1000)),timeout=60,
        headers={"User-Agent":"k20-growthos-phase16-visible-anchor/1.0","Cache-Control":"no-cache, no-store","Pragma":"no-cache"})
    r.raise_for_status(); return r.text

def clean_title(post):
    t=(post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or ""
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",t))).strip()

def checks(text):
    return {
      "sources_section_visible":"منابع" in text,
      "editorial_analysis_visible":"نظر کارشناسی کشاورز بیست" in text,
      "review_method_visible":"روش تهیه و بازبینی" in text,
      "editorial_policy_link_visible":"/editorial-policy/" in text
    }

def meets(c,missing): return all(c.get(k,True) for k in missing)

def block(add_editorial):
    editorial=""
    if add_editorial:
        editorial="""
<h2>نظر کارشناسی کشاورز بیست <span style="font-size:.72em;font-weight:500">(تحلیل تحریریه)</span></h2>
<p>این بخش جمع‌بندی تحریریه کشاورز بیست برای کمک به تصمیم‌گیری است و به معنی تأیید یک کارشناس نام‌دار یا توصیه اختصاصی برای مزرعه شما نیست. برای تصمیم‌هایی که به دوز، فشار، دبی، سازگاری، آب، خاک یا مرحله رشد وابسته‌اند، داده واقعی پروژه و منبع مستقیم همان موضوع یا محصول را ملاک قرار دهید.</p>"""
    return f"""
<!-- {MARKER} -->
<section class="k20-phase16-editorial-trust-v4" dir="rtl" style="direction:rtl;text-align:right;line-height:2;border:1px solid #dfe8e2;border-radius:16px;padding:18px;margin:28px 0;background:#f8fbf9">
{editorial}
<h2>روش تهیه و بازبینی</h2>
<p><strong>مسئول محتوا:</strong> تحریریه کشاورز بیست. ادعاهای قابل بررسی باید به منابع مستقیم یا ارجاعات همین صفحه متکی باشند. در این نسخه بازبین نام‌دار یا متخصص مستقلی که هویت و نقش او تأیید شده باشد ثبت نشده است؛ بنابراین نام شخص، مدرک تخصصی یا تجربه میدانی ساختگی به محتوا اضافه نمی‌شود.</p>
<p>اگر عدد، مشخصه فنی یا توضیحی نیاز به اصلاح داشته باشد، باید با منبع مستقیم بازبینی شود. روش منبع‌سنجی، استفاده از ابزارهای خودکار و سیاست اصلاح محتوا در <a href="{POLICY_URL}">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> توضیح داده شده است.</p>
</section>
<!-- /{MARKER} -->
"""

CLOSERS=["<!-- /wp:html -->","<!-- /wp:group -->","<!-- /wp:paragraph -->","<!-- /wp:list -->","</section>","</article>","</aside>","</details>","</table>","</ul>","</ol>","</div>","</p>"]

def unique_anchor(pid,term):
    sr=bridge("content.search",f"growthos-phase16-v4-term-{pid}",{
      "target_type":"post","post_id":pid,"field":"post_content","pattern":term,"context":300
    })
    snippets=sr.get("snippets") or []
    for sn in reversed(snippets):
        s=str(sn.get("snippet") or "")
        if not s: continue
        pos=s.rfind(term)
        if pos<0: continue
        ends=[]
        for closer in CLOSERS:
            p=s.find(closer,pos)
            if p>=0: ends.append((p+len(closer),closer))
        if not ends: continue
        ends.sort(reverse=True)
        for end,closer in ends:
            for span in (700,900,1100):
                start=max(0,end-span); cand=s[start:end]
                if len(cand)<60: continue
                chk=bridge("content.search",f"growthos-phase16-v4-anchor-{pid}-{end}-{span}",{
                  "target_type":"post","post_id":pid,"field":"post_content","pattern":cand,"context":40
                })
                if int(chk.get("matches") or 0)==1 and chk.get("sha256"):
                    return {"candidate":cand,"sha256":chk["sha256"],"closer":closer,"offset":sn.get("offset")}
    return None

def apply(pid,row):
    post=get_post(pid); url=post.get("link") or row.get("url")
    before=checks(get_public(url))
    if meets(before,row.get("missing") or []):
        return {"id":pid,"status":"already_complete","title":clean_title(post),"checks":before}

    # Use only anchors already proven visible by the public page.
    terms=[]
    if before["editorial_analysis_visible"]:
        terms.append("نظر کارشناسی کشاورز بیست")
    if "جمع‌بندی" in get_public(url):
        terms.append("جمع‌بندی")
    if not terms:
        # Last-resort visible heading only for the old Ethephon article.
        terms.append("منابع")

    anchor=None; chosen=None
    for term in terms:
        anchor=unique_anchor(pid,term)
        if anchor:
            chosen=term; break
    if not anchor:
        raise RuntimeError("no unique visible anchor available")

    b=block(not before["editorial_analysis_visible"])
    old=anchor["candidate"]; new=old+"\n"+b
    dry=bridge("content.patch",f"growthos-phase16-v4-dry-{pid}",{
      "target_type":"post","post_id":pid,"field":"post_content","old_content":old,"new_content":new,"expected_sha256":anchor["sha256"]
    },dry_run=True)
    if not dry.get("planned"): raise RuntimeError("dry-run was not planned")
    live=bridge("content.patch",f"growthos-phase16-v4-live-{pid}",{
      "target_type":"post","post_id":pid,"field":"post_content","old_content":old,"new_content":new,"expected_sha256":anchor["sha256"]
    })
    raw=bridge("content.search",f"growthos-phase16-v4-verifyraw-{pid}",{
      "target_type":"post","post_id":pid,"field":"post_content","pattern":MARKER,"context":40
    })
    if int(raw.get("matches") or 0)<1: raise RuntimeError("raw marker missing after patch")
    return {"id":pid,"status":"patched_raw_verified","title":clean_title(post),"url":url,"term":chosen,"closer":anchor["closer"],"changed":live.get("changed"),"before":before}

backlog=json.loads(BACKLOG.read_text(encoding="utf-8"))
rows=backlog.get("posts") or []
results=[]; failures=[]
for row in rows:
    pid=int(row["id"])
    try: results.append(apply(pid,row))
    except Exception as exc: failures.append({"id":pid,"title":row.get("title"),"error":str(exc)[:500]})

try: cache=bridge("cache.purge","growthos-phase16-v4-cache-purge",{})
except Exception as exc: cache={"error":str(exc)[:300]}
time.sleep(4)

public_fail=[]
for item in results:
    if item.get("status")!="patched_raw_verified": continue
    row=next(x for x in rows if int(x["id"])==int(item["id"]))
    try:
        c=checks(get_public(item["url"])); item["public_checks"]=c
        if meets(c,row.get("missing") or []): item["status"]="patched_and_publicly_verified"
        else: public_fail.append({"id":item["id"],"checks":c,"missing":row.get("missing")})
    except Exception as exc: public_fail.append({"id":item["id"],"error":str(exc)[:300]})

all_fail=failures+public_fail
report={
  "ok":not all_fail,
  "phase":16,
  "title":"Human Expertise & Editorial Trust — visible anchor repair",
  "generated_at_utc":NOW,
  "target_count":len(rows),
  "patched_and_publicly_verified":sum(1 for x in results if x.get("status")=="patched_and_publicly_verified"),
  "already_complete":sum(1 for x in results if x.get("status")=="already_complete"),
  "failure_count":len(all_fail),
  "failures":all_fail,
  "results":results,
  "cache_purge":cache,
  "safety":{"technical_claims_rewritten":0,"fake_authors_created":0,"fake_reviewers_created":0,"price_stock_discount_mutations":0,"orders_created":0,"messages_sent":0}
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ["ok","target_count","patched_and_publicly_verified","already_complete","failure_count"]},ensure_ascii=False))
if not report["ok"]: raise SystemExit(2)
