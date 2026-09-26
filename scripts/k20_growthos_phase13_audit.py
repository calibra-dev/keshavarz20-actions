#!/usr/bin/env python3
import json, os, re, requests
from datetime import datetime, timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.0,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry)); S.mount("http://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase13-audit/1.0"})
TARGETS=[
 ("post",143698,"drip-tape-length-fittings-calculator","calculate_drip_tape"),
 ("page",144239,"irrigation-fittings-compatibility-selector","check_connector_compatibility"),
 ("page",145233,"one-hectare-drip-irrigation-basket","build_irrigation_cart"),
 ("page",145286,"request-proforma","request_proforma_invoice")
]

def get(kind,pid):
 typ="posts" if kind=="post" else "pages"
 r=S.get(urljoin(BASE+"/",f"wp-json/wp/v2/{typ}/{pid}"),params={"context":"edit"},timeout=60)
 r.raise_for_status(); return r.json()

def attrs(tag):
 out={}
 for m in re.finditer(r'([:\w-]+)\s*=\s*["\']([^"\']*)["\']',tag,re.I):
  out[m.group(1).lower()]=m.group(2)
 return out

def text(s):
 return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s or '')).strip()

rows=[]
for kind,pid,slug,tool in TARGETS:
 o=get(kind,pid); raw=((o.get("content") or {}).get("raw") or "")
 controls=[]
 for m in re.finditer(r'<(input|select|textarea)\b[^>]*>',raw,re.I):
  tag=m.group(0); a=attrs(tag); cid=a.get("id",""); name=a.get("name",""); ctype=a.get("type",m.group(1).lower())
  item={"tag":m.group(1).lower(),"id":cid,"name":name,"type":ctype,"value":a.get("value"),"placeholder":a.get("placeholder"),"required":"required" in tag.lower()}
  if m.group(1).lower()=="select" and cid:
   sm=re.search(r'<select\b[^>]*\bid=["\']'+re.escape(cid)+r'["\'][^>]*>([\s\S]*?)</select>',raw,re.I)
   opts=[]
   if sm:
    for om in re.finditer(r'<option\b([^>]*)>([\s\S]*?)</option>',sm.group(1),re.I):
     oa=attrs(om.group(1)); opts.append({"value":oa.get("value",text(om.group(2))),"label":text(om.group(2))})
   item["options"]=opts
  controls.append(item)
 buttons=[]
 for bm in re.finditer(r'<button\b([^>]*)>([\s\S]*?)</button>',raw,re.I):
  ba=attrs(bm.group(1)); buttons.append({"id":ba.get("id"),"type":ba.get("type","submit"),"text":text(bm.group(2))})
 result_ids=[]
 for x in re.findall(r'getElementById\(["\']([^"\']+)["\']\)',raw):
  if x not in [c.get("id") for c in controls] and x not in [b.get("id") for b in buttons] and x not in result_ids:
   result_ids.append(x)
 rows.append({
  "tool":tool,"kind":kind,"id":pid,"slug":slug,"status":o.get("status"),"link":o.get("link"),
  "controls":controls,"buttons":buttons,"script_result_ids":result_ids,"all_ids":list(dict.fromkeys(re.findall(r'\\bid=["\\\']([^"\\\']+)["\\\']',raw,re.I))),
  "has_phase9":raw.count("K20-GROWTHOS-PHASE9-FLOW-START")==1,
  "has_phase10":raw.count("K20-GROWTHOS-PHASE10-MEASUREMENT-START")==1,
  "has_existing_webmcp":"modelContext" in raw or "toolname=" in raw.lower(),
  "chars":len(raw)
 })
out={"phase":13,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"targets":rows}
os.makedirs("growthos-phase13-results",exist_ok=True)
with open("growthos-phase13-results/form-audit.json","w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({"targets":len(rows),"tools":[{"tool":x["tool"],"controls":len(x["controls"]),"buttons":len(x["buttons"]),"existing_webmcp":x["has_existing_webmcp"]} for x in rows]},ensure_ascii=False))
