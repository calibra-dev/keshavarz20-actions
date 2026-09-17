#!/usr/bin/env python3
import json,time
from pathlib import Path
import requests

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
targets=pim.get("products",[])[:5]
rows=[]
for x in targets:
    seq=[]
    for i in range(3):
        t=time.perf_counter()
        r=requests.get(x["permalink"],timeout=120,allow_redirects=True,headers={"User-Agent":"k20-phase3-cache-probe/1.0","Accept":"text/html"})
        elapsed=round(time.perf_counter()-t,3)
        seq.append({
          "attempt":i+1,"status":r.status_code,"seconds":elapsed,
          "x_litespeed_cache":r.headers.get("x-litespeed-cache"),
          "x_litespeed_cache_control":r.headers.get("x-litespeed-cache-control"),
          "cache_control":r.headers.get("cache-control"),
          "set_cookie":bool(r.headers.get("set-cookie"))
        })
        time.sleep(0.8)
    hit=any(str(z.get("x_litespeed_cache") or "").lower()=="hit" for z in seq[1:])
    explicit_nocache=any("no-cache" in str(z.get("x_litespeed_cache_control") or "").lower() for z in seq)
    rows.append({"rank":x["rank"],"product_id":x["product_id"],"url":x["permalink"],"cache_hit_after_warmup":hit,"explicit_litespeed_nocache":explicit_nocache,"requests":seq})
summary={
 "sample":len(rows),
 "cache_hit_after_warmup":sum(1 for x in rows if x["cache_hit_after_warmup"]),
 "explicit_litespeed_nocache":sum(1 for x in rows if x["explicit_litespeed_nocache"])
}
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":True,"version":"phase3-product-cache-probe-v1","summary":summary,"products":rows},
          open("phase3-results/product-cache-probe.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_PRODUCT_CACHE_PROBE",summary)
