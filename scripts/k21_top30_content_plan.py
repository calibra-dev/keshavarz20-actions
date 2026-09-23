#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"bridge-v3-ops"

SPECS={
135349:{"model":"شیر توپی تک‌ضرب دسته فلزی","size":"۲ اینچ / ۶۳ میلی‌متر","material":"پلیمری / uPVC","connection":"دنده‌ای","pressure":"۶ بار"},
135339:{"model":"شیر پروانه‌ای پلیمری دسته فلزی","size":"۴ اینچ / ۱۱۰ میلی‌متر","material":"UPVC","connection":"ویفری، نصب بین دو فلنج","pressure":"۶ بار"},
140407:{"model":"تانک کود / مخزن تزریق کود","capacity":"۲۰۰ لیتر","size":"ورودی و خروجی ۱ اینچ","connection":"ورودی و خروجی ۱ اینچ؛ پیش از نصب با نمونه تحویلی تطبیق شود"},
135341:{"model":"شیر پروانه‌ای پلیمری دسته فلزی","size":"۵ اینچ / ۱۲۵ میلی‌متر","material":"UPVC","connection":"ویفری، نصب بین دو فلنج","pressure":"۶ بار"},
140406:{"model":"تانک کود / مخزن تزریق کود","capacity":"۱۰۰ لیتر","size":"ورودی و خروجی ۳/۴ اینچ","connection":"ورودی و خروجی ۳/۴ اینچ؛ پیش از نصب با نمونه تحویلی تطبیق شود"},
141196:{"model":"سرشلنگی فلزی","size":"۱ اینچ / ۳۲ میلی‌متر","material":"فلزی","connection":"سرشلنگی؛ مهار با بست متناسب"},
141536:{"model":"سوپاپ چدنی","size":"۶ اینچ","material":"چدن"},
140610:{"model":"کمربند انشعاب پلی‌اتیلن","size":"لوله اصلی ۶۳ میلی‌متر / خروجی ۲ اینچ","material":"پلی‌اتیلن","connection":"کمربندی دو تکه + رزوه مادگی ۲ اینچ"},
135385:{"model":"رابط مساوی","size":"۳ اینچ / ۹۰ میلی‌متر","material":"پلی‌اتیلن","connection":"پیچی/فشاری دو سر مساوی"},
140656:{"model":"شیر توپی تک‌ضرب دسته فلزی","size":"۳ اینچ / ۹۰ میلی‌متر","material":"پلیمری / uPVC","connection":"دنده‌ای","pressure":"۶ بار"},
140595:{"model":"کمربند انشعاب پلی‌اتیلن","size":"لوله اصلی ۶۳ میلی‌متر / خروجی ۱/۲ اینچ","material":"پلی‌اتیلن","connection":"کمربندی دو تکه + رزوه مادگی ۱/۲ اینچ"},
141188:{"model":"سرشلنگی فلزی","size":"۲ اینچ / ۶۳ میلی‌متر","material":"فلزی","connection":"سرشلنگی؛ مهار با بست متناسب"},
135331:{"model":"شیر توپی تک‌ضرب دسته پلیمری","size":"۲ و ۱/۲ اینچ / ۷۵ میلی‌متر","material":"پلیمری / uPVC","connection":"دنده‌ای","pressure":"۶ بار"},
139231:{"model":"زانو ۹۰ درجه جوشی","size":"۳ اینچ / ۹۰ میلی‌متر","material":"پلی‌اتیلن","connection":"جوش لب‌به‌لب","pressure":"۶ بار"},
135383:{"model":"رابط مساوی","size":"۴ اینچ / ۱۱۰ میلی‌متر","material":"پلی‌اتیلن","connection":"پیچی/فشاری دو سر مساوی"},
141528:{"model":"سوپاپ آهنی","size":"۵ اینچ","material":"آهنی"},
140014:{"model":"لوله بارانی مه‌پاش","size":"۲ اینچ","length":"۱۰۰ متر","connection":"سرشلنگی/رابط و بست متناسب با لوله ۲ اینچ","pressure":"حداکثر ۰.۸ بار برای خانواده رین‌پایپ آسایش؛ لیبل رول تحویلی کنترل شود"},
141527:{"model":"سوپاپ آهنی","size":"۴ اینچ","material":"آهنی"},
141710:{"model":"فلنج دنده‌ای آهنی","size":"۳ اینچ","material":"آهنی","connection":"رزوه‌ای × فلنجی"},
135064:{"model":"کمربند انشعاب پلی‌اتیلن","size":"لوله اصلی ۹۰ میلی‌متر / خروجی ۱ اینچ","material":"پلیمری","connection":"کمربندی دو تکه + رزوه مادگی ۱ اینچ"},
135255:{"model":"شیر توپی دو سر ماده دسته پلیمری","size":"۳ اینچ / ۹۰ میلی‌متر","connection":"رزوه مادگی در دو سمت"},
140501:{"model":"زانو پلی‌اتیلن یکسر ماده","size":"لوله ۲۵ میلی‌متر / رزوه ۳/۴ اینچ","material":"پلی‌اتیلن","connection":"پیچی/فشاری × رزوه مادگی"},
140661:{"model":"شیر توپی تک‌ضرب دسته پلیمری","size":"۴ اینچ / ۱۱۰ میلی‌متر","material":"پلیمری / uPVC","connection":"دنده‌ای","pressure":"۶ بار"},
140503:{"model":"زانو پلی‌اتیلن یکسر ماده","size":"لوله ۶۳ میلی‌متر / رزوه ۲ اینچ","material":"پلی‌اتیلن","connection":"پیچی/فشاری × رزوه مادگی","pressure":"۱۰ بار"},
139232:{"model":"زانو ۹۰ درجه جوشی","size":"۴ اینچ / ۱۱۰ میلی‌متر","material":"پلی‌اتیلن","connection":"جوش لب‌به‌لب","pressure":"۶ بار"},
135667:{"model":"شیر توپی دو سر ماده دسته پلیمری","size":"۱ اینچ / ۳۲ میلی‌متر","connection":"رزوه مادگی در دو سمت"},
140657:{"model":"شیر توپی تک‌ضرب دسته فلزی","size":"۴ اینچ / ۱۱۰ میلی‌متر","material":"پلیمری / uPVC","connection":"دنده‌ای","pressure":"۶ بار"},
135102:{"model":"فلنج پلی‌اتیلن جوشی","size":"۴ اینچ / ۱۱۰ میلی‌متر","material":"پلی‌اتیلن","connection":"جوش لب‌به‌لب × فلنجی","pressure":"۶ اتمسفر"},
135323:{"model":"شیر توپی تک‌ضرب دسته پلیمری","size":"۱ اینچ / ۳۲ میلی‌متر","material":"پلیمری / uPVC","connection":"دنده‌ای","pressure":"۶ بار"},
135235:{"model":"نوار تیپ آبیاری قطره‌ای برای کشت زیر پلاستیک","emitter":"۲۰ سانتی‌متر"},
}

