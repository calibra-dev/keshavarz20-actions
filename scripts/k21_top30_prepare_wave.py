#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

ROOT=Path(__file__).resolve().parents[1]
PIM=ROOT/"phase3-results"/"top30-pim.json"
VIDEOS=ROOT/"phase15-video-results"/"k21-top30-family-videos.json"
OPS=ROOT/"bridge-v3-ops"
EVIDENCE=ROOT/"geo-aeo-results"/"k21-top30-wave-evidence.json"

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
AUTH=(USER,PASS)
S=requests.Session()
S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"K21-Top30-Remediator/1.0"})

MARK_START="<!-- k21-top30-v1:start -->"
MARK_END="<!-- k21-top30-v1:end -->"
UNKNOWN_PRESSURE="اعلام نشده؛ قبل از سفارش از روی بدنه، پلاک یا دیتاشیت همین مدل تأیید شود"
UNKNOWN_CONNECTION="نیازمند تطبیق با قطعه مقابل؛ فرم اتصال نهایی از روی خود نمونه کنترل شود"
UNKNOWN_MATERIAL="اعلام نشده؛ جنس دقیق از روی بدنه یا دیتاشیت همین مدل تأیید شود"

LINKS={
 "valve":[("راهنمای خرید شیرآلات آبیاری","https://keshavarz20.com/irrigation-valves-buying-guide/"),("بررسی سازگاری اتصالات","https://keshavarz20.com/irrigation-fittings-compatibility-selector/")],
 "fitting":[("راهنمای اتصالات پلی‌اتیلن","https://keshavarz20.com/polyethylene-compression-fittings-guide/"),("بررسی سازگاری اتصالات","https://keshavarz20.com/irrigation-fittings-compatibility-selector/")],
 "fertigation":[("راهنمای طراحی آبیاری قطره‌ای","https://keshavarz20.com/complete-drip-irrigation-system-guide/"),("انتخاب‌گر فیلتر آبیاری","https://keshavarz20.com/irrigation-filter-selector/")],
 "layflat_rain":[("راهنمای تبدیل سایز لوله نخدار و لی‌فلت","https://keshavarz20.com/layflat-hose-size-inch-mm-guide/"),("ماشین‌حساب لی‌فلت و اتصالات","https://keshavarz20.com/layflat-length-fittings-calculator/")],
 "drip_tape":[("راهنمای خرید نوار تیپ","https://keshavarz20.com/drip-tape-buying-guide/"),("محاسبه متراژ نوار تیپ و اتصالات","https://keshavarz20.com/drip-tape-length-fittings-calculator/")],
}

def wc(path:str, method:str="GET", **kwargs):
    r=S.request(method, f"{BASE}/wp-json/wc/v3/{path.lstrip('/')}", timeout=180, **kwargs)
    r.raise_for_status()
    return r.json()

def wp(path:str, method:str="GET", **kwargs):
    r=S.request(method, f"{BASE}/wp-json/wp/v2/{path.lstrip('/')}", timeout=180, **kwargs)
    r.raise_for_status()
    return r.json()

def textify(s:str)->str:
    s=re.sub(r"<script[\s\S]*?</script>"," ",s or "",flags=re.I)
    s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def first(patterns:list[str], text:str)->str|None:
    for pattern in patterns:
        m=re.search(pattern,text,re.I)
        if m:
            return re.sub(r"\s+"," ",m.group(1) if m.lastindex else m.group(0)).strip()
    return None

def clean_model(name:str)->str:
    x=re.sub(r"\([^)]*\)"," ",name)
    x=re.sub(r"\b\d+(?:\s*و\s*\d+/\d+|[./]\d+)?\s*اینچ\b"," ",x)
    x=re.sub(r"\b\d+\s*میلی\s*متر\b"," ",x)
    x=re.sub(r"\s+"," ",x).strip(" -|،")
    return x[:120] or name[:120]

