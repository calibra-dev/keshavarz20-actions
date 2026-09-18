#!/usr/bin/env python3
import json,time,requests,os
from datetime import datetime,timezone
urls=[
("135349","https://keshavarz20.com/product/%d8%b4%db%8c%d8%b1%d8%aa%d9%88%d9%be%db%8c-%d8%aa%da%a9-%d8%b6%d8%b1%d8%a8-%d8%af%d8%b3%d8%aa%d9%87-%d9%81%d9%84%d8%b2%db%8c-%d9%88%db%8c%d8%b3%d9%be%d8%a7%d8%b1-2-%d8%a7%db%8c%d9%86%da%86-63-%d9%85/"),
("140407","https://keshavarz20.com/product/%d9%85%d8%ae%d8%b2%d9%86-%d8%aa%d8%b2%d8%b1%db%8c%d9%82-%da%a9%d9%88%d8%af-%d8%aa%d8%a7%d9%86%da%a9-%da%a9%d9%88%d8%af-200-%d9%84%db%8c%d8%aa%d8%b1%db%8c/"),
("135339","https://keshavarz20.com/product/%d8%b4%db%8c%d8%b1-%d9%be%d8%b1%d9%88%d8%a7%d9%86%d9%87-%d8%a7%db%8c-%d9%be%d9%84%db%8c%d9%85%d8%b1%db%8c-%d8%a8%d8%a7-%d8%af%d8%b3%d8%aa%d9%87-%d9%81%d9%84%d8%b2%db%8c-%d9%88%db%8c%d8%b3%d9%be-2/")
]
rows=[]
stamp=int(time.time())
for pid,u in urls:
    sep='&' if '?' in u else '?'
    try:
        r=requests.get(u+sep+'k20_phase11_verify='+str(stamp),headers={'User-Agent':'K20-Phase11-LiveVerify/1.1','Cache-Control':'no-cache'},timeout=60)
        text=r.text
        rows.append({
          "id":int(pid),"http_status":r.status_code,"final_url":r.url,
          "decision_heading_present":"این محصول برای چه شرایطی مناسب است؟" in text,
          "evidence_limit_note_present":"مشخصات نامشخص عمداً حدس زده نشده‌اند" in text,
          "marker_present":"k20-phase11-decision:start" in text,
          "content_length":len(text),
          "cache_control":r.headers.get("x-litespeed-cache-control") or r.headers.get("cache-control"),
          "x_litespeed_cache":r.headers.get("x-litespeed-cache")
        })
    except Exception as e:
        rows.append({"id":int(pid),"error":type(e).__name__,"message":str(e)[:240]})
ok=all(x.get("http_status")==200 and x.get("decision_heading_present") and x.get("evidence_limit_note_present") for x in rows)
out={"phase":11,"verified_at_utc":datetime.now(timezone.utc).isoformat(),"ok":ok,"products":rows}
os.makedirs("phase11-results",exist_ok=True)
with open("phase11-results/public-live-verify.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2);f.write("\n")
print(json.dumps(out,ensure_ascii=False))