ATTR_NAMES={
 "model":"مدل / نوع محصول","size":"سایز / قطر اسمی","material":"جنس","connection":"نوع اتصال",
 "pressure":"فشار کاری / کلاس فشار","length":"طول","capacity":"ظرفیت","emitter":"فاصله قطره‌چکان"
}

FAMILY_COPY={
"valve":{
 "suitable":"برای قطع‌و‌وصل یا کنترل جریان در شبکه آبیاری و انتقال آب، زمانی که سایز، نوع اتصال و فشار واقعی خط با همین مدل تطبیق دارد.",
 "unsuitable":"برای خطی که فشار آن از رده تأییدشده محصول بالاتر است، یا وقتی نوع اتصال قطعه مقابل هنوز مشخص نشده، انتخاب نهایی نکنید.",
 "install":"شیر را بدون تنش و کجی بین دو سمت خط نصب کنید، فضای کامل حرکت دسته را آزاد بگذارید و پس از آبگیری مرحله‌ای، آب‌بندی دو طرف را کنترل کنید.",
 "complement":"اتصال یا فلنج سازگار دو سمت، آب‌بند مناسب و ساپورت خط را هم‌زمان با شیر بررسی کنید. جایگزین باید با همان سایز، استاندارد اتصال و فشار کاری انتخاب شود."
},
"fitting":{
 "suitable":"برای تکمیل اتصال در شبکه آبیاری و انتقال آب، وقتی سایز، جنس، نوع اتصال و قطعه مقابل با مشخصات همین کالا هم‌خوان است.",
 "unsuitable":"اگر فقط عدد اینچ یا میلی‌متر مشابه است ولی نوع رزوه، روش جوش، فلنج یا شیوه مهار متفاوت است، سازگاری را قطعی فرض نکنید.",
 "install":"دو سمت اتصال را تمیز و هم‌راستا آماده کنید، آب‌بندی یا جوش را متناسب با نوع واقعی اتصال انجام دهید و پس از نصب با آبگیری کنترل‌شده نشتی را بررسی کنید.",
 "complement":"واشر، اورینگ، بست، فلنج یا رابط واسط فقط بر اساس هندسه واقعی همین اتصال انتخاب شود. محصول هم‌اندازه با استاندارد اتصال متفاوت، جایگزین مستقیم نیست."
},
"fertigation":{
 "suitable":"برای تزریق محلول کود در شبکه آبیاری، وقتی ظرفیت مخزن، اندازه ورودی و خروجی، فضای نصب و شرایط هیدرولیکی پروژه با نمونه تحویلی تطبیق دارد.",
 "unsuitable":"بدون تأیید پلاک یا دیتاشیت همین مخزن، فشار مجاز، جنس دقیق بدنه یا کاربرد خارج از مدار تزریق را فرض نکنید.",
 "install":"مخزن را روی بستر پایدار و قابل دسترس نصب کنید؛ پیش از سرویس فشار را قطع کنید و تمام اتصالات ورودی و خروجی را پس از راه‌اندازی از نظر نشتی کنترل کنید.",
 "complement":"شیرهای ایزوله، اتصالات ورودی و خروجی، شیلنگ یا لوله تزریق و تجهیزات کنترل باید متناسب با اندازه واقعی پورت‌های مخزن انتخاب شوند."
},
"layflat_rain":{
 "suitable":"برای خط بارانی یا مه‌پاش انعطاف‌پذیر در مزرعه و باغ، زمانی که سایز، طول مسیر، دبی و فشار واقعی شبکه با مشخصات رول تطبیق دارد.",
 "unsuitable":"برای فشار بالا یا پروژه‌ای که مشخصات دبی و فشار آن هنوز محاسبه نشده است، صرفاً بر اساس عبارت «۲ اینچ» تصمیم نگیرید.",
 "install":"لوله را بدون پیچ‌خوردگی روی مسیر باز کنید، سرشلنگی و بست را هم‌راستا ببندید و آبگیری اولیه را تدریجی انجام دهید تا نشتی و حرکت غیرعادی مشخص شود.",
 "complement":"سرشلنگی، رابط، بست، شیر و فیلتر باید با قطر واقعی و روش اتصال لوله هماهنگ باشند؛ هم‌نام بودن سایز به‌تنهایی کافی نیست."
},
"drip_tape":{
 "suitable":"برای کشت ردیفی زیر پلاستیک و پروژه‌ای که فاصله ۲۰ سانتی‌متری خروجی‌ها با الگوی کاشت، نیاز آبی و آرایش ردیف‌ها هماهنگ است.",
 "unsuitable":"اگر کیفیت آب، فیلتراسیون، طول خطوط جانبی یا فشار بهره‌برداری هنوز مشخص نیست، متراژ نهایی و تعداد رول را قطعی نکنید.",
 "install":"نوار را بدون کشش و پیچ‌خوردگی پهن کنید، ابتدای خط و انتهای خط را درست مهار کنید و پیش از بهره‌برداری کامل، شست‌وشوی اولیه و کنترل خروجی‌ها را انجام دهید.",
 "complement":"فیلتر، رابط تیپ، شیر انشعاب، انتهای خط و لوله اصلی باید در طراحی کل سیستم دیده شوند. جایگزین با فاصله خروجی متفاوت، الگوی آبیاری را تغییر می‌دهد."
}
}