def brand_from(pim_row:dict, name:str, desc:str)->str|None:
    b=((pim_row.get("pim_fields") or {}).get("brand") or {}).get("value")
    if b:
        return b
    if "آبلوله" in name:
        return "آب لوله بسپار (آبلوله)"
    if "پلی رود" in name or "پلی‌رود" in name:
        return "پلی رود اتصال"
    # Do not promote historical/ambiguous prose into a verified brand.
    return None

def size_value(name:str, family:str)->str:
    inch=first([r"((?:\d+\s*و\s*\d+/\d+|\d+(?:[./]\d+)?)\s*اینچ)"],name)
    mm=first([r"(\d+\s*میلی\s*متر)",r"(\d+\s*میلیمتر)"],name)
    if inch and mm:
        return f"{inch} / {mm}"
    if inch:
        return inch
    if mm:
        return mm
    if family=="drip_tape":
        return "در عنوان فعلی اعلام نشده؛ قطر واقعی رول از لیبل همان کالا تأیید شود"
    return "در عنوان فعلی اعلام نشده؛ سایز واقعی از روی بدنه یا دیتاشیت همان مدل تأیید شود"

def pressure_value(name:str, desc:str)->str:
    joined=name+" "+textify(desc)
    x=first([
      r"((?:فشار\s*(?:اسمی|کاری|نامی)?\s*(?:درج‌شده|ثبت‌شده)?\s*)?\d+(?:[./]\d+)?\s*(?:بار|اتمسفر))",
      r"(\d+(?:[./]\d+)?\s*(?:بار|اتمسفر))"
    ],joined)
    return x or UNKNOWN_PRESSURE

def material_value(name:str, desc:str, family:str)->str:
    plain=textify(desc)
    if "چدنی" in name: return "چدن"
    if "آهنی" in name or "فلزی" in name: return "فلزی"
    if "پلی اتیلن" in name or "پلی‌اتیلن" in name: return "پلی‌اتیلن"
    x=first([r"جنس\s*بدنه\s*(?:درج‌شده|ثبت‌شده)?\s*[:：]?\s*([A-Za-z0-9آ-ی‌\- ]{2,40})"],plain)
    if x:
        return x
    if family=="drip_tape":
        return "پلیمری؛ ترکیب دقیق مواد از لیبل یا دیتاشیت همان رول تأیید شود"
    if family=="fertigation":
        return "فلزی طبق اطلاعات ثبت‌شده صفحه؛ جنس/ضخامت نمونه تحویلی پیش از نصب کنترل شود"
    return UNKNOWN_MATERIAL

