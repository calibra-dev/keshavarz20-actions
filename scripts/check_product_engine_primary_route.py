#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "product-engine" / "PRIMARY_ROUTE_LOCK.json"
CONFIG_PATH = ROOT / "product-engine" / "config.json"
PROMPT_PATH = ROOT / "product-engine" / "SCHEDULED_TASK_PROMPT.md"
README_PATH = ROOT / "product-engine" / "README.md"
API_WF_PATH = ROOT / ".github" / "workflows" / "k20-product-autopilot.yml"
QUEUE_WF_PATH = ROOT / ".github" / "workflows" / "k20-product-queue-publisher.yml"
PROMOTER_WF_PATH = ROOT / ".github" / "workflows" / "k20-product-queue-promoter.yml"
PUBLISHER_PATH = ROOT / "product-engine" / "publish_queue.py"


def fail(message: str) -> None:
    raise SystemExit(f"PRODUCT_ROUTE_GUARD_FAILED: {message}")


lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
prompt = PROMPT_PATH.read_text(encoding="utf-8")
readme = README_PATH.read_text(encoding="utf-8")
api_wf = API_WF_PATH.read_text(encoding="utf-8")
queue_wf = QUEUE_WF_PATH.read_text(encoding="utf-8")
promoter_wf = PROMOTER_WF_PATH.read_text(encoding="utf-8")
publisher_py = PUBLISHER_PATH.read_text(encoding="utf-8")

if lock.get("primary_producer") != "connected_chatgpt_queue":
    fail("route lock primary_producer changed")

live_read = lock.get("producer_live_read") or {}
if live_read.get("gateway_workflow") != ".github/workflows/k20-bridge-v3-gateway.yml":
    fail("producer live-read gateway must remain Bridge v3 gateway")
if live_read.get("product_action") != "rest.proxy" or live_read.get("product_method") != "GET":
    fail("producer live-read product route must remain read-only rest.proxy GET")
if live_read.get("product_path_template") != "/wc/v3/products/<PRODUCT_ID>":
    fail("producer live-read product path template changed")
if live_read.get("seo_action") != "seo.read":
    fail("producer live-read SEO action must remain seo.read")
if live_read.get("required_freshness_field") != "result.data_date_modified_gmt":
    fail("producer freshness field must remain Bridge live date_modified_gmt")
if live_read.get("direct_wordpress_credentials_forbidden") is not True:
    fail("producer must not gain a direct WordPress credential path")
if live_read.get("separate_producer_workflow_forbidden") is not True:
    fail("producer live-read must reuse the guarded Bridge gateway")

if config.get("primary_producer") != "connected_chatgpt_queue":
    fail("config primary_producer must be connected_chatgpt_queue")

if config.get("api_fallback_manual_only") is not True:
    fail("API fallback must remain manual-only")

if int(config.get("concurrency") or 0) != 1:
    fail("product concurrency must remain 1")

if int(config.get("max_products_per_run") or 0) != 1:
    fail("max_products_per_run must remain 1")

api_trigger_block = api_wf.split("\npermissions:", 1)[0]
if "\n  schedule:" in api_trigger_block or "\n  push:" in api_trigger_block:
    fail("API fallback workflow gained an automatic trigger")

if "workflow_dispatch:" not in api_trigger_block:
    fail("API fallback workflow must retain manual workflow_dispatch")

if "product-engine/queue/*.json" not in queue_wf:
    fail("queue publisher trigger/path is missing")

if "OPENAI_API_KEY" in queue_wf:
    fail("primary queue publisher must not depend on OPENAI_API_KEY")

if "python product-engine/ai_runtime.py" in queue_wf:
    fail("primary queue publisher must not invoke ai_runtime.py")

if "automation/product-*" not in promoter_wf:
    fail("queue promoter must watch automation/product-* branches")
if "product-engine/queue/*.json" not in promoter_wf:
    fail("queue promoter must be scoped to product queue files")
if "OPENAI_API_KEY" in promoter_wf or "ai_runtime.py" in promoter_wf:
    fail("queue promoter must not use model/API generation path")
if "actions: write" not in promoter_wf:
    fail("queue promoter must have actions: write for explicit publisher dispatch")
if "k20-product-queue-publisher.yml/dispatches" not in promoter_wf:
    fail("queue promoter must explicitly dispatch product queue publisher")
if "workflow_dispatch" not in queue_wf:
    fail("queue publisher must retain workflow_dispatch for promoter handoff")

if "product-engine/recovery/*-stale-recovery.json" not in queue_wf:
    fail("queue publisher stale-recovery trigger is missing")
if "stale_recovery_evidence" not in publisher_py or "producer_timestamp_source_bug" not in publisher_py:
    fail("publisher fail-closed stale recovery support is missing")

required_prompt_markers = [
    "Connected ChatGPT",
    "product-engine/queue/*.json",
    "Never call product-engine/ai_runtime.py",
    "OPENAI_API_KEY",
]
for marker in required_prompt_markers:
    if marker not in prompt:
        fail(f"canonical producer prompt missing marker: {marker}")

for marker in ["### Freshness source rule", "expected_date_modified_gmt", "Never copy this field from `inventory.json`", "## Producer live-read route", "result.data_date_modified_gmt"]:
    if marker not in prompt:
        fail(f"canonical producer freshness rule missing marker: {marker}")

required_readme_markers = [
    "Connected ChatGPT -> product-engine/queue/*.json",
    "manual fallback only",
]
for marker in required_readme_markers:
    if marker not in readme:
        fail(f"README missing route invariant: {marker}")

print("PRODUCT_ROUTE_GUARD_OK")
