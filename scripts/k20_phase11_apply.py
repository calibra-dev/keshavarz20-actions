#!/usr/bin/env python3
import hashlib, json, os, re
from datetime import datetime, timezone
import requests

base=os.environ["WP_BASE_URL"].rstrip("/")
auth=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
marker_start='<!-- k20-phase11-decision:start -->'
marker_end='<!-- k20-phase11-decision:end -->'

specs={
135349:{
"title":"راهنمای تصمیم خرید این مدل",
"suitable":"اگر در خط آبیاری به شیر توپی با سایز نامی ۲ اینچ / ۶۳ میلی‌متر نیاز دارید و نوع اتصال، فشار کاری و آرایش اتصالات خط را قبل از خرید با سیستم موجود تطبیق داده‌اید.",
"not_suitable":"اگر فقط بر اساس قطر لوله انتخاب می‌کنید، فشار کاری خط یا نوع اتصال مشخص نیست، یا هنوز معلوم نیست شیر باید با کدام اتصال و تبدیل نصب شود.",
"facts":[("مدل","شیر توپی تک‌ضرب دسته فلزی ویسپار ۲ اینچ (۶۳ میلی‌متر)"),("برند","ویسپار (Vispar)"),("SKU","430000600")],
"inputs":["قطر خارجی/سایز لوله در محل نصب","نوع اتصال دو سمت شیر","فشار کاری واقعی خط","فضای لازم برای باز و بسته شدن دسته","ترتیب اتصالات قبل و بعد از شیر"],
"compat":"در داده مرجع فعلی، اتصال و کلاس فشار این کالا به‌صورت سخت‌تأییدشده ثبت نشده است؛ پیش از سفارش این دو مورد را با خط موجود تطبیق دهید.",
"links":[("راهنمای خرید شیرآلات آبیاری","https://keshavarz20.com/irrigation-valves-buying-guide/"),("راهنمای سازگاری اتصالات","https://keshavarz20.com/irrigation-fittings-compatibility-selector/")]
},
140407:{
"title":"راهنمای تصمیم خرید این مخزن",
"suitable":"اگر برای سامانه آبیاری به مخزن تزریق کود ۲۰۰ لیتری نیاز دارید و ظرفیت، محل نصب، اتصالات ورودی/خروجی و شرایط فشار سیستم را پیش از خرید مشخص کرده‌اید.",
"not_suitable":"اگر حجم موردنیاز شما هنوز محاسبه نشده، سایز اتصال یا فشار کاری مدار مشخص نیست، یا قرار است مخزن بدون بررسی آرایش تزریق و فیلتراسیون نصب شود.",
"facts":[("مدل","مخزن تزریق کود (تانک کود) ۲۰۰ لیتری"),("SKU","170010004")],
"inputs":["حجم محلول موردنیاز در هر نوبت","سایز اتصال ورودی و خروجی موردنیاز","فشار کاری و اختلاف فشار قابل استفاده","محل نصب و فضای سرویس","چیدمان فیلتر و مسیر تزریق"],
"compat":"ظرفیت در نام رسمی محصول مشخص است؛ اما سایز اتصال و الزام فشار در PIM فعلی به‌عنوان مشخصات سخت‌تأییدشده ثبت نشده‌اند. این دو ورودی باید قبل از سفارش بررسی شوند.",
"links":[("راهنمای کامل سیستم آبیاری قطره‌ای","https://keshavarz20.com/complete-drip-irrigation-system-guide/"),("انتخاب‌گر فیلتر آبیاری","https://keshavarz20.com/irrigation-filter-selector/")]
},
135339:{
"title":"راهنمای تصمیم خرید این مدل",
"suitable":"اگر در خط آبیاری به شیر پروانه‌ای پلیمری ویسپار ۴ اینچ / ۱۱۰ میلی‌متر نیاز دارید و نوع اتصال، فشار کاری و فضای نصب دسته فلزی با خط موجود تطبیق داده شده است.",
"not_suitable":"اگر کلاس فشار، نوع اتصال یا فضای نصب مشخص نیست، یا فقط با دیدن عدد ۱۱۰ میلی‌متر می‌خواهید سازگاری را قطعی فرض کنید.",
"facts":[("مدل","شیر پروانه‌ای پلیمری ویسپار ۴ اینچ با دسته فلزی (۱۱۰ میلی‌متر)"),("برند","ویسپار (Vispar)"),("SKU","430301000")],
"inputs":["قطر و سایز واقعی خط","نوع اتصال و فلنج/رابط مورد استفاده","فشار کاری خط","فضای لازم برای حرکت دسته","نیاز به سرویس و دسترسی دوره‌ای"],
"compat":"در داده مرجع فعلی، نوع اتصال و کلاس فشار به‌صورت سخت‌تأییدشده ثبت نشده است؛ سازگاری باید با اتصالات واقعی خط بررسی شود.",
"links":[("راهنمای خرید شیرآلات آبیاری","https://keshavarz20.com/irrigation-valves-buying-guide/"),("راهنمای سازگاری اتصالات","https://keshavarz20.com/irrigation-fittings-compatibility-selector/")]
}
}

