#!/usr/bin/env python3
from __future__ import annotations
import os,re,json,requests,time,hashlib
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
POLICY="https://keshavarz20.com/editorial-policy/"
MARK="k20-phase16-native-elementor-v1"
OUT=Path("growthos-phase16-results/native-elementor-completion.json")

POSTS={
142587:{
 "analysis":"اتفون یک تنظیم‌کننده رشد گیاهی است و اثر آن به مرحله بلوغ میوه، دما، وضعیت تنش گیاه و برچسب همان فرآورده وابسته است. برای گوجه‌فرنگی، منبع EPA نشان می‌دهد کاربرد برچسب‌محور می‌تواند رسیدگی را جلو بیندازد و یکنواخت‌تر کند؛ اما دوز، زمان مصرف، فاصله تا برداشت و محدودیت‌ها باید فقط از برچسب ثبت‌شده همان محصول و ضوابط محلی خوانده شوند. بنابراین این مقاله نباید نسخه عمومی دوز مصرف تلقی شود.",
 "checks":["مرحله بلوغ میوه قبل از تصمیم به مصرف مشخص شود.","تنش خشکی، بیماری، ضعف ریشه و دمای بالا قبل از کاربرد بررسی شود.","هیچ دوز یا فاصله تا برداشت از یک برچسب خارجی به محصول ثبت‌شده در ایران تعمیم داده نشود."],
 "sources":[["US EPA — Nufarm Ethephon 2 label index","https://ordspub.epa.gov/ords/pesticides/f?p=PPLS:102:::NO::P102_REG_NUM:228-660"],["US EPA — Ethephon 3 label, tomato directions","https://www3.epa.gov/pesticides/chem_search/ppls/005905-00595-20180123.pdf"]],
 "mode":"standalone"
},
145237:{
 "analysis":"برد کم همیشه به معنی کمبود ظرفیت پمپ نیست. فشار خارج از محدوده طراحی، گرفتگی یا فرسودگی نازل، نشتی و چیدمان نامناسب می‌تواند الگوی پاشش را خراب کند. فشار خیلی زیاد نیز با مه‌پاشی و افزایش تلفات باد، یکنواختی را کاهش می‌دهد.",
 "checks":["فشار دینامیک نزدیک آبپاش در زمان کار اندازه‌گیری شود.","نازل و فیلتر از نظر گرفتگی، فرسودگی و تفاوت سایز بررسی شوند.","چیدمان و هم‌پوشانی آبپاش‌ها و اثر باد جدا از فشار ارزیابی شود."],
 "sources":[["Oklahoma State University — Managing Pressure in Irrigation","https://extension.okstate.edu/fact-sheets/managing-pressure-in-the-home-irrigation-system"],["Colorado State University Extension — Irrigation: Inspecting and Correcting","https://extension.colostate.edu/docs/pubs/crops/04722.pdf"]],
 "mode":"after_expert"
},
145238:{
 "analysis":"برای شیرهای توپی و پروانه‌ای، نشتی یا سفتی می‌تواند از آلودگی در ناحیه آب‌بندی، آسیب یا فرسودگی سیت، دیسک یا آب‌بند، نصب نامناسب یا کارکرد خارج از محدوده طراحی باشد. باز و بسته کردن با نیروی بیشتر بدون تشخیص علت می‌تواند خرابی را تشدید کند.",
 "checks":["وجود جسم خارجی یا رسوب در سطح آب‌بندی بررسی شود.","سیت، دیسک، ساقه و آب‌بندها از نظر سایش یا آسیب بررسی شوند.","فشار و شرایط نصب با محدوده کاری سازنده مقایسه شود."],
 "sources":[["AVK — Double Eccentric Butterfly Valve O&M","https://files.avkvalves.com/updated-ftp/downloads/756_operation_maintenance_2024_af_245137.pdf"],["Bray — Resilient Seated Butterfly Valve IOM","https://www.bray.com/docs/default-source/manuals-guides/iom-manuals/en_iom_3cx.pdf"]],
 "mode":"after_expert"
},
145251:{
 "analysis":"EC شاخصی از بار نمکی محلول است و SAR رابطه سدیم را با کلسیم و منیزیم نشان می‌دهد؛ اما تفسیر این دو عدد بدون توجه به خاک، زهکشی، کیفیت آب، محصول و روش آبیاری می‌تواند گمراه‌کننده باشد. تصمیم مدیریتی باید بر اساس گزارش آزمایشگاه و شرایط مزرعه انجام شود.",
 "checks":["واحد EC و روش آزمایش قبل از مقایسه اعداد کنترل شود.","SAR در کنار EC، خاک و نفوذپذیری تفسیر شود.","ریسک رسوب و گرفتگی جدا از شوری و سدیمی‌شدن بررسی شود."],
 "sources":[["University of Arizona — Water Quality and Uses","https://extension.arizona.edu/publication/arizona-guide-water-quality-and-uses"],["University of Arizona — Soil Quick Guide","https://extension.arizona.edu/publication/soil-quick-guide"]],
 "mode":"after_expert"
},
145253:{
 "analysis":"خطای نمونه‌برداری می‌تواند از خود آزمایشگاه مهم‌تر باشد. نمونه باید نماینده یک ناحیه مدیریتی نسبتاً یکنواخت باشد، از چند زیرنمونه تشکیل شود و عمق نمونه‌گیری با روش توصیه کودی مورد استفاده سازگار باشد. نقاط غیرعادی مثل محل دپو، آبراهه یا لکه‌های کاملاً متفاوت بهتر است جداگانه نمونه‌برداری شوند.",
 "checks":["هر نمونه مرکب از چند زیرنمونه نماینده ناحیه تهیه شود.","عمق نمونه‌گیری ثابت و متناسب با پروتکل آزمایشگاه باشد.","نقاط غیرعادی و سابقه متفاوت مدیریت با نمونه اصلی مخلوط نشوند."],
 "sources":[["Illinois Extension — Soil Sampling","https://extension.illinois.edu/crops/soil-sampling"],["Penn State Extension — Soil Sampling","https://extension.psu.edu/soil-sampling"],["Iowa State Extension — Recipe for Success with Soil Sampling","https://crops.extension.iastate.edu/encyclopedia/recipe-success-soil-sampling"]],
 "mode":"after_expert"
},
145259:{
 "analysis":"ضربه قوچ یک تغییر سریع فشار ناشی از تغییر ناگهانی سرعت جریان است. بستن سریع شیر، توقف پمپ یا تغییر ناگهانی جریان می‌تواند موج فشار ایجاد کند. راهکار مناسب به طول خط، سرعت جریان، جنس و کلاس لوله، آرایش شیرها و تجهیزات حفاظت بستگی دارد و فقط با افزودن یک شیر هوا به‌صورت عمومی حل نمی‌شود.",
 "checks":["سرعت جریان و زمان باز و بسته شدن شیرها بررسی شود.","محل‌های توقف ناگهانی جریان و خاموشی پمپ مشخص شوند.","راهکارهای حفاظت بر اساس طراحی خط و فشار مجاز لوله انتخاب شوند."],
 "sources":[["USDA NRCS — National Engineering Handbook, Sprinkler Irrigation","https://www.wcc.nrcs.usda.gov/ftpref/wntsc/waterMgt/irrigation/NEH15/ch11.pdf"]],
 "mode":"after_expert"
},
145263:{
 "analysis":"محاسبه متراژ از هندسه مزرعه شروع می‌شود، اما انتخاب طول مجاز هر لاترال فقط هندسی نیست. قطر داخلی تیپ، فاصله و دبی خروجی‌ها، فشار ورودی، شیب و مشخصات سازنده محدودیت هیدرولیکی ایجاد می‌کنند. بنابراین خروجی محاسبه‌گر باید برآورد اولیه خرید تلقی شود و طول نهایی با جدول فنی همان تیپ کنترل شود.",
 "checks":["متراژ هندسی از طول ردیف‌ها و فاصله بین ردیف‌ها جداگانه محاسبه شود.","طول هر لاترال با مشخصات فشار، دبی و شیب همان محصول کنترل شود.","تعداد اتصالات با تعداد واقعی خطوط و آرایش مانیفولد تطبیق داده شود."],
 "sources":[["Oklahoma State University — Drip Irrigation Systems","https://extension.okstate.edu/fact-sheets/drip-irrigation-systems"]],
 "mode":"after_expert"
},
145281:{
 "analysis":"در فرتیگیشن، محلول‌بودن کود به‌تنهایی کافی نیست؛ واکنش کود با آب و سایر مواد می‌تواند رسوب ایجاد کند و قطره‌چکان را مسدود کند. کیفیت آب، ترتیب تزریق، سازگاری ترکیبات، زمان تزریق و شست‌وشوی انتهایی باید با هم دیده شوند. تست سازگاری در مقیاس کوچک پیش از اختلاط مخزن اصلی یک کنترل کم‌هزینه و مهم است.",
 "checks":["کیفیت آب و احتمال رسوب قبل از برنامه تزریق بررسی شود.","سازگاری کودها و آب با تست کوچک یا دستور سازنده کنترل شود.","پس از تزریق، زمان کافی برای شست‌وشوی خطوط در نظر گرفته شود."],
 "sources":[["University of Florida IFAS — Tomato Production Using Fertigation Technology","https://edis.ifas.ufl.edu/hs1392"],["University of Florida IFAS — Five Rs of Nutrient Stewardship for Fertigation","https://edis.ifas.ufl.edu/hs1386"]],
 "mode":"after_expert"
},
145330:{
 "analysis":"قطره‌چکان جبران‌کننده فشار در بازه کاری تعریف‌شده می‌تواند دبی را در برابر تغییرات فشار پایدارتر نگه دارد، اما جای طراحی هیدرولیکی را نمی‌گیرد. در زمین شیب‌دار یا خطوط طولانی، اختلاف ارتفاع و افت اصطکاکی باید محاسبه شود و بازه فشار کاری مدل واقعی قطره‌چکان با شرایط خط تطبیق داده شود.",
 "checks":["بازه فشار کاری مدل واقعی PC از دیتاشیت سازنده کنترل شود.","اختلاف ارتفاع و افت فشار خط قبل از انتخاب نوع قطره‌چکان محاسبه شود.","PC به‌عنوان راه‌حل مطلق برای طراحی ضعیف یا گرفتگی معرفی نشود."],
 "sources":[["Oklahoma State University — Drip Irrigation Systems","https://extension.okstate.edu/fact-sheets/drip-irrigation-systems"]],
 "mode":"after_expert"
},
145775:{
 "analysis":"DU یک شاخص میدانی برای دیدن توزیع واقعی آب است و باید با نمونه‌گیری منظم و قابل‌تکرار انجام شود. هدف فقط تولید یک درصد نیست؛ اختلاف فشار، گرفتگی و نقاط کم‌دبی باید از روی داده‌ها قابل‌ردیابی باشند. ثبت محل نمونه‌ها، زمان جمع‌آوری و فشار سیستم باعث می‌شود تست بعدی قابل مقایسه باشد.",
 "checks":["نمونه‌گیری از نقاط نماینده ابتدا، میانه و انتهای خطوط انجام شود.","زمان جمع‌آوری برای همه نمونه‌ها یکسان و ظروف مناسب باشند.","همراه دبی، فشار و محل نمونه ثبت شود تا علت افت یکنواختی قابل پیگیری باشد."],
 "sources":[["Cal Poly ITRC — Irrigation System Evaluations","https://itrc.org/projects/evals.htm"],["Cal Poly ITRC — Irrigation Evaluation Data","https://www.itrc.org/irrevaldata/index.html"]],
 "mode":"after_expert"
}
}