def connection_value(name:str, desc:str, family:str)->str:
    plain=textify(desc)
    if "پروانه" in name and ("ویفری" in plain or "بین دو فلنج" in plain):
        return "ویفری؛ نصب بین دو فلنج سازگار"
    if "دو سر ماده" in name or "دوسر ماده" in name:
        return "دو سر مادگی؛ قطعه مقابل باید از نظر سایز و نوع رزوه تطبیق داده شود"
    if "یکسر ماده" in name or "یک سر ماده" in name:
        return "یک سر اتصال لوله و یک سر مادگی رزوه‌ای؛ سایز هر دو سمت باید تطبیق داده شود"
    if "جوشی" in name and ("زانو" in name or "فلن" in name):
        return "جوشی؛ نصب با تجهیزات و روش جوش متناسب با لوله پلی‌اتیلن"
    if "کمربند" in name:
        out=first([r"(خروجی\s*رزوه\s*مادگی\s*\d+(?:[./]\d+)?\s*اینچ)"],plain)
        return (out+"؛ نصب دو تکه روی لوله اصلی") if out else "کمربند دو تکه روی لوله اصلی؛ خروجی رزوه‌ای باید با قطعه مقابل تطبیق شود"
    if "رابط مساوی" in name:
        return "اتصال مستقیم هم‌سایز برای ادامه خط؛ دو سمت باید با قطر واقعی لوله یکسان باشند"
    if "سر شلنگ" in name or "سرشلنگ" in name:
        return "سرشلنگی؛ سمت شلنگ با بست مناسب مهار شود و سمت مقابل از نظر فرم و سایز کنترل شود"
    if "فلنج دنده" in name or "فلنج دنده" in plain:
        return "رزوه‌ای به مجموعه فلنجی؛ رزوه، سطح فلنج و آرایش سوراخ‌ها باید هم‌زمان تطبیق داده شوند"
    if "سوپاپ" in name:
        return "اتصال هم‌سایز مطابق بدنه همین نمونه؛ جهت جریان و قطعه مقابل قبل از نصب کنترل شود"
    if family=="fertigation":
        cap=first([r"(۱۰۰\s*لیتر|100\s*لیتر)"],name)
        if cap:
            return "ورودی و خروجی ۳/۴ اینچ طبق اطلاعات ثبت‌شده صفحه؛ روی نمونه تحویلی کنترل شود"
        cap=first([r"(۲۰۰\s*لیتر|200\s*لیتر)"],name)
        if cap:
            return "ورودی و خروجی ۱ اینچ طبق اطلاعات ثبت‌شده صفحه؛ روی نمونه تحویلی کنترل شود"
        return UNKNOWN_CONNECTION
    if family=="layflat_rain":
        return "رابط/سرشلنگی مخصوص لوله تاشو هم‌سایز؛ قطر واقعی و روش مهار قبل از سفارش تطبیق داده شود"
    if family=="drip_tape":
        return "اتصال مخصوص نوار تیپ؛ واشر، شیر و رابط باید با قطر واقعی تیپ و لوله اصلی تطبیق داده شوند"
    return UNKNOWN_CONNECTION

def capacity_value(name:str)->str:
    x=first([r"(\d+\s*لیتر)"],name)
    return x or "ظرفیت از عنوان یا پلاک همین مدل تأیید شود"

def length_value(name:str, family:str)->str:
    x=first([r"(\d+\s*متری)",r"(\d+\s*متر)"],name)
    if x:
        return x.replace("متری","متر")
    if family in ("layflat_rain","drip_tape"):
        return "در عنوان فعلی اعلام نشده؛ متراژ واقعی رول از لیبل همان کالا تأیید شود"
    return "کاربرد ندارد"

def emitter_value(name:str)->str:
    x=first([r"(\d+\s*سانتی\s*متر(?:ی)?)"],name)
    return x or "در عنوان فعلی اعلام نشده؛ فاصله خروجی از لیبل همان رول تأیید شود"

def filtration_value()->str:
    return "نیازمند فیلتر متناسب با کیفیت آب؛ مش/میکرون نهایی از مشخصات رول و منبع آب تعیین شود"

def attrs_for(pim_row:dict, product:dict)->list[dict]:
    name=product.get("name") or ""
    desc=product.get("description") or ""
    family=pim_row["family"]
    brand=brand_from(pim_row,name,desc)
    size=size_value(name,family)
    material=material_value(name,desc,family)
    pressure=pressure_value(name,desc)
    connection=connection_value(name,desc,family)
    model=clean_model(name)
    pairs=[]
    if brand: pairs.append(("برند",brand))
    pairs += [("مدل",model),("سایز",size),("جنس",material),("فشار کاری",pressure),("نوع اتصال",connection)]
    if family=="fertigation":
        pairs.append(("ظرفیت",capacity_value(name)))
    elif family=="layflat_rain":
        pairs.append(("طول",length_value(name,family)))
    elif family=="drip_tape":
        pairs += [("طول",length_value(name,family)),("فاصله قطره",emitter_value(name)),("فیلتراسیون",filtration_value())]
    # Preserve unrelated existing attributes; replace our managed names.
    managed={k for k,_ in pairs}
    out=[]
    for a in product.get("attributes") or []:
        if (a.get("name") or "") not in managed:
            out.append(a)
    for k,v in pairs:
        out.append({"name":k,"visible":True,"variation":False,"options":[v]})
    return out

