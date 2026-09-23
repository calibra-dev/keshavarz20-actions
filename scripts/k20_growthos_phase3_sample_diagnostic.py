#!/usr/bin/env python3
import json, urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

URLS=[
 {"id":134984,"expected_brand":"پلی رود اتصال( Poliroodetesal)","url":"https://keshavarz20.com/product/%d8%a7%d8%aa%d8%b5%d8%a7%d9%84-%d9%86%d8%b1-%d9%be%d9%84%db%8c-%d8%b1%d9%88%d8%af-502-%d9%85%db%8c%d9%84%db%8c%d9%85%d8%aa%d8%b1/"},
 {"id":136067,"expected_brand":None,"url":"https://keshavarz20.com/product/%da%a9%d9%84%d9%85-%da%af%d9%84/"}
]
OUT=Path("growthos-phase3-results/parity-sample-diagnostic.json")

class P(HTMLParser):
 def __init__(self):
  super().__init__(); self.on=False; self.buf=[]; self.blocks=[]
 def handle_starttag(self,tag,attrs):
  if tag.lower()=="script" and (dict(attrs).get("type") or "").lower()=="application/ld+json":
   self.on=True; self.buf=[]
 def handle_endtag(self,tag):
  if tag.lower()=="script" and self.on:
   self.blocks.append("".join(self.buf)); self.on=False; self.buf=[]
 def handle_data(self,data):
  if self.on:self.buf.append(data)

def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values():yield from walk(v)
 elif isinstance(x,list):
  for v in x:yield from walk(v)

rows=[]
for item in URLS:
 req=urllib.request.Request(item["url"],headers={"User-Agent":"K20-GrowthOS-P3-Diagnostic/1.0","Cache-Control":"no-cache"})
 with urllib.request.urlopen(req,timeout=90) as r:
  status=int(r.status); h=r.read().decode("utf-8","replace")
 p=P(); p.feed(h)
 nodes=[]
 for raw in p.blocks:
  try:nodes.extend(list(walk(json.loads(unescape(raw)))))
  except Exception:pass
 products=[n for n in nodes if isinstance(n,dict) and "Product" in (n.get("@type") if isinstance(n.get("@type"),list) else [n.get("@type")])]
 prod=products[0] if products else None
 brand=(prod or {}).get("brand")
 if isinstance(brand,dict):brand=brand.get("name")
 elif isinstance(brand,list):brand=[x.get("name") if isinstance(x,dict) else x for x in brand]
 rows.append({
  "product_id":item["id"],"http":status,"product_schema_present":bool(prod),
  "schema_sku":(prod or {}).get("sku"),"schema_brand":brand,
  "expected_brand":item["expected_brand"],"ld_json_blocks":len(p.blocks)
 })
OUT.write_text(json.dumps({"rows":rows},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"rows":rows},ensure_ascii=False))
