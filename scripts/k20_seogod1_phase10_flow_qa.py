#!/usr/bin/env python3
import os,json,requests,re
from datetime import datetime,timezone
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session();S.auth=AUTH;S.headers.update({"Accept":"application/json","User-Agent":"k20-seogod1-flow-qa/1.0","Cache-Control":"no-cache"})
def get(path,params=None):
 r=S.get(BASE+"/"+path.lstrip("/"),params=params,timeout=120);r.raise_for_status();return r.json()
def public(url):
 r=requests.get(url,timeout=60,headers={"User-Agent":"k20-seogod1-flow-qa/1.0","Cache-Control":"no-cache"})
 return {"http":r.status_code,"bytes":len(r.content),"final_url":r.url}
posts=get("wp-json/wp/v2/posts",{"slug":"drip-tape-length-fittings-calculator","context":"edit","per_page":5})
if not posts: raise RuntimeError("calculator missing")
calc=posts[0]; calc_raw=((calc.get("content") or {}).get("raw") or "")
pages={}
for key,pid in [("basket",145233),("comparator",145234)]:
 o=get(f"wp-json/wp/v2/pages/{pid}",{"context":"edit"}); raw=((o.get("content") or {}).get("raw") or "")
 pages[key]={"id":pid,"status":o.get("status"),"slug":o.get("slug"),"link":o.get("link"),"chars":len(raw),"raw":raw,"public":public(o.get("link"))}
store=requests.get(BASE+"/wp-json/wc/store/v1/products",params={"per_page":2},timeout=60,headers={"User-Agent":"k20-seogod1-flow-qa/1.0"})
store_ok=store.ok and isinstance(store.json(),list)
# Keep the already-reviewed quantity formula and test a deterministic case.
area=10000; length=100; spacing=1; waste=5; roll=1000
width=area/length; rows=max(1,int(width//spacing)); base=rows*length; total=base*(1+waste/100); rolls=int(-(-total//roll))
formula={"rows":rows,"base_tape_m":base,"total_tape_m":total,"rolls":rolls,"ok":rows==100 and base==10000 and total==10500 and rolls==11}
checks={
 "calculator_public":calc.get("status")=="publish" and public(calc.get("link")).get("http")==200,
 "calculator_to_basket":"one-hectare-drip-irrigation-basket" in calc_raw,
 "calculator_to_comparator":"irrigation-product-comparator" in calc_raw,
 "calculator_to_quote":"wa.me/989179197005" in calc_raw and "پیش" in calc_raw,
 "basket_public":pages["basket"]["status"]=="publish" and pages["basket"]["public"]["http"]==200,
 "basket_has_calculator":"drip-tape-length-fittings-calculator" in pages["basket"]["raw"],
 "basket_has_comparator":"irrigation-product-comparator" in pages["basket"]["raw"],
 "basket_has_quote":"wa.me/989179197005" in pages["basket"]["raw"] and "پیش" in pages["basket"]["raw"],
 "basket_safety_copy":"طراحی هیدرولیکی" in pages["basket"]["raw"] and "تأیید فنی" in pages["basket"]["raw"],
 "comparator_public":pages["comparator"]["status"]=="publish" and pages["comparator"]["public"]["http"]==200,
 "comparator_to_basket":"one-hectare-drip-irrigation-basket" in pages["comparator"]["raw"],
 "comparator_has_quote":"wa.me/989179197005" in pages["comparator"]["raw"] and "پیش" in pages["comparator"]["raw"],
 "comparator_unknown_policy":"اعلام نشده" in pages["comparator"]["raw"],
 "store_api_ok":store_ok,
 "formula_ok":formula["ok"]
}
out={"program":"SEO God1","phase":10,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"checks":checks,"formula_test":formula,
 "objects":{"calculator":{"id":calc.get("id"),"status":calc.get("status"),"link":calc.get("link"),"chars":len(calc_raw)},
            "basket":{k:v for k,v in pages["basket"].items() if k!="raw"},"comparator":{k:v for k,v in pages["comparator"].items() if k!="raw"}},
 "pass":all(checks.values()),
 "policy":"Flow is calculator -> basket/comparator -> quote/expert review. No exact compatibility is inferred from same-size/title-only clues."}
os.makedirs("seo-god1-results",exist_ok=True)
with open("seo-god1-results/phase10-flow-qa.json","w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
print("PHASE10_FLOW_QA",out["pass"],json.dumps(checks,ensure_ascii=False))