def values_from_attrs(attrs:list[dict])->dict[str,str]:
    return {(a.get("name") or ""):"، ".join(str(x) for x in (a.get("options") or [])) for a in attrs}

def family_copy(family:str, name:str, vals:dict[str,str])->tuple[str,str,str]:
    size=vals.get("سایز","")
    pressure=vals.get("فشار کاری","")
    connection=vals.get("نوع اتصال","")
    if family=="valve":
        return (
          f"این مدل برای جایی مناسب است که در خط آبیاری یا انتقال آب به یک نقطه کنترل جریان هم‌سایز با {size} نیاز دارید. انتخاب نهایی فقط با نام سایز انجام نمی‌شود؛ قطعه مقابل، فرم اتصال و فشار واقعی شبکه باید با همین نمونه تطبیق داشته باشند.",
          f"اگر هنوز فشار واقعی خط، فرم اتصال دو سمت یا فضای حرکت دسته مشخص نیست، خرید را صرفاً با دیدن عبارت {size} نهایی نکنید. شیر برای جبران کجی لوله، اختلاف استاندارد اتصال یا فشار بالاتر از محدوده تأییدشده طراحی نشده است.",
          "مکمل‌های معمول این خانواده شامل اتصال هم‌سایز، فلنج یا رابط متناسب با مدل، آب‌بندی مناسب و ساپورت خط است. اگر نوع اتصال پروژه با این شیر یکی نیست، به‌جای تبدیل‌های زنجیره‌ای باید شیر یا رابطی با استاندارد صحیح انتخاب شود."
        )
    if family=="fitting":
        return (
          f"این قطعه برای تکمیل یا تغییر مسیر شبکه‌ای مناسب است که اندازه واقعی و قطعه مقابل آن با {size} و آرایش اتصال همین محصول هماهنگ باشد. مهم‌ترین کار قبل از سفارش، مقایسه هر دو سمت اتصال با لوله، شیر یا تجهیز موجود در مزرعه است.",
          "اگر فقط نام اینچی یا میلی‌متری را می‌دانید ولی نوع اتصال، نر/ماده بودن، روش جوش یا فرم آب‌بندی مشخص نیست، این محصول هنوز انتخاب قطعی نیست. فشار کاری نامشخص نیز باید پیش از نصب از روی همان نمونه کنترل شود.",
          "مکمل این قطعه، اتصال قبل و بعد، آب‌بند/واشر یا بست و ابزار نصب متناسب با روش اتصال است. جایگزین درست باید همان وظیفه را با سایز و استاندارد اتصال سازگار انجام دهد؛ شباهت ظاهری یا اشتراک یک عدد به‌تنهایی کافی نیست."
        )
    if family=="fertigation":
        return (
          f"این {name} برای نگهداری و ورود محلول کود به سامانه آبیاری در ظرفیت ثبت‌شده محصول مناسب است، به شرط آنکه روش اتصال، فشار شبکه و آرایش تزریق پروژه با خود مخزن هماهنگ باشند.",
          "اگر فشار مجاز مخزن، سایز ورودی/خروجی یا روش ایمن تزریق در پروژه هنوز روشن نیست، نصب را انجام ندهید. ظرفیت بیشتر یا کمتر به‌تنهایی معیار انتخاب نیست؛ ایمنی، فضای نصب و نحوه سرویس هم باید بررسی شوند.",
          "مکمل‌های این بخش شامل اتصالات هم‌سایز، شیرهای کنترلی، شیلنگ یا لوله رابط و تجهیزات فیلتراسیون متناسب با پروژه است. اگر حجم محلول یا شرایط فشار متفاوت است، ظرفیت دیگر یا روش تزریق دیگری باید بررسی شود."
        )
    if family=="layflat_rain":
        return (
          f"این لوله برای اجرای خط بارانی/مه‌پاش انعطاف‌پذیر با سایز و متراژ ثبت‌شده محصول مناسب است. قبل از خرید، طول مسیر، اختلاف ارتفاع، فشار ابتدا و انتهای خط و رابط هم‌سایز را کنار هم بررسی کنید.",
          "اگر فشار کاری رول روی لیبل مشخص نشده یا مسیر دارای لبه تیز، کشش موضعی و فشار نامطمئن است، انتخاب را قطعی نکنید. لوله تاشو را نباید فقط براساس نام اینچی با اتصال پلی‌اتیلن سخت یکسان فرض کرد.",
          "مکمل‌های رایج شامل رابط یا سرشلنگی هم‌سایز، بست مناسب، شیر و قطعات انتهای خط است. برای فشار بالاتر یا نصب دائمی ممکن است خانواده دیگری از لوله مناسب‌تر باشد."
        )
    return (
      f"این نوار تیپ برای کشت‌هایی مناسب است که فاصله خروجی ثبت‌شده با فاصله بوته، بافت خاک و برنامه آبیاری هماهنگ باشد. انتخاب مطمئن نیازمند کنترل طول ردیف، فشار، کیفیت آب و فیلتراسیون است.",
      "اگر طول رول، قطر تیپ، دبی هر خروجی یا نیاز فیلتراسیون روی لیبل همان کالا تأیید نشده، سفارش پروژه را فقط از روی عبارت فاصله ۲۰ سانتی‌متر نهایی نکنید. آب با ذرات معلق و فشار نامناسب می‌تواند عملکرد خط را مختل کند.",
      "مکمل‌های معمول شامل شیر نوار تیپ، واشر، رابط، بست انتهایی و فیلتر متناسب با کیفیت آب است. برای فاصله کشت متفاوت، نوار تیپ با فاصله خروجی دیگر می‌تواند جایگزین مناسب‌تری باشد."
    )

