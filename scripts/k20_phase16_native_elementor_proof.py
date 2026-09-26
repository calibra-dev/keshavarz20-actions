#!/usr/bin/env python3
import os,re,json,requests,time,hashlib
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
MARK="k20-phase16-native-elementor-v1"

S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase16-native-elementor-proof/1.0","Cache-Control":"no-cache"})

def get_post():
    r=S.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit"},timeout=90)
    r.raise_for_status(); return r.json()

def bridge(action,request_id,payload=None,id=None):
    body={"action":action,"request_id":request_id,"payload":payload or {}}
    if id is not None: body["id"]=id
    r=S.post(BASE+"/wp-json/keshavarz20-ops/v3/execute",json=body,timeout=180)
    try:data=r.json()
    except Exception: raise RuntimeError(f"{action}: non-json HTTP {r.status_code}: {(r.text or '')[:200]}")
    if not r.ok or data.get("ok") is not True:
        raise RuntimeError(f"{action}: HTTP {r.status_code} code={data.get('code')} message={data.get('message')} result={str(data.get('result'))[:300]}")
    return data.get("result") or {}

def walk_nodes(x):
    if isinstance(x,list):
        for v in x: yield from walk_nodes(v)
    elif isinstance(x,dict):
        if x.get("id"): yield x
        for v in x.get("elements") or []: yield from walk_nodes(v)

def find_editor(tree):
    hits=[]
    for n in walk_nodes(tree):
        ed=(n.get("settings") or {}).get("editor")
        if isinstance(ed,str) and "نظر کارشناسی کشاورز بیست" in ed and "اگر چند ردیف یا یک بخش مشخص" in ed:
            hits.append((n,ed))
    if len(hits)!=1: raise RuntimeError(f"expected 1 target editor, got {len(hits)}")
    return hits[0]

def make_editor(editor):
    editor=re.sub(r'<!-- '+re.escape(MARK)+r' -->[\s\S]*?<!-- /'+re.escape(MARK)+r' -->','',editor,flags=re.I)
    h=re.search(r'<h2[^>]*>\s*نظر کارشناسی کشاورز بیست\s*</h2>',editor,re.I)
    if not h: raise RuntimeError("expert heading missing")
    p=re.search(r'<p[^>]*>[\s\S]*?</p>',editor[h.end():],re.I)
    if not p: raise RuntimeError("expert paragraph missing")
    pos=h.end()+p.end()
    addon=f'''\n<!-- {MARK} -->\n<div class="k20-phase16-deep-live" style="margin-top:18px;padding-top:16px;border-top:1px solid rgba(255,255,255,.3)">\n<h3 style="font-size:21px;line-height:1.8;margin:0 0 10px">بازبینی عمیق فنی</h3>\n<p>عیب‌یابی یکنواختی باید از اندازه‌گیری فشار و دبی شروع شود، نه از تعویض تصادفی قطعه. اختلاف ارتفاع، افت فشار در لوله، گرفتگی، طول زیاد لاترال و تنظیم نامناسب فشار می‌توانند هم‌زمان روی دبی قطره‌چکان‌ها اثر بگذارند. مقایسه نقاط ابتدا، میانه و انتهای زون مسیر تشخیص را کوتاه‌تر می‌کند.</p>\n<p><strong>چک‌های اجرایی:</strong> فشار ورودی و انتهای زون را در حالت کار اندازه بگیرید؛ دبی چند خروجی نماینده را مقایسه کنید؛ سپس فیلتر، گرفتگی، اختلاف ارتفاع و طول لاترال را بررسی کنید.</p>\n<p><strong>منابع مرجع تکمیلی:</strong> <a href="https://extension.okstate.edu/fact-sheets/drip-irrigation-systems" rel="nofollow noopener">Oklahoma State University — Drip Irrigation Systems</a> و <a href="https://itrc.org/projects/evals.htm" rel="nofollow noopener">Cal Poly ITRC — Irrigation System Evaluations</a>.</p>\n<p><strong>روش تهیه و بازبینی:</strong> این بخش با رجوع به منابع دانشگاهی و پژوهشی بازبینی شده است. داده‌های وابسته به فشار، دبی، مدل محصول و شرایط مزرعه باید با وضعیت واقعی همان شبکه تطبیق داده شوند. هیچ بازبین، مدرک یا تجربه میدانی ساختگی به محتوا افزوده نشده است. جزئیات در <a href="https://keshavarz20.com/editorial-policy/" style="color:inherit;text-decoration:underline">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> آمده است.</p>\n</div>\n<!-- /{MARK} -->'''
    return editor[:pos]+addon+editor[pos:]

p=get_post()
meta=(p.get("meta") or {}).get("_elementor_data")
if not isinstance(meta,str) or not meta: raise SystemExit("missing elementor data")
tree=json.loads(meta)
node,before=find_editor(tree)
eid=node["id"]
after=make_editor(before)
if before==after: raise SystemExit("no editor change planned")
changed=False
try:
    result=bridge("elementor.structure","phase16-native-elementor-proof-145235",{
        "operation":"update_settings",
        "element_id":eid,
        "settings":{"editor":after}
    },PID)
    changed=True
    bridge("cache.purge","phase16-native-elementor-proof-purge",{})
    time.sleep(3)
    p2=get_post()
    rendered=(p2.get("content") or {}).get("rendered") or ""
    meta2=(p2.get("meta") or {}).get("_elementor_data") or ""
    pub=requests.get(p2["link"]+"?k20_p16_native="+str(int(time.time()*1000)),timeout=90,headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-native-proof/1.0"})
    checks={
      "element_id":eid,
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
    ok=all(v is True or v==200 or k=="element_id" for k,v in checks.items())
    print(json.dumps({"id":PID,"bridge_result":result,"checks":checks},ensure_ascii=False))
    if not ok: raise RuntimeError("native Elementor verification failed")
except Exception:
    if changed:
        try:
            bridge("elementor.structure","phase16-native-elementor-proof-rollback-145235",{
                "operation":"update_settings",
                "element_id":eid,
                "settings":{"editor":before}
            },PID)
            bridge("cache.purge","phase16-native-elementor-proof-rollback-purge",{})
        except Exception as rb:
            print("ROLLBACK_ERROR",repr(rb))
    raise
