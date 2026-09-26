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
    r=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit","_fields":"id,status,slug,link,title,content,modified_gmt"},timeout=90)
    r.raise_for_status(); return r.json()

def clean_title(post):
    t=(post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or ""
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",t))).strip()

def public_html(url):
    sep="&" if "?" in url else "?"
    r=requests.get(url+sep+"k20_deep="+str(int(time.time()*1000)),timeout=60,headers={"User-Agent":"k20-phase16-deep-completion/1.0","Cache-Control":"no-cache, no-store","Pragma":"no-cache"})
    r.raise_for_status(); return r

def strip_old_blocks(raw):
    pats=[
      r"<!-- k20-phase16-deep-review-v1 -->[\\s\\S]*?<!-- /k20-phase16-deep-review-v1 -->",
      r"<!-- k20-phase16-editorial-trust-start -->[\\s\\S]*?<!-- k20-phase16-editorial-trust-end -->",
      r"<!-- wp:html -->\\s*<!-- k20-phase16-gutenberg-test-v1 -->[\\s\\S]*?<!-- /k20-phase16-gutenberg-test-v1 -->\\s*<!-- /wp:html -->",
      r"<!-- k20-phase16-editorial-trust-v5 -->[\\s\\S]*?<!-- /k20-phase16-editorial-trust-v5 -->",
      r"<!-- k20-phase16-editorial-trust-v4 -->[\\s\\S]*?<!-- /k20-phase16-editorial-trust-v4 -->",
      r"<!-- k20-phase16-editorial-trust-v3 -->[\\s\\S]*?<!-- /k20-phase16-editorial-trust-v3 -->",
      r"<!-- k20-phase16-editorial-trust-v2 -->[\\s\\S]*?<!-- /k20-phase16-editorial-trust-v2 -->"
    ]
    n=0
    for p in pats:
        raw,count=re.subn(p,"",raw,flags=re.I); n+=count
    return raw,n

def deep_inner(cfg):
    lis="".join("<li>"+html.escape(x)+"</li>" for x in cfg["checks"])
    src="".join('<li><a href="'+html.escape(u,quote=True)+'" rel="nofollow noopener" target="_blank">'+html.escape(n)+'</a></li>' for n,u in cfg["sources"])
    return f"""
<!-- {MARKER} -->
<hr style="border:0;border-top:1px solid rgba(255,255,255,.28);margin:22px 0">
<h3 style="font-size:21px;line-height:1.8">بازبینی عمیق فنی</h3>
<p>{html.escape(cfg["analysis"])}</p>
<h3 style="font-size:20px;line-height:1.8">چک‌های اجرایی قبل از تصمیم</h3>
<ul>{lis}</ul>
<h3 style="font-size:20px;line-height:1.8">منابع مرجع تکمیلی</h3>
<ul>{src}</ul>
<h3 style="font-size:20px;line-height:1.8">روش تهیه و بازبینی</h3>
<p>این بخش در بازبینی فاز ۱۶ با رجوع به منابع دانشگاهی، دولتی، مراکز پژوهشی یا مستندات فنی سازنده تکمیل شده است. ادعاهای عددی یا تصمیم‌های وابسته به مدل محصول، مزرعه، آب، خاک، فشار، دبی یا برچسب مصرف باید با داده واقعی همان مورد تطبیق داده شوند. هیچ کارشناس، تجربه میدانی یا تأییدیه شخصی ساختگی به این نوشته افزوده نشده است.</p>
<p>جزئیات معیار انتخاب منبع، اصلاح محتوا و استفاده از ابزارهای خودکار در <a href="{POLICY_URL}" style="color:inherit;text-decoration:underline">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> آمده است.</p>
<!-- /{MARKER} -->
"""

def standalone_editorial_section(cfg):
    return f"""
<section class="k20-phase16-deep-review" dir="rtl" style="direction:rtl;text-align:right;line-height:2;background:linear-gradient(135deg,#0F3F25,#17653A);color:#fff;border-radius:20px;padding:26px;margin:22px 0">
<h2 style="margin-top:0;color:#fff;font-size:25px;line-height:1.7">نظر کارشناسی کشاورز بیست — بازبینی عمیق فنی</h2>
{deep_inner(cfg)}
</section>
"""

def expand_inside_render_root(raw,pid,cfg):
    if pid==142587:
        m=re.search(r"<h[1-6][^>]*>[^<]*منابع[^<]*</h[1-6]>",raw,re.I)
        if not m:
            raise RuntimeError("visible sources heading not found")
        sec_start=raw.rfind("<section",0,m.start())
        if sec_start<0:
            raise RuntimeError("sources section boundary not found")
        return raw[:sec_start]+standalone_editorial_section(cfg)+"\\n"+raw[sec_start:],"before_sources_in_root"

    term="نظر کارشناسی کشاورز بیست"
    pos=raw.find(term)
    if pos<0:
        raise RuntimeError("visible editorial heading not found")
    h_start=raw.rfind("<h2",0,pos)
    h_end=raw.find("</h2>",pos)
    sec_start=raw.rfind("<section",0,h_start)
    sec_end=raw.find("</section>",h_end)
    if min(h_start,h_end,sec_start,sec_end)<0:
        raise RuntimeError("editorial section boundaries not found")
    addon=deep_inner(cfg)
    return raw[:sec_end]+addon+raw[sec_end:],"expand_existing_editorial_section"

def core_update(pid,content):
    r=S.post(f"{BASE}/wp-json/wp/v2/posts/{pid}",json={"content":content},timeout=120)
    r.raise_for_status()
    return r.json()
def legacy_update(pid,new_content):
    with tempfile.TemporaryDirectory(prefix=f"k20-p16-deep-{pid}-") as td:
        req=Path(td)/"request.json"; res=Path(td)/"result.json"
        req.write_text(json.dumps({"action":"post.update","id":pid,"payload":{"content":new_content}},ensure_ascii=False),encoding="utf-8")
        cp=subprocess.run(["pwsh","-NoLogo","-NoProfile","-File","scripts/Invoke-K20SiteGateway.ps1","-RequestPath",str(req),"-OutputPath",str(res)],text=True,capture_output=True,timeout=300)
        if cp.returncode!=0: raise RuntimeError("legacy gateway failed: "+(cp.stderr or cp.stdout)[-600:])
        data=json.loads(res.read_text(encoding="utf-8-sig"))
        if data.get("ok") is not True: raise RuntimeError("legacy gateway returned not-ok")
        return data.get("result") or {}

def bridge(action,request_id,payload=None):
    r=S.post(BASE+"/wp-json/keshavarz20-ops/v3/execute",json={"action":action,"request_id":request_id,"payload":payload or {}},timeout=120)
    data=r.json()
    if not r.ok or data.get("ok") is not True: raise RuntimeError(f"{action} failed: {data.get('code')} {data.get('message')}")
    return data.get("result") or {}

results=[]; failures=[]
for pid,cfg in POSTS.items():
    try:
        post=get_post(pid); raw=((post.get("content") or {}).get("raw") or "")
        if not raw: raise RuntimeError("empty post_content")
        # Create a reversible snapshot through a no-op exact patch on a unique anchor when possible.
        snap=None
        try:
            sr=bridge("content.search",f"p16-deep-snap-search-{pid}",{"target_type":"post","post_id":pid,"field":"post_content","pattern":cfg["anchor"],"context":40})
            if int(sr.get("matches") or 0)==1 and sr.get("sha256"):
                sp=bridge("content.patch",f"p16-deep-snapshot-{pid}",{"target_type":"post","post_id":pid,"field":"post_content","old_content":cfg["anchor"],"new_content":cfg["anchor"],"expected_sha256":sr["sha256"]})
                snap={"captured":True,"before_sha256":sp.get("before_sha256")}
        except Exception as exc:
            snap={"captured":False,"reason":str(exc)[:180]}
        cleaned,removed=strip_old_blocks(raw)
        new_content,mode=expand_inside_render_root(cleaned,pid,cfg)
        gw=core_update(pid,new_content)
        time.sleep(1.5)
        post2=get_post(pid); rendered=((post2.get("content") or {}).get("rendered") or "")
        url=post2.get("link")
        pub=public_html(url)
        checks={
          "rest_rendered_deep_review":"بازبینی عمیق فنی" in rendered,
          "rest_review_method":"روش تهیه و بازبینی" in rendered,
          "rest_policy_link":"/editorial-policy/" in rendered,
          "rest_editorial_analysis":"نظر کارشناسی کشاورز بیست" in rendered,
          "rest_source_links":all(u in rendered for _,u in cfg["sources"]),
          "public_http":pub.status_code,
          "public_policy_link":"/editorial-policy/" in pub.text,
          "public_review_method":"روش تهیه و بازبینی" in pub.text,
          "public_editorial_analysis":"نظر کارشناسی کشاورز بیست" in pub.text
        }
        verified=all(v is True or v==200 for v in checks.values())
        results.append({"id":pid,"title":clean_title(post2),"url":url,"status":"verified" if verified else "verification_failed","insert_mode":mode,"old_phase16_blocks_removed":removed,"snapshot":snap,"modified_gmt":gw.get("modified_gmt") or gw.get("modified"),"checks":checks})
        if not verified: failures.append({"id":pid,"reason":"public_or_rendered_verification_failed","checks":checks})
    except Exception as exc:
        failures.append({"id":pid,"title":cfg["title"],"reason":str(exc)[:700]})

try: cache=bridge("cache.purge","p16-deep-cache-purge",{})
except Exception as exc: cache={"error":str(exc)[:300]}
time.sleep(4)

report={
 "ok":not failures,
 "phase":16,
 "title":"Phase 16 deep research completion for legacy 11",
 "generated_at_utc":NOW,
 "target_count":len(POSTS),
 "verified_count":sum(1 for x in results if x.get("status")=="verified"),
 "failure_count":len(failures),
 "results":results,
 "failures":failures,
 "cache_purge":cache,
 "safety":{"fake_authors_created":0,"fake_reviewers_created":0,"price_stock_discount_mutations":0,"orders_created":0,"messages_sent":0},
 "source_policy":"government, university extension, research center, or manufacturer technical documentation"
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ["ok","target_count","verified_count","failure_count"]},ensure_ascii=False))
if failures: raise SystemExit(2)