def clean_old_k21(desc:str)->str:
    return re.sub(r'<!-- k21-top30-start -->[\s\S]*?<!-- k21-top30-end -->','',desc or '',flags=re.I).strip()

def attrs_merge(current:list[dict], spec:dict)->list[dict]:
    out=[]
    used=set()
    for a in current or []:
        name=(a.get("name") or "").strip()
        if name in ATTR_NAMES.values():
            continue
        out.append({"name":name,"visible":bool(a.get("visible",True)),"variation":bool(a.get("variation",False)),"options":a.get("options") or []})
        used.add(name)
    for k,label in ATTR_NAMES.items():
        v=spec.get(k)
        if v:
            out.append({"name":label,"visible":True,"variation":False,"options":[v]})
    return out

def facts_table(spec:dict,brand:str|None,sku:str)->str:
    rows=[]
    if brand: rows.append(("برند ثبت‌شده",brand))
    if sku: rows.append(("SKU کشاورز بیست",sku))
    for k,label in ATTR_NAMES.items():
        if spec.get(k): rows.append((label,spec[k]))
    rows.append(("GTIN / MPN","در داده معتبر فعلی تأیید نشده؛ عددی ساخته نشده است"))
    return "<table>"+''.join(f"<tr><th>{a}</th><td>{b}</td></tr>" for a,b in rows)+"</table>"

