#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
import re
import textwrap
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

ROOT=Path(__file__).resolve().parents[1]
READ_DIR=ROOT/"bridge-v3-results"
PIM_PATH=ROOT/"phase3-results"/"top30-pim.json"
VIDEO_PATH=ROOT/"phase15-video-results"/"k21-top30-family-videos.json"
LEDGER_PATH=ROOT/"geo-aeo-results"/"k21-top30-remediation-ledger.json"

UNKNOWN_MARKERS=("اعلام نشده","نیازمند تأیید","نامشخص","unknown","تأیید نشده")

def jload(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def strip_tags(s:str)->str:
    s=re.sub(r"<script[\s\S]*?</script>"," ",s or "",flags=re.I)
    s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=html.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def is_known(v:str|None)->bool:
    if not v: return False
    low=v.strip().lower()
    return not any(m in low for m in UNKNOWN_MARKERS)

def table_value(raw:str, labels:list[str])->str|None:
    for label in labels:
        pat=rf"<t[dh][^>]*>\s*{re.escape(label)}[^<]*</t[dh]>\s*<td[^>]*>([\s\S]*?)</td>"
        m=re.search(pat,raw or "",flags=re.I)
        if m:
            v=strip_tags(m.group(1))
            if v: return v
    return None

def persian_to_ascii(s:str)->str:
    return (s or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹","0123456789"))

def first_match(patterns:list[str], text:str)->str|None:
    for pat in patterns:
        m=re.search(pat,text or "",flags=re.I)
        if m: return m.group(0).strip()
    return None

def brand_for(pim:dict,name:str)->tuple[str,str,str]:
    b=((pim.get("pim_fields") or {}).get("brand") or {}).get("value")
    if b: return b,"woocommerce_brand","high"
    mapping=[
        ("ویسپار","ویسپار (Vispar)"),
        ("آبافرین","آبافرین سیستم (Abafarin System)"),
        ("آبلوله","آب لوله بسپار (Ablooleh baspar)"),
        ("آب لوله","آب لوله بسپار (Ablooleh baspar)"),
        ("آسایش آذربایجان","آسایش آذربایجان"),
        ("پلی رود","پلی رود اتصال (Polirood Etesal)"),
    ]
    for needle,value in mapping:
        if needle in name: return value,"product_title","high"
    return "Generic / بدون برند ثبت‌شده","catalog_brand_absence","high"

def model_for(name:str,family:str)->str:
    pairs=[
        ("شیر پروانه","شیر پروانه‌ای"),
        ("شیر توپی تک‌ضرب","شیر توپی تک‌ضرب"),
        ("شیر توپی دو سر ماده","شیر توپی دو سر ماده"),
        ("شیر توپی","شیر توپی"),
        ("سوپاپ","سوپاپ"),
        ("کمربند","کمربند انشعاب"),
        ("رابط مساوی","رابط مساوی"),
        ("زانو 90 درجه جوشی","زانو ۹۰ درجه جوشی"),
        ("زانو پلی","زانو پلی‌اتیلن یکسر ماده"),
        ("سر شلنگی","سرشلنگی"),
        ("سرشلنگی","سرشلنگی"),
        ("فلنج","فلنج"),
        ("فلنچ","فلنج"),
        ("مخزن تزریق کود","مخزن تزریق کود"),
        ("لوله بارانی مه","لوله بارانی مه‌پاش"),
        ("نوار تیپ","نوار تیپ آبیاری قطره‌ای"),
    ]
    for needle,value in pairs:
        if needle in name: return value
    return family

def nominal_size(name:str,raw:str)->str|None:
    tv=table_value(raw,["سایز اسمی","سایز","قطر","سایز لوله اصلی"])
    if tv and len(tv)<80 and not any(x in tv for x in ["90،","6،"]): return tv
    # saddle / compound sizes
    m=re.search(r"([۰-۹0-9]+\s*[×x]\s*[۰-۹0-9]+(?:/[۰-۹0-9]+)?\s*اینچ)",name)
    if m: return m.group(1)
    # inch + mm in parentheses
    m=re.search(r"([۰-۹0-9]+(?:\s*و\s*[۰-۹0-9]+/[۰-۹0-9]+|/[۰-۹0-9]+)?\s*اینچ)\s*\(([^)]*?میلی[^)]*)\)",name)
    if m: return f"{m.group(1)} / {m.group(2)}"
    m=re.search(r"([۰-۹0-9]+(?:/[۰-۹0-9]+)?\s*اینچ)",name)
    return m.group(1) if m else None

def material_for(name:str,raw:str)->str|None:
    tv=table_value(raw,["جنس بدنه","جنس","متریال"])
    if tv and is_known(tv) and "مطابق مشخصات" not in tv: return tv
    if "UPVC" in strip_tags(raw).upper(): return "UPVC"
    for needle,val in [
        ("پلی‌اتیلن","پلی‌اتیلن"),("پلی اتیلن","پلی‌اتیلن"),("پلیمری","پلیمری"),
        ("چدنی","چدن"),("آهنی","آهن"),("فلزی","فلزی")
    ]:
        if needle in name: return val
    return None

def pressure_for(name:str,raw:str)->tuple[str|None,str|None,str|None]:
    tv=table_value(raw,["فشار کاری","فشار اسمی","کلاس فشار","فشار"])
    if tv and re.search(r"[۰-۹0-9].*(بار|اتمسفر)",tv): return tv,"visible_product_table","high"
    plain=strip_tags(raw)
    for pat in [
        r"فشار\s+(?:اسمی|کاری|نامی)\s+(?:ثبت‌شده|درج‌شده)?\s*([۰-۹0-9.]+)\s*(بار|اتمسفر)",
        r"فشار\s+(?:اسمی|کاری|نامی)[^۰-۹0-9]{0,35}([۰-۹0-9.]+)\s*(بار|اتمسفر)",
    ]:
        m=re.search(pat,plain)
        if m: return f"{m.group(1)} {m.group(2)}","visible_product_content","high"
    m=re.search(r"([۰-۹0-9.]+)\s*(بار|اتمسفر)",name)
    if m: return f"{m.group(1)} {m.group(2)}","product_title","high"
    # Secondary family evidence only for Vispar single-stroke ball valves.
    if "ویسپار" in name and "شیر توپی" in name and "تک‌ضرب" in name:
        return "۶ بار؛ لیبل/کاتالوگ همان قطعه ملاک نهایی","secondary_family_reference_mirabsaze","medium"
    return None,None,None

def connection_for(name:str,raw:str,categories:list[dict])->tuple[str|None,str|None]:
    tv=table_value(raw,["نوع اتصال","اتصال","نوع نصب"])
    if tv and is_known(tv) and "مطابق مدل" not in tv: return tv,"visible_product_table"
    plain=strip_tags(raw)
    cats=" ".join((x.get("name") or "") for x in categories)
    if "ویفری" in plain and "شیر پروانه" in name: return "ویفری، نصب بین دو فلنج","visible_product_content"
    if "دو سر ماده" in name: return "رزوه مادگی دوطرفه","product_title"
    if "یکسر ماده" in name: return "یک سر مادگی رزوه‌ای؛ سمت دیگر مطابق ساختار زانوی پلی‌اتیلن","product_title"
    if "جوشی" in name: return "جوشی پلی‌اتیلن","product_title"
    if "فلنج دنده" in name or "فلنچ دنده" in name: return "فلنجی + رزوه‌ای","product_title"
    if "کمربند" in name:
        if "رزوه مادگی" in plain: return "کمربندی/پیچ‌ومهره‌ای با خروجی رزوه مادگی","visible_product_content"
        return "کمربندی؛ خروجی رزوه‌ای باید با قطعه مقابل تطبیق شود","visible_product_content"
    if "سر شلنگی" in name or "سرشلنگی" in name: return "سرشلنگی دنباله‌دار؛ مهار با بست متناسب","product_title"
    if "پلی اتیلن پیچی" in cats or "پلی‌اتیلن پیچی" in cats: return "پیچی/فشاری پلی‌اتیلن","woocommerce_category"
    if "رابط مساوی" in name and "آبلوله" in name: return "رابط مساوی پلی‌اتیلن؛ مکانیزم اتصال باید با قطعه واقعی تطبیق شود","product_title"
    if "ویسپار" in name and "شیر توپی" in name and "تک‌ضرب" in name:
        return "دنده‌ای دوطرفه؛ منبع ثانویه خانواده محصول","secondary_family_reference_mirabsaze"
    if "لوله بارانی" in name or "مه‌پاش" in name: return "اتصال مخصوص لوله تاشو/مه‌پاش متناسب با سایز واقعی","product_family"
    if "نوار تیپ" in name: return "اتصال مخصوص نوار تیپ؛ نوع رابط باید با قطر واقعی رول تطبیق شود","product_family"
    return None,None

def length_for(name:str,raw:str)->str|None:
    tv=table_value(raw,["طول کلاف","طول رول","طول","متراژ"])
    if tv and is_known(tv): return tv
    m=re.search(r"([۰-۹0-9]+)\s*متری",name)
    return f"{m.group(1)} متر" if m else None

def capacity_for(name:str,raw:str)->str|None:
    tv=table_value(raw,["ظرفیت","حجم"])
    if tv and is_known(tv): return tv
    m=re.search(r"([۰-۹0-9]+)\s*لیتری",name)
    return f"{m.group(1)} لیتر" if m else None

def emitter_for(name:str,raw:str)->str|None:
    tv=table_value(raw,["فاصله قطره‌چکان","فاصله خروجی","فاصله قطره"])
    if tv and is_known(tv): return tv
    if "نوار تیپ" in name:
        m=re.search(r"([۰-۹0-9]+)\s*سانتی",name)
        if m: return f"{m.group(1)} سانتی‌متر"
    return None

def filtration_for(name:str,raw:str)->str|None:
    plain=strip_tags(raw)
    m=re.search(r"([۰-۹0-9]+)\s*(?:مش|mesh)",plain,re.I)
    if m: return f"{m.group(1)} مش"
    return None

def flow_for(name:str,raw:str)->str|None:
    plain=strip_tags(raw)
    m=re.search(r"(?:دبی|آبدهی)[^۰-۹0-9]{0,25}([۰-۹0-9.]+)\s*(لیتر[^،.;<]{0,20})",plain)
    return f"{m.group(1)} {m.group(2)}".strip() if m else None

def build_facts(pim:dict,read:dict)->dict:
    name=read["data_name"]; raw=read.get("data_description") or ""
    brand,brand_src,brand_conf=brand_for(pim,name)
    pressure,pressure_src,pressure_conf=pressure_for(name,raw)
    conn,conn_src=connection_for(name,raw,read.get("data_categories") or [])
    facts={
      "brand":{"value":brand,"source":brand_src,"confidence":brand_conf},
      "model":{"value":model_for(name,pim["family"]),"source":"product_title","confidence":"high"},
      "nominal_size":{"value":nominal_size(name,raw),"source":"product_title_or_visible_table","confidence":"high"},
      "material":{"value":material_for(name,raw),"source":"product_title_or_visible_table","confidence":"high"},
      "pressure_class":{"value":pressure,"source":pressure_src,"confidence":pressure_conf or "missing"},
      "length":{"value":length_for(name,raw),"source":"product_title_or_visible_table","confidence":"high"},
      "capacity":{"value":capacity_for(name,raw),"source":"product_title_or_visible_table","confidence":"high"},
      "connection_type":{"value":conn,"source":conn_src,"confidence":"medium" if conn_src and "secondary" in conn_src else "high"},
      "flow_rate":{"value":flow_for(name,raw),"source":"visible_product_content","confidence":"high"},
      "filtration_grade":{"value":filtration_for(name,raw),"source":"visible_product_content","confidence":"high"},
      "emitter_spacing":{"value":emitter_for(name,raw),"source":"product_title_or_visible_table","confidence":"high"},
    }
    return facts

ATTR_NAMES={
 "brand":"برند","model":"مدل / نوع","nominal_size":"سایز / قطر اسمی","material":"جنس",
 "pressure_class":"فشار کاری / کلاس فشار","length":"طول / متراژ","capacity":"ظرفیت",
 "connection_type":"نوع اتصال","flow_rate":"دبی","filtration_grade":"نیاز فیلتراسیون / درجه فیلتر",
 "emitter_spacing":"فاصله خروجی / قطره‌چکان"
}

def merge_attrs(existing:list[dict],facts:dict)->list[dict]:
    out=[]; seen=set()
    for a in existing or []:
        name=(a.get("name") or "").strip()
        if not name: continue
        out.append({"name":name,"visible":bool(a.get("visible",True)),"variation":bool(a.get("variation",False)),"options":list(a.get("options") or [])})
        seen.add(name)
    for key,label in ATTR_NAMES.items():
        v=(facts.get(key) or {}).get("value")
        if v and label not in seen:
            out.append({"name":label,"visible":True,"variation":False,"options":[str(v)]})
            seen.add(label)
    return out

def fact_row(label:str,item:dict|None)->str:
    v=(item or {}).get("value")
    if not v: return f"<tr><th>{html.escape(label)}</th><td>اعلام نشده؛ پیش از خرید از لیبل، بدنه یا دیتاشیت همین مدل تأیید شود.</td></tr>"
    conf=(item or {}).get("confidence")
    suffix=" <small>(منبع ثانویه خانواده محصول؛ کنترل لیبل همان قطعه توصیه می‌شود)</small>" if conf=="medium" else ""
    return f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(v))}{suffix}</td></tr>"

