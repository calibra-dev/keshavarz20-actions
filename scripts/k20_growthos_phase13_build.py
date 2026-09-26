#!/usr/bin/env python3
import json, os, re, requests, subprocess, tempfile
from datetime import datetime, timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S=requests.Session();S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.2,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET","POST"]))
S.mount("https://",HTTPAdapter(max_retries=retry));S.mount("http://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase13-build/1.0","Cache-Control":"no-cache"})

START="<!-- K20-GROWTHOS-PHASE13-WEBMCP-START -->"
END="<!-- K20-GROWTHOS-PHASE13-WEBMCP-END -->"
TARGETS=[
 ("post",143698,"drip-tape-length-fittings-calculator",["calculate_drip_tape","estimate_shipping"]),
 ("page",144239,"irrigation-fittings-compatibility-selector",["check_connector_compatibility","estimate_shipping"]),
 ("page",145233,"one-hectare-drip-irrigation-basket",["build_irrigation_cart","estimate_shipping"]),
 ("page",145286,"request-proforma",["request_proforma_invoice","estimate_shipping"])
]
ALL_TOOLS=["calculate_drip_tape","check_connector_compatibility","build_irrigation_cart","request_proforma_invoice","estimate_shipping"]

def get(path,params=None,auth=True,timeout=90):
    sess=S if auth else requests
    headers=None if auth else {"User-Agent":"k20-growthos-phase13-build/1.0","Cache-Control":"no-cache"}
    r=sess.get(urljoin(BASE+"/",path.lstrip("/")),params=params,timeout=timeout,headers=headers)
    r.raise_for_status(); return r

def api(path,params=None): return get(path,params,True).json()

def page(kind,pid):
    typ="posts" if kind=="post" else "pages"
    return api(f"wp-json/wp/v2/{typ}/{pid}",{"context":"edit"})

def write(kind,pid,content):
    typ="posts" if kind=="post" else "pages"
    r=S.post(urljoin(BASE+"/",f"wp-json/wp/v2/{typ}/{pid}"),json={"content":content},timeout=120)
    r.raise_for_status()
    return r.json() if r.content else {"http":r.status_code}

def patch(raw,block):
    p=re.compile(re.escape(START)+r"[\s\S]*?"+re.escape(END))
    return p.sub(lambda _m:block,raw,count=1) if p.search(raw) else raw.rstrip()+"\n\n"+block+"\n"

# Guard prior phases.
for rel in ["growthos-phase9-results/final-summary.json","growthos-phase10-results/summary.json","growthos-phase11-results/summary.json","growthos-phase12-results/summary.json"]:
    path=os.path.join(ROOT,rel)
    if not os.path.exists(path): raise SystemExit("Missing prerequisite "+rel)
    data=json.load(open(path,encoding="utf-8"))
    status=str(data.get("status") or "")
    if not (data.get("ok") is True or status.startswith("PASS")): raise SystemExit("Prerequisite not PASS: "+rel+" status="+status)

# Current shipping configuration, titles only; no rates/customer data.
shipping=[]
try:
    zones=api("wp-json/wc/v3/shipping/zones")
    for zid in [0]+[int(z["id"]) for z in zones]:
        try: methods=api(f"wp-json/wc/v3/shipping/zones/{zid}/methods")
        except Exception: methods=[]
        for m in methods:
            if m.get("enabled"):
                shipping.append({"zone_id":zid,"method_id":m.get("method_id"),"title":m.get("title")})
except Exception as e:
    shipping=[{"zone_id":None,"method_id":None,"title":"روش ارسال در زمان درخواست باید تأیید شود","audit_error":type(e).__name__}]
observed=datetime.now(timezone.utc).isoformat()
shipping_payload={"enabled_methods":shipping,"pricing":"پس‌کرایه/نیازمند تأیید حامل","amount_known":False}

asset_path=os.path.join(ROOT,"growthos-phase13-assets/webmcp-tools.html")
asset=open(asset_path,encoding="utf-8").read().strip()
block=asset.replace("__K20_SHIPPING_METHOD_JSON__",json.dumps(shipping_payload,ensure_ascii=False,separators=(",",":"))).replace("__K20_SHIPPING_OBSERVED_AT__",observed)

# Fail before site writes if JS syntax is invalid or contract names are missing.
m=re.search(r"<script>([\s\S]*?)</script>",block,re.I)
if not m: raise SystemExit("WebMCP script block missing")
for name in ALL_TOOLS:
    if ("name:\""+name+"\"") not in m.group(1): raise SystemExit("Missing WebMCP tool "+name)
with tempfile.NamedTemporaryFile("w",suffix=".js",encoding="utf-8",delete=False) as f:
    f.write(m.group(1)); tmp=f.name
try:
    subprocess.run(["node","--check",tmp],check=True,capture_output=True,text=True)
finally:
    try: os.unlink(tmp)
    except OSError: pass

