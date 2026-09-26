#!/usr/bin/env python3
import os,re,json,requests,time,hashlib
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
MARK="k20-phase16-deep-live-v1"
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase16-elementor-meta-proof/1.0","Cache-Control":"no-cache"})

def get():
 r=S.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit"},timeout=90); r.raise_for_status(); return r.json()
def put_meta(meta_value):
 r=S.post(f"{BASE}/wp-json/wp/v2/posts/{PID}",json={"meta":{"_elementor_data":meta_value}},timeout=120)
 r.raise_for_status(); return r.json()
def purge(tag):
 r=S.post(BASE+"/wp-json/keshavarz20-ops/v3/execute",json={"action":"cache.purge","request_id":tag,"payload":{}},timeout=120)
 r.raise_for_status()
 try:return r.json()
 except:return {}
def walk_find(x,path="$"):
 hits=[]
 if isinstance(x,dict):
  for k,v in x.items(): hits += walk_find(v,path+"."+str(k))
 elif isinstance(x,list):
  for i,v in enumerate(x): hits += walk_find(v,f"{path}[{i}]")
 elif isinstance(x,str) and "نظر کارشناسی کشاورز بیست" in x and "اگر چند ردیف یا یک بخش مشخص" in x:
  hits.append((path,x))
 return hits
def set_path(root,path,value):
 # path like $[0].elements[0].elements[0].settings.editor
 toks=re.findall(r'\.([A-Za-z0-9_]+)|\[(\d+)\]',path[1:])
 cur=root
 for a,b in toks[:-1]:
  cur=cur[int(b)] if b else cur[a]
 a,b=toks[-1]
 if b: cur[int(b)]=value
 else: cur[a]=value

p=get()
before=p.get("meta",{}).get("_elementor_data")
if not isinstance(before,str) or not before.strip(): raise SystemExit("missing _elementor_data")
tree=json.loads(before)
hits=walk_find(tree)
if len(hits)!=1: raise SystemExit(f"expected 1 live editor hit, got {len(hits)}")
path,editor=hits[0]
# Idempotency.
editor=re.sub(r'<!-- '+re.escape(MARK)+r' -->[\s\S]*?<!-- /'+re.escape(MARK)+r' -->','',editor,flags=re.I)
hpat=re.compile(r'<h2[^>]*>\s*نظر کارشناسی کشاورز بیست\s*</h2>',re.I)
m=hpat.search(editor)
if not m: raise SystemExit("live expert heading absent in Elementor editor")
pm=re.search(r'<p[^>]*>([\s\S]*?)</p>',editor[m.end():],re.I)
if not pm: raise SystemExit("live expert paragraph absent")
p_end=m.end()+pm.end()
addon=f'''\n<!-- {MARK} -->\n<div class="k20-phase16-deep-live" style="margin-top:18px;padding-top:16px;border-top:1px solid rgba(255,255,255,.3)">\n<h3 style="font-size:21px;line-height:1.8;margin:0 0 10px">بازبینی عمیق فنی</h3>\n<p>عیب‌یابی یکنواختی باید از اندازه‌گیری فشار و دبی شروع شود، نه از تعویض تصادفی قطعه. اختلاف ارتفاع، افت فشار در لوله، گرفتگی، طول زیاد لاترال و تنظیم نامناسب فشار می‌توانند هم‌زمان روی دبی قطره‌چکان‌ها اثر بگذارند. مقایسه نقاط ابتدا، میانه و انتهای زون مسیر تشخیص را کوتاه‌تر می‌کند.</p>\n<p><strong>چک‌های اجرایی:</strong> فشار ورودی و انتهای زون را در حالت کار اندازه بگیرید؛ دبی چند خروجی نماینده را مقایسه کنید؛ سپس فیلتر، گرفتگی، اختلاف ارتفاع و طول لاترال را بررسی کنید.</p>\n<p><strong>منابع مرجع تکمیلی:</strong> <a href="https://extension.okstate.edu/fact-sheets/drip-irrigation-systems" rel="nofollow noopener">Oklahoma State University — Drip Irrigation Systems</a> و <a href="https://itrc.org/projects/evals.htm" rel="nofollow noopener">Cal Poly ITRC — Irrigation System Evaluations</a>.</p>\n<p><strong>روش تهیه و بازبینی:</strong> این بخش با رجوع به منابع دانشگاهی و پژوهشی بازبینی شده است. داده‌های وابسته به فشار، دبی، مدل محصول و شرایط مزرعه باید با وضعیت واقعی همان شبکه تطبیق داده شوند. هیچ بازبین، مدرک یا تجربه میدانی ساختگی به محتوا افزوده نشده است. جزئیات در <a href="https://keshavarz20.com/editorial-policy/" style="color:inherit;text-decoration:underline">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> آمده است.</p>\n</div>\n<!-- /{MARK} -->'''
editor2=editor[:p_end]+addon+editor[p_end:]
set_path(tree,path,editor2)
after=json.dumps(tree,ensure_ascii=False,separators=(",",":"))
before_sha=hashlib.sha256(before.encode()).hexdigest()
after_sha=hashlib.sha256(after.encode()).hexdigest()
rolled_back=False
try:
 put_meta(after)
 purge("phase16-elementor-meta-proof-purge")
 time.sleep(3)
 p2=get()
 meta2=p2.get("meta",{}).get("_elementor_data") or ""
 rendered=(p2.get("content") or {}).get("rendered") or ""
 pub=requests.get(p2["link"]+"?k20_p16_meta="+str(int(time.time()*1000)),timeout=90,headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-meta-proof/1.0"})
 checks={
  "meta_marker":MARK in meta2,
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
 ok=all(v is True or v==200 for v in checks.values())
 print(json.dumps({"id":PID,"path":path,"before_sha256":before_sha,"after_sha256":after_sha,"checks":checks},ensure_ascii=False))
 if not ok: raise RuntimeError("verification failed")
except Exception:
 rolled_back=True
 put_meta(before)
 purge("phase16-elementor-meta-proof-rollback-purge")
 time.sleep(2)
 raise