def required_status(pim:dict,facts:dict)->list[tuple[str,str,bool]]:
    aliases={"connection_size":"nominal_size","pressure_requirement":"pressure_class","filtration_requirement":"filtration_grade"}
    labels={
      "nominal_size":"سایز/قطر","connection_type":"نوع اتصال","pressure_class":"فشار کاری",
      "material":"جنس","length":"طول","capacity":"ظرفیت","flow_rate":"دبی",
      "filtration_grade":"فیلتراسیون","emitter_spacing":"فاصله خروجی",
      "connection_size":"سایز اتصال","pressure_requirement":"فشار موردنیاز/مجاز",
      "filtration_requirement":"نیاز فیلتراسیون"
    }
    rows=[]
    for req in pim.get("compatibility_required_fields") or []:
        key=aliases.get(req,req); item=facts.get(key) or {}; v=item.get("value")
        rows.append((labels.get(req,req),str(v) if v else "نیازمند تأیید از مدرک همان مدل",bool(v)))
    return rows

def family_copy(family:str,name:str,facts:dict)->dict:
    size=(facts.get("nominal_size") or {}).get("value") or "سایز درج‌شده روی همین محصول"
    conn=(facts.get("connection_type") or {}).get("value") or "نوع اتصال واقعی قطعه"
    pressure=(facts.get("pressure_class") or {}).get("value") or "فشار مجاز تأییدشده همان مدل"
    if family=="valve":
        return {
          "fit":f"برای شبکه‌ای مناسب است که به قطع‌و‌وصل یا کنترل جریان در {size} نیاز دارد و نوع اتصال دو سمت با «{conn}» تطبیق داده شده باشد.",
          "not":f"اگر فشار شبکه از {pressure} عبور می‌کند، یا نوع اتصال/فلنج قطعه مقابل با این مدل تطبیق ندارد، انتخاب این شیر بدون بررسی فنی مناسب نیست.",
          "problem":"هدف این قطعه ایجاد یک نقطه کنترل قابل سرویس در خط است؛ یعنی بتوان بخشی از شبکه را برای آبیاری، تعمیر یا تعویض اتصال مدیریت کرد بدون اینکه انتخاب شیر بر پایه سایز اسمی به‌تنهایی انجام شود.",
          "complement":"قطعات مکمل بسته به آرایش خط می‌توانند شامل رابط، فلنج، مغزی، واشر یا آب‌بند سازگار باشند. مکمل نهایی باید از روی اتصال واقعی دو سمت انتخاب شود.",
          "alternative":"اگر نوع اتصال، فشار یا فضای حرکت دسته با پروژه نمی‌خواند، سراغ شیر هم‌کاربرد با اتصال و کلاس فشار متناسب بروید؛ صرفاً یک سایز مشابه را جایگزین نکنید.",
          "check":["سایز واقعی دو سمت خط","نوع اتصال و نر/ماده یا فلنجی بودن قطعه مقابل","فشار واقعی شبکه و ضربه قوچ","فضای آزاد حرکت کامل دسته","امکان مهار وزن لوله و سرویس بعدی"]
        }
    if family=="fitting":
        return {
          "fit":f"برای مونتاژی مناسب است که اندازه واقعی قطعه مقابل با {size} و روش اتصال با «{conn}» هم‌خوان باشد.",
          "not":f"اگر فقط عدد اینچ یا میلی‌متر مشترک است اما رزوه، روش اتصال، جنس یا فشار کاری تطبیق ندارد، این اتصال نباید سازگار فرض شود. فشار مرجع فعلی: {pressure}.",
          "problem":"این قطعه یک نقطه اتصال یا تغییر مسیر در شبکه می‌سازد؛ کیفیت انتخاب آن مستقیماً روی آب‌بندی، سرعت نصب و امکان سرویس اثر دارد.",
          "complement":"بسته به نوع نصب، آب‌بند، اورینگ، نوار آب‌بندی رزوه، بست، پیچ‌ومهره یا قطعه واسط می‌تواند لازم باشد. فقط اقلامی را اضافه کنید که با اتصال واقعی این مدل سازگارند.",
          "alternative":"جایگزین باید همان کارکرد را با سایز، جنس، فشار و استاندارد اتصال برابر یا سازگار ارائه کند؛ شباهت ظاهری یا نام یکسان کافی نیست.",
          "check":["قطر یا سایز واقعی هر دو سمت","نوع اتصال و استاندارد رزوه/فلنج/جوش","جنس قطعه و قطعه مقابل","فشار کاری واقعی شبکه","واشر، اورینگ یا ابزار نصب موردنیاز"]
        }
    if family=="fertigation":
        cap=(facts.get("capacity") or {}).get("value") or "ظرفیت ثبت‌شده"
        return {
          "fit":f"برای پروژه‌ای مناسب است که حجم تزریق و برنامه کوددهی با {cap} هم‌خوان باشد و سایز ورودی/خروجی و فشار شبکه قبل از نصب تأیید شده باشد.",
          "not":"اگر فشار مجاز مخزن، سایز اتصال‌ها یا روش تزریق هنوز از پلاک/دیتاشیت همین نمونه تأیید نشده است، اتصال مستقیم به شبکه بدون بررسی فنی توصیه نمی‌شود.",
          "problem":"تانک کود برای واردکردن کنترل‌شده محلول کود به مدار آبیاری استفاده می‌شود؛ انتخاب ظرفیت باید با مساحت، برنامه کوددهی و زمان تزریق هماهنگ باشد.",
          "complement":"شیرهای ایزوله، شیلنگ یا لوله رابط، فیلتر مناسب، اتصالات ورودی/خروجی و تجهیزات کنترل تزریق باید به‌صورت یک مجموعه بررسی شوند.",
          "alternative":"اگر حجم تزریق کم‌تر یا بیش‌تر است، ظرفیت دیگر تانک یا روش تزریق جایگزین فقط پس از مقایسه فشار، دبی و روش اتصال انتخاب شود.",
          "check":["ظرفیت موردنیاز هر نوبت تزریق","سایز ورودی و خروجی واقعی","فشار مجاز مخزن از روی پلاک","محل نصب و دسترسی برای شست‌وشو","سازگاری کود و روش تزریق با شبکه"]
        }
    if family=="layflat_rain":
        return {
          "fit":f"برای خط بارانی/مه‌پاش انعطاف‌پذیر با {size} مناسب است؛ طول مسیر، افت فشار، منبع آب و نوع رابط باید پیش از خرید محاسبه شود.",
          "not":"اگر فشار کاری رول، فاصله خروجی‌ها یا دبی موردنیاز از روی لیبل همین رول مشخص نیست، استفاده در طراحی مرزی یا مسیرهای طولانی بدون تأیید فنی مناسب نیست.",
          "problem":"این لوله انتقال و توزیع آب را در یک خط سبک و قابل جمع‌کردن انجام می‌دهد، اما کیفیت پاشش به فشار واقعی و افت طول مسیر وابسته است.",
          "complement":"رابط، سرشلنگی، بست، درپوش انتهایی و فیلتراسیون متناسب با کیفیت آب باید همراه خط دیده شوند.",
          "alternative":"برای نصب دائمی یا فشار بالاتر، لوله پلی‌اتیلن سخت با کلاس فشار مناسب می‌تواند گزینه بررسی باشد؛ انتخاب نهایی باید با هیدرولیک پروژه انجام شود.",
          "check":["سایز واقعی رابط","طول مسیر و اختلاف ارتفاع","فشار ابتدای خط و انتهای خط","کیفیت آب و فیلتراسیون","تعداد رول و اتصالات انتهایی"]
        }
    if family=="drip_tape":
        spacing=(facts.get("emitter_spacing") or {}).get("value") or "فاصله خروجی ثبت‌شده"
        return {
          "fit":f"برای کشت‌هایی مناسب است که آرایش بوته و نیاز آبی با {spacing} هم‌خوان باشد و کیفیت آب، طول ردیف و فشار شبکه کنترل شده باشد.",
          "not":"اگر طول رول، قطر واقعی، دبی خروجی یا نیاز فیلتراسیون همان رول تأیید نشده است، برآورد متراژ و طراحی هیدرولیکی نباید فقط از روی نام محصول انجام شود.",
          "problem":"نوار تیپ آب را در طول ردیف کشت توزیع می‌کند؛ انتخاب فاصله خروجی باید با فاصله بوته، بافت خاک و طول ردیف هماهنگ باشد.",
          "complement":"فیلتر، رابط تیپ، شیر انشعاب، واشر، رابط تیپ‌به‌تیپ و بست انتهایی باید بر اساس تعداد ردیف و قطر واقعی اجزا محاسبه شوند.",
          "alternative":"اگر فاصله بوته یا شرایط خاک متفاوت است، نوار با فاصله خروجی دیگر می‌تواند مناسب‌تر باشد؛ تغییر فاصله باید بر اساس الگوی کشت انجام شود.",
          "check":["فاصله بوته و ردیف","طول هر ردیف","فشار کاری مجاز رول","کیفیت آب و درجه فیلتراسیون","متراژ کل و تعداد اتصالات"]
        }
    return {"fit":"مناسب پس از تطبیق مشخصات واقعی پروژه.","not":"بدون تطبیق فنی انتخاب نشود.","problem":"کمک به تکمیل شبکه آبیاری.","complement":"اقلام مکمل بر اساس اتصال واقعی انتخاب شوند.","alternative":"جایگزین بر اساس مشخصات فنی انتخاب شود.","check":["سایز","اتصال","فشار","کاربرد"]}