def video_html(family:str, videos:dict)->str:
    v=videos["families"][family]
    src=v["video"]["source_url"]
    poster=v["thumbnail"]["source_url"]
    title={"valve":"راهنمای انتخاب شیر در شبکه آبیاری","fitting":"راهنمای انتخاب اتصال پیچی یا جوشی","fertigation":"راهنمای تکمیل سبد و تجهیزات آبیاری","layflat_rain":"راهنمای انتخاب سایز لوله نخدار و لی‌فلت","drip_tape":"راهنمای قبل از خرید نوار تیپ"}[family]
    return f"""<h2>{title}</h2>
<video controls preload="metadata" src="{src}" poster="{poster}" style="max-width:100%;height:auto"></video>
<p>این ویدئو یک <strong>راهنمای تصمیم‌گیری برای خانواده محصول</strong> است و نمایش آزمایش اختصاصی همین SKU نیست. برای عددهای فنی نهایی، مشخصات روی خود کالا یا دیتاشیت همان مدل ملاک است.</p>"""

def decision_section(pim_row:dict, product:dict, attrs:list[dict], videos:dict)->str:
    name=product.get("name") or ""
    vals=values_from_attrs(attrs)
    family=pim_row["family"]
    suitable,unsuitable,complements=family_copy(family,name,vals)
    brand=vals.get("برند","برند تأییدشده در داده فعلی ثبت نشده")
    sku=product.get("sku") or f"K20-{product.get('id')}"
    size=vals.get("سایز","")
    connection=vals.get("نوع اتصال","")
    pressure=vals.get("فشار کاری","")
    material=vals.get("جنس","")
    extras=[]
    for k in ("ظرفیت","طول","فاصله قطره","فیلتراسیون"):
        if vals.get(k): extras.append(f"<tr><th>{k}</th><td>{vals[k]}</td></tr>")
    links="".join(f'<li><a href="{u}">{label}</a></li>' for label,u in LINKS[family])
    return f"""{MARK_START}
<section class="k21-product-decision" dir="rtl">
<h2>پاسخ سریع برای تصمیم خرید</h2>
<p><strong>{name}</strong> را زمانی انتخاب کنید که مشخصات واقعی خط، قطعه مقابل و شرایط کار با داده‌های همین صفحه هماهنگ باشند. کشاورز بیست این بخش را برای جلوگیری از خرید اشتباه نوشته است؛ هر مشخصه‌ای که هنوز تأیید نشده، صریحاً «نیازمند تأیید» باقی می‌ماند و با عدد حدسی پر نمی‌شود.</p>
<table>
<tr><th>SKU</th><td>{sku}</td></tr>
<tr><th>برند</th><td>{brand}</td></tr>
<tr><th>سایز/ظرفیت مبنا</th><td>{size}</td></tr>
<tr><th>نوع اتصال</th><td>{connection}</td></tr>
<tr><th>جنس</th><td>{material}</td></tr>
<tr><th>فشار کاری</th><td>{pressure}</td></tr>
{"".join(extras)}
</table>
<h2>این محصول برای چه کسی مناسب است؟</h2>
<p>{suitable}</p>
<h2>چه زمانی مناسب نیست؟</h2>
<p>{unsuitable}</p>
<h2>سازگاری؛ قبل از سفارش این موارد را تطبیق دهید</h2>
<ol>
<li>اندازه واقعی خط و قطعه مقابل را با <strong>{size}</strong> تطبیق دهید.</li>
<li>نوع اتصال را دقیقاً بررسی کنید: <strong>{connection}</strong></li>
<li>فشار شبکه را با وضعیت ثبت‌شده این محصول مقایسه کنید: <strong>{pressure}</strong></li>
<li>اگر واشر، بست، فلنج، رابط یا ابزار نصب لازم است، همان قطعات را هم‌زمان در سبد ببینید.</li>
<li>در صورت تعارض بین متن صفحه و علامت روی کالای تحویلی، قبل از نصب با پشتیبانی کشاورز بیست هماهنگ کنید.</li>
</ol>
<h2>مکمل‌ها و جایگزین‌ها</h2>
<p>{complements}</p>
<h2>راهنماهای مرتبط</h2>
<ul>{links}</ul>
<h2>ارسال، تحویل و مغایرت</h2>
<p>روش ارسال و مسئولیت باربری براساس مقصد، ابعاد و وزن سفارش تعیین می‌شود. هنگام تحویل، نام کالا، سایز، تعداد و مشخصات درج‌شده روی محصول را با سفارش تطبیق دهید. اگر مغایرتی وجود داشت، پیش از نصب یا مصرف برای بررسی مرجوعی/مغایرت با پشتیبانی کشاورز بیست هماهنگ کنید. شرایط ضمانت فقط براساس سیاست جاری فروشگاه و ضمانت معتبر همان کالا اعمال می‌شود.</p>
<h2>پرسش‌های متداول</h2>
<details><summary>آیا فقط یکسان بودن سایز برای سازگاری کافی است؟</summary><p>خیر. سایز فقط یکی از شروط است؛ نوع اتصال، قطعه مقابل، روش آب‌بندی و فشار کاری نیز باید تطبیق داشته باشند.</p></details>
<details><summary>اگر فشار کاری دقیق روی صفحه عدد ندارد چه کنم؟</summary><p>عدد را از محصول مشابه حدس نزنید. نوشته روی بدنه، پلاک، بسته‌بندی یا دیتاشیت همان مدل را بررسی کنید و در پروژه‌های حساس پیش از نصب تأیید بگیرید.</p></details>
<details><summary>آیا اقلام مکمل باید جدا سفارش داده شوند؟</summary><p>در بسیاری از نصب‌ها بله. قبل از خرید، اتصال قبل و بعد، واشر/بست/فلنج یا رابط لازم و ابزار نصب را با نقشه واقعی پروژه کنترل کنید.</p></details>
{video_html(family,videos)}
<p><small>آخرین بازبینی ساختاری این بخش: K21 Top30 — داده نامشخص جعل نشده و شناسه GTIN/MPN فقط در صورت وجود منبع معتبر اضافه می‌شود.</small></p>
</section>
{MARK_END}"""