S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase16-native-elementor-batch/1.0","Cache-Control":"no-cache"})

def get_post(pid):
 r=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=90); r.raise_for_status(); return r.json()

def bridge(action,request_id,payload=None,id=None):
 body={"action":action,"request_id":request_id,"payload":payload or {}}
 if id is not None: body["id"]=id
 r=S.post(BASE+"/wp-json/keshavarz20-ops/v3/execute",json=body,timeout=180)
 try:data=r.json()
 except Exception: raise RuntimeError(f"{action}: non-json HTTP {r.status_code}: {(r.text or '')[:160]}")
 if not r.ok or data.get("ok") is not True:
  raise RuntimeError(f"{action}: HTTP {r.status_code} code={data.get('code')} message={data.get('message')}")
 return data.get("result") or {}

def walk_nodes(x):
 if isinstance(x,list):
  for v in x: yield from walk_nodes(v)
 elif isinstance(x,dict):
  if x.get("id"): yield x
  for v in x.get("elements") or []: yield from walk_nodes(v)

def find_main_editor(tree,cfg):
 candidates=[]
 for n in walk_nodes(tree):
  ed=(n.get("settings") or {}).get("editor")
  if not isinstance(ed,str) or len(ed)<1500: continue
  score=len(ed)
  if "نظر کارشناسی کشاورز بیست" in ed: score+=1000000
  if "منابع" in ed: score+=100000
  candidates.append((score,n,ed))
 if not candidates: raise RuntimeError("no substantial Elementor text-editor found")
 candidates.sort(key=lambda x:x[0],reverse=True)
 return candidates[0][1],candidates[0][2]

