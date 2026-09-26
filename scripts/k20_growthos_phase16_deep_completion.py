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
OUT=Path("growthos-phase16-results/deep-completion.json")
POLICY_URL="https://keshavarz20.com/editorial-policy/"
MARKER="k20-phase16-deep-review-v1"
NOW=datetime.now(timezone.utc).isoformat()

S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=0.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase16-deep-completion/1.0","Cache-Control":"no-cache"})

POSTS={
142587:{
 "title":"اتفون چیست؟ کاربرد، زمان مصرف، عوارض و مصرف در گوجه‌فرنگی",
 "anchor":"منابع",
 "analysis":"اتفون یک تنظیم‌کننده رشد گیاهی است و اثر آن به مرحله بلوغ میوه، دما، وضعیت تنش گیاه و برچسب همان فرآورده وابسته است. برای گوجه‌فرنگی، منبع EPA نشان می‌دهد کاربرد برچسب‌محور می‌تواند رسیدگی را جلو بیندازد و یکنواخت‌تر کند؛ اما دوز، زمان مصرف، فاصله تا برداشت و محدودیت‌ها باید فقط از برچسب ثبت‌شده همان محصول و ضوابط محلی خوانده شوند. بنابراین این مقاله نباید نسخه عمومیِ دوز مصرف تلقی شود.",
 "checks":["مرحله بلوغ میوه قبل از تصمیم به مصرف مشخص شود.","تنش خشکی، بیماری، ضعف ریشه و دمای بالا قبل از کاربرد بررسی شود.","هیچ دوز یا فاصله تا برداشت از یک برچسب خارجی به محصول ثبت‌شده در ایران تعمیم داده نشود."],
 "sources":[
  ("US EPA — Nufarm Ethephon 2 label index","https://ordspub.epa.gov/ords/pesticides/f?p=PPLS:102:::NO::P102_REG_NUM:228-660"),
  ("US EPA — Ethephon 3 label, tomato directions","https://www3.epa.gov/pesticides/chem_search/ppls/005905-00595-20180123.pdf")
 ]},
145235:{
 "title":"چرا یک زون آبیاری قطره‌ای یکنواخت آب نمی‌دهد؟",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"عیب‌یابی یکنواختی باید از اندازه‌گیری فشار و دبی شروع شود، نه از تعویض تصادفی قطعه. اختلاف ارتفاع، افت فشار در لوله، گرفتگی، طول زیاد لترال و تنظیم نامناسب فشار می‌توانند هم‌زمان روی دبی قطره‌چکان‌ها اثر بگذارند. مقایسه چند نقطه در ابتدا، میانه و انتهای زون مسیر تشخیص را بسیار کوتاه‌تر می‌کند.",
 "checks":["فشار در ورودی و انتهای زون در حالت کار اندازه‌گیری شود.","دبی چند قطره‌چکان در نقاط مختلف جمع‌آوری و با هم مقایسه شود.","فیلتر، گرفتگی، اختلاف ارتفاع و طول لترال قبل از تغییر پمپ یا رگلاتور بررسی شوند."],
 "sources":[
  ("Oklahoma State University — Drip Irrigation Systems","https://extension.okstate.edu/fact-sheets/drip-irrigation-systems"),
  ("Cal Poly ITRC — Irrigation System Evaluations","https://itrc.org/projects/evals.htm")
 ]},
145237:{
 "title":"چرا آبپاش برد کم یا پاشش نامنظم دارد؟",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"برد کم همیشه به معنی کمبود ظرفیت پمپ نیست. فشار خارج از محدوده طراحی، گرفتگی یا فرسودگی نازل، نشتی و چیدمان نامناسب می‌تواند الگوی پاشش را خراب کند. فشار خیلی زیاد نیز با مه‌پاشی و افزایش تلفات باد، یکنواختی را کاهش می‌دهد.",
 "checks":["فشار دینامیک نزدیک آبپاش در زمان کار اندازه‌گیری شود.","نازل و فیلتر از نظر گرفتگی، فرسودگی و تفاوت سایز بررسی شوند.","چیدمان و هم‌پوشانی آبپاش‌ها و اثر باد جدا از فشار ارزیابی شود."],
 "sources":[
  ("Oklahoma State University — Managing Pressure in Irrigation","https://extension.okstate.edu/fact-sheets/managing-pressure-in-the-home-irrigation-system"),
  ("Colorado State University Extension — Irrigation: Inspecting and Correcting","https://extension.colostate.edu/docs/pubs/crops/04722.pdf")
 ]},
145238:{
 "title":"نشتی، سفتی یا بسته‌نشدن شیر آبیاری",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"برای شیرهای توپی و پروانه‌ای، نشتی یا سفتی می‌تواند از آلودگی در ناحیه آب‌بندی، آسیب یا فرسودگی سیت، دیسک یا آب‌بند، نصب نامناسب یا کارکرد خارج از محدوده طراحی باشد. باز و بسته کردن با نیروی بیشتر بدون تشخیص علت می‌تواند خرابی را تشدید کند.",
 "checks":["وجود جسم خارجی یا رسوب در سطح آب‌بندی بررسی شود.","سیت، دیسک، ساقه و آب‌بندها از نظر سایش یا آسیب بررسی شوند.","فشار و شرایط نصب با محدوده کاری سازنده مقایسه شود."],
 "sources":[
  ("AVK — Double Eccentric Butterfly Valve O&M","https://files.avkvalves.com/updated-ftp/downloads/756_operation_maintenance_2024_af_245137.pdf"),
  ("Bray — Resilient Seated Butterfly Valve IOM","https://www.bray.com/docs/default-source/manuals-guides/iom-manuals/en_iom_3cx.pdf")
 ]},
145251:{
 "title":"آزمایش آب آبیاری را چگونه بخوانیم؟",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"EC شاخصی از بار نمکی محلول است و SAR رابطه سدیم را با کلسیم و منیزیم نشان می‌دهد؛ اما تفسیر این دو عدد بدون توجه به خاک، زهکشی، کیفیت آب، محصول و روش آبیاری می‌تواند گمراه‌کننده باشد. تصمیم مدیریتی باید بر اساس گزارش آزمایشگاه و شرایط مزرعه انجام شود.",
 "checks":["واحد EC و روش آزمایش قبل از مقایسه اعداد کنترل شود.","SAR در کنار EC، خاک و نفوذپذیری تفسیر شود.","ریسک رسوب و گرفتگی جدا از شوری و سدیمی‌شدن بررسی شود."],
 "sources":[
  ("University of Arizona — Water Quality and Uses","https://extension.arizona.edu/publication/arizona-guide-water-quality-and-uses"),
  ("University of Arizona — Soil Quick Guide","https://extension.arizona.edu/publication/soil-quick-guide")
 ]},
145253:{
 "title":"نمونه‌برداری خاک برای آزمایش؛ قبل از کوددهی",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"خطای نمونه‌برداری می‌تواند از خود آزمایشگاه مهم‌تر باشد. نمونه باید نماینده یک ناحیه مدیریتی نسبتاً یکنواخت باشد، از چند زیرنمونه تشکیل شود و عمق نمونه‌گیری با روش توصیه کودی مورد استفاده سازگار باشد. نقاط غیرعادی مثل محل دپو، آبراهه یا لکه‌های کاملاً متفاوت بهتر است جداگانه نمونه‌برداری شوند.",
 "checks":["هر نمونه مرکب از چند زیرنمونه نماینده ناحیه تهیه شود.","عمق نمونه‌گیری ثابت و متناسب با پروتکل آزمایشگاه باشد.","نقاط غیرعادی و سابقه متفاوت مدیریت با نمونه اصلی مخلوط نشوند."],
 "sources":[
  ("Illinois Extension — Soil Sampling","https://extension.illinois.edu/crops/soil-sampling"),
  ("Penn State Extension — Soil Sampling","https://extension.psu.edu/soil-sampling"),
  ("Iowa State Extension — Recipe for Success with Soil Sampling","https://crops.extension.iastate.edu/encyclopedia/recipe-success-soil-sampling")
 ]},
145259:{
 "title":"ضربه قوچ در آبیاری چیست؟",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"ضربه قوچ یک تغییر سریع فشار ناشی از تغییر ناگهانی سرعت جریان است. بستن سریع شیر، توقف پمپ یا تغییر ناگهانی جریان می‌تواند موج فشار ایجاد کند. راهکار مناسب به طول خط، سرعت جریان، جنس و کلاس لوله، آرایش شیرها و تجهیزات حفاظت بستگی دارد و فقط با افزودن یک شیر هوا به‌صورت عمومی حل نمی‌شود.",
 "checks":["سرعت جریان و زمان باز و بسته شدن شیرها بررسی شود.","محل‌های توقف ناگهانی جریان و خاموشی پمپ مشخص شوند.","راهکارهای حفاظت بر اساس طراحی خط و فشار مجاز لوله انتخاب شوند."],
 "sources":[
  ("USDA NRCS — National Engineering Handbook, Sprinkler Irrigation","https://www.wcc.nrcs.usda.gov/ftpref/wntsc/waterMgt/irrigation/NEH15/ch11.pdf")
 ]},
145263:{
 "title":"محاسبه متراژ نوار تیپ و تعداد اتصالات",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"محاسبه متراژ از هندسه مزرعه شروع می‌شود، اما انتخاب طول مجاز هر لترال فقط هندسی نیست. قطر داخلی تیپ، فاصله و دبی خروجی‌ها، فشار ورودی، شیب و مشخصات سازنده محدودیت هیدرولیکی ایجاد می‌کنند. بنابراین خروجی محاسبه‌گر باید برآورد اولیه خرید تلقی شود و طول نهایی با جدول فنی همان تیپ کنترل شود.",
 "checks":["متراژ هندسی از طول ردیف‌ها و فاصله بین ردیف‌ها جداگانه محاسبه شود.","طول هر لترال با مشخصات فشار، دبی و شیب همان محصول کنترل شود.","تعداد اتصالات با تعداد واقعی خطوط و آرایش مانیفولد تطبیق داده شود."],
 "sources":[
  ("Oklahoma State University — Drip Irrigation Systems","https://extension.okstate.edu/fact-sheets/drip-irrigation-systems")
 ]},
145281:{
 "title":"تزریق کود در آبیاری قطره‌ای",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"در فرتیگیشن، محلول‌بودن کود به‌تنهایی کافی نیست؛ واکنش کود با آب و سایر مواد می‌تواند رسوب ایجاد کند و قطره‌چکان را مسدود کند. کیفیت آب، ترتیب تزریق، سازگاری ترکیبات، زمان تزریق و شست‌وشوی انتهایی باید با هم دیده شوند. تست سازگاری در مقیاس کوچک پیش از اختلاط مخزن اصلی یک کنترل کم‌هزینه و مهم است.",
 "checks":["کیفیت آب و احتمال رسوب قبل از برنامه تزریق بررسی شود.","سازگاری کودها و آب با تست کوچک یا دستور سازنده کنترل شود.","پس از تزریق، زمان کافی برای شست‌وشوی خطوط در نظر گرفته شود."],
 "sources":[
  ("University of Florida IFAS — Tomato Production Using Fertigation Technology","https://edis.ifas.ufl.edu/hs1392"),
  ("University of Florida IFAS — Five Rs of Nutrient Stewardship for Fertigation","https://edis.ifas.ufl.edu/hs1386")
 ]},
145330:{
 "title":"قطره‌چکان PC یا معمولی؟",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"قطره‌چکان جبران‌کننده فشار در بازه کاری تعریف‌شده می‌تواند دبی را در برابر تغییرات فشار پایدارتر نگه دارد، اما جای طراحی هیدرولیکی را نمی‌گیرد. در زمین شیب‌دار یا خطوط طولانی، اختلاف ارتفاع و افت اصطکاکی باید محاسبه شود و بازه فشار کاری مدل واقعی قطره‌چکان با شرایط خط تطبیق داده شود.",
 "checks":["بازه فشار کاری مدل واقعی PC از دیتاشیت سازنده کنترل شود.","اختلاف ارتفاع و افت فشار خط قبل از انتخاب نوع قطره‌چکان محاسبه شود.","PC به‌عنوان راه‌حل مطلق برای طراحی ضعیف یا گرفتگی معرفی نشود."],
 "sources":[
  ("Oklahoma State University — Drip Irrigation Systems","https://extension.okstate.edu/fact-sheets/drip-irrigation-systems")
 ]},
145775:{
 "title":"آبیاری قطره‌ای یکنواخت است یا نه؟ تست دبی و DU",
 "anchor":"نظر کارشناسی کشاورز بیست",
 "analysis":"DU یک شاخص میدانی برای دیدن توزیع واقعی آب است و باید با نمونه‌گیری منظم و قابل‌تکرار انجام شود. هدف فقط تولید یک درصد نیست؛ اختلاف فشار، گرفتگی و نقاط کم‌دبی باید از روی داده‌ها قابل‌ردیابی باشند. ثبت محل نمونه‌ها، زمان جمع‌آوری و فشار سیستم باعث می‌شود تست بعدی قابل مقایسه باشد.",
 "checks":["نمونه‌گیری از نقاط نماینده ابتدا، میانه و انتهای خطوط انجام شود.","زمان جمع‌آوری برای همه نمونه‌ها یکسان و ظروف مناسب باشند.","همراه دبی، فشار و محل نمونه ثبت شود تا علت افت یکنواختی قابل پیگیری باشد."],
 "sources":[
  ("Cal Poly ITRC — Irrigation System Evaluations","https://itrc.org/projects/evals.htm"),
  ("Cal Poly ITRC — Irrigation Evaluation Data","https://www.itrc.org/irrevaldata/index.html")
 ]}
}