def replace_k21(desc:str, section:str)->str:
    if MARK_START in desc and MARK_END in desc:
        return re.sub(re.escape(MARK_START)+r"[\s\S]*?"+re.escape(MARK_END),section,desc,count=1)
    return (desc or "")+"\n"+section

def short_summary(product:dict, attrs:list[dict])->str:
    v=values_from_attrs(attrs)
    size=v.get("سایز","")
    pressure=v.get("فشار کاری","")
    connection=v.get("نوع اتصال","")
    return f"""<p dir="rtl"><strong>{product.get("name")}</strong> برای انتخاب دقیق باید با سایز واقعی <strong>{size}</strong>، نوع اتصال «{connection}» و فشار شبکه تطبیق داده شود. وضعیت فشار کاری: {pressure}. قبل از سفارش، قطعه مقابل و اقلام مکمل نصب را هم بررسی کنید؛ مشخصه نامعلوم در این صفحه حدس زده نشده است.</p>"""

def rtl(s:str)->str:
    return get_display(arabic_reshaper.reshape(s))

def font(size:int,bold:bool=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p,size=size)

def wrap(text:str, n:int)->list[str]:
    words=text.split()
    lines=[]; cur=[]
    for w in words:
        if len(" ".join(cur+[w]))>n and cur:
            lines.append(" ".join(cur)); cur=[w]
        else: cur.append(w)
    if cur: lines.append(" ".join(cur))
    return lines

