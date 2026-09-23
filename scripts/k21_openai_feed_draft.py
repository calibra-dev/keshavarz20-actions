#!/usr/bin/env python3
import os, json, re, html, datetime
from pathlib import Path
from urllib.parse import urljoin
import requests

ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k21-openai-feed-draft/1.0","Cache-Control":"no-cache"})
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()

def load(rel):
    with open(ROOT/rel,encoding="utf-8") as f:return json.load(f)

def plain(v):
    v=html.unescape(v or "")
    v=re.sub(r"<script\b[^>]*>.*?</script>"," ",v,flags=re.I|re.S)
    v=re.sub(r"<style\b[^>]*>.*?</style>"," ",v,flags=re.I|re.S)
    v=re.sub(r"<[^>]+>"," ",v)
    return re.sub(r"\s+"," ",v).strip()

def money_irr(raw,currency):
    try: amount=float(str(raw).replace(",","").strip())
    except: return None
    cur=(currency or "").upper()
    if cur in ("IRT","TMN","TOMAN"):
        amount*=10
        cur="IRR"
    elif cur!="IRR":
        return None
    if amount<=0:return None
    # IRR has no useful fractional precision for this catalog.
    return f"{int(round(amount))} IRR"

pim=load("phase3-results/top30-pim.json")
existing=load("phase19-results/product-discovery-readiness-feed-persisted.json")
existing_by={int(x["wp_product_id"]):x for x in existing.get("products",[]) if x.get("wp_product_id")}

valid=[]; blocked=[]
for item in pim.get("products",[]):
    pid=int(item["product_id"])
    r=S.get(urljoin(BASE,f"wp-json/wc/v3/products/{pid}"),timeout=120)
    r.raise_for_status(); p=r.json()
    old=existing_by.get(pid,{})
    description=plain(p.get("short_description") or "")
    if len(description)<20: description=plain(p.get("description") or "")
    description=description[:5000].strip()
    fields=item.get("pim_fields") or {}
    brand=((fields.get("brand") or {}).get("value") if isinstance(fields.get("brand"),dict) else fields.get("brand"))
    images=p.get("images") or []
    image_url=(images[0].get("src") if images else None)
    price=money_irr(p.get("price"),old.get("store_currency_raw") or "IRT")
    avail={"instock":"in_stock","outofstock":"out_of_stock","onbackorder":"backorder"}.get(p.get("stock_status"),"unknown")
    row={
      "item_id":(p.get("sku") or f"K20-{pid}").strip(),
      "title":(p.get("name") or "").strip()[:150],
      "description":description,
      "url":p.get("permalink"),
      "brand":brand,
      "seller_name":"Keshavarz20",
      "image_url":image_url,
      "availability":avail,
      "price":price,
      "wp_product_id":pid,
      "source_policy":"Existing WooCommerce visible/catalog data only; no generated specifications."
    }
    missing=[k for k in ["item_id","title","description","url","brand","seller_name","image_url","availability","price"] if not row.get(k)]
    # OpenAI discovery accepts explicit unknown availability, but current Woo state is known for these products.
    if missing:
        blocked.append({"wp_product_id":pid,"title":row["title"],"missing_required_fields":missing,"row":row})
    else:
        valid.append(row)

out={
 "program":"K21 GEO/AEO OpenAI Product Discovery",
 "version":"k21-openai-discovery-draft-v1",
 "generated_at_utc":NOW,
 "status":"INTERNAL_DRAFT_NOT_SUBMITTED",
 "official_schema_basis":"OpenAI Agentic Commerce stable file-upload product discovery: nine basic required fields.",
 "market_gate":{
   "approved_partner_access_verified":False,
   "iran_market_acceptance_verified":False,
   "standard_openai_upload_market_note":"Official documentation currently states standard OpenAI-format uploads target the US unless OpenAI confirms additional market setup.",
   "submission_allowed":False
 },
 "currency_rule":{
   "store_currency":"IRT/Toman",
   "feed_currency":"IRR",
   "conversion":"store price x10 -> IRR",
   "basis":"Existing live page/schema parity already validates IRT store amounts against IRR structured-data amounts."
 },
 "summary":{"top30":len(pim.get("products",[])),"schema_complete_rows":len(valid),"blocked_rows":len(blocked),"externally_submitted":0},
 "valid_rows":valid,
 "blocked_rows":blocked,
 "guardrails":[
   "No external submission is performed by this workflow.",
   "Missing brand or other required fields block a row instead of using placeholders.",
   "Descriptions come from existing WooCommerce product text; no new technical claims are generated.",
   "Prices and stock are read only and are never changed."
 ]
}
Path(ROOT/"geo-aeo-results").mkdir(exist_ok=True)
with open(ROOT/"geo-aeo-results/k21-openai-discovery-feed-draft.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
with open(ROOT/"geo-aeo-results/k21-openai-discovery-valid.jsonl","w",encoding="utf-8") as f:
    for row in valid:
        public={k:row[k] for k in ["item_id","title","description","url","brand","seller_name","image_url","availability","price"]}
        f.write(json.dumps(public,ensure_ascii=False)+"\n")
print("K21_OPENAI_FEED_DRAFT_OK",json.dumps(out["summary"],ensure_ascii=False))