def block(name:str,sku:str,brand:str|None,family:str,spec:dict,video:dict,links:list[dict])->str:
    copy=FAMILY_COPY[family]
    known=", ".join(v for k,v in spec.items() if k in ("size","capacity","length","emitter","connection","pressure") and v)
    direct=f"{name} با SKU {sku or 'ثبت‌نشده'} در کشاورز بیست برای انتخاب دقیق باید بر اساس مشخصات همین مدل بررسی شود."
    if known: direct += f" داده‌های تصمیم‌ساز ثبت‌شده این صفحه شامل {known} است."
    direct += " هر مشخصه‌ای که برای همین مدل تأیید نشده، عمداً حدس زده نشده است."
    links_html=''.join(f'<li><a href="{x["url"]}">{x["label"]}</a></li>' for x in links)
    video_html=""
    if video and video.get("video",{}).get("source_url"):
        vu=video["video"]["source_url"]; pu=video.get("thumbnail",{}).get("source_url") or ""
        poster=f' poster="{pu}"' if pu else ""
        video_html=f'''<h2>ویدئوی راهنمای این خانواده محصول</h2>
<video controls preload="metadata" src="{vu}"{poster} style="max-width:100%;height:auto"></video>
<p>این ویدئو یک راهنمای تصمیم‌گیری برای خانواده همین محصول است و جایگزین کنترل سایز، فشار، قطعه مقابل و مشخصات نمونه تحویلی نیست.</p>'''
    return f'''<!-- k21-top30-start -->
<section class="k21-top30-decision" dir="rtl" style="direction:rtl;text-align:right;line-height:2">
<h2>خلاصه انتخاب؛ قبل از خرید این محصول چه چیزی را بدانیم؟</h2>
<p><strong>{direct}</strong></p>
<h2>مشخصات قابل اتکای همین مدل</h2>
{facts_table(spec,brand,sku)}
<h2>برای چه شرایطی مناسب است؟</h2>
<p>{copy["suitable"]}</p>
<h2>چه زمانی انتخاب مناسبی نیست؟</h2>
<p>{copy["unsuitable"]}</p>
<h2>سازگاری؛ قبل از ثبت سفارش</h2>
<p>سازگاری را با یک عدد تنها نسنجید. سایز واقعی، نوع اتصال، قطعه مقابل، جهت مونتاژ و در کاربردهای حساس فشار کاری باید با هم بررسی شوند. اگر فشار یا استاندارد اتصال در جدول بالا ثبت نشده، برای همان فیلد وضعیت «تأییدنشده» است و باید از روی بدنه، بسته‌بندی یا دیتاشیت همان نمونه کنترل شود.</p>
<h2>نصب و کنترل اولیه</h2>
<p>{copy["install"]}</p>
<h2>مکمل‌ها و جایگزین‌ها</h2>
<p>{copy["complement"]}</p>
<h2>پرسش‌های پرتکرار</h2>
<details><summary>مهم‌ترین کنترل قبل از خرید چیست؟</summary><p>سایز و نوع اتصال را با قطعه واقعی پروژه تطبیق دهید و اگر فشار کاری برای تصمیم شما مهم است، فقط مقدار تأییدشده همین مدل را ملاک قرار دهید.</p></details>
<details><summary>آیا هم‌اندازه بودن اینچ یا میلی‌متر یعنی دو قطعه حتماً به هم می‌خورند؟</summary><p>خیر. نوع رزوه، فلنج، روش جوش یا مهار و هندسه قطعه مقابل هم تعیین‌کننده‌اند.</p></details>
<details><summary>اگر یکی از مشخصات فنی روی صفحه نیست چه کار کنیم؟</summary><p>آن مشخصه نباید از محصول مشابه حدس زده شود. عکس لیبل، نوشته روی بدنه یا دیتاشیت همان مدل را بررسی کنید و در صورت ابهام از پشتیبانی کشاورز بیست استعلام بگیرید.</p></details>
<details><summary>بعد از نصب چه چیزی را کنترل کنیم؟</summary><p>راه‌اندازی را مرحله‌ای انجام دهید و نشتی، حرکت غیرعادی، کجی اتصال و فشار مکانیکی روی قطعه را بررسی کنید.</p></details>
<h2>ارسال، مرجوعی و ضمانت</h2>
<p>شرایط ارسال، مغایرت، مرجوعی و ضمانت براساس سیاست جاری کشاورز بیست و وضعیت همان سفارش اعمال می‌شود. هنگام تحویل، نام و سایز محصول، سلامت ظاهری و مشخصات درج‌شده روی قطعه یا بسته‌بندی را با سفارش تطبیق دهید؛ در صورت مغایرت، پیش از نصب موضوع را ثبت کنید.</p>
<h2>راهنمای تکمیلی برای تصمیم بهتر</h2>
<ul>{links_html}</ul>
{video_html}
</section>
<!-- k21-top30-end -->'''