def build_section(pim:dict,read:dict,facts:dict,video:dict|None)->str:
    name=read["data_name"]; sku=read.get("data_sku") or f"K20-{read['data_id']}"
    fam=pim["family"]; copy=family_copy(fam,name,facts)
    req=required_status(pim,facts)
    status_rows="".join(f"<tr><th>{html.escape(lbl)}</th><td>{html.escape(val)}</td><td>{'تأییدشده' if ok else 'نیازمند تأیید'}</td></tr>" for lbl,val,ok in req)
    rows="".join([
      fact_row("برند",facts.get("brand")),fact_row("مدل / نوع",facts.get("model")),
      fact_row("سایز / قطر اسمی",facts.get("nominal_size")),fact_row("جنس",facts.get("material")),
      fact_row("فشار کاری / کلاس فشار",facts.get("pressure_class")),fact_row("نوع اتصال",facts.get("connection_type")),
      fact_row("طول / متراژ",facts.get("length")),fact_row("ظرفیت",facts.get("capacity")),
      fact_row("دبی",facts.get("flow_rate")),fact_row("فیلتراسیون",facts.get("filtration_grade")),
      fact_row("فاصله خروجی",facts.get("emitter_spacing"))
    ])
    checks="".join(f"<li>{html.escape(x)}</li>" for x in copy["check"])
    video_html=""
    if video and video.get("video",{}).get("source_url"):
        vu=html.escape(video["video"]["source_url"]); tu=html.escape((video.get("thumbnail") or {}).get("source_url") or "")
        poster=f' poster="{tu}"' if tu else ""
        video_html=f"""<h2>ویدئوی راهنمای این خانواده محصول</h2>
<video controls preload="metadata" src="{vu}"{poster} style="max-width:100%;height:auto"></video>
<p>این ویدئو راهنمای تصمیم‌گیری برای خانواده «{html.escape(fam)}» است و جای مشخصات اختصاصی همین مدل را نمی‌گیرد. مقادیر نهایی را با جدول و لیبل همین کالا تطبیق دهید.</p>"""
    source_note="داده‌های این بخش از عنوان زنده محصول، محتوای فعلی صفحه، ویژگی‌های ثبت‌شده ووکامرس و رسانه واقعی همین کالا استخراج شده‌اند. هر مقدار تأییدنشده به‌صراحت با «نیازمند تأیید» نگه داشته شده و GTIN/MPN ساخته نشده است."
    if (facts.get("pressure_class") or {}).get("source")=="secondary_family_reference_mirabsaze":
        source_note+=" فشار ۶ بار در این مورد از یک منبع ثانویه خانواده شیر توپی تک‌ضرب ویسپار آمده است؛ نوشته روی قطعه یا کاتالوگ همان نمونه اولویت دارد."
    return f"""
<!-- k21-top30-start -->
<section class="k21-top30-ai-readiness" dir="rtl" data-product-id="{read['data_id']}" style="direction:rtl;text-align:right;line-height:2">
<h2>جمع‌بندی انتخاب؛ قبل از خرید این محصول چه بدانیم؟</h2>
<p><strong>{html.escape(name)}</strong> با شناسه <strong>SKU {html.escape(sku)}</strong> زمانی انتخاب مطمئن‌تری است که سایز، اتصال و شرایط کاری آن با خط واقعی پروژه تطبیق داده شود. هدف این بخش جلوگیری از خرید قطعه هم‌نام اما ناسازگار است، نه صرفاً افزایش حجم توضیحات.</p>
<p><strong>مناسب است وقتی:</strong> {html.escape(copy['fit'])}</p>
<p><strong>مناسب نیست وقتی:</strong> {html.escape(copy['not'])}</p>
<p><strong>مسئله‌ای که حل می‌کند:</strong> {html.escape(copy['problem'])}</p>

<h2>مشخصات تصمیم‌ساز و وضعیت اطمینان داده</h2>
<table><tbody>{rows}</tbody></table>

<h2>کنترل سازگاری قبل از سفارش</h2>
<table><thead><tr><th>فیلد لازم</th><th>وضعیت/مقدار</th><th>نتیجه</th></tr></thead><tbody>{status_rows}</tbody></table>
<p>هم‌اندازه بودن اینچ یا میلی‌متر به‌تنهایی سازگاری را ثابت نمی‌کند. نوع اتصال، فشار، جنس، آب‌بندی و قطعه مقابل باید جداگانه بررسی شوند.</p>

<h2>چک‌لیست کوتاه قبل از خرید</h2>
<ul>{checks}</ul>

<h2>مکمل‌ها و جایگزین‌ها</h2>
<p><strong>مکمل:</strong> {html.escape(copy['complement'])}</p>
<p><strong>جایگزین:</strong> {html.escape(copy['alternative'])}</p>

<h2>پرسش‌های متداول فنی</h2>
<details><summary>آیا فقط با سایز درج‌شده در نام می‌توان سفارش داد؟</summary><p>خیر. سایز نقطه شروع است؛ نوع اتصال، قطعه مقابل و شرایط کاری باید هم‌زمان کنترل شوند.</p></details>
<details><summary>اگر فشار کاری روی صفحه مشخص نباشد چه کنیم؟</summary><p>عدد حدسی استفاده نکنید. فشار را از نوشته روی بدنه، بسته‌بندی یا دیتاشیت همان مدل تأیید کنید؛ برای طراحی نزدیک حد فشار این کنترل ضروری است.</p></details>
<details><summary>چطور از ناسازگاری اتصال جلوگیری کنیم؟</summary><p>عکس و اندازه واقعی دو سمت اتصال، نر/ماده یا فلنجی/جوشی بودن و روش آب‌بندی را قبل از سفارش با محصول تطبیق دهید.</p></details>
<details><summary>آیا محصول هم‌سایز می‌تواند جایگزین مستقیم باشد؟</summary><p>نه همیشه. جایگزینی فقط زمانی قابل قبول است که سایز، استاندارد اتصال، جنس و محدوده فشار نیز سازگار باشند.</p></details>

{video_html}

<h2>ارسال، مغایرت و کنترل هنگام تحویل</h2>
<p>شرایط ارسال و مرجوعی براساس سیاست جاری کشاورز بیست اعمال می‌شود. هنگام تحویل، نام و سایز، سلامت ظاهری و در صورت وجود نوشته‌های روی بدنه/لیبل را با سفارش تطبیق دهید. اگر مشخصات روی کالای تحویلی با صفحه تفاوت داشت، قبل از نصب برای بررسی مغایرت با پشتیبانی هماهنگ کنید.</p>
<p><small>{html.escape(source_note)}</small></p>
</section>
<!-- k21-top30-end -->
"""

