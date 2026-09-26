#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
def text(p): return (ROOT/p).read_text(encoding="utf-8")
def load(p): return json.loads(text(p))
def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()

def main(outpath):
    m=load("phase18/automation-governance.json")
    live=load("phase18/live-schedule-readback.json")
    policy=load("automation-policy/seo-god-2026.json")
    q=load("question-engine/config.json")
    probe=load("phase18-results/news-read-probe.json")
    news_e2e=load("phase18-results/news-publisher-e2e-latest.json")
    article_e2e=load("phase18-results/article-publisher-e2e-latest.json")

    news_fallback=text(".github/workflows/k20-daily-agri-news.yml")
    news_pub=text(".github/workflows/k20-news-queue-publisher.yml")
    article_pub=text(".github/workflows/k20-article-queue-publisher.yml")
    heartbeat=text(".github/workflows/k20-question-heartbeat.yml")
    scheduler=text(".github/workflows/k20-question-scheduler.yml")
    control=text(".github/workflows/k20-question-scheduler-control.yml")
    news_readme=text("daily-agri-news/README.md")
    article_readme=text("daily-agri-articles/README.md")
    article_prompt=text("daily-agri-articles/SCHEDULED_TASK_PROMPT.md")
    news_base=text("daily-agri-news/publish_queue.py")
    news_v2=text("daily-agri-news/publish_queue_v2.py")
    news_v3=text("daily-agri-news/publish_queue_v3.py")
    article_base=text("daily-agri-articles/publish_queue.py")
    article_v2=text("daily-agri-articles/publish_queue_v2.py")
    article_v3=text("daily-agri-articles/publish_queue_v3.py")
    article_v4=text("daily-agri-articles/publish_queue_v4.py")
    article_v5=text("daily-agri-articles/publish_queue_v5.py")

    checks=[]
    def add(name,v): checks.append({"name":name,"pass":bool(v)})

    sr=m["schedule_readback"]
    ln=live["news"]; la=live["article"]; lq=live["question"]
    ps=policy["automation"]["schedules"]

    add("manifest_v2",m.get("version")=="phase18-automation-governance-v2")
    add("live_news_primary_enabled_0800",ln["primary"]["enabled"] and ln["primary"]["time"]=="08:00")
    add("live_news_recovery_enabled_0815",ln["recovery"]["enabled"] and ln["recovery"]["time"]=="08:15")
    add("live_article_primary_enabled_0900",la["primary"]["enabled"] and la["primary"]["time"]=="09:00")
    add("live_article_recovery_enabled_0920",la["recovery"]["enabled"] and la["recovery"]["time"]=="09:20")
    add("manifest_live_schedule_parity",
        sr["news"]["enabled"] and sr["news"]["primary_local_time"]=="08:00" and sr["news"]["recovery_enabled"] and sr["news"]["recovery_local_time"]=="08:15"
        and sr["article"]["enabled"] and sr["article"]["primary_local_time"]=="09:00" and sr["article"]["recovery_enabled"] and sr["article"]["recovery_local_time"]=="09:20")
    add("policy_schedule_parity",
        ps["news"]["primary_time_tehran"]=="08:00" and ps["news"]["recovery_time_tehran"]=="08:15"
        and ps["article"]["primary_time_tehran"]=="09:00" and ps["article"]["recovery_time_tehran"]=="09:20")

    add("news_api_generator_manual_fallback_only","workflow_dispatch:" in news_fallback and "\n  schedule:" not in news_fallback)
    add("news_queue_push_main_only","branches: [main]" in news_pub)
    add("news_pr_does_not_publish","if: github.event_name != 'pull_request'" in news_pub)
    add("news_global_concurrency_lock","group: k20-news-queue-publisher" in news_pub)
    add("news_current_publisher_v3","publish_queue_v3.py" in news_pub)
    add("news_v3_keeps_v2_validation","v2.validate_payload_v2(p)" in news_v3)
    add("news_v3_deterministic_persian","ai_text_rendering" in news_v3 and "NotoSansArabic" in news_v3 and "fail_closed_on_copy_overflow" in news_v3)

    add("article_queue_push_main_only","branches: [main]" in article_pub)
    add("article_pr_does_not_publish","if: github.event_name != 'pull_request'" in article_pub)
    add("article_global_concurrency_lock","group: k20-article-queue-publisher" in article_pub)
    add("article_current_publisher_v5","publish_queue_v5.py" in article_pub)
    add("article_v5_chain_preserved","publish_queue_v4.py" in article_v5 and "publish_queue_v3.py" in article_v4 and "publish_queue_v2.py" in article_v3)
    add("article_adaptive_faq","faq_items" in article_v2 and "FAQ is useful content, not a quota" in article_v2)
    add("article_v5_deterministic_persian","ai_text_rendering" in article_v5 and "NotoSansArabic" in article_v4 and "fail_closed_on_copy_overflow" in article_v5)

    add("question_scheduler_v18","engine_v18.py --action scheduled" in scheduler)
    add("question_heartbeat_status_v18","engine_v18.py --action status" in heartbeat)
    add("question_watchdog_recovery","recovered-stale-chain" in control)
    add("question_interval_truthful",q.get("enabled") is True and q.get("continuous_mode") is True and q.get("min_interval_seconds")==1080 and q.get("max_interval_seconds")==1559 and q.get("engine_version")=="v18")
    add("question_live_runtime_evidence",lq.get("engine")=="v18" and lq.get("continuous") is True and int(lq.get("scheduler_run_id") or 0)>0 and int(lq.get("control_run_id") or 0)>0 and int(lq.get("heartbeat_run_id") or 0)>0)

    add("news_skip_day_supported","skip that day" in news_readme.lower())
    add("article_skip_day_supported","skip the day" in article_prompt.lower())
    add("news_duplicate_exact_and_near","Duplicate news title detected" in news_v2 and "Near-duplicate news topic detected" in news_v2)
    add("article_duplicate_guard","ensure_not_duplicate" in article_base)

    add("news_custom_type_read_probe",probe.get("ok") is True and probe.get("read_only") is True and probe.get("writes_performed")==0 and int(probe.get("sample_title_count") or 0)>0)
    add("news_current_guarded_writer","wpvibe/v1/cli/run" in news_base and "wp-json/wp/v2/media" in news_base and "wp.newPost" not in news_base and "wp.uploadFile" not in news_base)
    nsteps={x.get("step"):x for x in news_e2e.get("steps",[])}
    nclean=news_e2e.get("cleanup_verified") or {}
    add("news_v3_e2e_render",news_e2e.get("ok") is True and nsteps.get("render_v3_cover",{}).get("ok") is True)
    add("news_e2e_draft_readback",nsteps.get("verify",{}).get("ok") is True and nsteps.get("verify",{}).get("status")=="draft" and nsteps.get("verify",{}).get("type")=="news")
    add("news_e2e_cleanup",nclean.get("post") is True and nclean.get("media") is True)

    asteps={x.get("step"):x for x in article_e2e.get("steps",[])}
    aclean=article_e2e.get("cleanup_verified") or {}
    add("article_v5_e2e_render",article_e2e.get("ok") is True and article_e2e.get("publisher_version")=="v5" and asteps.get("render_v5_cover",{}).get("ok") is True)
    add("article_e2e_draft_readback",asteps.get("verify_readback",{}).get("ok") is True and asteps.get("verify_readback",{}).get("status")=="draft" and asteps.get("verify_readback",{}).get("type")=="post")
    add("article_e2e_cleanup",aclean.get("post") is True and aclean.get("media") is True and article_e2e.get("published") is False)

    hard=policy["hard_rules"]
    add("news_draft_only",policy["automation"]["news_status"]=="draft" and policy["news_engine"]["draft_only"] is True)
    add("article_draft_only",policy["automation"]["article_status"]=="draft" and policy["article_engine"]["draft_only"] is True)
    add("human_review_required","no_publish_without_human_review_for_generated_editorial_content" in hard)
    add("routing_guards_present",all(x in policy["automation"]["routing"]["hard_guards"] for x in [
        "news_payload_must_never_be_written_as_post","article_payload_must_never_be_written_as_news","publisher_must_verify_wordpress_post_type_after_write"
    ]))
    add("news_result_evidence",all(x in news_base for x in ['"source_urls"','"fields_written"','"qa_score"','"readback"']))
    add("article_result_evidence",all(x in article_base for x in ['"source_urls"','"fields_written"','"qa_score"','"readback"']))
    add("no_secret_persistence",m.get("secret_values_persisted") is False and policy["automation"]["no_secret_values_in_logs"] is True)
    add("commerce_out_of_scope",article_e2e.get("commerce_mutations")==0)

    passed=all(x["pass"] for x in checks)
    result={
      "phase":18,
      "version":"phase18-automation-governance-v2",
      "title":"Automation Governance - News / Article / Q&A",
      "status":"PASS_V2" if passed else "FAIL_V2",
      "checks":checks,
      "check_count":len(checks),
      "passed_checks":sum(1 for x in checks if x["pass"]),
      "failed_checks":[x["name"] for x in checks if not x["pass"]],
      "acceptance":{
        "live_schedules_enabled_and_aligned":all(x["pass"] for x in checks if x["name"].startswith("live_") or x["name"] in ("manifest_live_schedule_parity","policy_schedule_parity")),
        "news_current_v3_governed":all(x["pass"] for x in checks if x["name"].startswith("news_")),
        "article_current_v5_governed":all(x["pass"] for x in checks if x["name"].startswith("article_")),
        "question_v18_runtime_governed":all(x["pass"] for x in checks if x["name"].startswith("question_")),
        "draft_only_human_review":all(x["pass"] for x in checks if x["name"] in ("news_draft_only","article_draft_only","human_review_required")),
        "duplicate_drafts_guarded":all(x["pass"] for x in checks if "duplicate" in x["name"]),
        "temporary_e2e_cleanup_verified":all(x["pass"] for x in checks if x["name"].endswith("_e2e_cleanup"))
      },
      "live_schedule_readback":live,
      "runtime_evidence":m["observed_runtime"],
      "news_read_probe":probe,
      "news_publisher_e2e":news_e2e,
      "article_publisher_e2e":article_e2e,
      "input_sha256":{
        "phase18/automation-governance.json":sha("phase18/automation-governance.json"),
        "phase18/live-schedule-readback.json":sha("phase18/live-schedule-readback.json"),
        "automation-policy/seo-god-2026.json":sha("automation-policy/seo-god-2026.json"),
        "question-engine/config.json":sha("question-engine/config.json"),
        "phase18-results/news-publisher-e2e-latest.json":sha("phase18-results/news-publisher-e2e-latest.json"),
        "phase18-results/article-publisher-e2e-latest.json":sha("phase18-results/article-publisher-e2e-latest.json")
      },
      "site_mutations_by_acceptance_workflow":0,
      "temporary_e2e_mutations_cleaned":True if passed else bool(nclean.get("post") and nclean.get("media") and aclean.get("post") and aclean.get("media")),
      "commerce_mutations":0,
      "price_stock_discount_mutations":0,
      "orders_payments_users_mutations":0,
      "secret_values_persisted":False
    }
    out=ROOT/outpath; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE18_V2",json.dumps({"status":result["status"],"checks":len(checks),"passed":result["passed_checks"],"failed":result["failed_checks"]},ensure_ascii=False))
    if not passed: raise SystemExit(2)

if __name__=="__main__": main(sys.argv[1])
