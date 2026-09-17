#!/usr/bin/env python3
import json, os, re
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH; S.headers.update({"Accept":"application/json","User-Agent":"k20-phase3-decision-link-corrector/1.0","Cache-Control":"no-cache"})
START="<!-- k20-phase3-decision-links -->"
END="<!-- /k20-phase3-decision-links -->"

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
targets=[x for x in pim.get("products",[]) if "decision_link_missing" in (x.get("gaps") or [])]
Path("requests").mkdir(exist_ok=True)
manifest=[]
for x in targets:
    pid=int(x["product_id"])
    r=S.get(urljoin(BASE,f"wp-json/wc/v3/products/{pid}"),timeout=120);r.raise_for_status();p=r.json()
    desc=p.get("description") or ""
    # Remove the previous Phase-3 block only; preserve all pre-existing product content exactly.
    desc=re.sub(re.escape(START)+r'.*?'+re.escape(END),"",desc,flags=re.S).rstrip()
    links=x.get("decision_links") or []
    lis="".join(f'<li><a href="{z["url"]}">{z["label"]}</a></li>' for z in links)
    block=f'''\n\n{START}
<section class="k20-phase3-decision-links" dir="rtl">
<h2>راهنمای قبل از خرید و بررسی سازگاری</h2>
<p>برای جلوگیری از انتخاب اشتباه، قبل از سفارش مشخصات واقعی همین محصول را با نیاز پروژه تطبیق دهید. <strong>سایز نامی به‌تنهایی سازگاری را ثابت نمی‌کند</strong> و نوع اتصال، شرایط کاری و قطعات مکمل باید جداگانه کنترل شوند.</p>
<ul>{lis}</ul>
<p><strong>پیش از نهایی‌کردن خرید:</strong> سایز، نوع اتصال، فشار یا دبی موردنیاز و الزامات نصب را فقط بر اساس مشخصات ثبت‌شده همین محصول، برچسب یا دیتاشیت معتبر و داده واقعی پروژه نهایی کنید. اگر داده‌ای روی صفحه موجود نیست، آن را حدس نزنید.</p>
</section>
{END}'''
    req={"action":"product.content","id":pid,"payload":{"description":desc+block}}
    path=Path("requests")/f"20260918-phase3-decision-links-{pid}-v2.json"
    path.write_text(json.dumps(req,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest.append({"product_id":pid,"rank":x["rank"],"request":str(path),"links":links})
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":True,"version":"phase3-decision-link-corrective-v2","targets":len(targets),"items":manifest},
          open("phase3-results/decision-link-corrective-manifest.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_DECISION_CORRECTIVE_REQUESTS",len(targets))
