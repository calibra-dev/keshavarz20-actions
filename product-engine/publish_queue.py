#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import k20_sanitizer
from product_engine_compat import add_product_engine_path
add_product_engine_path()

from core import (
    RESULT_DIR, STATE_PATH, apply_image_alts, cache_purge, load_json, product_read, public_html,
    rollback, save_json, semantic_content_match, seo_read, textify, utcnow, write_candidate
)
from perf import http_probe, lighthouse, passes as performance_passes, regressions
from media_perf import maybe_optimize_featured, restore_featured
from qa import score as quality_score, update_bank, validate as validate_candidate

class QueueError(RuntimeError):
    pass

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

def load_queue(path: Path) -> dict[str,Any]:
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise QueueError("queue root must be an object")
    if data.get("content_type")!="product":
        raise QueueError("content_type must be product")
    pid=int(data.get("product_id") or 0)
    if pid<=0:
        raise QueueError("product_id is required")
    candidate=data.get("candidate")
    if not isinstance(candidate,dict):
        raise QueueError("candidate object is required")
    source_urls=data.get("source_urls") or candidate.get("source_urls") or []
    if not isinstance(source_urls,list):
        raise QueueError("source_urls must be a list")
    candidate["source_urls"]=list(dict.fromkeys(str(x) for x in source_urls if str(x).startswith("http")))
    k20_sanitizer.sanitize_payload_inplace(candidate)
    k20_sanitizer.assert_clean(candidate)
    return data

def seo_matches(seo: dict[str,Any], c: dict[str,Any]) -> bool:
    return (
        str(seo.get("title") or "")==str(c.get("seo_title") or "")
        and str(seo.get("description") or "")==str(c.get("meta_description") or "")
        and str(seo.get("focus_keyword") or "")==str(c.get("focus_keyphrase") or "")
    )

def update_state(state: dict[str,Any], pid: int, result: dict[str,Any], candidate: dict[str,Any] | None=None) -> None:
    processed=state.setdefault("processed",{})
    processed[str(pid)]={
        "status":result["status"],
        "finished_at":result.get("finished_at") or utcnow(),
        "content_quality_score":result.get("content_quality_score"),
        "performance":((result.get("after_performance") or {}).get("representative") or {}).get("performance"),
        "blocker":result.get("blocker"),
        "result_file":f"product-engine/results/{pid}.json",
    }
    stats=state.setdefault("stats",{})
    if result["status"]=="ACCEPTED":
        stats["accepted"]=int(stats.get("accepted",0))+1
        if candidate:
            update_bank(state,pid,candidate)
    elif result["status"]=="PLATFORM_BLOCKED":
        stats["platform_blocked"]=int(stats.get("platform_blocked",0))+1
    elif result["status"]=="ROLLED_BACK":
        stats["rolled_back"]=int(stats.get("rolled_back",0))+1
    elif result["status"]=="FAILED":
        stats["failed"]=int(stats.get("failed",0))+1
    else:
        stats["blocked"]=int(stats.get("blocked",0))+1
    state["updated_at"]=utcnow()
    save_json(STATE_PATH,state)

