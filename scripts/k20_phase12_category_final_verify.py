#!/usr/bin/env python3
import json, os, time
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from html import unescape
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT=Path(__file__).resolve().parents[1]
MODULE_FILE=ROOT/"phase12-input"/"category-decision-modules-20261001.json"
OUT=ROOT/"phase12-results"/"category-decision-final-verify-20261001.json"
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
START="<!--k20-phase12-category-decision:start-->"
END="<!--k20-phase12-category-decision:end-->"

mods=json.loads(MODULE_FILE.read_text(encoding="utf-8"))["categories"]
s=requests.Session()
s.auth=AUTH
s.headers.update({"Accept":"application/json","User-Agent":"K20-Phase12-FinalVerify/1.0"})
retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=0.8,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
s.mount("https://",HTTPAdapter(max_retries=retry))
s.mount("http://",HTTPAdapter(max_retries=retry))
public=requests.Session()
public.headers.update({"User-Agent":"K20-Phase12-FinalVerify/1.0","Cache-Control":"no-cache"})
public.mount("https://",HTTPAdapter(max_retries=retry))
public.mount("http://",HTTPAdapter(max_retries=retry))

class SemanticHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text=[]
        self.links=[]
    def handle_data(self,data):
        value=re.sub(r"\s+"," ",unescape(data)).strip()
        if value:
            self.text.append(value)
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a":
            href=dict(attrs).get("href")
            if href:
                self.links.append(href.strip())

def semantic_signature(fragment):
    p=SemanticHTML()
    p.feed(fragment)
    return {"text":" ".join(p.text),"links":sorted(set(p.links))}

rows=[]
for key,spec in mods.items():
    cid=int(key)
    r=s.get(f"{BASE}/wp-json/wp/v2/product_cat/{cid}",params={"context":"edit"},timeout=35)
    r.raise_for_status()
    j=r.json()
    desc=j.get("description")
    if isinstance(desc,dict):
        desc=desc.get("raw") or desc.get("rendered") or ""
    desc=desc or ""
    a=desc.count(START); b=desc.count(END)
    semantic=False
    if a==1 and b==1:
        i=desc.index(START); e=desc.index(END,i)+len(END)
        semantic=(semantic_signature(desc[i:e])==semantic_signature(spec["html"]))
    link=j.get("link")
    pub=public.get(
        link+("?k20_phase12_final_verify="+str(int(time.time())) if "?" not in link else "&k20_phase12_final_verify="+str(int(time.time()))),
        timeout=35,allow_redirects=True,
        headers={"User-Agent":"K20-Phase12-FinalVerify/1.0","Cache-Control":"no-cache"}
    )
    rows.append({
        "id":cid,"name":j.get("name"),"link":link,
        "marker_start_count":a,"marker_end_count":b,
        "module_semantic_match":semantic,
        "decision_heading_in_rest":"راهنمای تصمیم انتخاب در این دسته" in desc,
        "public_http":pub.status_code,
        "public_heading_present":"راهنمای تصمیم انتخاب در این دسته" in pub.text,
        "public_final_url":pub.url
    })

ok=all(
    x["marker_start_count"]==1 and x["marker_end_count"]==1 and
    x["module_semantic_match"] and x["decision_heading_in_rest"] and
    x["public_http"]==200 and x["public_heading_present"]
    for x in rows
)
out={
    "schema_version":"seo-god2-phase12-final-verify-v2",
    "phase":12,
    "generated_at_utc":datetime.now(timezone.utc).isoformat(),
    "read_only":True,
    "status":"PASS" if ok else "FAIL",
    "categories":rows,
    "acceptance":{
        "rest_marker_exact_once":f"{sum(x['marker_start_count']==1 and x['marker_end_count']==1 for x in rows)}/6",
        "module_semantic_match":f"{sum(x['module_semantic_match'] for x in rows)}/6",
        "public_http_200":f"{sum(x['public_http']==200 for x in rows)}/6",
        "public_heading_present":f"{sum(x['public_heading_present'] for x in rows)}/6"
    }
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":ok,"status":out["status"],"acceptance":out["acceptance"]},ensure_ascii=False))
if not ok:
    raise SystemExit(1)