def addon(cfg):
 lis="".join("<li>"+x+"</li>" for x in cfg["checks"])
 src="".join('<li><a href="'+u+'" rel="nofollow noopener" target="_blank">'+n+'</a></li>' for n,u in cfg["sources"])
 return f'''\n<!-- {MARK} -->\n<div class="k20-phase16-deep-live" style="margin-top:18px;padding-top:16px;border-top:1px solid rgba(255,255,255,.28)">\n<h3 style="font-size:21px;line-height:1.8;margin:0 0 10px">بازبینی عمیق فنی</h3>\n<p>{cfg["analysis"]}</p>\n<h4 style="margin:14px 0 8px">چک‌های اجرایی قبل از تصمیم</h4><ul>{lis}</ul>\n<h4 style="margin:14px 0 8px">منابع مرجع تکمیلی</h4><ul>{src}</ul>\n<h4 style="margin:14px 0 8px">روش تهیه و بازبینی</h4>\n<p>این بخش با رجوع به منابع دانشگاهی، دولتی، مراکز پژوهشی یا مستندات فنی سازنده بازبینی شده است. ادعاهای عددی یا تصمیم‌های وابسته به مدل محصول، مزرعه، آب، خاک، فشار، دبی یا برچسب مصرف باید با داده واقعی همان مورد تطبیق داده شوند. هیچ بازبین، مدرک، تجربه میدانی یا تأییدیه شخصی ساختگی به محتوا افزوده نشده است. جزئیات در <a href="{POLICY}" style="color:inherit;text-decoration:underline">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> آمده است.</p>\n</div>\n<!-- /{MARK} -->'''

