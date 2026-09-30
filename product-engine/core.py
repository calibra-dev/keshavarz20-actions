from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = Path(__file__).resolve().parent
STATE_PATH = ENGINE_DIR / "state.json"
INVENTORY_PATH = ENGINE_DIR / "inventory.json"
RESULT_DIR = ENGINE_DIR / "results"
LAST_RUN_PATH = ENGINE_DIR / "last-run.json"

BASE = os.environ["WP_BASE_URL"].rstrip("/") + "/"
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
UA = "k20-product-autopilot/1.0"

TERMINAL = {
    "ACCEPTED", "PLATFORM_BLOCKED", "NEEDS_EVIDENCE", "QA_BLOCKED",
    "ROLLED_BACK", "SKIPPED", "FAILED", "MODEL_ACCESS_BLOCKED"
}

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def bridge(action: str, *, request_id: str | None = None, allow_approval: bool = True, **fields: Any) -> dict[str, Any]:
    body = {"action": action, "request_id": request_id or f"product-auto-{int(time.time()*1000)}"}
    body.update(fields)
    endpoint = urljoin(BASE, "wp-json/keshavarz20-ops/v3/execute")
    r = requests.post(
        endpoint, auth=AUTH, json=body,
        headers={"Accept":"application/json","User-Agent":UA}, timeout=240
    )
    try:
        data = r.json()
    except Exception as exc:
        raise RuntimeError(f"Bridge returned non-JSON HTTP {r.status_code}") from exc
    if r.ok and data.get("ok") is True:
        return data
    if allow_approval and data.get("approval_id") and data.get("fingerprint"):
        frozen = {
            "action":"approval.execute",
            "request_id":body["request_id"] + "-approval",
            "payload":{"approval_id":data["approval_id"],"fingerprint":data["fingerprint"]},
        }
        rr = requests.post(
            endpoint, auth=AUTH, json=frozen,
            headers={"Accept":"application/json","User-Agent":UA}, timeout=240
        )
        aa = rr.json()
        if rr.ok and aa.get("ok") is True:
            return aa
    raise RuntimeError(
        f"Bridge failure action={action} http={r.status_code} "
        f"code={data.get('code')} message={data.get('message')}"
    )

def rest(method: str, path: str, *, query: dict[str,Any] | None=None, payload: dict[str,Any] | None=None) -> Any:
    req: dict[str,Any] = {"method":method,"path":path}
    if query:
        req["query"] = query
    if payload is not None:
        req["payload"] = payload
    out = bridge("rest.proxy", **req)
    result = out.get("result") or {}
    return result.get("data", result)

def seo_read(product_id: int) -> dict[str,Any]:
    return bridge("seo.read", id=product_id).get("result") or {}

def seo_write(product_id: int, candidate: dict[str,Any]) -> dict[str,Any]:
    payload = {
        "title":candidate["seo_title"],
        "description":candidate["meta_description"],
        "focus_keyword":candidate["focus_keyphrase"],
    }
    return bridge("seo.update", id=product_id, payload=payload).get("result") or {}

def cache_purge() -> None:
    try:
        bridge("cache.purge")
    except Exception:
        pass

def product_read(product_id: int) -> dict[str,Any]:
    p = rest("GET", f"/wc/v3/products/{product_id}")
    if not isinstance(p,dict) or int(p.get("id") or 0) != product_id:
        raise RuntimeError(f"Product read failed for {product_id}")
    return p

def fetch_inventory() -> list[dict[str,Any]]:
    rows_out: list[dict[str,Any]] = []
    page = 1
    while True:
        rows = rest("GET","/wc/v3/products",query={
            "status":"publish","per_page":100,"page":page,"orderby":"id","order":"asc"
        })
        if not isinstance(rows,list) or not rows:
            break
        for p in rows:
            rows_out.append({
                "id":int(p["id"]),
                "name":p.get("name") or "",
                "permalink":p.get("permalink") or "",
                "status":p.get("status") or "",
                "type":p.get("type") or "",
                "date_modified_gmt":p.get("date_modified_gmt"),
            })
        if len(rows) < 100:
            break
        page += 1
        if page > 50:
            raise RuntimeError("Inventory safety limit reached")
    rows_out.sort(key=lambda x:x["id"])
    return rows_out