def short_summary(read:dict,facts:dict,pim:dict)->str:
    name=read["data_name"]; size=(facts.get("nominal_size") or {}).get("value")
    conn=(facts.get("connection_type") or {}).get("value")
    p=(facts.get("pressure_class") or {}).get("value")
    bits=[f"<strong>{html.escape(name)}</strong>"]
    if size: bits.append(f"سایز {html.escape(size)}")
    if conn: bits.append(f"اتصال {html.escape(conn)}")
    if p: bits.append(f"فشار {html.escape(p)}")
    bits.append("قبل از سفارش، سازگاری با قطعه مقابل و شرایط واقعی شبکه را کنترل کنید.")
    return '<div dir="rtl"><p>'+"؛ ".join(bits)+".</p></div>"

def remove_old_section(desc:str)->str:
    return re.sub(r"\s*<!-- k21-top30-start -->[\s\S]*?<!-- k21-top30-end -->\s*","\n",desc or "",flags=re.I)

def font_paths():
    bold="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    reg="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return bold,reg

def rtl(s:str)->str:
    return get_display(arabic_reshaper.reshape(s))

def fit_image(source:bytes,size=(360,360))->Image.Image:
    im=Image.open(io.BytesIO(source)).convert("RGB")
    return ImageOps.contain(im,size)