def make_editor(editor,cfg):
 editor=re.sub(r'<!-- '+re.escape(MARK)+r' -->[\s\S]*?<!-- /'+re.escape(MARK)+r' -->','',editor,flags=re.I)
 block=addon(cfg)
 if cfg["mode"]=="after_expert":
  h=re.search(r'<h[1-6][^>]*>\s*نظر کارشناسی کشاورز بیست\s*</h[1-6]>',editor,re.I)
  if not h: raise RuntimeError("visible expert heading absent in Elementor source")
  p=re.search(r'<p[^>]*>[\s\S]*?</p>',editor[h.end():],re.I)
  if not p: raise RuntimeError("expert paragraph absent")
  pos=h.end()+p.end()
  return editor[:pos]+block+editor[pos:]
 # Ethephon: add an explicit editorial section immediately before visible sources.
 m=re.search(r'<h[1-6][^>]*>\s*منابع\s*</h[1-6]>',editor,re.I)
 if not m:
  m=re.search(r'منابع',editor,re.I)
 if not m: raise RuntimeError("sources anchor absent for standalone editorial block")
 section='''\n<section style="background:linear-gradient(135deg,#0F3F25,#17653A);color:#fff;border-radius:20px;padding:24px;margin:22px 0"><h2 style="margin-top:0;color:#fff">نظر کارشناسی کشاورز بیست</h2><p>این جمع‌بندی تحریریه برای تصمیم‌گیری آگاهانه است و توصیه اختصاصی مزرعه یا تأیید یک متخصص نام‌دار محسوب نمی‌شود.</p>'''+block+'''</section>\n'''
 return editor[:m.start()]+section+editor[m.start():]

