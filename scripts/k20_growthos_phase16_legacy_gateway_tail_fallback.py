#!/usr/bin/env python3
from __future__ import annotations
import html, json, os, re, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
BACKLOG=Path("growthos-phase16-results/legacy-backlog.json")
OUT=Path("growthos-phase16-results/legacy-gateway-tail-fallback.json")
POLICY_URL="https://keshavarz20.com/editorial-policy/"
MARKER="k20-phase16-editorial-trust-v5"
NOW=datetime.now(timezone.utc).isoformat()

S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=0.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase16-tail-fallback/1.0","Cache-Control":"no-cache"})

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
    r=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit","_fields":"id,status,type,slug,link,title,content,modified_gmt"},timeout=90)
    r.raise_for_status(); return r.json()

def get_public(url):
    sep="&" if "?" in url else "?"
    r=requests.get(url+sep+"k20_phase16_v5="+str(int(time.time()*1000)),timeout=60,
        headers={"User-Agent":"k20-growthos-phase16-tail-fallback/1.0","Cache-Control":"no-cache, no-store","Pragma":"no-cache"})
    r.raise_for_status(); return r.text

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

def meets(c,missing): return all(c.get(k,True) for k in missing)

def trust_block(add_editorial):
    editorial=""
    if add_editorial:
        editorial="""
<h2>نظر کارشناسی کشاورز بیست <span style="font-size:.72em;font-weight:500">(تحلیل تحریریه)</span></h2>
<p>این بخش جمع‌بندی تحریریه کشاورز بیست برای کمک به تصمیم‌گیری است و به معنی تأیید یک کارشناس نام‌دار یا توصیه اختصاصی برای مزرعه شما نیست. برای تصمیم‌هایی که به دوز، فشار، دبی، سازگاری، آب، خاک یا مرحله رشد وابسته‌اند، داده واقعی پروژه و منبع مستقیم همان موضوع یا محصول را ملاک قرار دهید.</p>"""
    return f"""
<!-- {MARKER} -->
<section class="k20-phase16-editorial-trust-v5" dir="rtl" style="direction:rtl;text-align:right;line-height:2;border:1px solid #dfe8e2;border-radius:16px;padding:18px;margin:28px 0;background:#f8fbf9">
{editorial}
<h2>روش تهیه و بازبینی</h2>
<p><strong>مسئول محتوا:</strong> تحریریه کشاورز بیست. ادعاهای قابل بررسی باید به منابع مستقیم یا ارجاعات همین صفحه متکی باشند. در این نسخه بازبین نام‌دار یا متخصص مستقلی که هویت و نقش او تأیید شده باشد ثبت نشده است؛ بنابراین نام شخص، مدرک تخصصی یا تجربه میدانی ساختگی به محتوا اضافه نمی‌شود.</p>
<p>اگر عدد، مشخصه فنی یا توضیحی نیاز به اصلاح داشته باشد، باید با منبع مستقیم بازبینی شود. روش منبع‌سنجی، استفاده از ابزارهای خودکار و سیاست اصلاح محتوا در <a href="{POLICY_URL}">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> توضیح داده شده است.</p>
</section>
<!-- /{MARKER} -->
"""

def capture_snapshot(pid):
    markers=[
      "<!-- k20-phase16-editorial-trust-v3 -->",
      "<!-- k20-phase16-editorial-trust-v2 -->",
      "<!-- k20-phase16-editorial-trust-start -->"
    ]
    for i,pat in enumerate(markers):
        sr=bridge("content.search",f"growthos-phase16-v5-snapsearch-{pid}-{i}",{
          "target_type":"post","post_id":pid,"field":"post_content","pattern":pat,"context":40
        })
        if int(sr.get("matches") or 0)==1 and sr.get("sha256"):
            # v3.2 content.patch snapshots before a non-dry-run post_content write.
            result=bridge("content.patch",f"growthos-phase16-v5-snapshot-{pid}",{
              "target_type":"post","post_id":pid,"field":"post_content",
              "old_content":pat,"new_content":pat,"expected_sha256":sr["sha256"]
            })
            return {"captured":True,"anchor":pat,"before_sha256":result.get("before_sha256")}
    return {"captured":False,"reason":"no_unique_prior_phase16_marker"}

def strip_failed_blocks(raw):
    patterns=[
      r"<!-- k20-phase16-editorial-trust-v3 -->[\s\S]*?<!-- /k20-phase16-editorial-trust-v3 -->",
      r"<!-- k20-phase16-editorial-trust-v2 -->[\s\S]*?<!-- /k20-phase16-editorial-trust-v2 -->"
    ]
    removed=0
    out=raw
    for pat in patterns:
        out,n=re.subn(pat,"",out,flags=re.I)
        removed+=n
    return out,removed

