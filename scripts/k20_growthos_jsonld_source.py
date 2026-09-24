#!/usr/bin/env python3
import json, urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
URL="https://keshavarz20.com/product/%d8%a7%d8%aa%d8%b5%d8%a7%d9%84-%d9%86%d8%b1-%d9%be%d9%84%db%8c-%d8%b1%d9%88%d8%af-502-%d9%85%db%8c%d9%84%db%8c%d9%85%d8%aa%d8%b1/"
OUT=Path("growthos-phase3-results/jsonld-source-sample.json")
class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.on=False; self.buf=[]; self.blocks=[]; self.attrs=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag.lower()=="script" and (a.get("type") or "").lower()=="application/ld+json":
            self.on=True; self.buf=[]; self.attrs.append(a)
    def handle_endtag(self,tag):
        if tag.lower()=="script" and self.on:
            self.blocks.append("".join(self.buf)); self.on=False; self.buf=[]
    def handle_data(self,d):
        if self.on:self.buf.append(d)
def walk(x,path="$"):
    if isinstance(x,dict):
        yield path,x
        for k,v in x.items():
            yield from walk(v,f"{path}.{k}")
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,f"{path}[{i}]")
req=urllib.request.Request(URL,headers={"User-Agent":"K20-GrowthOS-JSONLD-Source/1.0","Cache-Control":"no-cache"})
with urllib.request.urlopen(req,timeout=90) as r:
    status=int(r.status); html=r.read().decode("utf-8","replace")
p=P(); p.feed(html)
out=[]
for i,raw in enumerate(p.blocks):
    rec={"index":i,"attrs":p.attrs[i] if i<len(p.attrs) else {}}
    try:
        data=json.loads(unescape(raw)); rec["json_valid"]=True
        nodes=[]
        for path,node in walk(data):
            if not isinstance(node,dict): continue
            t=node.get("@type")
            types=t if isinstance(t,list) else [t]
            if any(x in ("Product","Offer","Organization","WebPage","BreadcrumbList","ProductGroup") for x in types):
                nodes.append({
                    "path":path,
                    "@type":t,
                    "@id":node.get("@id"),
                    "sku":node.get("sku"),
                    "brand":node.get("brand"),
                    "seller":node.get("seller"),
                    "has_offers":bool(node.get("offers")),
                    "keys":sorted(node.keys()),
                })
        rec["nodes"]=nodes
    except Exception as e:
        rec["json_valid"]=False; rec["error"]=type(e).__name__
    out.append(rec)
result={"http":status,"url":URL,"ld_json_blocks":len(out),"blocks":out}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