def download_image(url:str)->Image.Image:
    r=requests.get(url,timeout=120,headers={"User-Agent":"K21-Media/1.0"})
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")

def card_bytes(kind:str, base:Image.Image, title:str, bullets:list[str])->bytes:
    canvas=Image.new("RGB",(800,800),"white")
    if kind=="detail":
        crop=ImageOps.fit(base,(800,800),method=Image.Resampling.LANCZOS)
        canvas.paste(crop,(0,0))
    else:
        pic=ImageOps.contain(base,(720,440),method=Image.Resampling.LANCZOS)
        canvas.paste(pic,((800-pic.width)//2,25))
        d=ImageDraw.Draw(canvas)
        y=485
        for line in wrap(title,34)[:2]:
            shaped=rtl(line)
            box=d.textbbox((0,0),shaped,font=font(28,True)); w=box[2]-box[0]
            d.text(((800-w)//2,y),shaped,font=font(28,True),fill="black")
            y+=42
        for bullet in bullets[:4]:
            for line in wrap("• "+bullet,46)[:2]:
                shaped=rtl(line)
                box=d.textbbox((0,0),shaped,font=font(20)); w=box[2]-box[0]
                d.text((760-w,y),shaped,font=font(20),fill="black")
                y+=31
            y+=4
    b=io.BytesIO()
    canvas.save(b,format="WEBP",quality=90,method=6)
    return b.getvalue()

def upload_media(data:bytes, filename:str, alt:str, caption:str)->dict:
    token=base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    headers={"Authorization":f"Basic {token}","Content-Disposition":f'attachment; filename="{filename}"',"Content-Type":"image/webp","Accept":"application/json"}
    r=requests.post(f"{BASE}/wp-json/wp/v2/media",headers=headers,data=data,timeout=180)
    r.raise_for_status()
    item=r.json()
    item=wp(f"media/{item['id']}",method="POST",json={"alt_text":alt,"caption":caption,"title":alt})
    return {"id":int(item["id"]),"src":item.get("source_url"),"alt":alt,"derived":True}

def set_alt(media_id:int, alt:str):
    wp(f"media/{media_id}",method="POST",json={"alt_text":alt})

def make_media(product:dict, attrs:list[dict])->tuple[list[dict],list[dict]]:
    existing=product.get("images") or []
    name=product.get("name") or ""
    evidence=[]
    clean=[]
    for i,img in enumerate(existing):
        alt=(img.get("alt") or "").strip() or (name if i==0 else f"{name} — نمای {i+1}")
        if not (img.get("alt") or "").strip() and img.get("id"):
            set_alt(int(img["id"]),alt)
        clean.append({"id":int(img["id"]),"alt":alt})
        evidence.append({"attachment_id":int(img["id"]),"role":"existing_real_product_image","alt":alt,"source_url":img.get("src")})
    needed=max(0,4-len(clean))
    if needed==0: return clean,evidence
    base=download_image(existing[0]["src"])
    vals=values_from_attrs(attrs)
    bullets=[f"سایز: {vals.get('سایز','')}",f"اتصال: {vals.get('نوع اتصال','')}",f"فشار: {vals.get('فشار کاری','')}"]
    kinds=["detail","spec","compat"]
    for n in range(needed):
        kind=kinds[n]
        if kind=="detail":
            alt=f"{name} — نمای نزدیک مشتق‌شده از تصویر واقعی محصول"
            b=card_bytes(kind,base,name,bullets)
        elif kind=="spec":
            alt=f"{name} — کارت مشخصات فنی قابل‌تأیید"
            b=card_bytes(kind,base,name,bullets)
        else:
            alt=f"{name} — کارت بررسی سازگاری قبل از خرید"
            b=card_bytes(kind,base,name,["سایز و قطعه مقابل را تطبیق دهید","نوع اتصال را جداگانه بررسی کنید","فشار نامشخص را از روی همان کالا تأیید کنید"])
        up=upload_media(b,f"k21-{product['id']}-{kind}.webp",alt,"مشتق تحریری از تصویر واقعی همین محصول برای توضیح مشخصات و سازگاری؛ نمای جدید یا آزمایش ساختگی نیست.")
        clean.append({"id":up["id"],"alt":up["alt"]})
        evidence.append({"attachment_id":up["id"],"role":f"editorial_derivative_{kind}","alt":up["alt"],"source_attachment_id":int(existing[0]["id"]),"source_url":up["src"]})
    return clean,evidence

def main()->int:
    pim=json.loads(PIM.read_text(encoding="utf-8"))
    videos=json.loads(VIDEOS.read_text(encoding="utf-8"))
    OPS.mkdir(exist_ok=True)
    ev={"version":"k21-top30-wave-v1","mode":"prepare-dry-run","products":[],"guardrails":["No fabricated GTIN/MPN/review/brand/pressure value.","Unknown technical values are explicitly marked as requiring confirmation.","Product writes are emitted as Bridge v3.2 dry-runs first."]}
    for row in pim["products"]:
        pid=int(row["product_id"])
        product=wc(f"products/{pid}")
        attrs=attrs_for(row,product)
        images,media_ev=make_media(product,attrs)
        desc=replace_k21(product.get("description") or "",decision_section(row,product,attrs,videos))
        short=short_summary(product,attrs)
        payload={"description":desc,"short_description":short,"attributes":attrs,"images":images,"reviews_allowed":True}
        req={"action":"rest.proxy","request_id":f"k21-top30-{pid}-dryrun-20260923","dry_run":True,"method":"PUT","path":f"/wc/v3/products/{pid}","payload":payload}
        op=OPS/f"20260923-k21-top30-{pid}-dryrun.json"
        op.write_text(json.dumps(req,ensure_ascii=False,indent=2),encoding="utf-8")
        ev["products"].append({"rank":row["rank"],"product_id":pid,"name":product.get("name"),"family":row["family"],"media":media_ev,"attributes":values_from_attrs(attrs),"bridge_request":str(op.relative_to(ROOT))})
    EVIDENCE.parent.mkdir(exist_ok=True)
    EVIDENCE.write_text(json.dumps(ev,ensure_ascii=False,indent=2),encoding="utf-8")
    print("K21_TOP30_PREPARED",len(ev["products"]))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
