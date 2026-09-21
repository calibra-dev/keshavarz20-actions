#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")+"/"
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
REQ_PATH=sys.argv[1]
OUT_PATH=sys.argv[2]

S=requests.Session()
S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-countrywide-shipping/1.0","Cache-Control":"no-cache"})

def api(method,path,body=None):
    url=urljoin(BASE,path.lstrip("/"))
    r=S.request(method,url,json=body,timeout=120)
    data=None
    try:data=r.json()
    except Exception:pass
    if not r.ok:
        raise RuntimeError(f"{method} {path} HTTP {r.status_code}: {str(data)[:500]}")
    return data

def method_state(m):
    settings=m.get("settings") or {}
    def val(k):
        v=settings.get(k)
        if isinstance(v,dict): return v.get("value")
        return v
    return {
        "id":m.get("id"),
        "method_id":m.get("method_id"),
        "title":m.get("title"),
        "enabled":m.get("enabled"),
        "settings":{
            "title":val("title"),
            "cost":val("cost"),
        }
    }

def put_method(zone_id,instance_id,enabled=None,title=None,cost=None):
    body={}
    if enabled is not None: body["enabled"]=bool(enabled)
    settings={}
    if title is not None: settings["title"]=str(title)
    if cost is not None: settings["cost"]=str(cost)
    if settings: body["settings"]=settings
    return api("PUT",f"wp-json/wc/v3/shipping/zones/{zone_id}/methods/{instance_id}",body)

with open(REQ_PATH,"r",encoding="utf-8-sig") as f:
    req=json.load(f)

if req.get("action")!="apply_countrywide_carrier":
    raise RuntimeError("Unsupported action")

zone_id=int(req.get("zone_id",1))
flat_id=int(req.get("flat_rate_instance_id",2))
local_id=int(req.get("local_pickup_instance_id",3))
target_title=str(req.get("title") or "ارسال با باربری یا تیپاکس به سراسر کشور (هزینه حمل پس‌کرایه)")

zone=api("GET",f"wp-json/wc/v3/shipping/zones/{zone_id}")
locations=api("GET",f"wp-json/wc/v3/shipping/zones/{zone_id}/locations")
methods=api("GET",f"wp-json/wc/v3/shipping/zones/{zone_id}/methods")
by_id={int(m.get("id")):m for m in methods}

if zone.get("name")!="ایران":
    raise RuntimeError(f"Refusing write: zone {zone_id} is not named ایران")
if not any(str(x.get("code","")).upper()=="IR" and str(x.get("type","")).lower()=="country" for x in locations):
    raise RuntimeError("Refusing write: Iran zone does not explicitly cover country IR")
if flat_id not in by_id or by_id[flat_id].get("method_id")!="flat_rate":
    raise RuntimeError("Expected flat_rate instance not found")
if local_id not in by_id or by_id[local_id].get("method_id")!="local_pickup":
    raise RuntimeError("Expected local_pickup instance not found")

before={"flat_rate":method_state(by_id[flat_id]),"local_pickup":method_state(by_id[local_id])}
changed=False
try:
    put_method(zone_id,flat_id,enabled=True,title=target_title,cost="0")
    flat=api("GET",f"wp-json/wc/v3/shipping/zones/{zone_id}/methods/{flat_id}")
    fs=method_state(flat)
    if not fs["enabled"]:
        raise RuntimeError("Flat rate failed to enable")
    if fs["settings"]["title"]!=target_title and fs["title"]!=target_title:
        raise RuntimeError(f"Flat rate title mismatch after write: {fs}")
    if str(fs["settings"]["cost"] or "") not in ("0","0.0","0.00"):
        raise RuntimeError(f"Flat rate cost is not zero/postpaid-safe: {fs}")
    changed=True

    put_method(zone_id,local_id,enabled=False)
    local=api("GET",f"wp-json/wc/v3/shipping/zones/{zone_id}/methods/{local_id}")
    ls=method_state(local)
    if ls["enabled"]:
        raise RuntimeError("Local pickup failed to disable")

    final_methods=api("GET",f"wp-json/wc/v3/shipping/zones/{zone_id}/methods")
    final_states=[method_state(x) for x in final_methods]
    active=[x for x in final_states if x["enabled"]]
    if len(active)!=1 or active[0]["method_id"]!="flat_rate":
        raise RuntimeError(f"Unexpected active shipping methods after write: {active}")

    result={
      "ok":True,
      "executed_at_utc":datetime.now(timezone.utc).isoformat(),
      "zone":{"id":zone_id,"name":zone.get("name"),"locations":locations},
      "model":"countrywide_postpaid_carrier",
      "customer_facing_title":target_title,
      "carrier_options":["باربری","تیپاکس"],
      "cost_model":"postpaid_to_carrier",
      "woocommerce_shipping_cost":"0",
      "before":before,
      "after":{"active_methods":active,"all_methods":final_states},
      "local_pickup_disabled":True,
      "free_shipping_enabled":any(x["enabled"] and x["method_id"]=="free_shipping" for x in final_states),
      "price_or_product_changes":False
    }
except Exception:
    if changed:
        try:
            old=before["flat_rate"]
            put_method(zone_id,flat_id,enabled=bool(old["enabled"]),title=old["settings"]["title"],cost=old["settings"]["cost"])
            oldl=before["local_pickup"]
            put_method(zone_id,local_id,enabled=bool(oldl["enabled"]))
        except Exception:
            pass
    raise

os.makedirs(os.path.dirname(OUT_PATH),exist_ok=True)
with open(OUT_PATH,"w",encoding="utf-8") as f:
    json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({"ok":True,"zone":zone_id,"active":result["after"]["active_methods"],"local_pickup_disabled":True},ensure_ascii=False))
