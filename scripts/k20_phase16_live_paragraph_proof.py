#!/usr/bin/env python3
import os,re,json,requests,subprocess,tempfile,time,html
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
POLICY="https://keshavarz20.com/editorial-policy/"
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase16-live-paragraph-proof/1.0","Cache-Control":"no-cache"})

def get():
 r=S.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit","_fields":"id,link,title,content,modified_gmt"},timeout=90); r.raise_for_status(); return r.json()

def gateway_update(content):
 with tempfile.TemporaryDirectory(prefix="k20-p16-live-proof-") as td:
  req=Path(td)/"request.json"; out=Path(td)/"result.json"
  req.write_text(json.dumps({"action":"post.update","id":PID,"payload":{"content":content}},ensure_ascii=False),encoding="utf-8")
  cp=subprocess.run(["pwsh","-NoLogo","-NoProfile","-File","scripts/Invoke-K20SiteGateway.ps1","-RequestPath",str(req),"-OutputPath",str(out)],text=True,capture_output=True,timeout=300)
  if cp.returncode: raise RuntimeError((cp.stderr or cp.stdout)[-1200:])
  data=json.loads(out.read_text(encoding="utf-8-sig"))
  if data.get("ok") is not True: raise RuntimeError("gateway result not ok")
  return data.get("result") or {}

p=get(); raw=p["content"]["raw"]
# Remove only the known hidden malformed deep-review chain immediately before the exact live editorial heading.
hpat=re.compile(r'<h2[^>]*>\s*نظر کارشناسی کشاورز بیست\s*</h2>',re.I)
m=hpat.search(raw)
if not m: raise SystemExit("exact live editorial heading not found")
before=raw[:m.start()]
start=before.find("<!-- k20-phase16-deep-review-v1 -->")
end=before.rfind("<!-- /k20-phase16-deep-review-v1 -->")
if start>=0 and end>=start:
  end += len("<!-- /k20-phase16-deep-review-v1 -->")
  raw=raw[:start]+raw[end:]
# Re-find live heading, then its immediately following paragraph.
m=hpat.search(raw)
if not m: raise SystemExit("live heading lost after cleanup")
pm=re.search(r'<p[^>]*>([\s\S]*?)</p>',raw[m.end():],re.I)
if not pm: raise SystemExit("live editorial paragraph not found")
p_start=m.end()+pm.start(); p_end=m.end()+pm.end()
oldp=raw[p_start:p_end]
# Idempotency: strip any prior proof payload inside this paragraph.
oldp=re.sub(r'<br><br><strong>بازبینی عمیق فنی:</strong>[\s\S]*?(?=</p>)','',oldp,flags=re.I)
insert='''<br><br><strong>بازبینی عمیق فنی:</strong> عیب‌یابی یکنواختی باید از اندازه‌گیری فشار و دبی شروع شود، نه از تعویض تصادفی قطعه. اختلاف ارتفاع، افت فشار در لوله، گرفتگی، طول زیاد لاترال و تنظیم نامناسب فشار می‌توانند هم‌زمان روی دبی قطره‌چکان‌ها اثر بگذارند. مقایسه نقاط ابتدا، میانه و انتهای زون مسیر تشخیص را کوتاه‌تر می‌کند.<br><strong>چک‌های اجرایی:</strong> فشار ورودی و انتهای زون را در حالت کار اندازه بگیرید؛ دبی چند خروجی نماینده را مقایسه کنید؛ سپس فیلتر، گرفتگی، اختلاف ارتفاع و طول لاترال را بررسی کنید.<br><strong>منابع مرجع تکمیلی:</strong> <a href="https://extension.okstate.edu/fact-sheets/drip-irrigation-systems" rel="nofollow noopener">Oklahoma State University — Drip Irrigation Systems</a> و <a href="https://itrc.org/projects/evals.htm" rel="nofollow noopener">Cal Poly ITRC — Irrigation System Evaluations</a>.<br><strong>روش تهیه و بازبینی:</strong> این بخش با رجوع به منابع دانشگاهی و پژوهشی بازبینی شده است. داده‌های وابسته به فشار، دبی، مدل محصول و شرایط مزرعه باید با وضعیت واقعی همان شبکه تطبیق داده شوند و هیچ بازبین، مدرک یا تجربه میدانی ساختگی به محتوا افزوده نشده است. جزئیات در <a href="https://keshavarz20.com/editorial-policy/">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> آمده است.'''
newp=oldp[:-4]+insert+"</p>"
newraw=raw[:p_start]+newp+raw[p_end:]
gateway_update(newraw)
time.sleep(3)
p2=get(); rendered=p2["content"]["rendered"]
pub=requests.get(p2["link"]+"?k20_phase16_liveproof="+str(int(time.time()*1000)),timeout=90,headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-live-proof/1.0"})
checks={
 "rendered_deep":"بازبینی عمیق فنی" in rendered,
 "rendered_review":"روش تهیه و بازبینی" in rendered,
 "rendered_policy":"/editorial-policy/" in rendered,
 "rendered_itrc":"https://itrc.org/projects/evals.htm" in rendered,
 "public_http":pub.status_code,
 "public_deep":"بازبینی عمیق فنی" in pub.text,
 "public_review":"روش تهیه و بازبینی" in pub.text,
 "public_policy":"/editorial-policy/" in pub.text,
 "public_itrc":"https://itrc.org/projects/evals.htm" in pub.text
}
print(json.dumps({"id":PID,"checks":checks,"modified_gmt":p2.get("modified_gmt")},ensure_ascii=False))
if not all(v is True or v==200 for v in checks.values()): raise SystemExit(2)