def get_post(pid):
    r=S.get(
        f"{BASE}/wp-json/wp/v2/posts/{pid}",
        params={"context":"edit","_fields":"id,status,slug,link,title,content,meta,modified_gmt"},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()

def clean_title(post):
    t=(post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or ""
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",t))).strip()

def public_html(url):
    sep="&" if "?" in url else "?"
    r=requests.get(
        url+sep+"k20_p16_final="+str(int(time.time()*1000)),
        timeout=60,
        headers={"User-Agent":"k20-phase16-elementor-final/1.0","Cache-Control":"no-cache, no-store","Pragma":"no-cache"},
    )
    r.raise_for_status()
    return r

def bridge(action,request_id,payload=None):
    body={"action":action,"request_id":request_id,"payload":payload or {}}
    r=S.post(BASE+"/wp-json/keshavarz20-ops/v3/execute",json=body,timeout=180)
    try: data=r.json()
    except Exception:
        raise RuntimeError(f"{action}: non-json HTTP {r.status_code}: {(r.text or '')[:200]}")
    if not r.ok or data.get("ok") is not True:
        raise RuntimeError(f"{action}: HTTP {r.status_code} code={data.get('code')} message={data.get('message')}")
    return data.get("result") or {}

def parse_elementor(post):
    meta=post.get("meta") if isinstance(post.get("meta"),dict) else {}
    raw=meta.get("_elementor_data") or ""
    if not isinstance(raw,str) or not raw.strip():
        raise RuntimeError("missing _elementor_data")
    try: data=json.loads(raw)
    except Exception as exc: raise RuntimeError("invalid _elementor_data JSON: "+str(exc))
    return data

def walk_settings(node,path="root",out=None):
    out=out if out is not None else []
    if isinstance(node,dict):
        settings=node.get("settings") if isinstance(node.get("settings"),dict) else {}
        for key,val in settings.items():
            if isinstance(val,str):
                out.append({
                    "path":path,"element_id":node.get("id"),"elType":node.get("elType"),
                    "widgetType":node.get("widgetType"),"setting_key":key,"value":val
                })
        for key,val in node.items():
            if key!="settings": walk_settings(val,path+"."+str(key),out)
    elif isinstance(node,list):
        for i,val in enumerate(node): walk_settings(val,path+"["+str(i)+"]",out)
    return out

def text_only(v):
    s=re.sub(r"<script[\s\S]*?</script>"," ",str(v or ""),flags=re.I)
    s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",html.unescape(s)).strip()

def overlap_score(candidate,rendered):
    ct=text_only(candidate)
    rt=text_only(rendered)
    if not ct or not rt: return 0
    chunks=[x.strip() for x in re.split(r"[.!؟\n]+",ct) if len(x.strip())>=45]
    if not chunks:
        chunks=[ct[i:i+80] for i in range(0,max(0,len(ct)-79),80)]
    return sum(1 for x in chunks[:80] if x in rt)

def locate_live_setting(post,pid):
    data=parse_elementor(post)
    rendered=((post.get("content") or {}).get("rendered") or "")
    settings=walk_settings(data)
    if pid==142587:
        candidates=[x for x in settings if "منابع" in x["value"]]
        if not candidates: raise RuntimeError("no Elementor setting containing sources")
        ranked=sorted(
            [(overlap_score(x["value"],rendered),len(x["value"]),x) for x in candidates],
            key=lambda z:(z[0],z[1]),reverse=True
        )
        if ranked[0][0] <= 0:
            raise RuntimeError("no source widget overlaps rendered output")
        return ranked[0][2],ranked[0][0]
    candidates=[x for x in settings if "نظر کارشناسی کشاورز بیست" in x["value"]]
    if len(candidates)!=1:
        raise RuntimeError(f"expected one live editorial Elementor setting, found {len(candidates)}")
    return candidates[0],overlap_score(candidates[0]["value"],rendered)

def deep_inner(cfg):
    lis="".join("<li>"+html.escape(x)+"</li>" for x in cfg["checks"])
    src="".join(
        '<li><a href="'+html.escape(u,quote=True)+'" rel="nofollow noopener" target="_blank">'+html.escape(n)+'</a></li>'
        for n,u in cfg["sources"]
    )
    return f"""
<!-- k20-phase16-elementor-deep-v1 -->
<div class="k20-phase16-elementor-deep-v1" dir="rtl" style="direction:rtl;text-align:right;line-height:2;margin-top:22px;padding-top:18px;border-top:1px solid rgba(255,255,255,.28)">
<h3 style="font-size:21px;line-height:1.8">بازبینی عمیق فنی</h3>
<p>{html.escape(cfg["analysis"])}</p>
<h3 style="font-size:20px;line-height:1.8">چک‌های اجرایی قبل از تصمیم</h3>
<ul>{lis}</ul>
<h3 style="font-size:20px;line-height:1.8">منابع مرجع تکمیلی</h3>
<ul>{src}</ul>
<h3 style="font-size:20px;line-height:1.8">روش تهیه و بازبینی</h3>
<p>این بخش در بازبینی فاز ۱۶ با رجوع به منابع دانشگاهی، دولتی، مراکز پژوهشی یا مستندات فنی سازنده تکمیل شده است. ادعاهای عددی یا تصمیم‌های وابسته به مدل محصول، مزرعه، آب، خاک، فشار، دبی یا برچسب مصرف باید با داده واقعی همان مورد تطبیق داده شوند. هیچ کارشناس، تجربه میدانی یا تأییدیه شخصی ساختگی به این نوشته افزوده نشده است.</p>
<p>جزئیات معیار انتخاب منبع، اصلاح محتوا و استفاده از ابزارهای خودکار در <a href="{POLICY_URL}" style="color:inherit;text-decoration:underline">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> آمده است.</p>
</div>
<!-- /k20-phase16-elementor-deep-v1 -->
"""

def ethephon_block(cfg):
    return f"""
<section class="k20-phase16-elementor-deep-v1" dir="rtl" style="direction:rtl;text-align:right;line-height:2;border:1px solid #d9e7dd;border-radius:18px;padding:22px;margin:26px 0;background:#f8fbf9">
<h2>نظر کارشناسی کشاورز بیست — بازبینی عمیق فنی</h2>
{deep_inner(cfg)}
</section>
"""

def remove_existing_elementor_deep(v):
    pats=[
      r"<!-- k20-phase16-elementor-deep-v1 -->[\s\S]*?<!-- /k20-phase16-elementor-deep-v1 -->",
      r"<section[^>]*class=[\"'][^\"']*k20-phase16-elementor-deep-v1[^\"']*[\"'][^>]*>[\s\S]*?</section>"
    ]
    total=0
    for pat in pats:
        v,n=re.subn(pat,"",v,flags=re.I); total+=n
    return v,total

def build_new_value(pid,current,cfg):
    current,removed=remove_existing_elementor_deep(current)
    if pid==142587:
        m=re.search(r"<h[1-6][^>]*>[^<]*منابع[^<]*</h[1-6]>",current,re.I)
        if m:
            sec_start=current.rfind("<section",0,m.start())
            at=sec_start if sec_start>=0 else m.start()
        else:
            pos=current.find("منابع")
            if pos<0: raise RuntimeError("sources anchor missing in selected Elementor widget")
            at=current.rfind("<",0,pos)
            if at<0: at=pos
        return current[:at]+ethephon_block(cfg)+"\n"+current[at:],removed,"before_sources"
    pos=current.find("نظر کارشناسی کشاورز بیست")
    if pos<0: raise RuntimeError("editorial heading missing in selected Elementor widget")
    h_end=current.find("</h2>",pos)
    if h_end<0: raise RuntimeError("editorial heading boundary missing")
    sec_end=current.find("</section>",h_end)
    if sec_end<0: raise RuntimeError("editorial section boundary missing")
    return current[:sec_end]+deep_inner(cfg)+current[sec_end:],removed,"inside_editorial_section"

def setting_readback(post,element_id,setting_key):
    data=parse_elementor(post)
    vals=[x for x in walk_settings(data) if str(x.get("element_id"))==str(element_id) and x.get("setting_key")==setting_key]
    if len(vals)!=1:
        raise RuntimeError(f"Elementor readback target count {len(vals)}")
    return vals[0]["value"]

def trust_checks(text,cfg):
    return {
      "editorial_analysis":"نظر کارشناسی کشاورز بیست" in text,
      "deep_review":"بازبینی عمیق فنی" in text,
      "review_method":"روش تهیه و بازبینی" in text,
      "policy_link":"/editorial-policy/" in text,
      "sources":all(u in text for _,u in cfg["sources"])
    }

results=[]; failures=[]
for pid,cfg in POSTS.items():
    try:
        before=get_post(pid)
        rendered_before=((before.get("content") or {}).get("rendered") or "")
        live,score=locate_live_setting(before,pid)
        existing=live["value"]
        existing_checks=trust_checks(rendered_before,cfg)
        if existing_checks["review_method"] and existing_checks["policy_link"] and existing_checks["editorial_analysis"]:
            results.append({
              "id":pid,"title":clean_title(before),"status":"already_complete",
              "element_id":live["element_id"],"setting_key":live["setting_key"],
              "overlap_score":score,"checks":existing_checks
            })
            continue
        new_value,removed,mode=build_new_value(pid,existing,cfg)
        update=bridge(
          "elementor.structure",
          f"p16-elementor-final-{pid}",
          {
            "operation":"update_settings",
            "element_id":live["element_id"],
            "settings":{live["setting_key"]:new_value}
          }
        )
        time.sleep(2)
        after=get_post(pid)
        saved=setting_readback(after,live["element_id"],live["setting_key"])
        saved_checks=trust_checks(saved,cfg)
        rendered=((after.get("content") or {}).get("rendered") or "")
        rendered_checks=trust_checks(rendered,cfg)
        pub=public_html(after.get("link") or before.get("link") or "")
        public_checks=trust_checks(pub.text,cfg)
        verified=(
          all(saved_checks.values()) and
          rendered_checks["editorial_analysis"] and rendered_checks["review_method"] and rendered_checks["policy_link"] and
          public_checks["editorial_analysis"] and public_checks["review_method"] and public_checks["policy_link"] and
          pub.status_code==200
        )
        results.append({
          "id":pid,"title":clean_title(after),"url":after.get("link"),"status":"verified" if verified else "verification_failed",
          "element_id":live["element_id"],"setting_key":live["setting_key"],"overlap_score":score,
          "insert_mode":mode,"previous_deep_blocks_removed":removed,
          "bridge_result":{k:update.get(k) for k in ["changed","snapshot_id","approval_id","fingerprint"] if k in update},
          "saved_checks":saved_checks,"rendered_checks":rendered_checks,"public_checks":public_checks,"public_http":pub.status_code
        })
        if not verified:
            failures.append({"id":pid,"reason":"Elementor write did not pass rendered/public verification"})
    except Exception as exc:
        failures.append({"id":pid,"title":cfg["title"],"reason":str(exc)[:700]})

try: cache=bridge("cache.purge","p16-elementor-final-cache",{})
except Exception as exc: cache={"error":str(exc)[:300]}
time.sleep(4)

# Post-purge public verification for every target, including already-complete rows.
for item in results:
    pid=int(item["id"]); cfg=POSTS[pid]
    try:
        p=get_post(pid); pub=public_html(p.get("link") or "")
        final_checks=trust_checks(pub.text,cfg)
        item["post_purge_public_http"]=pub.status_code
        item["post_purge_public_checks"]=final_checks
        if not (pub.status_code==200 and final_checks["editorial_analysis"] and final_checks["review_method"] and final_checks["policy_link"]):
            if not any(int(x.get("id") or 0)==pid for x in failures):
                failures.append({"id":pid,"reason":"post-purge public trust verification failed"})
        elif item.get("status")=="verification_failed":
            item["status"]="verified"
    except Exception as exc:
        if not any(int(x.get("id") or 0)==pid for x in failures):
            failures.append({"id":pid,"reason":"post-purge readback: "+str(exc)[:500]})

report={
 "ok":not failures,
 "phase":16,
 "title":"Phase 16 deep research completion on canonical Elementor sources",
 "generated_at_utc":NOW,
 "target_count":len(POSTS),
 "verified_count":sum(1 for x in results if x.get("status") in {"verified","already_complete"} and x.get("post_purge_public_checks",{}).get("review_method")),
 "failure_count":len(failures),
 "results":results,
 "failures":failures,
 "cache_purge":cache,
 "canonical_source":"Elementor registered meta (_elementor_data), per live source-map verification",
 "post_content_writes":0,
 "safety":{"fake_authors_created":0,"fake_reviewers_created":0,"price_stock_discount_mutations":0,"orders_created":0,"messages_sent":0},
 "source_policy":"government, university extension, research center, or manufacturer technical documentation"
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ["ok","target_count","verified_count","failure_count","post_content_writes"]},ensure_ascii=False))
if failures: raise SystemExit(2)
