from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from ai_runtime import ModelAccessError, compose, research
from core import (
    LAST_RUN_PATH, RESULT_DIR, STATE_PATH, TERMINAL,
    load_json, product_read, public_html, refresh_inventory,
    research_input, save_json, seo_read, utcnow
)
from publish_queue import run as run_queue_pipeline
from qa import score as quality_score, validate as validate_candidate

CONFIG_PATH=Path(__file__).resolve().parent / "config.json"


def load_config() -> dict[str,Any]:
    return load_json(CONFIG_PATH,{})


def default_state() -> dict[str,Any]:
    return {
        "schema_version":"product-autopilot-v2","enabled":True,"kill_switch":False,
        "created_at":utcnow(),"updated_at":utcnow(),"processed":{},"sentence_bank":{},
        "stats":{"accepted":0,"platform_blocked":0,"blocked":0,"rolled_back":0,"failed":0},
    }


def build_candidate(entry: dict[str,Any], state: dict[str,Any], config: dict[str,Any]) -> tuple[dict[str,Any] | None,list[str],int,dict[str,Any],list[str]]:
    pid=int(entry["id"])
    product=product_read(pid)
    seo=seo_read(pid)
    html=public_html(str(product.get("permalink") or ""))
    live=research_input(product,seo,html)
    report,sources=research(live)
    candidate=None
    errors=[]
    qscore=0
    qdetail={}
    feedback=""
    target=int(config.get("content_acceptance") or 96)
    for attempt in range(1,4):
        candidate=compose(live,report,sources,feedback)
        errors=validate_candidate(candidate,product,sources,state.get("sentence_bank") or {})
        qscore,qdetail=quality_score(candidate,product,sources,errors)
        if not errors and qscore>=target:
            break
        feedback=json.dumps({
            "attempt":attempt,"validation_errors":errors,
            "quality_score":qscore,"quality_detail":qdetail
        },ensure_ascii=False)
    return candidate,errors,qscore,qdetail,sources


def process_one(entry: dict[str,Any], state: dict[str,Any], run_mode: str) -> dict[str,Any]:
    config=load_config()
    pid=int(entry["id"])
    result={"schema_version":"product-result-v2","product_id":pid,"name":entry.get("name"),"started_at":utcnow(),"status":"STARTED"}
    try:
        product=product_read(pid)
        if str(product.get("status") or "")!="publish":
            result.update(status="SKIPPED",blocker="product is not published",finished_at=utcnow())
            return result

        candidate,errors,qscore,qdetail,sources=build_candidate(entry,state,config)
        result["research_source_urls"]=sources
        result["research_source_count"]=len(sources)
        result["content_quality_score"]=qscore
        result["content_score_detail"]=qdetail
        result["validation_errors"]=errors
        if not candidate or errors or qscore<int(config.get("content_acceptance") or 96):
            status="NEEDS_EVIDENCE" if len(sources)<2 else "QA_BLOCKED"
            result.update(status=status,blocker="candidate did not clear content/evidence gate",finished_at=utcnow())
            return result
        if run_mode=="dry_run":
            result.update(status="DRY_RUN_READY",finished_at=utcnow())
            return result

        queue={
            "content_type":"product",
            "product_id":pid,
            "candidate":candidate,
            "source_urls":sources
        }
        return run_queue_pipeline(queue,f"auto:{pid}",False)

    except ModelAccessError as exc:
        result.update(status="MODEL_ACCESS_BLOCKED",blocker=str(exc),finished_at=utcnow(),pause_engine=True,retry_same_product=True)
        return result
    except Exception as exc:
        message=f"{type(exc).__name__}: {exc}"
        lowered=message.lower()
        if "insufficient_quota" in lowered or "credit_balance_exhausted" in lowered or "no credits remaining" in lowered:
            result.update(status="MODEL_ACCESS_BLOCKED",blocker=message,finished_at=utcnow(),pause_engine=True,retry_same_product=True)
            return result
        result.update(status="FAILED",blocker=message,finished_at=utcnow())
        return result


