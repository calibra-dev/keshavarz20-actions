#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-phase3-decision-links/1.0","Cache-Control":"no-cache"})
MARKER="<!-- k20-phase3-decision-links -->"

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
out=[]
for item in pim.get("products",[]):
    pid=int(item["product_id"])
    r=S.get(urljoin(BASE,f"wp-json/wc/v3/products/{pid}"),timeout=120)
    r.raise_for_status()
    p=r.json()
    desc=p.get("description") or ""
    if MARKER in desc:
        out.append({"product_id":pid,"status":"already_present"})
        continue
    links=item.get("decision_links") or []
    if not links:
        out.append({"product_id":pid,"status":"no_verified_site_links"})
        continue
    lis="".join(f'<li><a href="{x["url"]}">{x["label"]}</a></li>' for x in links)
    block=f'''\n\n{MARKER}
<section class="k20-phase3-decision-links" dir="rtl">
<h2>راهنمای قبل از خرید و بررسی سازگاری</h2>
<p>برای جلوگیری از انتخاب اشتباه، قبل از سفارش مشخصات واقعی همین محصول را با نیاز پروژه تطبیق دهید. <strong>سایز نامی به‌تنهایی سازگاری را ثابت نمی‌کند</strong> و نوع اتصال، شرایط کاری و قطعات مکمل باید جداگانه کنترل شوند.</p>
<ul>{lis}</ul>
<p><strong>پیش از نهایی‌کردن خرید:</strong> سایز، نوع اتصال، فشار یا دبی موردنیاز و الزامات نصب را فقط بر اساس مشخصات ثبت‌شده همین محصول، برچسب یا دیتاشیت معتبر و داده واقعی پروژه نهایی کنید. اگر داده‌ای روی صفحه موجود نیست، آن را حدس نزنید.</p>
</section>
<!-- /k20-phase3-decision-links -->'''
    new_desc=desc.rstrip()+block
    req={"action":"product.content","id":pid,"payload":{"description":new_desc}}
    path=Path("requests")/f"20260918-phase3-decision-links-{pid}-v1.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(req,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    out.append({"product_id":pid,"status":"request_created","request":str(path),"links":links})

Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":True,"version":"phase3-decision-links-v1","marker":MARKER,
           "created":sum(1 for x in out if x["status"]=="request_created"),
           "already_present":sum(1 for x in out if x["status"]=="already_present"),
           "items":out},
          open("phase3-results/decision-link-request-manifest.json","w",encoding="utf-8"),
          ensure_ascii=False,indent=2)
print("PHASE3_DECISION_LINK_REQUESTS_OK",sum(1 for x in out if x["status"]=="request_created"))