def public_checks(pid,cfg):
 p=get_post(pid)
 rendered=(p.get("content") or {}).get("rendered") or ""
 url=p.get("link")
 pub=requests.get(url+("?k20_p16_final="+str(int(time.time()*1000))),timeout=90,headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-native-batch/1.0"})
 source_urls=[u for _,u in cfg["sources"]]
 checks={
  "rendered_deep":"بازبینی عمیق فنی" in rendered,
  "rendered_review":"روش تهیه و بازبینی" in rendered,
  "rendered_policy":"/editorial-policy/" in rendered,
  "rendered_editorial":"نظر کارشناسی کشاورز بیست" in rendered,
  "rendered_sources":all(u in rendered for u in source_urls),
  "public_http":pub.status_code,
  "public_deep":"بازبینی عمیق فنی" in pub.text,
  "public_review":"روش تهیه و بازبینی" in pub.text,
  "public_policy":"/editorial-policy/" in pub.text,
  "public_editorial":"نظر کارشناسی کشاورز بیست" in pub.text,
  "public_sources":all(u in pub.text for u in source_urls)
 }
 return checks

results=[]; failures=[]; originals={}
# 145235 was already natively proven and is intentionally not rewritten here.
proven_cfg={"sources":[["Oklahoma State University — Drip Irrigation Systems","https://extension.okstate.edu/fact-sheets/drip-irrigation-systems"],["Cal Poly ITRC — Irrigation System Evaluations","https://itrc.org/projects/evals.htm"]]}
try:
 c235=public_checks(145235,proven_cfg)
 results.append({"id":145235,"status":"already_native_verified","checks":c235})
 if not all(v is True or v==200 for v in c235.values()): failures.append({"id":145235,"error":"previous native proof no longer verifies","checks":c235})
except Exception as exc:
 failures.append({"id":145235,"error":str(exc)[:500]})

for pid,cfg in POSTS.items():
 try:
  p=get_post(pid)
  meta=(p.get("meta") or {}).get("_elementor_data")
  if not isinstance(meta,str) or not meta: raise RuntimeError("missing _elementor_data")
  tree=json.loads(meta)
  node,before=find_main_editor(tree,cfg)
  eid=node.get("id")
  if not eid: raise RuntimeError("target Elementor element has no id")
  after=make_editor(before,cfg)
  originals[pid]={"element_id":eid,"editor":before}
  br=bridge("elementor.structure",f"phase16-native-final-{pid}",{"operation":"update_settings","element_id":eid,"settings":{"editor":after}},pid)
  bridge("cache.purge",f"phase16-native-final-purge-{pid}",{})
  time.sleep(2)
  checks=public_checks(pid,cfg)
  ok=all(v is True or v==200 for v in checks.values())
  results.append({"id":pid,"status":"verified" if ok else "verification_failed","element_id":eid,"bridge_changed":br.get("changed"),"before_sha256":br.get("before_sha256"),"after_sha256":br.get("after_sha256"),"checks":checks})
  if not ok:
   failures.append({"id":pid,"error":"public/rendered verification failed","checks":checks})
 except Exception as exc:
  failures.append({"id":pid,"error":str(exc)[:700]})

# Roll back only failed targets whose original Elementor editor was captured.
if failures:
 failed_ids={x["id"] for x in failures if x.get("id") in originals}
 for pid in failed_ids:
  try:
   orig=originals[pid]
   bridge("elementor.structure",f"phase16-native-final-rollback-{pid}",{"operation":"update_settings","element_id":orig["element_id"],"settings":{"editor":orig["editor"]}},pid)
   bridge("cache.purge",f"phase16-native-final-rollback-purge-{pid}",{})
  except Exception as exc:
   failures.append({"id":pid,"rollback_error":str(exc)[:500]})

report={
 "ok":not failures,
 "phase":16,
 "title":"Native Elementor completion of Phase 16 legacy editorial backlog",
 "target_count":11,
 "already_native_verified":sum(1 for x in results if x.get("status")=="already_native_verified"),
 "newly_verified":sum(1 for x in results if x.get("status")=="verified"),
 "failure_count":len(failures),
 "results":results,
 "failures":failures,
 "safety":{"fake_authors_created":0,"fake_reviewers_created":0,"named_human_experts_created":0,"price_stock_discount_mutations":0,"orders_created":0,"messages_sent":0},
 "source_policy":"government, university extension, research center, or manufacturer technical documentation"
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ["ok","target_count","already_native_verified","newly_verified","failure_count"]},ensure_ascii=False))
if failures: raise SystemExit(2)