def update_stats(state: dict[str,Any], result: dict[str,Any]) -> None:
    status=result["status"]
    stats=state.setdefault("stats",{})
    if status=="ACCEPTED":
        stats["accepted"]=int(stats.get("accepted",0))+1
    elif status=="PLATFORM_BLOCKED":
        stats["platform_blocked"]=int(stats.get("platform_blocked",0))+1
    elif status=="ROLLED_BACK":
        stats["rolled_back"]=int(stats.get("rolled_back",0))+1
    elif status=="FAILED":
        stats["failed"]=int(stats.get("failed",0))+1
    elif status not in {"DRY_RUN_READY","SKIPPED"}:
        stats["blocked"]=int(stats.get("blocked",0))+1


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--max-products",type=int,default=1)
    ap.add_argument("--run-mode",choices=["auto","dry_run"],default="auto")
    ap.add_argument("--target-id",type=int,default=0)
    ap.add_argument("--pause",action="store_true")
    ap.add_argument("--resume",action="store_true")
    args=ap.parse_args()
    if not 1<=args.max_products<=5:
        raise SystemExit("--max-products must be 1..5")

    config=load_config()
    state=load_json(STATE_PATH,default_state())
    state["schema_version"]="product-autopilot-v2"

    if args.pause:
        state["enabled"]=False
        state["updated_at"]=utcnow()
        save_json(STATE_PATH,state)
        save_json(LAST_RUN_PATH,{"ok":True,"status":"PAUSED","at":utcnow()})
        return 0
    if args.resume:
        state["enabled"]=True
        state["kill_switch"]=False
        state["updated_at"]=utcnow()
        save_json(STATE_PATH,state)
        save_json(LAST_RUN_PATH,{"ok":True,"status":"RESUMED","at":utcnow()})
        return 0
    if state.get("kill_switch"):
        save_json(LAST_RUN_PATH,{"ok":False,"status":"KILL_SWITCH","at":utcnow()})
        return 3
    if not state.get("enabled",True):
        save_json(LAST_RUN_PATH,{"ok":True,"status":"PAUSED","at":utcnow()})
        return 0
    if not os.environ.get("OPENAI_API_KEY","").strip():
        blocked_at=utcnow()
        state["updated_at"]=blocked_at
        state["model_access_blocked_at"]=blocked_at
        save_json(STATE_PATH,state)
        save_json(LAST_RUN_PATH,{
            "ok":False,"status":"MODEL_ACCESS_BLOCKED",
            "blocker":"OPENAI_API_KEY is not configured for product-engine",
            "at":blocked_at,"auto_retry_on_schedule":True
        })
        print(json.dumps({"ok":False,"status":"MODEL_ACCESS_BLOCKED","enabled":True,"auto_retry":True},ensure_ascii=False))
        return 0

    inventory=refresh_inventory()
    processed=state.setdefault("processed",{})
    canary=config.get("canary") or {}
    canary_id=int(canary.get("product_id") or 0)
    require_canary=bool(canary.get("require_acceptance_before_catalog_advance",False))

    if args.target_id:
        targets=[x for x in inventory if int(x["id"])==args.target_id][:1]
    elif require_canary and canary_id and (processed.get(str(canary_id)) or {}).get("status")!="ACCEPTED":
        targets=[x for x in inventory if int(x["id"])==canary_id][:1]
    else:
        targets=[
            x for x in inventory
            if str(x["id"]) not in processed
            or processed[str(x["id"])].get("status") not in TERMINAL
        ][:args.max_products]

    run={
        "schema_version":"product-autopilot-run-v2","started_at":utcnow(),
        "run_mode":args.run_mode,"targets":[x["id"] for x in targets],"results":[]
    }
    RESULT_DIR.mkdir(parents=True,exist_ok=True)

    for entry in targets:
        result=process_one(entry,state,args.run_mode)
        run["results"].append(result)
        pid=str(entry["id"])
        save_json(RESULT_DIR/f"{pid}.json",result)

        if result.get("pause_engine"):
            state["enabled"]=False
        if result["status"]!="DRY_RUN_READY" and not result.get("retry_same_product"):
            summary=((result.get("after_performance") or {}).get("summary") or {})
            processed[pid]={
                "status":result["status"],"finished_at":result.get("finished_at") or utcnow(),
                "content_quality_score":result.get("content_quality_score"),
                "performance":((summary.get("performance") or {}).get("median")),
                "accessibility":((summary.get("accessibility") or {}).get("median")),
                "media_all_webp":((result.get("media_optimization") or {}).get("all_webp")),
                "blocker":result.get("blocker"),"result_file":f"product-engine/results/{pid}.json"
            }
            update_stats(state,result)

        if (
            (result["status"]=="FAILED" and "Bridge" in str(result.get("blocker") or ""))
            or result.get("rollback_readback_ok") is False
        ):
            state["kill_switch"]=True
        state["updated_at"]=utcnow()
        save_json(STATE_PATH,state)
        if result.get("pause_engine") or state.get("kill_switch"):
            break

    run["finished_at"]=utcnow()
    run["inventory_count"]=len(inventory)
    run["processed_count"]=len(processed)
    run["remaining_initial_sweep"]=sum(
        1 for x in inventory
        if str(x["id"]) not in processed
        or processed[str(x["id"])].get("status") not in TERMINAL
    )
    run["enabled"]=state.get("enabled")
    run["kill_switch"]=state.get("kill_switch")
    save_json(LAST_RUN_PATH,run)
    print(json.dumps({
        "ok":True,"targets":run["targets"],"statuses":[x["status"] for x in run["results"]],
        "inventory_count":run["inventory_count"],"processed_count":run["processed_count"],
        "remaining":run["remaining_initial_sweep"],"enabled":run["enabled"],"kill_switch":run["kill_switch"]
    },ensure_ascii=False))
    return 0 if not state.get("kill_switch") else 4


if __name__=="__main__":
    raise SystemExit(main())
