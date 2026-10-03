#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from perf import acceptance_delta

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT / "product-engine"
CONFIG=ENGINE / "config.json"
STATE_PATH=ENGINE / "state.json"
RESULTS=ENGINE / "results"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def textify(raw: str) -> str:
    text=re.sub(r"<[^>]+>"," ",raw or "")
    text=html.unescape(text)
    return re.sub(r"\s+"," ",text).strip()


def sentence_fingerprints(raw: str) -> list[tuple[str,str]]:
    text=textify(raw).lower()
    chunks=re.split(r"[.!؟]\s+|\n+",text)
    out=[]
    for sentence in chunks:
        norm=re.sub(r"[^\w\u0600-\u06ff]+"," ",sentence)
        norm=re.sub(r"\s+"," ",norm).strip()
        if len(norm.split())<12:
            continue
        out.append((hashlib.sha256(norm.encode("utf-8")).hexdigest()[:20],norm[:220]))
    return out


def update_bank(state: dict[str,Any], product_id: int, candidate: dict[str,Any]) -> None:
    bank=state.setdefault("sentence_bank",{})
    raw=str(candidate.get("short_description_html") or "")+" "+str(candidate.get("description_html") or "")
    for digest,snippet in sentence_fingerprints(raw):
        bank[digest]={"product_id":product_id,"snippet":snippet}
    if len(bank)>3000:
        for key in list(bank)[:len(bank)-3000]:
            bank.pop(key,None)


def fail(message: str) -> None:
    raise SystemExit(f"PRODUCT_PLATFORM_DEBT_RECLASSIFY_FAILED: {message}")


def reclassify(product_id: int) -> dict[str,Any]:
    config=load_json(CONFIG,{})
    state=load_json(STATE_PATH,{})
    result_path=RESULTS / f"{product_id}.json"
    if not result_path.is_file():
        fail("result file missing")
    result=load_json(result_path,{})
    if result.get("status")!="PLATFORM_BLOCKED":
        fail(f"result status is {result.get('status')}, expected PLATFORM_BLOCKED")
    if result.get("regressions"):
        fail("result contains measured regressions")

    readback=result.get("readback") or {}
    if readback.get("content_ok") is not True or readback.get("seo_ok") is not True:
        fail("content/SEO readback is not fully verified")
    if (result.get("protected_fields") or {}).get("ok") is not True:
        fail("protected-field guard did not pass")
    if (result.get("visual_guard") or {}).get("ok") is not True:
        fail("visual guard did not pass")

    schema=result.get("schema_readback") or {}
    if schema.get("product") is not True or schema.get("offer") is not True or int(schema.get("h1_count") or 0)!=1:
        fail("schema/H1 guard did not pass")

    media=result.get("media_optimization") or {}
    if result.get("before_media") and (media.get("readback_ok") is not True or media.get("all_webp") is not True):
        fail("media readback/WebP guard did not pass")

    policy=((result.get("policy") or {}).get("lighthouse_acceptance") or config.get("lighthouse_acceptance") or {}).copy()
    policy["inherited_platform_debt_is_warning"]=True
    delta=acceptance_delta(result.get("baseline_performance") or {},result.get("after_performance") or {},policy)
    if delta.get("new_reasons"):
        fail("new post-publish Lighthouse blockers remain: "+"; ".join(delta["new_reasons"]))

    queue_path=ROOT / str(result.get("queue_file") or "")
    if not queue_path.is_file():
        fail("bound immutable queue file missing")
    queue=load_json(queue_path,{})
    if int(queue.get("product_id") or 0)!=product_id:
        fail("queue product_id mismatch")

    previous_blocker=result.get("blocker")
    now=utcnow()
    result["previous_status"]="PLATFORM_BLOCKED"
    result["previous_blocker"]=previous_blocker
    result["status"]="ACCEPTED"
    result["blocker"]=None
    result["acceptance_mode"]="baseline_relative"
    result["platform_debt"]=delta
    result["platform_warnings"]=delta.get("inherited_reasons") or []
    result["reclassification"]={
        "schema_version":"product-platform-debt-reclassification-v1",
        "reclassified_at":now,
        "reason":"preexisting_sitewide_lighthouse_debt_without_product_regression",
        "from_status":"PLATFORM_BLOCKED",
        "to_status":"ACCEPTED",
    }
    save_json(result_path,result)

    processed=(state.setdefault("processed",{})).get(str(product_id))
    if not isinstance(processed,dict) or processed.get("status")!="PLATFORM_BLOCKED":
        fail("state entry is not PLATFORM_BLOCKED")
    processed["status"]="ACCEPTED"
    processed["blocker"]=None
    processed["platform_warning"]="; ".join(result["platform_warnings"]) or None
    processed["reclassified_at"]=now

    stats=state.setdefault("stats",{})
    stats["platform_blocked"]=max(0,int(stats.get("platform_blocked",0))-1)
    stats["accepted"]=int(stats.get("accepted",0))+1
    update_bank(state,product_id,queue.get("candidate") or {})
    state["updated_at"]=now
    save_json(STATE_PATH,state)

    return {"product_id":product_id,"status":"ACCEPTED","warnings":result["platform_warnings"]}


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("product_id",type=int)
    args=ap.parse_args()
    out=reclassify(args.product_id)
    print(f"PRODUCT_PLATFORM_DEBT_RECLASSIFIED product_id={out['product_id']} status={out['status']} warnings={len(out['warnings'])}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