def run(queue: dict[str,Any], queue_path: str, validate_only: bool=False) -> dict[str,Any]:
    pid=int(queue["product_id"])
    candidate=queue["candidate"]
    source_urls=candidate.get("source_urls") or []
    strict=bool(queue.get("strict_acceptance",True))
    state=load_json(STATE_PATH,default_state())
    result={
        "schema_version":"product-queue-result-v1",
        "queue_file":queue_path,
        "product_id":pid,
        "started_at":utcnow(),
        "status":"STARTED",
    }

    before=product_read(pid)
    result["product_name"]=before.get("name")
    result["permalink"]=before.get("permalink")
    if str(before.get("status") or "")!="publish":
        raise QueueError("target product is not published")

    expected_modified=str(queue.get("expected_date_modified_gmt") or "")
    actual_modified=str(before.get("date_modified_gmt") or "")
    if (not validate_only) and expected_modified and expected_modified!=actual_modified:
        raise QueueError(f"stale queue: expected date_modified_gmt {expected_modified}, got {actual_modified}")
    if validate_only and expected_modified and expected_modified!=actual_modified:
        result["stale_queue_observed"]={
            "expected_date_modified_gmt":expected_modified,
            "actual_date_modified_gmt":actual_modified,
            "write_blocked":True
        }

    errors=validate_candidate(candidate,before,source_urls,state.get("sentence_bank") or {})
    qscore,qdetail=quality_score(candidate,before,source_urls,errors)
    result["content_quality_score"]=qscore
    result["content_score_detail"]=qdetail
    result["validation_errors"]=errors
    if errors or qscore<96:
        result.update(status="QA_BLOCKED",blocker="candidate did not clear product QA >=96",finished_at=utcnow())
        return result

    if validate_only:
        url=str(before.get("permalink") or "")
        result["http_probe"]=http_probe(url,5)
        baseline=lighthouse(url,3)
        result["baseline_performance"]=baseline
        result.update(status="VALIDATED",finished_at=utcnow())
        return result

    seo_before=seo_read(pid)
    page_before=public_html(str(before.get("permalink") or ""))
    result["baseline_schema"]={
        "product":bool(re.search(r'"@type"\s*:\s*"Product"',page_before,re.I)),
        "offer":bool(re.search(r'"@type"\s*:\s*"Offer"',page_before,re.I)),
        "h1_count":len(re.findall(r"<h1\b",page_before,re.I)),
    }
    baseline=lighthouse(str(before.get("permalink") or ""),3)
    result["baseline_performance"]=baseline

    write_candidate(before,candidate,write_media=False)
    after=product_read(pid)
    seo_after=seo_read(pid)
    desc_ok,desc_detail=semantic_content_match(
        str(candidate.get("description_html") or ""),
        str(after.get("description") or "")
    )
    short_ok,short_detail=semantic_content_match(
        str(candidate.get("short_description_html") or ""),
        str(after.get("short_description") or "")
    )
    content_ok=bool(desc_ok and short_ok)
    seo_ok=seo_matches(seo_after,candidate)
    result["readback"]={
        "content_ok":content_ok,
        "seo_ok":seo_ok,
        "description":desc_detail,
        "short_description":short_detail,
    }
    if not content_ok or not seo_ok:
        rb=rollback(before,seo_before)
        result.update(status="ROLLED_BACK",rollback_readback_ok=rb,blocker="content/SEO readback mismatch",finished_at=utcnow())
        return result

    media_action={"attempted":False,"reason":"not evaluated"}
    try:
        media_action=maybe_optimize_featured(after,baseline)
    except Exception as exc:
        media_action={"attempted":False,"error":f"{type(exc).__name__}: {exc}"}
    result["featured_image_performance_repair"]=media_action
    cache_purge()

    after=product_read(pid)
    page_after=public_html(str(after.get("permalink") or ""))
    schema={
        "product":bool(re.search(r'"@type"\s*:\s*"Product"',page_after,re.I)),
        "offer":bool(re.search(r'"@type"\s*:\s*"Offer"',page_after,re.I)),
        "h1_count":len(re.findall(r"<h1\b",page_after,re.I)),
    }
    result["schema_readback"]=schema
    perf=lighthouse(str(after.get("permalink") or ""),3)
    result["after_performance"]=perf
    reg=regressions(baseline,perf)
    result["regressions"]=reg

    blockers=[]
    if reg:
        blockers.extend(reg)
    if not performance_passes(perf):
        blockers.append("mobile Lighthouse acceptance below 96 or CWV lab guard failed")
    if not schema["product"] or not schema["offer"]:
        blockers.append("Product/Offer schema parity not fully observable")
    if schema["h1_count"]!=1:
        blockers.append(f"H1 count is {schema['h1_count']}, expected 1")

    if blockers and strict:
        image_rb=restore_featured(pid,media_action)
        content_rb=rollback(before,seo_before)
        result.update(
            status="ROLLED_BACK",
            rollback_readback_ok=bool(image_rb and content_rb),
            image_rollback_ok=image_rb,
            content_rollback_ok=content_rb,
            blocker="; ".join(blockers),
            finished_at=utcnow(),
        )
        return result

    if blockers:
        result.update(status="PLATFORM_BLOCKED",blocker="; ".join(blockers))
    else:
        changed_alt_ids=apply_image_alts(after,candidate)
        if changed_alt_ids:
            cache_purge()
        result["image_alt_changed_ids"]=changed_alt_ids
        result.update(status="ACCEPTED")
    result["finished_at"]=utcnow()
    return result

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("queue_file")
    ap.add_argument("--validate-only",action="store_true")
    args=ap.parse_args()
    path=Path(args.queue_file)
    if not path.exists():
        raise SystemExit(f"queue file not found: {path}")
    queue=load_queue(path)
    result=run(queue,str(path),args.validate_only)
    RESULT_DIR.mkdir(parents=True,exist_ok=True)
    save_json(RESULT_DIR/f"{int(queue['product_id'])}.json",result)
    if result["status"] not in {"VALIDATED"}:
        state=load_json(STATE_PATH,default_state())
        update_state(state,int(queue["product_id"]),result,queue.get("candidate"))
    print(json.dumps({
        "ok":result["status"] in {"VALIDATED","ACCEPTED","PLATFORM_BLOCKED"},
        "status":result["status"],
        "product_id":result["product_id"],
        "permalink":result.get("permalink"),
        "content_quality_score":result.get("content_quality_score"),
        "performance":((result.get("after_performance") or {}).get("representative") or {}).get("performance"),
        "blocker":result.get("blocker"),
    },ensure_ascii=False))
    return 0 if result["status"] in {"VALIDATED","ACCEPTED","PLATFORM_BLOCKED"} else 2

if __name__=="__main__":
    raise SystemExit(main())