results=[]
origin_trial_any=False
for kind,pid,slug,expected in TARGETS:
    o=page(kind,pid); before=((o.get("content") or {}).get("raw") or "")
    after=patch(before,block)
    changed=after!=before
    if changed: write(kind,pid,after)
    rb=page(kind,pid); raw=((rb.get("content") or {}).get("raw") or "")
    public=requests.get(rb.get("link"),timeout=60,headers={"User-Agent":"k20-growthos-phase13-public/1.0","Cache-Control":"no-cache"},allow_redirects=True)
    public_text=public.text
    origin_header=bool(public.headers.get("Origin-Trial"))
    origin_meta_static=bool(re.search(r"<meta[^>]+http-equiv=[\\\"']origin-trial[\\\"']",public_text,re.I))
    origin_meta_runtime=(
        'otMeta.httpEquiv="origin-trial"' in public_text
        and 'data-k20-webmcp' in public_text
        and 'otMeta.content=' in public_text
    )
    origin_trial_detected=origin_header or origin_meta_static or origin_meta_runtime
    origin_trial_any=origin_trial_any or origin_trial_detected
    tools_ok=all(('name:"'+x+'"') in raw for x in expected)
    public_signal=("__k20WebMCPPhase13" in public_text and all(x in public_text for x in expected))
    results.append({
      "kind":kind,"id":pid,"slug":slug,"status":rb.get("status"),"changed":changed,
      "marker_count":raw.count(START),"phase9_marker_count":raw.count("K20-GROWTHOS-PHASE9-FLOW-START"),
      "phase10_marker_count":raw.count("K20-GROWTHOS-PHASE10-MEASUREMENT-START"),
      "expected_tools":expected,"tools_in_readback":tools_ok,
      "public_http":public.status_code,"public_marker_comment":START in public_text,"public_webmcp_signal":public_signal,
      "origin_trial_header":origin_header,"origin_trial_meta_static":origin_meta_static,
      "origin_trial_meta_runtime":origin_meta_runtime,"origin_trial_detected":origin_trial_detected,
      "verified":rb.get("status")=="publish" and raw.count(START)==1 and tools_ok and public.status_code==200 and public_signal
    })

tool_contract={
 "phase":13,"version":"growthos-webmcp-v1","generated_at_utc":observed,
 "standard":{
   "api":"document.modelContext.registerTool",
   "fallback_alias":"navigator.modelContext",
   "secure_context_required":True,
   "permissions_policy_default":"self",
   "browser_status":"WebMCP is experimental/origin-trial technology; progressive enhancement only"
 },
 "tools":[
   {"name":"calculate_drip_tape","canonical_page":"/drip-tape-length-fittings-calculator/","effect":"mutates only local form/result state","real_order":False,"consequential":False},
   {"name":"check_connector_compatibility","canonical_page":"/irrigation-fittings-compatibility-selector/","effect":"mutates only local selector/result state","verified_fit_claim":False,"consequential":False},
   {"name":"build_irrigation_cart","canonical_page":"/one-hectare-drip-irrigation-basket/","effect":"builds draft basket only","woocommerce_cart_mutation":False,"consequential":False},
   {"name":"request_proforma_invoice","canonical_page":"/request-proforma/","effect":"builds local draft only","message_sent":False,"invoice_issued":False,"order_created":False,"consequential":False},
   {"name":"estimate_shipping","canonical_pages":[x[2] for x in TARGETS],"effect":"read-only policy result; no numeric price fabrication","estimated_amount":None,"consequential":False}
 ],
 "shipping_observed":shipping_payload,
 "security":{
   "no_arbitrary_fetch":True,"no_credentials":True,"no_customer_order_export":True,"no_price_stock_write":True,
   "no_auto_purchase":True,"no_auto_message_send":True,"input_schemas_closed_with_additionalProperties_false":True
 }
}
all_verified=all(x["verified"] for x in results)
summary={
 "ok":all_verified,
 "phase":13,"title":"WebMCP","generated_at_utc":observed,
 "status":"PASS_IMPLEMENTED_ORIGIN_TRIAL_GATE" if all_verified and not origin_trial_any else ("PASS_LIVE_ORIGIN_TRIAL" if all_verified else "FAIL"),
 "pages_verified":sum(1 for x in results if x["verified"]),"pages_total":len(results),
 "unique_tools":ALL_TOOLS,"unique_tool_count":len(ALL_TOOLS),
 "current_api":"document.modelContext.registerTool",
 "public_origin_trial_token_detected":origin_trial_any,
 "progressive_enhancement":True,
 "human_ui_preserved":True,
 "price_stock_discount_mutations":0,
 "orders_created":0,"messages_sent":0,
 "next_external_gate":"Enroll keshavarz20.com in the Chrome WebMCP origin trial and install the issued Origin-Trial token if broad live Chrome exposure is desired." if not origin_trial_any else None
}
os.makedirs("growthos-phase13-results",exist_ok=True)
for name,obj in [("tool-contract.json",tool_contract),("write-readback.json",{"results":results}),("summary.json",summary)]:
    with open("growthos-phase13-results/"+name,"w",encoding="utf-8") as f: json.dump(obj,f,ensure_ascii=False,indent=2)
print("GROWTHOS_PHASE13",json.dumps(summary,ensure_ascii=False))
