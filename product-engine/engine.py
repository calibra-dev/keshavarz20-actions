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
MODEL = os.environ.get("OPENAI_PRODUCT_MODEL", "gpt-5.6")
AUTO_WRITE = os.environ.get("K20_PRODUCT_AUTOWRITE", "true").lower() in {"1", "true", "yes"}
UA = "k20-product-autopilot/1.0"

TERMINAL = {
    "ACCEPTED", "PLATFORM_BLOCKED", "NEEDS_EVIDENCE", "QA_BLOCKED",
    "ROLLED_BACK", "SKIPPED", "FAILED"
}
BANNED_COPY = [
    "堹堭 塈�� ��塈��", "堹堭 塈堹塈��", "堭�奡 堛��� � 堥塈堬堥���", "�婺堭 琠塈堭奡�塈堻� 琠奡塈�堭堬 堥�堻堛",
    "��塈��煞� 琠� ���胰戒�", "堹堭 堹��塈� 塈�堭�堬", "堥� 媟�堭 琠�� ���舍戒� 痧�堛",
    "堥��煞� 琠�� ���舍戒� 痧�堛", "�堶媯��� 琠塈堭堥堭堹� � 堥塈琠���堛", "堥�堛堭�� 痧堬���",
    "塈�堛堮塈堥� 塈�堹��Ｋ� 堥堭塈� ���"
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


def rest(method: str, path: str, payload: dict[str, Any] | None = None, query: dict[str, Any] | None = None) -> Any:
    req: dict[str, Any] = {"method": method, "path": path}
    if payload is not None:
        req["payload"] = payload
    if query:
        req["query"] = query
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
        rows = rest("GET", "/wc/v3/products", query={"status": "publish", "per_page": 100, "page": page, "orderby": "id", "order": "asc"})
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
    return re.笮="25旄蹈�旄蹈��圪褕���悼�悒螂��悼栫}�褕���褕�}��弘�}��弗羺�嗶桾火��(梇峬�蝴�塾}纓由憢�褕�t��褕�(梇峬�蝴�塾}�褕��弘��褕��弘(梇峬�末飼刓妀��悼�悒螂(梇峬���}邯紫�t��(�弗��������弗�������敝�9蝴(�蔥���惦��������蔥���惦�������敝�9蝴(調�桯���腹芺桾�怳�((�厭�����褓�末�褓��馽�(�晇���9M}Y%9��﹠調�����}	1=-�(梇邿桷��﹠�晇沭迕梋��������請��馽�晱������旦生�灊�厭�中(桾��邯教((�尥飼善�鐀�扤}尥��厭�UQ=}]I%Q�(梇邿桷��﹠�晇泔�Ie}IU9}Id�旦生�灊�厭�中(桾��邯教((�謠勗}���������(為�}賽��訄�}������}���怴薔����(梇峬���迪蓮�蓮(�厭�蓮�(蔣��活����罷���(梇邿桷��﹠�晇泔=11}	,�掃�賽���塾����生����馴矷�}灊�厭�中(桾��邯教((�}×粥�轅�}×粥�}賽��邿���悼僧���(梇峬�����(刓�蝸陛�嗶����栫�怢廦怢刓����扐×粥���$中�(��蝸陛�嗶����栫�怢廦怢�=�����扐×粥���$中�(�癮桯���腹��旦�掠﹍q����扐×粥���$中�((�}���悼恁調��}賽��邿���悼僧���怳(梇峬�}��褕���t���扐��(���穸螂�旦�}���(梇峬��迋末嘐���(��(蔣��活����罷���(��賽��恚��℅��(蔣��迪蓮��(﹎���民悒螂���鐀��褕���民悒螂���(��﹎��■奷}��犮蹊末��褓��鐀��褕��■奷}��犮蹊末��褓��(�(梇峬蔣��迪���}蓮�刓控�}蓮(梇邿桷��﹠�晇泔=11}	,�掃��忝斥﹎�什�旦生�灊�厭�中(桾��邯教((��塾�}�僧﹠���薔����(�★�}��妀�mt(�厭���}�迒�}��方(�★�}��妀�謠��弗�1�×■梠���蹊�謱�褓�]X��������(�厭��邯敗l���l刓�厭��邯敗l���l��(�★�}��妀�謠�刓�=���犮栵請�梇曹���(��邯敗l���l�癮桯�t殲(�★�}��妀�謠� �桯�甘�邯敗l���l�癮桯�u羺�徶�����(��馴�惦��妀�(梇邿桷��﹠�晇泔1Q=I5}	1=-�掃��忝斥×�★�}��妀中(�敝(梇邿桷��﹠�晇泔�AQ(梇峬�旦生��桻豌(桾��邯教(����悒螂��(梇邿桷��﹠�晇泔�%1�掃�栫���允}}��}}鐓�旦生�灊�厭�中(桾��邯教(()���斥湍塵�(������桮哻���(�戴��塵�斯�鉞賽��捈斲旦訄��教蠙�(�戴��塵�斯尥葭善��■�鯷�桻���扤}尥�t���梇哧�桻��(�戴��塵�斯��等��栫�鶗塵���梇哧壑(�戴��塵�斯�梠���悒螂�迕褕挸�(�戴��塵�斯�邯��末路挼�}挸�(����嘗�}(�僱}賽��捈��褓��拊�孷賽��捈�婰(�槥��嵽�紫聒刓�菅迖��譫詳((���掃�}怛螂﹐QQ}AQ �迕��梇�中(�嘗��(��l�����(��l��}�桻豌(怛螂﹐QQ}AQ �迕(怛螂�1MQ}IU9}AQ ��蓮尥�晇��UM���桻豌穭(桾��(�嘖桮(��l����Q尥�(��l弗惦俍由���(��l��}�桻豌(怛螂﹐QQ}AQ �迕(怛螂�1MQ}IU9}AQ ��蓮尥�晇��MU5���桻豌穭(桾��(�迕��弗惦俍由��(怛螂�1MQ}IU9}AQ ��蓮����晇���-%11}M]%Q ���桻豌穭(桾��(�厭�迕�����尥�(怛螂�1MQ}IU9}AQ ��蓮尥�晇��UM���桻豌穭(桾��((夥挼扞��﹙旦�塾褕��(刓�迋��迕���教�賽����薀�(�塾�恚��(�捈�m���斥夥挼扞�旦苤嫮�t�鐀��拊��}�ul餕t(�敝(�捈�m���斥夥挼扞�迕嫮�t�厭�斥刓�迋��賽��迕嫮�t另��迕梋請�QI5%91ul��拊�孷賽��敊t((楖�����}�奼末��刓�桻蝌弗請腆楖華���奷�}�厭�什桯}善���拊尥飼善���捈嫮�t�褓���疘�梇捈u�(MU1Q}%H僱�玄℅捈顟尥�嵽迕}蓮顟尥((�褓�塾扞���枔(梇��賽�矻蝴挸銊���嘖桯}善��(桯l梇捈�謠�邯教�(��迕挸嶚�t�(刓�迋�m薔��(�晇���邯敗l�晇�t�(�旦生�梇邿���旦生��桻豌�(�蝴�塾}纓由憢�褕���邯教��塾恚纓由憢�褕�什(伂��邯教����扐��褕����褓穭���賽�悒��薀允��伂��(�掃梇邿���掃�(梇恚��刓��旦�邯敗抻篴�藿怛螂((怛螂！MU1Q}%H��篴�藿怛螂梇苳(��邯敗l�晇�t鐀�AQ(��l�捈l����t�旦苤迕�捈����蹊�壑���(�悼��邯敗l�晇�t鐀1Q=I5}	1=-(��l�捈l��褕稀���t�旦苤迕�捈��螫伂}����壑���(�悼��邯敗l�晇�t鐀=11}	,(��l�捈l蔣���旦苤迕�捈��刓控�}�壑���(�悼��邯敗l�晇�t鐀�%1(��l�捈l���t�旦苤迕�捈���弗�壑���(��	犮���迕�邯教������褓��褓梇邿��蔣��迪���}蓮���(��l弗惦俍由��Q尥�(�敝(��l�捈l�掃��旦苤迕�捈������壑���(��l��}�桻豌(怛螂﹐QQ}AQ �迕((桯l�旦生��桻豌(桯l夥挼扤}桯�t��腹旦�塾褕鉹(桯l刓�迋�}桯�t��腹賽��(桯l馴�}旦由�惦俍��t�邯����斥夥挼扞�迕嫮�t�厭�斥刓�迋��賽��迕嫮�t另��迕梋請�QI5%90�(怛螂�1MQ}IU9}AQ �尥舅(犮塵〝芺號聒怴�(��Q尥(�捈桯l�捈�(�晇���m嫮�晇�t�褓�尥雍梇捈t�(夥挼扤}桯��尥雍夥挼扤}桯�t�(刓�迋�}桯��尥雍刓�迋�}桯�t�(馴�桯l馴�}旦由�惦俍��t�(弗惦俍由�����郊控}俍由��(�邯�}火�中(桾���請����郊控}俍由��敝��(()�}��}|鐀}�旦}|(�槥��嵽苤�斥�(