def short_text(name:str,spec:dict,family:str)->str:
    key=[]
    for k in ("size","capacity","length","emitter","connection","pressure"):
        if spec.get(k): key.append(spec[k])
    joined="، ".join(key[:4])
    return f'<div dir="rtl"><p><strong>{name}</strong> برای انتخاب درست باید با نیاز واقعی پروژه تطبیق داده شود. {("مشخصات کلیدی ثبت‌شده: "+joined+". ") if joined else ""}پیش از سفارش، سایز، نوع اتصال، قطعه مقابل و در صورت اهمیت فشار کاری را کنترل کنید. کشاورز بیست مشخصات تأییدنشده را از محصول مشابه حدس نمی‌زند.</p></div>'

def main()->int:
    pim=json.loads((ROOT/"phase3-results/top30-pim.json").read_text(encoding="utf-8"))
    vids=json.loads((ROOT/"phase15-video-results/k21-top30-family-videos.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    generated=[]
    for row in pim["products"]:
        pid=int(row["product_id"]); spec=SPECS[pid]; family=row["family"]
        live_path=ROOT/"bridge-v3-results"/f"20260923-top30-read-{pid}.json"
        live=json.loads(live_path.read_text(encoding="utf-8"))["result"]
        desc=clean_old_k21(live.get("data_description") or "")
        name=live.get("data_name") or row["name"]
        sku=live.get("data_sku") or ""
        brand=((row.get("pim_fields") or {}).get("brand") or {}).get("value")
        video=(vids.get("families") or {}).get(family) or {}
        enriched=desc+"\n"+block(name,sku,brand,family,spec,video,row.get("decision_links") or [])
        attrs=attrs_merge(live.get("data_attributes") or [],spec)
        req={
          "action":"rest.proxy","request_id":f"k21-top30-product-{pid}-20260923",
          "method":"PUT","path":f"/wc/v3/products/{pid}",
          "payload":{"description":enriched,"short_description":short_text(name,spec,family),"attributes":attrs}
        }
        (OUT/f"20260923-k21-top30-product-{pid}.json").write_text(json.dumps(req,ensure_ascii=False,indent=2),encoding="utf-8")
        seo={
          "action":"seo.update","request_id":f"k21-top30-seo-{pid}-20260923","id":pid,
          "payload":{
            "title":f"{name} | مشخصات و سازگاری | کشاورز بیست",
            "description":f"{name}؛ مشخصات قابل اتکا، راهنمای سازگاری، نکات نصب، موارد مناسب و نامناسب و کنترل‌های قبل از خرید در کشاورز بیست.",
            "focus_keyword":name
          }
        }
        (OUT/f"20260923-k21-top30-seo-{pid}.json").write_text(json.dumps(seo,ensure_ascii=False,indent=2),encoding="utf-8")
        generated.append({"product_id":pid,"name":name,"family":family,"spec":spec})
    manifest=ROOT/"k21-top30-results"
    manifest.mkdir(exist_ok=True)
    (manifest/"top30-content-plan.json").write_text(json.dumps({"ok":True,"count":len(generated),"products":generated},ensure_ascii=False,indent=2),encoding="utf-8")
    print("K21_TOP30_CONTENT_PLAN_OK",len(generated))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
