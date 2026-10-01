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

from a11y import analyze as analyze_accessibility
from core import (
    RESULT_DIR, STATE_PATH, apply_image_alts, cache_purge, load_json, product_read, public_html,
    rollback, save_json, semantic_content_match, seo_read, utcnow, write_candidate
)
from media_perf import optimize_product_images, remap_alt_suggestions, restore_product_images
from perf import acceptance as performance_acceptance, http_probe, lighthouse, regressions
from protected_fields import compare as compare_protected, snapshot as protected_snapshot
from qa import score as quality_score, update_bank, validate as validate_candidate
from visual_guard import compare as visual_compare

CONFIG_PATH=Path(__file__).resolve().parent / "config.json"


class QueueError(RuntimeError):
    pass


def load_config() -> dict[str,Any]:
    return load_json(CONFIG_PATH,{})


def default_state() -> dict[str,Any]:
    return {
        "schema_version":"product-autopilot-v2","enabled":True,"kill_switch":False,
        "created_at":utcnow(),"updated_at":utcnow(),"processed":{},"sentence_bank":{},
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


def media_snapshot(product: dict[str,Any]) -> list[dict[str,Any]]:
    return [{
        "role":"featured" if index==0 else "gallery",
        "attachment_id":int(image.get("id") or 0),
        "src":image.get("src"),"alt":image.get("alt")
    } for index,image in enumerate(product.get("images") or [])]


def rollback_all(pid: int, before: dict[str,Any], seo_before: dict[str,Any], media_action: dict[str,Any]) -> tuple[bool,bool]:
    image_ok=restore_product_images(pid,media_action)
    content_ok=rollback(before,seo_before)
    return image_ok,content_ok


def update_state(state: dict[str,Any], pid: int, result: dict[str,Any], candidate: dict[str,Any] | None=None) -> None:
    summary=((result.get("after_performance") or {}).get("summary") or {})
    state.setdefault("processed",{})[str(pid)]={
        "status":result["status"],"finished_at":result.get("finished_at") or utcnow(),
        "content_quality_score":result.get("content_quality_score"),
        "performance":((summary.get("performance") or {}).get("median")),
        "accessibility":((summary.get("accessibility") or {}).get("median")),
        "media_all_webp":((result.get("media_optimization") or {}).get("all_webp")),
        "protected_fields_ok":((result.get("protected_fields") or {}).get("ok")),
        "blocker":result.get("blocker"),"result_file":f"product-engine/results/{pid}.json"
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
    state["schema_version"]="product-autopilot-v2"
    state["updated_at"]=utcnow()
    save_json(STATE_PATH,state)


def run(queue: dict[str,Any], queue_path: str, validate_only: bool=False) -> dict[str,Any]:
    config=load_config()
    pid=int(queue["product_id"])
    candidate=queue["candidate"]
    source_urls=candidate.get("source_urls") or []
    state=load_json(STATE_PATH,default_state())
    result={
        "schema_version":"product-queue-result-v2","queue_file":queue_path,
        "product_id":pid,"started_at":utcnow(),"status":"STARTED",
        "policy":{
            "content_acceptance":int(config.get("content_acceptance") or 96),
            "lighthouse_acceptance":config.get("lighthouse_acceptance") or {},
            "media_optimization":config.get("media_optimization") or {}
        }
    }

    before=product_read(pid)
    result["product_name"]=before.get("name")
    result["permalink"]=before.get("permalink")
    result["before_media"]=media_snapshot(before)
    protected_before=protected_snapshot(before)
    if str(before.get("status") or "")!="publish":
        raise QueueError("target product is not published")

    expected_modified=str(queue.get("expected_date_modified_gmt") or "")
    actual_modified=str(before.get("date_modified_gmt") or "")
    if (not validate_only) and expected_modified and expected_modified!=actual_modified:
        raise QueueError(f"stale queue: expected date_modified_gmt {expected_modified}, got {actual_modified}")
    if validate_only and expected_modified and expected_modified!=actual_modified:
        result["stale_queue_observed"]={
            "expected_date_modified_gmt":expected_modified,
            "actual_date_modified_gmt":actual_modified,"write_blocked":True
        }

    errors=validate_candidate(candidate,before,source_urls,state.get("sentence_bank") or {})
    qscore,qdetail=quality_score(candidate,before,source_urls,errors)
    result["content_quality_score"]=qscore
    result["content_score_detail"]=qdetail
    result["validation_errors"]=errors
    content_gate=int(config.get("content_acceptance") or 96)
    if errors or qscore<content_gate:
        result.update(status="QA_BLOCKED",blocker=f"candidate did not clear product QA >={content_gate}",finished_at=utcnow())
        return result

    url=str(before.get("permalink") or "")
    if validate_only:
        result["http_probe"]=http_probe(url,5)
        baseline=lighthouse(url,3)
        result["baseline_performance"]=baseline
        result["baseline_accessibility"]=analyze_accessibility(baseline)
        result["baseline_acceptance"]=performance_acceptance(baseline,config.get("lighthouse_acceptance") or {})
        result.update(status="VALIDATED",finished_at=utcnow())
        return result

    seo_before=seo_read(pid)
    page_before=public_html(url)
    result["baseline_schema"]={
        "product":bool(re.search(r'"@type"\s*:\s*"Product"',page_before,re.I)),
        "offer":bool(re.search(r'"@type"\s*:\s*"Offer"',page_before,re.I)),
        "h1_count":len(re.findall(r"<h1\b",page_before,re.I))
    }
    result["http_probe_before"]=http_probe(url,3)
    baseline=lighthouse(url,3)
    result["baseline_performance"]=baseline
    result["baseline_accessibility"]=analyze_accessibility(baseline)

    write_candidate(before,candidate,write_media=False)
    after_content=product_read(pid)
    seo_after=seo_read(pid)
    desc_ok,desc_detail=semantic_content_match(str(candidate.get("description_html") or ""),str(after_content.get("description") or ""))
    short_ok,short_detail=semantic_content_match(str(candidate.get("short_description_html") or ""),str(after_content.get("short_description") or ""))
    content_ok=bool(desc_ok and short_ok)
    seo_ok=seo_matches(seo_after,candidate)
    result["readback"]={"content_ok":content_ok,"seo_ok":seo_ok,"description":desc_detail,"short_description":short_detail}
    if not content_ok or not seo_ok:
        rb=rollback(before,seo_before)
        result.update(status="ROLLED_BACK",rollback_readback_ok=rb,blocker="content/SEO readback mismatch",finished_at=utcnow())
        return result

    try:
        media_action=optimize_product_images(after_content,config.get("media_optimization") or {},candidate.get("image_alt_suggestions") or [])
    except Exception as exc:
        rb=rollback(before,seo_before)
        result["media_optimization"]={"attempted":True,"error":f"{type(exc).__name__}: {exc}"}
        result.update(status="ROLLED_BACK",rollback_readback_ok=rb,blocker="media optimization/readback failure",finished_at=utcnow())
        return result
    result["media_optimization"]=media_action

    after_media=product_read(pid)
    mapped_alts=remap_alt_suggestions(candidate.get("image_alt_suggestions") or [],media_action)
    changed_alt_ids=apply_image_alts(after_media,{"image_alt_suggestions":mapped_alts}) if mapped_alts else []
    result["image_alt_changed_ids"]=changed_alt_ids
    if changed_alt_ids:
        cache_purge()

    after=product_read(pid)
    protected_check=compare_protected(protected_before,protected_snapshot(after))
    result["protected_fields"]=protected_check
    if not protected_check["ok"]:
        image_rb,content_rb=rollback_all(pid,before,seo_before,media_action)
        result.update(
            status="ROLLED_BACK",image_rollback_ok=image_rb,content_rollback_ok=content_rb,
            rollback_readback_ok=bool(image_rb and content_rb),
            blocker="protected field mutation detected",finished_at=utcnow()
        )
        return result

    page_after=public_html(str(after.get("permalink") or ""))
    schema={
        "product":bool(re.search(r'"@type"\s*:\s*"Product"',page_after,re.I)),
        "offer":bool(re.search(r'"@type"\s*:\s*"Offer"',page_after,re.I)),
        "h1_count":len(re.findall(r"<h1\b",page_after,re.I))
    }
    result["schema_readback"]=schema
    visual=visual_compare(before,after,page_before,page_after,config.get("visual_guard") or {})
    result["visual_guard"]=visual
    if not visual["ok"]:
        image_rb,content_rb=rollback_all(pid,before,seo_before,media_action)
        result.update(
            status="ROLLED_BACK",image_rollback_ok=image_rb,content_rollback_ok=content_rb,
            rollback_readback_ok=bool(image_rb and content_rb),
            blocker="visual/DOM regression guard failed: "+"; ".join(visual["issues"]),finished_at=utcnow()
        )
        return result

    result["http_probe_after"]=http_probe(url,3)
    perf=lighthouse(url,3)
    result["after_performance"]=perf
    result["after_accessibility"]=analyze_accessibility(perf)
    acceptance=performance_acceptance(perf,config.get("lighthouse_acceptance") or {})
    result["acceptance"]=acceptance
    reg=regressions(baseline,perf)
    result["regressions"]=reg

    if reg:
        image_rb,content_rb=rollback_all(pid,before,seo_before,media_action)
        result.update(
            status="ROLLED_BACK",image_rollback_ok=image_rb,content_rollback_ok=content_rb,
            rollback_readback_ok=bool(image_rb and content_rb),
            blocker="; ".join(reg),finished_at=utcnow()
        )
        return result

    blockers=list(acceptance.get("reasons") or [])
    if not schema["product"] or not schema["offer"]:
        blockers.append("Product/Offer schema parity not fully observable")
    if schema["h1_count"]!=1:
        blockers.append(f"H1 count is {schema['h1_count']}, expected 1")
    if (after.get("images") or []) and not media_action.get("all_webp"):
        blockers.append("product media WebP coverage is incomplete")

    if blockers:
        result.update(status="PLATFORM_BLOCKED",blocker="; ".join(blockers))
    else:
        result.update(status="ACCEPTED")
    result["after_media"]=media_snapshot(product_read(pid))
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
    summary=((result.get("after_performance") or result.get("baseline_performance") or {}).get("summary") or {})
    print(json.dumps({
        "ok":result["status"] in {"VALIDATED","ACCEPTED","PLATFORM_BLOCKED"},
        "status":result["status"],"product_id":result["product_id"],
        "permalink":result.get("permalink"),"content_quality_score":result.get("content_quality_score"),
        "performance_median":((summary.get("performance") or {}).get("median")),
        "accessibility_median":((summary.get("accessibility") or {}).get("median")),
        "media_all_webp":((result.get("media_optimization") or {}).get("all_webp")),
        "blocker":result.get("blocker")
    },ensure_ascii=False))
    return 0 if result["status"] in {"VALIDATED","ACCEPTED","PLATFORM_BLOCKED"} else 2


if __name__=="__main__":
    raise SystemExit(main())
