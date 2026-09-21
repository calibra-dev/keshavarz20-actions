#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def text(p): return (ROOT/p).read_text(encoding="utf-8")
def load(p): return json.loads(text(p))
def main(outpath):
    m=load("phase18/automation-governance.json"); p=load("automation-policy/seo-god-2026.json"); q=load("question-engine/config.json"); probe=load("phase18-results/news-read-probe.json"); e2e=load("phase18-results/news-publisher-e2e-latest.json")
    news_fallback=text(".github/workflows/k20-daily-agri-news.yml"); news_pub=text(".github/workflows/k20-news-queue-publisher.yml"); article_pub=text(".github/workflows/k20-article-queue-publisher.yml")
    heartbeat=text(".github/workflows/k20-question-heartbeat.yml"); scheduler=text(".github/workflows/k20-question-scheduler.yml"); control=text(".github/workflows/k20-question-scheduler-control.yml")
    news_readme=text("daily-agri-news/README.md"); article_prompt=text("daily-agri-articles/SCHEDULED_TASK_PROMPT.md"); news_base=text("daily-agri-news/publish_queue.py"); news_v2=text("daily-agri-news/publish_queue_v2.py"); article_base=text("daily-agri-articles/publish_queue.py"); article_v3=text("daily-agri-articles/publish_queue_v3.py")
    checks=[]
    def add(name,v): checks.append({"name":name,"pass":bool(v)})
    sr=m["schedule_readback"]
    add("news_schedule_0800_tehran",sr["news"]["enabled"] and sr["news"]["timezone"]=="Asia/Tehran" and sr["news"]["local_time"]=="08:00")
    add("article_schedule_0820_tehran",sr["article"]["enabled"] and sr["article"]["timezone"]=="Asia/Tehran" and sr["article"]["local_time"]=="08:20")
    add("news_api_generator_manual_fallback_only","workflow_dispatch:" in news_fallback and "\n  schedule:" not in news_fallback)
    add("news_queue_push_main_only","branches: [main]" in news_pub); add("news_pr_does_not_publish","if: github.event_name != 'pull_request'" in news_pub); add("news_global_concurrency_lock","group: k20-news-queue-publisher" in news_pub)
    add("article_queue_push_main_only","branches: [main]" in article_pub); add("article_pr_does_not_publish","if: github.event_name != 'pull_request'" in article_pub); add("article_global_concurrency_lock","group: k20-article-queue-publisher\n" in article_pub); add("article_v3_keeps_v2_validation","base = v2.base" in article_v3)
    add("question_scheduler_v18","engine_v18.py --action scheduled" in scheduler); add("question_heartbeat_status_v18","engine_v18.py --action status" in heartbeat); add("question_watchdog_recovery","recovered-stale-chain" in control); add("question_interval_truthful",q.get("continuous_mode") is True and q.get("min_interval_seconds")==1080 and q.get("max_interval_seconds")==1559)
    add("news_skip_day_supported","skip that day" in news_readme.lower()); add("article_skip_day_supported","skip the day" in article_prompt.lower())
    add("news_duplicate_exact_and_near","Duplicate news title detected" in news_v2 and "Near-duplicate news topic detected" in news_v2); add("article_duplicate_guard","ensure_not_duplicate" in article_base)
    add("news_custom_type_read_probe",probe.get("ok") is True and probe.get("read_only") is True and probe.get("writes_performed")==0)
    add("news_no_broken_rest_cpt_route","/wp-json/wp/v2/news" not in news_base and "wpvibe/v1/cli/run" in news_base)
    add("news_writer_uses_wp_native_guarded_route","wpvibe/v1/cli/run" in news_base and "wp-json/wp/v2/media" in news_base and "wp.newPost" not in news_base and "wp.uploadFile" not in news_base)
    cleanup=e2e.get("cleanup_verified") or {}
    add("news_publisher_e2e_cleanup",e2e.get("ok") is True and cleanup.get("post") is True and cleanup.get("media") is True)
    add("news_draft_only",p["automation"]["news_status"]=="draft"); add("article_draft_only",p["automation"]["article_status"]=="draft"); add("human_review_required","no_publish_without_human_review_for_generated_editorial_content" in p["hard_rules"])
    add("news_result_evidence",all(x in news_base for x in ['"source_urls"','"fields_written"','"qa_score"','"readback"'])); add("article_result_evidence",all(x in article_base for x in ['"source_urls"','"fields_written"','"qa_score"','"readback"']))
    passed=all(x["pass"] for x in checks)
    result={"phase":18,"status":"PASS" if passed else "FAIL","checks":checks,"acceptance":{"news_0800_architecture_current_and_tested":all(x["pass"] for x in checks if x["name"] in ["news_schedule_0800_tehran","news_api_generator_manual_fallback_only","news_queue_push_main_only","news_pr_does_not_publish","news_global_concurrency_lock","news_custom_type_read_probe","news_no_broken_rest_cpt_route","news_writer_uses_wp_native_guarded_route","news_publisher_e2e_cleanup"]),"article_schedule_validated":all(x["pass"] for x in checks if x["name"].startswith("article_")),"question_cadence_truthful":all(x["pass"] for x in checks if x["name"].startswith("question_")),"skip_day_supported":all(x["pass"] for x in checks if "skip_day" in x["name"]),"duplicate_drafts_guarded":all(x["pass"] for x in checks if "duplicate" in x["name"])},"runtime_evidence":m["observed_runtime"],"news_read_probe":probe,"news_publisher_e2e":e2e,"site_mutations_by_acceptance_workflow":0,"commerce_mutations":0,"secret_values_persisted":False}
    out=ROOT/outpath; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE18_AUTOMATION_GOVERNANCE",json.dumps({"status":result["status"],"failed":sum(not x["pass"] for x in checks)},ensure_ascii=False))
    if not passed: raise SystemExit(2)
if __name__=="__main__": main(sys.argv[1])
