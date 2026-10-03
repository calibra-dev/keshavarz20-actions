#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from core import STATE_PATH, load_json, save_json, utcnow
from perf import acceptance_delta
from qa import update_bank

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT / "product-engine"
CONFIG=ENGINE / "config.json"
RESULTS=ENGINE / "results"


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
