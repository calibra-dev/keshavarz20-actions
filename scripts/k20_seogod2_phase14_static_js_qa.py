#!/usr/bin/env python3
import json, re, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
import requests

PAGES = {
 "drip_tape_calculator":"https://keshavarz20.com/drip-tape-length-fittings-calculator/",
 "pipe_size_selector":"https://keshavarz20.com/irrigation-pipe-size-selector/",
 "fittings_compatibility":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/",
 "filter_selector":"https://keshavarz20.com/irrigation-filter-selector/",
 "layflat_calculator":"https://keshavarz20.com/layflat-length-fittings-calculator/",
 "request_quotation":"https://keshavarz20.com/request-quotation/",
 "one_hectare_basket":"https://keshavarz20.com/one-hectare-drip-irrigation-basket/",
 "product_comparator":"https://keshavarz20.com/irrigation-product-comparator/",
 "proforma_request":"https://keshavarz20.com/request-proforma/",
}

SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.I|re.S)

def node_check(src):
    with tempfile.NamedTemporaryFile("w",suffix=".js",encoding="utf-8",delete=False) as f:
        f.write(src)
        p=f.name
    r=subprocess.run(["node","--check",p],capture_output=True,text=True)
    return {"ok":r.returncode==0,"stderr":(r.stderr or "")[-1800:]}

rows=[]
s=requests.Session()
s.headers.update({"User-Agent":"k20-seogod2-phase14-static-js-qa/1.0","Cache-Control":"no-cache"})
for key,url in PAGES.items():
    r=s.get(url,timeout=60)
    html=r.text or ""
    scripts=[]
    for i,(attrs,src) in enumerate(SCRIPT_RE.findall(html)):
        typem=re.search(r'type=["\']([^"\']+)["\']',attrs,re.I)
        typ=(typem.group(1).lower() if typem else "")
        if typ and typ not in {"text/javascript","application/javascript","module"}:
            continue
        chk=node_check(src)
        scripts.append({
          "index":i,"chars":len(src),"ok":chk["ok"],"stderr":chk["stderr"],
          "markers":[m for m in ["k20-calc","lfCalc","k20-search-btn","growthos","WebMCP"] if m.lower() in src.lower()]
        })
    rows.append({
      "key":key,"url":url,"http":r.status_code,"bytes":len(r.content),
      "script_count":len(scripts),"script_fail":sum(1 for x in scripts if not x["ok"]),
      "scripts":scripts,"pass":r.status_code==200 and all(x["ok"] for x in scripts)
    })

out={
 "program":"SEO God2","phase":14,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "mode":"public-read-only-static-js-parse",
 "pages":rows,
 "pages_pass":sum(1 for x in rows if x["pass"]),
 "pages_fail":sum(1 for x in rows if not x["pass"])
}
out["overall_pass"]=out["pages_fail"]==0
Path("seo-god2-results").mkdir(exist_ok=True)
Path("seo-god2-results/phase14-static-js-parse.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print("SEO_GOD2_PHASE14_STATIC_JS",out["overall_pass"],out["pages_pass"],"/",len(rows))
for x in rows:
    if not x["pass"]:
        print("FAIL",x["key"],[(s["index"],s["markers"],s["stderr"][-400:]) for s in x["scripts"] if not s["ok"]])