def refresh_inventory() -> list[dict[str,Any]]:
    live = fetch_inventory()
    old = load_json(INVENTORY_PATH, {"products":[]})
    old_ids = [int(x["id"]) for x in old.get("products",[]) if x.get("id")]
    live_by_id = {int(x["id"]):x for x in live}
    ordered: list[dict[str,Any]] = []
    for pid in old_ids:
        if pid in live_by_id:
            ordered.append(live_by_id.pop(pid))
        else:
            ordered.append({"id":pid,"name":"","permalink":"","status":"missing","type":"","date_modified_gmt":None})
    for pid in sorted(live_by_id):
        ordered.append(live_by_id[pid])
    save_json(INVENTORY_PATH,{
        "schema_version":"product-autopilot-inventory-v1",
        "selection_rule":"published product IDs frozen in original ascending order; new IDs append",
        "generated_at":utcnow(),"count":len(ordered),"products":ordered
    })
    return ordered

def public_html(url: str) -> str:
    if not url:
        return ""
    r = requests.get(url,headers={"User-Agent":UA,"Cache-Control":"no-cache"},timeout=90)
    r.raise_for_status()
    return r.text[:1_500_000]

def textify(raw: str) -> str:
    value = re.sub(r"<script\b.*?</script>"," ",raw or "",flags=re.I|re.S)
    value = re.sub(r"<style\b.*?</style>"," ",value,flags=re.I|re.S)
    value = re.sub(r"<[^>]+>"," ",value)
    return re.sub(r"\s+"," ",value).strip()

def research_input(product: dict[str,Any], seo: dict[str,Any], page_html: str) -> dict[str,Any]:
    return {
        "id":product.get("id"),"name":product.get("name"),"slug":product.get("slug"),
        "permalink":product.get("permalink"),"type":product.get("type"),"sku":product.get("sku"),
        "categories":product.get("categories"),"tags":product.get("tags"),"brands":product.get("brands"),
        "attributes":product.get("attributes"),
        "images":[{"id":x.get("id"),"name":x.get("name"),"alt":x.get("alt"),"src":x.get("src")} for x in (product.get("images") or [])],
        "short_description":(product.get("short_description") or "")[:42000],
        "description":(product.get("description") or "")[:65000],
        "seo":seo,
        "public_signals":{
            "product_schema":bool(re.search(r'"@type"\s*:\s*"Product"',page_html,re.I)),
            "offer_schema":bool(re.search(r'"@type"\s*:\s*"Offer"',page_html,re.I)),
            "h1_count":len(re.findall(r"<h1\b",page_html,re.I)),
        }
    }

def write_candidate(before: dict[str,Any], candidate: dict[str,Any]) -> None:
    pid = int(before["id"])
    rest("PUT",f"/wc/v3/products/{pid}",payload={
        "description":candidate["description_html"],
        "short_description":candidate["short_description_html"],
    })
    seo_write(pid,candidate)
    image_ids = {int(x.get("id") or 0):x for x in (before.get("images") or [])}
    for item in candidate.get("image_alt_suggestions") or []:
        aid = int(item.get("attachment_id") or 0)
        alt = textify(str(item.get("alt_text") or ""))
        current = textify(str((image_ids.get(aid) or {}).get("alt") or ""))
        if aid in image_ids and alt and alt != current:
            bridge("media.metadata",payload={"attachment_id":aid,"alt_text":alt})
    cache_purge()

def rollback(before: dict[str,Any], seo_before: dict[str,Any]) -> bool:
    pid = int(before["id"])
    rest("PUT",f"/wc/v3/products/{pid}",payload={
        "description":before.get("description") or "",
        "short_description":before.get("short_description") or "",
    })
    bridge("seo.update",id=pid,payload={
        "title":seo_before.get("title") or "",
        "description":seo_before.get("description") or "",
        "focus_keyword":seo_before.get("focus_keyword") or "",
    })
    cache_purge()
    check = product_read(pid)
    return (
        (check.get("description") or "") == (before.get("description") or "")
        and (check.get("short_description") or "") == (before.get("short_description") or "")
    )