def draw_wrapped(draw,txt,xy,font,fill,width_chars=42,spacing=10):
    x,y=xy
    for para in txt.split("\n"):
        lines=textwrap.wrap(para,width=width_chars,break_long_words=False,replace_whitespace=False) or [""]
        for line in lines:
            r=rtl(line)
            box=draw.textbbox((0,0),r,font=font)
            draw.text((x-(box[2]-box[0]),y),r,font=font,fill=fill)
            y+=box[3]-box[1]+spacing
        y+=4
    return y

def make_card(source:bytes,title:str,lines:list[str],footer:str)->bytes:
    W=1000;H=1000
    canvas=Image.new("RGB",(W,H),(248,249,246))
    draw=ImageDraw.Draw(canvas)
    bold_path,reg_path=font_paths()
    f_title=ImageFont.truetype(bold_path,38)
    f_body=ImageFont.truetype(reg_path,27)
    f_small=ImageFont.truetype(reg_path,20)
    im=fit_image(source,(390,390))
    canvas.paste(im,((W-im.width)//2,50))
    y=465
    draw_wrapped(draw,title,(930,y),f_title,(28,52,39),32,12); y+=70
    for line in lines:
        y=draw_wrapped(draw,"• "+line,(920,y),f_body,(45,58,50),46,8)+8
        if y>885: break
    draw_wrapped(draw,footer,(920,930),f_small,(95,105,98),72,4)
    out=io.BytesIO(); canvas.save(out,format="JPEG",quality=88,optimize=True)
    return out.getvalue()

def wp_auth():
    return (os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])

def upload_media(data:bytes,filename:str,title:str,alt:str,caption:str)->dict:
    base=os.environ["WP_BASE_URL"].rstrip("/")
    auth=wp_auth()
    r=requests.post(
        f"{base}/wp-json/wp/v2/media",
        auth=auth,
        headers={"Content-Disposition":f'attachment; filename="{filename}"',"Content-Type":"image/jpeg"},
        data=data,timeout=180
    )
    r.raise_for_status(); item=r.json(); mid=int(item["id"])
    p=requests.post(f"{base}/wp-json/wp/v2/media/{mid}",auth=auth,json={"title":title,"alt_text":alt,"caption":caption},timeout=120)
    p.raise_for_status(); item=p.json()
    return {"id":mid,"source_url":item.get("source_url"),"alt_text":item.get("alt_text")}

def patch_existing_alt(media_id:int,alt:str):
    base=os.environ["WP_BASE_URL"].rstrip("/")
    r=requests.post(f"{base}/wp-json/wp/v2/media/{media_id}",auth=wp_auth(),json={"alt_text":alt},timeout=120)
    r.raise_for_status()

def card_lines(facts:dict,pim:dict,kind:int)->tuple[str,list[str]]:
    known=[(ATTR_NAMES[k],v["value"]) for k,v in facts.items() if k in ATTR_NAMES and v.get("value")]
    req=required_status(pim,facts)
    if kind==1:
        return "مشخصات تصمیم‌ساز", [f"{a}: {b}" for a,b in known[:6]]
    if kind==2:
        return "سازگاری قبل از خرید", [f"{a}: {b}" for a,b,_ in req]+["هم‌اندازه بودن به‌تنهایی سازگاری را ثابت نمی‌کند."]
    return "چک‌لیست انتخاب مطمئن", ["سایز واقعی خط و قطعه مقابل را اندازه بگیرید.","نوع اتصال و روش آب‌بندی را کنترل کنید.","فشار کاری را با مدرک همان مدل تطبیق دهید.","اقلام مکمل نصب را قبل از ثبت سفارش کامل کنید."]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out-dir",required=True); args=ap.parse_args()
    out_dir=Path(args.out_dir); out_dir.mkdir(parents=True,exist_ok=True)
    pim=jload(PIM_PATH); videos=jload(VIDEO_PATH)["families"]
    ledger={"generated_at_utc":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"program":"K21 Top30 Human Remediation","products":[]}
    for p in pim.get("products",[]):
        pid=int(p["product_id"])
        read=jload(READ_DIR/f"20260923-top30-read-{pid}.json")["result"]
        facts=build_facts(p,read)
        family_video=videos.get(p["family"])
        current_desc=remove_old_section(read.get("data_description") or "")
        new_desc=current_desc+"\n"+build_section(p,read,facts,family_video)
        attrs=merge_attrs(read.get("data_attributes") or [],facts)

        # Existing real image + three clearly-labelled first-party decision-support cards.
        existing=read.get("data_images") or []
        image_ids=[]
        for im in existing:
            mid=int(im["id"]); image_ids.append(mid)
            if not (im.get("alt") or "").strip():
                patch_existing_alt(mid,read["data_name"])
        primary_url=(existing[0].get("src") if existing else None)
        cards=[]
        if primary_url:
            src=requests.get(primary_url,timeout=120,headers={"User-Agent":"K21-Top30-Media/1.0"}); src.raise_for_status()
            for kind in (1,2,3):
                title,lines=card_lines(facts,p,kind)
                data=make_card(src.content,title,lines,"keshavarz20.com | کارت راهنما بر پایه داده همین صفحه")
                uploaded=upload_media(data,f"k21-p{pid}-card-{kind}.jpg",f"{title} - {read['data_name']}",f"{title} برای {read['data_name']}","کارت راهنمای تصمیم‌گیری کشاورز بیست؛ تصویر مشتق‌شده از عکس واقعی محصول و داده ثبت‌شده صفحه.")
                image_ids.append(uploaded["id"]); cards.append(uploaded)

        payload={
          "description":new_desc,
          "short_description":short_summary(read,facts,p),
          "attributes":attrs,
        }
        if image_ids: payload["images"]=[{"id":x} for x in image_ids]
        request={
          "action":"rest.proxy","request_id":f"k21-top30-apply-{pid}-20260923","dry_run":False,
          "method":"PUT","path":f"/wc/v3/products/{pid}","payload":payload
        }
        (out_dir/f"01-product-{pid}.json").write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding="utf-8")

        meta=(" ".join(strip_tags(read.get("data_short_description") or "").split())[:155]).strip()
        if len(meta)<80:
            meta=strip_tags(short_summary(read,facts,p))[:155]
        seo={
          "action":"seo.update","request_id":f"k21-top30-seo-{pid}-20260923","id":pid,
          "payload":{"title":(read["data_name"][:54]+" | کشاورز بیست"),"description":meta,"focus_keyword":read["data_name"]}
        }
        (out_dir/f"02-seo-{pid}.json").write_text(json.dumps(seo,ensure_ascii=False,indent=2),encoding="utf-8")

        ledger["products"].append({
          "rank":p["rank"],"product_id":pid,"name":read["data_name"],"family":p["family"],
          "facts":facts,"compatibility":required_status(p,facts),"source_images":[x.get("id") for x in existing],
          "derived_decision_media":cards,"family_video":family_video,
          "policy":"No GTIN/MPN/review/customer outcome was fabricated. Unknown values remain explicitly unresolved."
        })

    cache={"action":"cache.purge","request_id":"k21-top30-final-cache-purge-20260923"}
    (out_dir/"99-cache-purge.json").write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding="utf-8")
    LEDGER_PATH.parent.mkdir(exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"ok":True,"products":len(ledger["products"]),"requests":len(list(out_dir.glob("*.json")))},ensure_ascii=False))

if __name__=="__main__":
    main()