def module(d):
    facts=''.join(f'<li><strong>{k}:</strong> {v}</li>' for k,v in d["facts"])
    inputs=''.join(f'<li>{x}</li>' for x in d["inputs"])
    links=''.join(f'<li><a href="{u}">{t}</a></li>' for t,u in d["links"])
    return f'''{marker_start}
<section class="k20-decision-module" dir="rtl">
<h2>{d["title"]}</h2>
<h3>این محصول برای چه شرایطی مناسب است؟</h3><p>{d["suitable"]}</p>
<h3>چه زمانی انتخاب مناسبی نیست؟</h3><p>{d["not_suitable"]}</p>
<h3>مشخصات تأییدشده برای تصمیم‌گیری</h3><ul>{facts}</ul>
<h3>قبل از سفارش این موارد را مشخص کنید</h3><ul>{inputs}</ul>
<h3>سازگاری و محدودیت شواهد</h3><p>{d["compat"]}</p>
<h3>راهنماهای مرتبط و گزینه‌های جایگزین</h3><ul>{links}</ul>
<p><small>این بخش برای کمک به انتخاب فنی نوشته شده است؛ مشخصات نامشخص عمداً حدس زده نشده‌اند.</small></p>
</section>
{marker_end}'''

results=[]
for pid,d in specs.items():
    url=f"{base}/wp-json/wc/v3/products/{pid}"
    r=requests.get(url,auth=auth,timeout=60); r.raise_for_status()
    p=r.json(); old=p.get("description") or ""
    old_hash=hashlib.sha256(old.encode()).hexdigest()
    cleaned=re.sub(re.escape(marker_start)+r'.*?'+re.escape(marker_end),'',old,flags=re.S).rstrip()
    new=(cleaned+"\n\n"+module(d)).strip()
    wr=requests.put(url,auth=auth,json={"description":new},timeout=90); wr.raise_for_status()
    try:
        rb=requests.get(url,auth=auth,timeout=60); rb.raise_for_status()
        q=rb.json(); desc=q.get("description") or ""
        ok=marker_start in desc and marker_end in desc and d["title"] in desc
        if not ok:
            requests.put(url,auth=auth,json={"description":old},timeout=90).raise_for_status()
            raise RuntimeError(f"readback marker failed for {pid}; rollback applied")
        results.append({
          "id":pid,"name":q.get("name"),"status":q.get("status"),"permalink":q.get("permalink"),
          "old_description_sha256":old_hash,"new_description_sha256":hashlib.sha256(desc.encode()).hexdigest(),
          "marker_verified":True,"price_touched":False,"stock_touched":False
        })
    except Exception:
        try: requests.put(url,auth=auth,json={"description":old},timeout=90)
        finally: raise

out={
 "phase":11,
 "title":"Priority Product Decision Pages",
 "status":"PASS_WITH_OWNER_DEPENDENCY_WAIVER",
 "executed_at_utc":datetime.now(timezone.utc).isoformat(),
 "owner_waiver":"User explicitly authorized writes and requested completion while phase 7/10 external blockers remain documented.",
 "products":results,
 "acceptance":{
   "suitable_not_suitable":True,"required_inputs":True,"real_specs_only":True,
   "compatibility_limitations_explicit":True,"alternatives_or_related_guides":True,
   "price_writes":False
 }
}
os.makedirs("phase11-results",exist_ok=True)
with open("phase11-results/priority-decision-modules.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
print(json.dumps({"ok":True,"products":len(results),"status":out["status"]},ensure_ascii=False))