def run_legacy_update(pid,new_content):
    with tempfile.TemporaryDirectory(prefix=f"k20-phase16-{pid}-") as td:
        req=Path(td)/"request.json"; res=Path(td)/"result.json"
        req.write_text(json.dumps({
          "action":"post.update",
          "id":pid,
          "payload":{"content":new_content}
        },ensure_ascii=False),encoding="utf-8")
        cp=subprocess.run([
          "pwsh","-NoLogo","-NoProfile","-File","scripts/Invoke-K20SiteGateway.ps1",
          "-RequestPath",str(req),"-OutputPath",str(res)
        ],text=True,capture_output=True,timeout=240)
        if cp.returncode!=0:
            raise RuntimeError("legacy gateway failed: "+(cp.stderr or cp.stdout)[-500:])
        data=json.loads(res.read_text(encoding="utf-8-sig"))
        if data.get("ok") is not True:
            raise RuntimeError("legacy gateway result not ok")
        return data.get("result") or {}

backlog=json.loads(BACKLOG.read_text(encoding="utf-8"))
rows=backlog.get("posts") or []
results=[]; failures=[]

for row in rows:
    pid=int(row["id"])
    try:
        post=get_post(pid); url=post.get("link") or row.get("url")
        before=public_checks(get_public(url))
        if meets(before,row.get("missing") or []):
            results.append({"id":pid,"title":title_text(post),"status":"already_complete","checks":before})
            continue
        raw=((post.get("content") or {}).get("raw") or "")
        if not raw:
            raise RuntimeError("empty raw content")
        snapshot=capture_snapshot(pid)
        cleaned,removed=strip_failed_blocks(raw)
        if MARKER in cleaned:
            # Prevent duplicate tail insertion if a previous attempt completed after read.
            new_content=cleaned
        else:
            new_content=cleaned.rstrip()+"\n\n"+trust_block(not before["editorial_analysis_visible"])+"\n"
        gateway=run_legacy_update(pid,new_content)
        post2=get_post(pid)
        raw2=((post2.get("content") or {}).get("raw") or "")
        if MARKER not in raw2:
            raise RuntimeError("post.update raw readback missing v5 marker")
        results.append({
          "id":pid,"title":title_text(post2),"status":"updated_raw_verified",
          "url":post2.get("link") or url,"removed_failed_blocks":removed,
          "snapshot":snapshot,"modified_gmt":gateway.get("modified_gmt")
        })
    except Exception as exc:
        failures.append({"id":pid,"title":row.get("title"),"error":str(exc)[:700]})

try: cache=bridge("cache.purge","growthos-phase16-v5-cache-purge",{})
except Exception as exc: cache={"error":str(exc)[:300]}
time.sleep(5)

public_fail=[]
for item in results:
    if item.get("status")!="updated_raw_verified": continue
    row=next(x for x in rows if int(x["id"])==int(item["id"]))
    try:
        c=public_checks(get_public(item["url"])); item["public_checks"]=c
        if meets(c,row.get("missing") or []): item["status"]="updated_and_publicly_verified"
        else: public_fail.append({"id":item["id"],"checks":c,"missing":row.get("missing")})
    except Exception as exc:
        public_fail.append({"id":item["id"],"error":str(exc)[:300]})

all_fail=failures+public_fail
report={
  "ok":not all_fail,
  "phase":16,
  "title":"Human Expertise & Editorial Trust — legacy gateway tail fallback",
  "generated_at_utc":NOW,
  "target_count":len(rows),
  "updated_and_publicly_verified":sum(1 for x in results if x.get("status")=="updated_and_publicly_verified"),
  "already_complete":sum(1 for x in results if x.get("status")=="already_complete"),
  "failure_count":len(all_fail),
  "failures":all_fail,
  "results":results,
  "cache_purge":cache,
  "fallback_reason":"Bridge exact patches were stored in raw post_content but did not render publicly for these remaining templates. The existing allow-listed legacy post.update gateway is used only for the unresolved posts.",
  "safety":{
    "legacy_gateway_allowlist_used":True,
    "snapshot_attempted_before_each_update":True,
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
print(json.dumps({k:report[k] for k in ["ok","target_count","updated_and_publicly_verified","already_complete","failure_count"]},ensure_ascii=False))
if not report["ok"]: raise SystemExit(2)
