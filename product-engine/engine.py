from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any

from ai_runtime import ModelAccessError, compose, research
from core import (
    INVENTORY_PATH, LAST_RUN_PATH, RESULT_DIR, STATE_PATH, TERMINAL,
    cache_purge, load_json, product_read, public_html, refresh_inventory,
    research_input, rollback, save_json, seo_read, textify, utcnow, write_candidate
)
from perf import lighthouse, passes as performance_passes, regressions
from qa import score as quality_score, update_bank, validate as validate_candidate

def default_state() -> dict[str,Any]:
    return {
        "schema_version":"product-autopilot-v1",
        "enabled":True,
        "kill_switch":False,
        "created_at":utcnow(),
        "updated_at":utcnow(),
        "processed":{},
        "sentence_bank":{},
        "stats":{"accepted":0,"platform_blocked":0,"blocked":0,"rolled_back":0,"failed":0},
    }

def seo_matches(seo: dict[str,Any], candidate: dict[str,Any]) -> bool:
    return (
        str(seo.get("title") or "")==str(candidate.get("seo_title") or "")
        and str(seo.get("description") or "")==str(candidate.get("meta_description") or "")
        and str(seo.get("focus_keyword") or "")==str(candidate.get("focus_keyphrase") or "")
    )

def process_one(entry: dict[str,Any], state: dict[str,Any], run_mode: str) -> dict[str,Any]:
    pid=int(entry["id"])
    result: dict[str,Any]={
        "schema_version":"product-result-v1","product_id":pid,
        "name":entry.get("name"),"started_at":utcnow(),"status":"STARTED"
    }
    try:
        before=product_read(pid)
        if str(before.get("status") or "")!="publish":
            result.update(status="SKIPPED",blocker="product is not published",finished_at=utcnow())
            return result

        seo_before=seo_read(pid)
        html_before=public_html(str(before.get("permalink") or ""))
        baseline=lighthouse(str(before.get("permalink") or ""),3)
        result["baseline_performance"]=baseline

        live=research_input(before,seo_before,html_before)
        report,sources=research(live)
        result["research_source_urls"]=sources
        result["research_source_count"]=len(sources)

        candidate=None
        errors=[]
        qscore=0
        qdetail={}
        feedback=""
        for attempt in range(1,4):
            candidate=compose(live,report,sources,feedback)
            errors=validate_candidate(candidate,before,sources,state.get("sentence_bank") or {})
            qscore,qdetail=quality_score(candidate,before,sources,errors)
            if not errors and qscore>=96:
                break
            feedback=json.dumps({
                "attempt":attempt,"validation_errors":errors,
                "quality_score":qscore,"quality_detail":qdetail
            },ensure_ascii=False)

        result["content_quality_score"]=qscore
        result["content_score_detail"]=qdetail
        result["validation_errors"]=errors
        result["candidate_summary"]={
            "family":candidate.get("family") if candidate else None,
            "commercial_angle":candidate.get("commercial_angle") if candidate else None,
        }

        if not candidate or errors or qscore<96:
            status="NEEDS_EVIDENCE" if len(sources)<2 else "QA_BLOCKED"
            result.update(status=status,blocker="candidate did not clear 96/evidence gate",finished_at=utcnow())
            return result

        if run_mode=="dry_run":
            result.update(status="DRY_RUN_READY",finished_at=utcnow())
            return result

        write_candidate(before,candidate)

        after=product_read(pid)
        seo_after=seo_read(pid)
        content_ok=(
            str(after.get("description") or "")==str(candidate["description_html"])
            and str(after.get("short_description") or "")==str(candidate["short_description_html"])
        )
        seo_ok=seo_matches(seo_after,candidate)
        result["readback"]={"content_ok":content_ok,"seo_ok":seo_ok}
        if not content_ok or not seo_ok:
            rb_ok=rollback(before,seo_before)
            result.update(
                status="ROLLED_BACK",rollback_readback_ok=rb_ok,
                blocker="write readback mismatch",finished_at=utcnow()
            )
            return result

        cache_purge()
        html_after=public_html(str(after.get("permalink") or ""))
        schema={
            "product":bool(re.search(r'"@type"\s*:\s*"Product"',html_after,re.I)),
            "offer":bool(re.search(r'"@type"\s*:\s*"Offer"',html_after,re.I)),
            "h1_count":len(re.findall(r"<h1\b",html_after,re.I)),
        }
        result["schema_readback"]=schema

        after_perf=lighthouse(str(after.get("permalink") or ""),3)
        result["after_performance"]=after_perf
        reg=regressions(baseline,after_perf)
        result["regressions"]=reg
        if reg:
            rb_ok=rollback(before,seo_before)
            result.update(
                status="ROLLED_BACK",rollback_readback_ok=rb_ok,
                blocker="; ".join(reg),finished_at=utcnow()
            )
            return result

        update_bank(state,pid,candidate)

        blockers=[]
        if not performance_passes(after_perf):
            blockers.append("mobile Lighthouse acceptance below 96 or CWV lab guard failed")
        if not schema["product"] or not schema["offer"]:
            blockers.append("Product/Offer schema parity not fully observable")
        if schema["h1_count"]!=1:
            blockers.append(f"H1 count is {schema['h1_count']}, expected 1")

        if blockers:
            result.update(status="PLATFORM_BLOCKED",blocker="; ".join(blockers))
        else:
            result.update(status="ACCEPTED")
        result["finished_at"]=utcnow()
        return result

    except ModelAccessError as exc:
        result.update(status="MODEL_ACCESS_BLOCKED",blocker=str(exc),finished_at=utcnow(),pause_engine=True)
        return result
    except Exception as exc:
        result.update(status="FAILED",blocker=f"{type(exc).__name__}: {exc}",finished_at=utcnow())
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

    state=load_json(STATE_PATH,default_state())

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
        state["updated_at"]=utcnow()
        state["model_access_blocked_at"]=utcnow()
        save_json(STATE_PATH,state)
        save_json(LAST_RUN_PATH,{
            "ok":False,"status":"MODEL_ACCESS_BLOCKED",
            "blocker":"OPENAI_API_KEY is not configured for product-engine",
            "at":utcnow(),"auto_retry_on_schedule":True
        })
        print(json.dumps({"ok":False,"status":"MODEL_ACCESS_BLOCKED","enabled":True,"auto_retry":True},ensure_ascii=False))
        return 0

    inventory=refresh_inventory()
    processed=state.setdefault("processed",{})

    if args.target_id:
        targets=[x for x in inventory if int(x["id"])==args.target_id][:1]
    else:
        targets=[
            x for x in inventory
            if str(x["id"]) not in processed
            or processed[str(x["id"])].get("status") not in TERMINAL
        ][:args.max_products]

    run={
        "schema_version":"product-autopilot-run-v1",
        "started_at":utcnow(),"run_mode":args.run_mode,
        "targets":[x["id"] for x in targets],"results":[]
    }
    RESULT_DIR.mkdir(parents=True,exist_ok=True)

    for entry in targets:
        result=process_one(entry,state,args.run_mode)
        run["results"].append(result)
        pid=str(entry["id"])
        save_json(RESULT_DIR/f"{pid}.json",result)

        if result.get("pause_engine"):
            state["enabled"]=False
            state["updated_at"]=utcnow()
            save_json(STATE_PATH,state)
            break

        if result["status"]!="DRY_RUN_READY":
            processed[pid]={
                "status":result["status"],
                "finished_at":result.get("finished_at") or utcnow(),
                "content_quality_score":result.get("content_quality_score"),
                "performance":((result.get("after_performance") or {}).get("representative") or {}).get("performance"),
                "blocker":result.get("blocker"),
                "result_file":f"product-engine/results/{pid}.json",
            }
            update_stats(state,result)

        if result["status"]=="FAILED" and (
            "Bridge" in str(result.get("blocker") or "")
            or result.get("rollback_readback_ok") is False
        ):
            state["kill_switch"]=True

        state["updated_at"]=utcnow()
        save_json(STATE_PATH,state)

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
        "ok":True,"targets":run["targets"],
        "statuses":[x["status"] for x in run["results"]],
        "inventory_count":run["inventory_count"],
        "processed_count":run["processed_count"],
        "remaining":run["remaining_initial_sweep"],
        "enabled":run["enabled"],"kill_switch":run["kill_switch"],
    },ensure_ascii=False))
    return 0 if not state.get("kill_switch") else 4

if __name__=="__main__":
    raise SystemExit(main())
