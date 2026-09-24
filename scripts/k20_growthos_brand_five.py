#!/usr/bin/env python3
import json, os, requests, html as htmlmod
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone

IDS=[135383,139231,139232,140406,140407]
BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
OUT=Path("growthos-phase3-results/brand-mismatch-five.json")

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

s=requests.Session(); s.auth=AUTH; s.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-brand-five/1.0"})
rows=[]
for pid in IDS:
    a=s.get(urljoin(BASE,f"wp-json/wc/v3/products/{pid}"),timeout=120); a.raise_for_status(); p=a.json()
    brands=[str(x.get("name") or "").strip() for x in (p.get("brands") or []) if str(x.get("name") or "").strip()]
    url=p.get("permalink")
    h=requests.get(url,timeout=90,headers={"User-Agent":"k20-growthos-brand-five/1.0","Cache-Control":"no-cache"})
    parser=P(); parser.feed(h.text[:1800000])
    nodes=[]
    for raw in parser.blocks:
        try:nodes.extend(list(walk(json.loads(htmlmod.unescape(raw)))))
        except Exception:pass
    products=[n for n in nodes if isinstance(n,dict) and "Product" in types(n)]
    prod=None
    sku=str(p.get("sku") or "").strip()
    for n in products:
        if sku and str(n.get("sku") or "").strip()==sku: prod=n; break
    if prod is None and products: prod=products[0]
    sb=(prod or {}).get("brand") if prod else None
    if isinstance(sb,dict): schema_brand=sb.get("name")
    elif isinstance(sb,list): schema_brand=[x.get("name") if isinstance(x,dict) else x for x in sb]
    else: schema_brand=sb
    rows.append({
      "product_id":pid,
      "name":p.get("name"),
      "sku":sku or None,
      "woo_brands":brands,
      "brand_count":len(brands),
      "http":h.status_code,
      "product_schema_present":bool(prod),
      "schema_brand":schema_brand,
      "schema_brand_present":bool(schema_brand),
      "permalink":url
    })
out={"phase":3,"version":"growthos-brand-mismatch-five-v1","generated_at_utc":datetime.now(timezone.utc).isoformat(),"rows":rows}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
