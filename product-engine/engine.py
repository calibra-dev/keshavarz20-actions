#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html as htmlmod
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from openai import OpenAI

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import k20_sanitizer

ENGINE_DIR = Path(__file__).resolve().parent
MASTER_PATH = ENGINE_DIR / "MASTER_PROMPT_V1.md"
STATE_PATH = ENGINE_DIR / "state.json"
INVENTORY_PATH = ENGINE_DIR / "inventory.json"
RESULT_DIR = ENGINE_DIR / "results"
LAST_RUN_PATH = ENGINE_DIR / "last-run.json"

BASE = os.environ["WP_BASE_URL"].rstrip("/") + "/"
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
MODEL = os.environ.get("OPENAI_PRODUCT_MODEL", "gpt-5.5")
AUTO_WRITE = os.environ.get("K20_PRODUCT_AUTOWRITE", "true").lower() in {"1", "true", "yes"}
UA = "k20-product-autopilot/1.0"

TERMINAL = {
    "ACCEPTED", "PLATFORM_BLOCKED", "NEEDS_EVIDENCE", "QA_BLOCKED",
    "ROLLED_BACK", "SKIPPED", "FAILED"
}
BANNED_COPY = [
    "Ø¯Ø± Ø§ÛŒÙ† Ù…Ù‚Ø§Ù„Ù‡", "Ø¯Ø± Ø§Ø¯Ø§Ù…Ù‡", "Ø±ÙˆØ´ ØªÙ‡ÛŒÙ‡ Ùˆ Ø¨Ø§Ø²Ø¨ÛŒÙ†ÛŒ", "Ù†Ø¸Ø± Ú©Ø§Ø±Ø´Ù†Ø§Ø³ÛŒ Ú©Ø´Ø§ÙˆØ±Ø² Ø¨ÛŒØ³Øª",
    "Ù‡Ù…Ø§Ù†â€ŒØ·ÙˆØ± Ú©Ù‡ Ù…ÛŒâ€ŒØ¯Ø§Ù†ÛŒØ¯", "Ø¯Ø± Ø¯Ù†ÛŒØ§ÛŒ Ø§Ù…Ø±ÙˆØ²", "Ø¨Ù‡ Ø·ÙˆØ± Ú©Ù„ÛŒ Ù…ÛŒâ€ŒØªÙˆØ§Ù† Ú¯ÙØª",
    "Ø¨Ù‡â€ŒØ·ÙˆØ± Ú©Ù„ÛŒ Ù…ÛŒâ€ŒØªÙˆØ§Ù† Ú¯ÙØª", "Ù…Ø­ØµÙˆÙ„ÛŒ Ú©Ø§Ø±Ø¨Ø±Ø¯ÛŒ Ùˆ Ø¨Ø§Ú©ÛŒÙÛŒØª", "Ø¨Ù‡ØªØ±ÛŒÙ† Ú¯Ø²ÛŒÙ†Ù‡",
    "Ø§Ù†ØªØ®Ø§Ø¨ÛŒ Ø§ÛŒØ¯Ù‡â€ŒØ¢Ù„ Ø¨Ø±Ø§ÛŒ Ù‡Ù…Ù‡"
]
ALLOWED_CLAIM_CLASSES = {
    "FACT", "MANUFACTURER_CLAIM", "ESTIMATE", "ENGINEERING_REQUIRED", "EXPERT_INTERPRETATION"
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


def state_default() -> dict[str, Any]:
    return {
        "schema_version": "product-autopilot-v1",
        "enabled": True,
        "kill_switch": False,
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "processed": {},
        "sentence_bank": {},
        "stats": {"accepted": 0, "platform_blocked": 0, "blocked": 0, "rolled_back": 0, "failed": 0},
    }


def bridge_request(action: str, *, request_id: str | None = None, allow_approval: bool = True, **fields: Any) -> dict[str, Any]:
    body = {"action": action, "request_id": request_id or f"product-auto-{int(time.time()*1000)}"}
    body.update(fields)
    endpoint = urljoin(BASE, "wp-json/keshavarz20-ops/v3/execute")
    r = requests.post(endpoint, auth=AUTH, json=body, headers={"Accept": "application/json", "User-Agent": UA}, timeout=240)
    try:
        data = r.json()
    except Exception as exc:
        raise RuntimeError(f"Bridge returned non-JSON HTTP {r.status_code}") from exc
    if r.ok and data.get("ok") is True:
        return data
    if allow_approval and data.get("approval_id") and data.get("fingerprint"):
        approval = {
            "action": "approval.execute",
            "request_id": body["request_id"] + "-approval",
            "payload": {
                "approval_id": data["approval_id"],
                "fingerprint": data["fingerprint"],
            },
        }
        rr = requests.post(endpoint, auth=AUTH, json=approval, headers={"Accept": "application/json", "User-Agent": UA}, timeout=240)
        aa = rr.json()
        if rr.ok and aa.get("ok") is True:
            return aa
    raise RuntimeError(f"Bridge failure action={action} http={r.status_code} code={data.get('code')} message={data.get('message')}")


def rest(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    req: dict[str, Any] = {"method": method, "path": path}
    if payload is not None:
        req["payload"] = payload
    out = bridge_request("rest.proxy", **req)
    result = out.get("result") or {}
    return result.get("data", result)


def seo_read(product_id: int) -> dict[str, Any]:
    out = bridge_request("seo.read", id=product_id)
    return out.get("result") or {}


def seo_write(product_id: int, candidate: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "title": candidate["seo_title"],
        "description": candidate["meta_description"],
        "focus_keyword": candidate["focus_keyphrase"],
    }
    out = bridge_request("seo.update", id=product_id, payload=payload)
    return out.get("result") or {}


def purge_cache() -> None:
    try:
        bridge_request("cache.purge")
    except Exception:
        pass


def fetch_inventory_live() -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    page = 1
    while True:
        rows = rest("GET", f"/wc/v3/products?status=publish&per_page=100&page={page}&orderby=id&order=asc")
        if not isinstance(rows, list) or not rows:
            break
        for p in rows:
            products.append({
                "id": int(p["id"]),
                "name": p.get("name") or "",
                "permalink": p.get("permalink") or "",
                "status": p.get("status") or "",
                "type": p.get("type") or "",
                "date_modified_gmt": p.get("date_modified_gmt"),
            })
        if len(rows) < 100:
            break
        page += 1
        if page > 50:
            raise RuntimeError("Inventory pagination safety limit reached")
    products.sort(key=lambda x: x["id"])
    return products


def refresh_inventory() -> list[dict[str, Any]]:
    live = fetch_inventory_live()
    old = load_json(INVENTORY_PATH, {"products": []})
    old_ids = [int(x["id"]) for x in old.get("products", []) if x.get("id")]
    by_id = {int(x["id"]): x for x in live}
    ordered: list[dict[str, Any]] = []
    for pid in old_ids:
        if pid in by_id:
            ordered.append(by_id.pop(pid))
        else:
            ordered.append({"id": pid, "name": "", "permalink": "", "status": "missing", "type": "", "date_modified_gmt": None})
    for pid in sorted(by_id):
        ordered.append(by_id[pid])
    record = {
        "schema_version": "product-autopilot-inventory-v1",
        "selection_rule": "published WooCommerce products; frozen original order then append newly discovered product IDs",
        "generated_at": utcnow(),
        "count": len(ordered),
        "products": ordered,
    }
    save_json(INVENTORY_PATH, record)
    return ordered


def product_read(product_id: int) -> dict[str, Any]:
    p = rest("GET", f"/wc/v3/products/{product_id}")
    if not isinstance(p, dict) or int(p.get("id") or 0) != product_id:
        raise RuntimeError(f"Product readback failed for {product_id}")
    return p


def public_html(url: str) -> str:
    if not url:
        return ""
    r = requests.get(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"}, timeout=90)
    r.raise_for_status()
    return r.text[:1_500_000]


def visible_text(raw: str) -> str:
    s = htmlmod.unescape(raw or "")
    s = re.sub(r"<script\b.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.²È="25ÑÑ•µÁÐˆè…ÑÑ•µÁÐ°€‰•ÉÉ½ÉÌˆèÙ…±¥‘…Ñ¥½¸°€‰ÅÕ…±¥Ñå}Í½É”ˆèÍ½É”°€‰Í½É•}‘•Ñ…¥°ˆèÍ½É•}‘•Ñ…¥±ô°•¹ÍÕÉ•}…Í¥¤õ…±Í”¤(€€€€€€€É•ÍÕ±Ñl‰½¹Ñ•¹Ñ}ÅÕ…±¥Ñå}Í½É”‰t€ôÍ½É”(€€€€€€€É•ÍÕ±Ñl‰½¹Ñ•¹Ñ}Í½É•}‘•Ñ…¥°‰t€ôÍ½É•}‘•Ñ…¥°(€€€€€€€É•ÍÕ±Ñl‰Ù…±¥‘…Ñ¥½¹}•ÉÉ½ÉÌ‰t€ôÙ…±¥‘…Ñ¥½¸(€€€€€€€É•ÍÕ±Ñl‰…¹‘¥‘…Ñ•}ÍÕµµ…Éä‰t€ôì(€€€€€€€€€€€€‰™…µ¥±äˆè…¹‘¥‘…Ñ”¹•Ð ‰™…µ¥±äˆ¤¥˜…¹‘¥‘…Ñ”•±Í”9½¹”°(€€€€€€€€€€€€‰½µµ•É¥…±}…¹±”ˆè…¹‘¥‘…Ñ”¹•Ð ‰½µµ•É¥…±}…¹±”ˆ¤¥˜…¹‘¥‘…Ñ”•±Í”9½¹”°(€€€€€€€€€€€€‰Í½ÕÉ•}½Õ¹Ðˆè±•¸¡Í½ÕÉ•Ì¤°(€€€€€€€ô(€€€€€€€¥˜¹½Ð…¹‘¥‘…Ñ”½ÈÙ…±¥‘…Ñ¥½¸½ÈÍ½É”€ð€äØè(€€€€€€€€€€€ÍÑ…ÑÕÌ€ô€‰9M}Y%9ˆ¥˜±•¸¡Í½ÕÉ•Ì¤€ð€È•±Í”€‰E}	1=-ˆ(€€€€€€€€€€€É•ÍÕ±Ð¹ÕÁ‘…Ñ”¡ÍÑ…ÑÕÌõÍÑ…ÑÕÌ°‰±½­•Èô‰…¹‘¥‘…Ñ”‘¥¹½Ð±•…È€äØ½•Ù¥‘•¹”…Ñ”ˆ°™¥¹¥Í¡•‘}…ÐõÕÑ¹½Ü ¤¤(€€€€€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ð((€€€€€€€¥˜ÉÕ¹}µ½‘”€ôô€‰‘Éå}ÉÕ¸ˆ½È¹½ÐUQ=}]I%Qè(€€€€€€€€€€€É•ÍÕ±Ð¹ÕÁ‘…Ñ”¡ÍÑ…ÑÕÌô‰Ie}IU9}Idˆ°™¥¹¥Í¡•‘}…ÐõÕÑ¹½Ü ¤¤(€€€€€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ð((€€€€€€€…ÁÁ±å}…¹‘¥‘…Ñ”¡‰•™½É”°…¹‘¥‘…Ñ”¤(€€€€€€€½¬°…™Ñ•É}ÁÉ½‘ÕÐ°…™Ñ•É}Í•¼€ôÉ•…‘‰…­}µ…Ñ¡•Ì¡Á¥°…¹‘¥‘…Ñ”¤(€€€€€€€É•ÍÕ±Ñl‰É•…‘‰…­}½¬‰t€ô½¬(€€€€€€€¥˜¹½Ð½¬è(€€€€€€€€€€€É½±±‰…¬¡‰•™½É”°Í•½}‰•™½É”¤(€€€€€€€€€€€É•ÍÕ±Ð¹ÕÁ‘…Ñ”¡ÍÑ…ÑÕÌô‰I=11}	,ˆ°‰±½­•Èô‰ÁÉ½‘ÕÐ½¹Ñ•¹ÐÉ•…‘‰…¬µ¥Íµ…Ñ ˆ°™¥¹¥Í¡•‘}…ÐõÕÑ¹½Ü ¤¤(€€€€€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ð((€€€€€€€…™Ñ•É}¡Ñµ°€ôÁÕ‰±¥}¡Ñµ°¡…™Ñ•É}ÁÉ½‘ÕÐ¹•Ð ‰Á•Éµ…±¥¹¬ˆ¤½È€ˆˆ¤(€€€€€€€É•ÍÕ±Ñl‰Í¡•µ…}É•…‘‰…¬‰t€ôì(€€€€€€€€€€€€‰ÁÉ½‘ÕÐˆè‰½½°¡É”¹Í•…É ¡Èœ‰ÑåÁ”‰qÌ¨éqÌ¨‰AÉ½‘ÕÐˆœ°…™Ñ•É}¡Ñµ°°É”¹$¤¤°(€€€€€€€€€€€€‰½™™•Èˆè‰½½°¡É”¹Í•…É ¡Èœ‰ÑåÁ”‰qÌ¨éqÌ¨‰=™™•Èˆœ°…™Ñ•É}¡Ñµ°°É”¹$¤¤°(€€€€€€€€€€€€‰ Å}½Õ¹Ðˆè±•¸¡É”¹™¥¹‘…±°¡Èˆñ Åqˆˆ°…™Ñ•É}¡Ñµ°°É”¹$¤¤°(€€€€€€€ô(€€€€€€€…™Ñ•É}Á•É˜€ô±¥¡Ñ¡½ÕÍ”¡…™Ñ•É}ÁÉ½‘ÕÐ¹•Ð ‰Á•Éµ…±¥¹¬ˆ¤½È€ˆˆ°€Ì¤(€€€€€€€É•ÍÕ±Ñl‰…™Ñ•É}Á•É™½Éµ…¹”‰t€ô…™Ñ•É}Á•É˜(€€€€€€€É•œ€ôÉ•É•ÍÍ¥½¸¡‰…Í•±¥¹”°…™Ñ•É}Á•É˜¤(€€€€€€€É•ÍÕ±Ñl‰É•É•ÍÍ¥½¹Ì‰t€ôÉ•œ(€€€€€€€¥˜É•œè(€€€€€€€€€€€É½±±‰…¬¡‰•™½É”°Í•½}‰•™½É”¤(€€€€€€€€€€€Éˆ€ôÁÉ½‘ÕÑ}É•…¡Á¥¤(€€€€€€€€€€€É½±±‰…­}½¬€ô€ (€€€€€€€€€€€€€€€€¡Éˆ¹•Ð ‰‘•ÍÉ¥ÁÑ¥½¸ˆ¤½È€ˆˆ¤€ôô€¡‰•™½É”¹•Ð ‰‘•ÍÉ¥ÁÑ¥½¸ˆ¤½È€ˆˆ¤(€€€€€€€€€€€€€€€…¹€¡Éˆ¹•Ð ‰Í¡½ÉÑ}‘•ÍÉ¥ÁÑ¥½¸ˆ¤½È€ˆˆ¤€ôô€¡‰•™½É”¹•Ð ‰Í¡½ÉÑ}‘•ÍÉ¥ÁÑ¥½¸ˆ¤½È€ˆˆ¤(€€€€€€€€€€€€¤(€€€€€€€€€€€É•ÍÕ±Ñl‰É½±±‰…­}É•…‘‰…­}½¬‰t€ôÉ½±±‰…­}½¬(€€€€€€€€€€€É•ÍÕ±Ð¹ÕÁ‘…Ñ”¡ÍÑ…ÑÕÌô‰I=11}	,ˆ°‰±½­•Èôˆì€ˆ¹©½¥¸¡É•œ¤°™¥¹¥Í¡•‘}…ÐõÕÑ¹½Ü ¤¤(€€€€€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ð((€€€€€€€ÕÁ‘…Ñ•}Í•¹Ñ•¹•}‰…¹¬¡ÍÑ…Ñ”°Á¥°…¹‘¥‘…Ñ”¤(€€€€€€€Ñ•¡¹¥…±}‰±½­•ÉÌ€ômt(€€€€€€€¥˜¹½ÐÁ•É™}Á…ÍÌ¡…™Ñ•É}Á•É˜¤è(€€€€€€€€€€€Ñ•¡¹¥…±}‰±½­•ÉÌ¹…ÁÁ•¹ ‰µ½‰¥±”1¥¡Ñ¡½ÕÍ”…•ÁÑ…¹”€ðäØ½È]X±…ˆÕ…É™…¥±•ˆ¤(€€€€€€€¥˜¹½ÐÉ•ÍÕ±Ñl‰Í¡•µ…}É•…‘‰…¬‰ul‰ÁÉ½‘ÕÐ‰t½È¹½ÐÉ•ÍÕ±Ñl‰Í¡•µ…}É•…‘‰…¬‰ul‰½™™•È‰tè(€€€€€€€€€€€Ñ•¡¹¥…±}‰±½­•ÉÌ¹…ÁÁ•¹ ‰AÉ½‘ÕÐ½=™™•ÈÍ¡•µ„Á…É¥Ñä¹½Ð™Õ±±ä½‰Í•ÉÙ…‰±”ˆ¤(€€€€€€€¥˜É•ÍÕ±Ñl‰Í¡•µ…}É•…‘‰…¬‰ul‰ Å}½Õ¹Ð‰t€„ô€Äè(€€€€€€€€€€€Ñ•¡¹¥…±}‰±½­•ÉÌ¹…ÁÁ•¹¡˜‰ Ä½Õ¹Ð¥ÌíÉ•ÍÕ±ÑlÍ¡•µ…}É•…‘‰…¬ul Å}½Õ¹Ðuô°•áÁ•Ñ•€Äˆ¤(€€€€€€€¥˜Ñ•¡¹¥…±}‰±½­•ÉÌè(€€€€€€€€€€€É•ÍÕ±Ð¹ÕÁ‘…Ñ”¡ÍÑ…ÑÕÌô‰A1Q=I5}	1=-ˆ°‰±½­•Èôˆì€ˆ¹©½¥¸¡Ñ•¡¹¥…±}‰±½­•ÉÌ¤¤(€€€€€€€•±Í”è(€€€€€€€€€€€É•ÍÕ±Ð¹ÕÁ‘…Ñ”¡ÍÑ…ÑÕÌô‰AQˆ¤(€€€€€€€É•ÍÕ±Ñl‰™¥¹¥Í¡•‘}…Ð‰t€ôÕÑ¹½Ü ¤(€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ð(€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€É•ÍÕ±Ð¹ÕÁ‘…Ñ”¡ÍÑ…ÑÕÌô‰%1ˆ°‰±½­•Èõ˜‰íÑåÁ”¡•áŒ¤¹}}¹…µ•}}ôèí•áôˆ°™¥¹¥Í¡•‘}…ÐõÕÑ¹½Ü ¤¤(€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ð(()‘•˜µ…¥¸ ¤€´ø¥¹Ðè(€€€…À€ô…ÉÁ…ÉÍ”¹ÉÕµ•¹ÑA…ÉÍ•È ¤(€€€…À¹…‘‘}…ÉÕµ•¹Ð ˆ´µµ…àµÁÉ½‘ÕÑÌˆ°ÑåÁ”õ¥¹Ð°‘•™…Õ±ÐôÄ¤(€€€…À¹…‘‘}…ÉÕµ•¹Ð ˆ´µÉÕ¸µµ½‘”ˆ°¡½¥•Ìõl‰…ÕÑ¼ˆ°€‰‘Éå}ÉÕ¸‰t°‘•™…Õ±Ðô‰…ÕÑ¼ˆ¤(€€€…À¹…‘‘}…ÉÕµ•¹Ð ˆ´µÑ…É•Ðµ¥ˆ°ÑåÁ”õ¥¹Ð°‘•™…Õ±ÐôÀ¤(€€€…À¹…‘‘}…ÉÕµ•¹Ð ˆ´µÁ…ÕÍ”ˆ°…Ñ¥½¸ô‰ÍÑ½É•}ÑÉÕ”ˆ¤(€€€…À¹…‘‘}…ÉÕµ•¹Ð ˆ´µÉ•ÍÕµ”ˆ°…Ñ¥½¸ô‰ÍÑ½É•}ÑÉÕ”ˆ¤(€€€…ÉÌ€ô…À¹Á…ÉÍ•}…ÉÌ ¤(€€€¥˜…ÉÌ¹µ…á}ÁÉ½‘ÕÑÌ€ð€Ä½È…ÉÌ¹µ…á}ÁÉ½‘ÕÑÌ€ø€Ôè(€€€€€€€É…¥Í”MåÍÑ•µá¥Ð ˆ´µµ…àµÁÉ½‘ÕÑÌµÕÍÐ‰”€Ä¸¸Ôˆ¤((€€€ÍÑ…Ñ”€ô±½…‘}©Í½¸¡MQQ}AQ °ÍÑ…Ñ•}‘•™…Õ±Ð ¤¤(€€€¥˜…ÉÌ¹Á…ÕÍ”è(€€€€€€€ÍÑ…Ñ•l‰•¹…‰±•‰t€ô…±Í”(€€€€€€€ÍÑ…Ñ•l‰ÕÁ‘…Ñ•‘}…Ð‰t€ôÕÑ¹½Ü ¤(€€€€€€€Í…Ù•}©Í½¸¡MQQ}AQ °ÍÑ…Ñ”¤(€€€€€€€Í…Ù•}©Í½¸¡1MQ}IU9}AQ °ì‰½¬ˆèQÉÕ”°€‰ÍÑ…ÑÕÌˆè€‰AUMˆ°€‰…ÐˆèÕÑ¹½Ü ¥ô¤(€€€€€€€É•ÑÕÉ¸€À(€€€¥˜…ÉÌ¹É•ÍÕµ”è(€€€€€€€ÍÑ…Ñ•l‰•¹…‰±•‰t€ôQÉÕ”(€€€€€€€ÍÑ…Ñ•l‰­¥±±}ÍÝ¥Ñ ‰t€ô…±Í”(€€€€€€€ÍÑ…Ñ•l‰ÕÁ‘…Ñ•‘}…Ð‰t€ôÕÑ¹½Ü ¤(€€€€€€€Í…Ù•}©Í½¸¡MQQ}AQ °ÍÑ…Ñ”¤(€€€€€€€Í…Ù•}©Í½¸¡1MQ}IU9}AQ °ì‰½¬ˆèQÉÕ”°€‰ÍÑ…ÑÕÌˆè€‰IMU5ˆ°€‰…ÐˆèÕÑ¹½Ü ¥ô¤(€€€€€€€É•ÑÕÉ¸€À(€€€¥˜ÍÑ…Ñ”¹•Ð ‰­¥±±}ÍÝ¥Ñ ˆ¤è(€€€€€€€Í…Ù•}©Í½¸¡1MQ}IU9}AQ °ì‰½¬ˆè…±Í”°€‰ÍÑ…ÑÕÌˆè€‰-%11}M]%Q ˆ°€‰…ÐˆèÕÑ¹½Ü ¥ô¤(€€€€€€€É•ÑÕÉ¸€Ì(€€€¥˜¹½ÐÍÑ…Ñ”¹•Ð ‰•¹…‰±•ˆ°QÉÕ”¤è(€€€€€€€Í…Ù•}©Í½¸¡1MQ}IU9}AQ °ì‰½¬ˆèQÉÕ”°€‰ÍÑ…ÑÕÌˆè€‰AUMˆ°€‰…ÐˆèÕÑ¹½Ü ¥ô¤(€€€€€€€É•ÑÕÉ¸€À((€€€¥¹Ù•¹Ñ½Éä€ôÉ•™É•Í¡}¥¹Ù•¹Ñ½Éä ¤(€€€ÁÉ½•ÍÍ•€ôÍÑ…Ñ”¹Í•Ñ‘•™…Õ±Ð ‰ÁÉ½•ÍÍ•ˆ°íô¤(€€€¥˜…ÉÌ¹Ñ…É•Ñ}¥è(€€€€€€€Ñ…É•ÑÌ€ômà™½Èà¥¸¥¹Ù•¹Ñ½Éä¥˜¥¹Ð¡ál‰¥‰t¤€ôô…ÉÌ¹Ñ…É•Ñ}¥‘ulèÅt(€€€•±Í”è(€€€€€€€Ñ…É•ÑÌ€ômà™½Èà¥¸¥¹Ù•¹Ñ½Éä¥˜ÍÑÈ¡ál‰¥‰t¤¹½Ð¥¸ÁÉ½•ÍÍ•½ÈÁÉ½•ÍÍ•‘mÍÑÈ¡ál‰¥‰t¥t¹•Ð ‰ÍÑ…ÑÕÌˆ¤¹½Ð¥¸QI5%91ulé…ÉÌ¹µ…á}ÁÉ½‘ÕÑÍt((€€€ÉÕ¸€ôì‰Í¡•µ…}Ù•ÉÍ¥½¸ˆè€‰ÁÉ½‘ÕÐµ…ÕÑ½Á¥±½ÐµÉÕ¸µØÄˆ°€‰ÍÑ…ÉÑ•‘}…ÐˆèÕÑ¹½Ü ¤°€‰ÉÕ¹}µ½‘”ˆè…ÉÌ¹ÉÕ¹}µ½‘”°€‰Ñ…É•ÑÌˆèmál‰¥‰t™½Èà¥¸Ñ…É•ÑÍt°€‰É•ÍÕ±ÑÌˆèmuô(€€€IMU1Q}%H¹µ­‘¥È¡Á…É•¹ÑÌõQÉÕ”°•á¥ÍÑ}½¬õQÉÕ”¤((€€€™½È•¹ÑÉä¥¸Ñ…É•ÑÌè(€€€€€€€É•ÍÕ±Ð€ôÁÉ½•ÍÍ}½¹”¡•¹ÑÉä°ÍÑ…Ñ”°…ÉÌ¹ÉÕ¹}µ½‘”¤(€€€€€€€ÉÕ¹l‰É•ÍÕ±ÑÌ‰t¹…ÁÁ•¹¡É•ÍÕ±Ð¤(€€€€€€€Á¥€ôÍÑÈ¡•¹ÑÉål‰¥‰t¤(€€€€€€€ÁÉ½•ÍÍ•‘mÁ¥‘t€ôì(€€€€€€€€€€€€‰ÍÑ…ÑÕÌˆèÉ•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t°(€€€€€€€€€€€€‰™¥¹¥Í¡•‘}…ÐˆèÉ•ÍÕ±Ð¹•Ð ‰™¥¹¥Í¡•‘}…Ðˆ¤½ÈÕÑ¹½Ü ¤°(€€€€€€€€€€€€‰½¹Ñ•¹Ñ}ÅÕ…±¥Ñå}Í½É”ˆèÉ•ÍÕ±Ð¹•Ð ‰½¹Ñ•¹Ñ}ÅÕ…±¥Ñå}Í½É”ˆ¤°(€€€€€€€€€€€€‰Á•É™½Éµ…¹”ˆè€ ¡É•ÍÕ±Ð¹•Ð ‰…™Ñ•É}Á•É™½Éµ…¹”ˆ¤½Èíô¤¹•Ð ‰É•ÁÉ•Í•¹Ñ…Ñ¥Ù”ˆ¤½Èíô¤¹•Ð ‰Á•É™½Éµ…¹”ˆ¤°(€€€€€€€€€€€€‰‰±½­•ÈˆèÉ•ÍÕ±Ð¹•Ð ‰‰±½­•Èˆ¤°(€€€€€€€€€€€€‰É•ÍÕ±Ñ}™¥±”ˆè˜‰ÁÉ½‘ÕÐµ•¹¥¹”½É•ÍÕ±ÑÌ½íÁ¥‘ô¹©Í½¸ˆ°(€€€€€€€ô(€€€€€€€Í…Ù•}©Í½¸¡IMU1Q}%H€¼˜‰íÁ¥‘ô¹©Í½¸ˆ°É•ÍÕ±Ð¤(€€€€€€€¥˜É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t€ôô€‰AQˆè(€€€€€€€€€€€ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰ul‰…•ÁÑ•‰t€ô¥¹Ð¡ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰t¹•Ð ‰…•ÁÑ•ˆ°€À¤¤€¬€Ä(€€€€€€€•±¥˜É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t€ôô€‰A1Q=I5}	1=-ˆè(€€€€€€€€€€€ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰ul‰Á±…Ñ™½Éµ}‰±½­•‰t€ô¥¹Ð¡ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰t¹•Ð ‰Á±…Ñ™½Éµ}‰±½­•ˆ°€À¤¤€¬€Ä(€€€€€€€•±¥˜É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t€ôô€‰I=11}	,ˆè(€€€€€€€€€€€ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰ul‰É½±±•‘}‰…¬‰t€ô¥¹Ð¡ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰t¹•Ð ‰É½±±•‘}‰…¬ˆ°€À¤¤€¬€Ä(€€€€€€€•±¥˜É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t€ôô€‰%1ˆè(€€€€€€€€€€€ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰ul‰™…¥±•‰t€ô¥¹Ð¡ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰t¹•Ð ‰™…¥±•ˆ°€À¤¤€¬€Ä(€€€€€€€€€€€¥˜€‰	É¥‘”ˆ¥¸ÍÑÈ¡É•ÍÕ±Ð¹•Ð ‰‰±½­•Èˆ¤½È€ˆˆ¤½ÈÉ•ÍÕ±Ð¹•Ð ‰É½±±‰…­}É•…‘‰…­}½¬ˆ¤¥Ì…±Í”è(€€€€€€€€€€€€€€€ÍÑ…Ñ•l‰­¥±±}ÍÝ¥Ñ ‰t€ôQÉÕ”(€€€€€€€•±Í”è(€€€€€€€€€€€ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰ul‰‰±½­•‰t€ô¥¹Ð¡ÍÑ…Ñ•l‰ÍÑ…ÑÌ‰t¹•Ð ‰‰±½­•ˆ°€À¤¤€¬€Ä(€€€€€€€ÍÑ…Ñ•l‰ÕÁ‘…Ñ•‘}…Ð‰t€ôÕÑ¹½Ü ¤(€€€€€€€Í…Ù•}©Í½¸¡MQQ}AQ °ÍÑ…Ñ”¤((€€€ÉÕ¹l‰™¥¹¥Í¡•‘}…Ð‰t€ôÕÑ¹½Ü ¤(€€€ÉÕ¹l‰¥¹Ù•¹Ñ½Éå}½Õ¹Ð‰t€ô±•¸¡¥¹Ù•¹Ñ½Éä¤(€€€ÉÕ¹l‰ÁÉ½•ÍÍ•‘}½Õ¹Ð‰t€ô±•¸¡ÁÉ½•ÍÍ•¤(€€€ÉÕ¹l‰É•µ…¥¹¥¹}¥¹¥Ñ¥…±}ÍÝ••À‰t€ôÍÕ´ Ä™½Èà¥¸¥¹Ù•¹Ñ½Éä¥˜ÍÑÈ¡ál‰¥‰t¤¹½Ð¥¸ÁÉ½•ÍÍ•½ÈÁÉ½•ÍÍ•‘mÍÑÈ¡ál‰¥‰t¥t¹•Ð ‰ÍÑ…ÑÕÌˆ¤¹½Ð¥¸QI5%90¤(€€€Í…Ù•}©Í½¸¡1MQ}IU9}AQ °ÉÕ¸¤(€€€ÁÉ¥¹Ð¡©Í½¸¹‘ÕµÁÌ¡ì(€€€€€€€€‰½¬ˆèQÉÕ”°(€€€€€€€€‰Ñ…É•ÑÌˆèÉÕ¹l‰Ñ…É•ÑÌ‰t°(€€€€€€€€‰ÍÑ…ÑÕÍ•Ìˆèmál‰ÍÑ…ÑÕÌ‰t™½Èà¥¸ÉÕ¹l‰É•ÍÕ±ÑÌ‰ut°(€€€€€€€€‰¥¹Ù•¹Ñ½Éå}½Õ¹ÐˆèÉÕ¹l‰¥¹Ù•¹Ñ½Éå}½Õ¹Ð‰t°(€€€€€€€€‰ÁÉ½•ÍÍ•‘}½Õ¹ÐˆèÉÕ¹l‰ÁÉ½•ÍÍ•‘}½Õ¹Ð‰t°(€€€€€€€€‰É•µ…¥¹¥¹œˆèÉÕ¹l‰É•µ…¥¹¥¹}¥¹¥Ñ¥…±}ÍÝ••À‰t°(€€€€€€€€‰­¥±±}ÍÝ¥Ñ ˆèÍÑ…Ñ”¹•Ð ‰­¥±±}ÍÝ¥Ñ ˆ¤°(€€€ô°•¹ÍÕÉ•}…Í¥¤õ…±Í”¤¤(€€€É•ÑÕÉ¸€À¥˜¹½ÐÍÑ…Ñ”¹•Ð ‰­¥±±}ÍÝ¥Ñ ˆ¤•±Í”€Ð(()¥˜}}¹…µ•}|€ôô€‰}}µ…¥¹}|ˆè(€€€É…¥Í”MåÍÑ•µá¥Ð¡µ…¥¸ ¤¤(