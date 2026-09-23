#!/usr/bin/env python3
import json, re, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone

TRUTH=Path("growthos-phase2-results/product-truth-registry.json")
OUT=Path("growthos-phase3-results/policy-schema-audit.json")
data=json.loads(TRUTH.read_text(encoding="utf-8"))
records=data.get("records") or []

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.on=False; self.buf=[]; self.blocks=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="script" and (dict(attrs).get("type") or "").lower()=="application/ld+json":
            self.on=True; self.buf=[]
    def handle_endtag(self,tag):
        if tag.lower()=="script" and self.on:
            self.blocks.append("".join(self.buf)); self.on=False; self.buf=[]
    def handle_data(self,d):
        if self.on:self.buf.append(d)

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

def types(n):
    t=n.get("@type") if isinstance(n,dict) else None
    return set(str(x) for x in (t if isinstance(t,list) else [t]) if x)

def brand_names(v):
    if not v:return []
    if isinstance(v,str):return [v]
    if isinstance(v,dict):return [str(v.get("name") or "")] if v.get("name") else []
    if isinstance(v,list):
        out=[]
        for x in v:out.extend(brand_names(x))
        return out
    return []

def norm(s):
    s=str(s or "").casefold()
    s=re.sub(r"[\s\u200c\u200f\(\)\[\]،,._\-]+","",s)
    return s

def inspect(rec):
    url=rec.get("permalink")
    row={"product_id":rec.get("product_id"),"name":rec.get("name"),"product_type":rec.get("product_type"),"url":url}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"K20-GrowthOS-P3-PolicySchema/1.0","Cache-Control":"no-cache"})
        with urllib.request.urlopen(req,timeout=60) as r:
            row["http"]=int(r.status); text=r.read().decode("utf-8","replace")
        p=P(); p.feed(text)
        nodes=[]
        parse_errors=0
        for raw in p.blocks:
            try:nodes.extend(list(walk(json.loads(unescape(raw)))))
            except Exception:parse_errors+=1
        products=[n for n in nodes if isinstance(n,dict) and "Product" in types(n)]
        offers=[n for n in nodes if isinstance(n,dict) and "Offer" in types(n)]
        groups=[n for n in nodes if isinstance(n,dict) and "ProductGroup" in types(n)]
        crumbs=[n for n in nodes if isinstance(n,dict) and "BreadcrumbList" in types(n)]
        orgs=[n for n in nodes if isinstance(n,dict) and ({"Organization","OnlineStore"} & types(n))]
        shipping=[n for n in nodes if isinstance(n,dict) and "OfferShippingDetails" in types(n)]
        returns=[n for n in nodes if isinstance(n,dict) and "MerchantReturnPolicy" in types(n)]
        ratings=[n for n in nodes if isinstance(n,dict) and "AggregateRating" in types(n)]
        prod=products[0] if products else {}
        offer=(prod.get("offers") if isinstance(prod,dict) else None)
        offer_list=offer if isinstance(offer,list) else ([offer] if isinstance(offer,dict) else [])
        all_offers=offer_list or offers
        nested_shipping=any(bool(o.get("shippingDetails")) for o in all_offers if isinstance(o,dict))
        nested_return=any(bool(o.get("hasMerchantReturnPolicy")) for o in all_offers if isinstance(o,dict))
        schema_brands=brand_names(prod.get("brand")) if isinstance(prod,dict) else []
        tf=(rec.get("fields") or {}).get("brand") or {}
        truth_brand=tf.get("value") if tf.get("status")!="UNKNOWN" else None
        truth_tokens=[norm(x) for x in re.split(r"[،,]",str(truth_brand or "")) if norm(x)]
        schema_tokens=[norm(x) for x in schema_brands if norm(x)]
        brand_match=None
        if truth_tokens:
            brand_match=any(any(a in b or b in a for b in schema_tokens) for a in truth_tokens) if schema_tokens else False
        row.update({
            "jsonld_parse_clean":parse_errors==0,
            "product_schema_present":bool(products),
            "offer_schema_present":bool(all_offers),
            "product_group_present":bool(groups),
            "breadcrumb_present":bool(crumbs),
            "organization_present":bool(orgs),
            "brand_truth_known":bool(truth_tokens),
            "brand_schema_present":bool(schema_tokens),
            "brand_match_when_truth_known":brand_match,
            "shipping_details_present":bool(shipping) or nested_shipping,
            "merchant_return_policy_present":bool(returns) or nested_return,
            "aggregate_rating_present":bool(ratings),
        })
    except Exception as e:
        row["error"]=type(e).__name__+": "+str(e)[:160]
    return row

rows=[]
with ThreadPoolExecutor(max_workers=12) as ex:
    fs=[ex.submit(inspect,r) for r in records]
    for f in as_completed(fs):rows.append(f.result())
rows.sort(key=lambda x:int(x.get("product_id") or 0))

def count(key,val=True):
    return sum(1 for r in rows if r.get(key) is val)
summary={
 "products":len(rows),
 "http_200":sum(1 for r in rows if r.get("http")==200),
 "product_schema_present":count("product_schema_present"),
 "offer_schema_present":count("offer_schema_present"),
 "breadcrumb_present":count("breadcrumb_present"),
 "organization_present":count("organization_present"),
 "product_group_present":count("product_group_present"),
 "brand_truth_known":count("brand_truth_known"),
 "brand_schema_present":count("brand_schema_present"),
 "brand_match_when_truth_known":count("brand_match_when_truth_known"),
 "shipping_details_present":count("shipping_details_present"),
 "merchant_return_policy_present":count("merchant_return_policy_present"),
 "aggregate_rating_present":count("aggregate_rating_present"),
 "jsonld_parse_clean":count("jsonld_parse_clean"),
 "errors":sum(1 for r in rows if r.get("error")),
}
fail_samples={
 "product_missing":[r for r in rows if r.get("product_schema_present") is False][:20],
 "brand_truth_known_schema_missing":[r for r in rows if r.get("brand_truth_known") and not r.get("brand_schema_present")][:20],
 "brand_mismatch":[r for r in rows if r.get("brand_match_when_truth_known") is False][:20],
 "shipping_absent_sample":[r for r in rows if not r.get("shipping_details_present")][:10],
 "return_absent_sample":[r for r in rows if not r.get("merchant_return_policy_present")][:10],
}
truth_shipping_known=sum(1 for r in records if ((r.get("fields") or {}).get("shipping_class") or {}).get("status")!="UNKNOWN")
truth_return_known=sum(1 for r in records if ((r.get("fields") or {}).get("warranty_return_status") or {}).get("status")!="UNKNOWN")
result={
 "phase":3,
 "version":"growthos-policy-schema-audit-v1",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "mode":"read-only",
 "summary":summary,
 "truth_context":{"shipping_class_known_records":truth_shipping_known,"warranty_return_known_records":truth_return_known},
 "interpretation":{
   "shipping_absence_is_not_auto_failure":"Shipping class is not enough to invent shippingDetails. Require real destination/rate/delivery evidence before markup.",
   "return_absence_is_not_auto_failure":"Do not invent MerchantReturnPolicy unless a verified return policy record exists.",
   "aggregate_rating_rule":"Presence is informational here; existing parity audit separately rejects AggregateRating when Woo review_count is zero."
 },
 "samples":fail_samples
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print("GROWTHOS_PHASE3_POLICY_SCHEMA",json.dumps({"summary":summary,"truth_context":result["truth_context"]},ensure_ascii=False))
