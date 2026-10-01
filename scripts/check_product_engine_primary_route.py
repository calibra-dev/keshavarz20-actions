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


def fail(message: str) -> None:
    raise SystemExit(f"PRODUCT_ROUTE_GUARD_FAILED: {message}")


lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
prompt = PROMPT_PATH.read_text(encoding="utf-8")
readme = README_PATH.read_text(encoding="utf-8")
api_wf = API_WF_PATH.read_text(encoding="utf-8")
queue_wf = QUEUE_WF_PATH.read_text(encoding="utf-8")

if lock.get("primary_producer") != "connected_chatgpt_queue":
    fail("route lock primary_producer changed")

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

required_prompt_markers = [
    "Connected ChatGPT",
    "product-engine/queue/*.json",
    "Never call product-engine/ai_runtime.py",
    "OPENAI_API_KEY",
]
for marker in required_prompt_markers:
    if marker not in prompt:
        fail(f"canonical producer prompt missing marker: {marker}")

required_readme_markers = [
    "Connected ChatGPT -> product-engine/queue/*.json",
    "manual fallback only",
]
for marker in required_readme_markers:
    if marker not in readme:
        fail(f"README missing route invariant: {marker}")

print("PRODUCT_ROUTE_GUARD_OK")
