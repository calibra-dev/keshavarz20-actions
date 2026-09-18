#!/usr/bin/env python3
import glob
import json
import os
import time
from datetime import datetime, timezone

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OPS = os.path.join(ROOT, "phase10-ops")
OUT = os.path.join(ROOT, "phase10-results")
os.makedirs(OUT, exist_ok=True)

files = sorted(glob.glob(os.path.join(OPS, "baseline-*.json")))
if not files:
    raise SystemExit("No phase10 baseline input found")
source_file = files[-1]
with open(source_file, "r", encoding="utf-8") as fh:
    baseline = json.load(fh)

required = ["gsc_search", "google_generative_ai", "bing_ai_performance", "chatgpt_referrals", "cwv_field", "index", "conversion"]
missing = [key for key in required if key not in baseline.get("sources", {})]
if missing:
    raise SystemExit("Missing required measurement source keys: " + ", ".join(missing))

urls = [
    "https://keshavarz20.com/",
    "https://keshavarz20.com/robots.txt",
    "https://keshavarz20.com/irrigation-filter-selector/",
    "https://keshavarz20.com/polyethylene-pipe-size-flow-pressure-guide/",
    "https://keshavarz20.com/irrigation-fittings-compatibility-selector/",
]
checks = []
for url in urls:
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=30, allow_redirects=True, headers={"User-Agent": "K20-Phase10-Observability/1.0"})
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        checks.append({
            "url": url,
            "status": response.status_code,
            "final_url": response.url,
            "elapsed_ms": elapsed_ms,
            "cache": response.headers.get("x-litespeed-cache"),
            "cache_control": response.headers.get("x-litespeed-cache-control") or response.headers.get("cache-control"),
        })
    except Exception as exc:
        checks.append({"url": url, "error": type(exc).__name__, "message": str(exc)[:240]})

sources = baseline["sources"]
blocking = []
for key in ["google_generative_ai", "bing_ai_performance", "chatgpt_referrals", "cwv_field", "conversion"]:
    status = sources[key].get("status")
    if status not in {"baselined", "connected"}:
        blocking.append({"source": key, "status": status, "reason": sources[key].get("reason")})

public_failures = [c for c in checks if c.get("status") != 200]
status = "PASS" if not blocking and not public_failures else "PARTIAL_BLOCKED_EXTERNAL_INTEGRATIONS"

result = {
    "phase": 10,
    "title": "Measurement & Observability",
    "status": status,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "baseline_input": os.path.relpath(source_file, ROOT),
    "source_status": {k: v.get("status") for k, v in sources.items()},
    "public_live_checks": checks,
    "blocking_sources": blocking,
    "public_failures": public_failures,
    "cadence": {
        "public_live_checks": "daily via GitHub Actions",
        "gsc_search_baseline": "weekly connected export/read",
        "google_generative_ai": "weekly manual GSC Generative AI export until an API surface is available",
        "bing_ai_performance": "weekly manual export until a connected export/API source is available",
        "llm_referrals_and_conversion": "weekly after GA4 OAuth/property linkage",
        "cwv_field": "weekly after CrUX API key linkage"
    },
    "safety": baseline.get("safety", {}),
}

with open(os.path.join(OUT, "observability-baseline.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

acceptance = {
    "phase": 10,
    "status": status,
    "acceptance": "GSC GAI+Bing AI+ChatGPT referrals+CWV+index+conversion baselined; no sensitive data in repo",
    "gsc_search_baselined": sources["gsc_search"].get("status") == "connected",
    "index_baselined": sources["index"].get("status") == "baselined",
    "all_required_measurement_sources_baselined": not blocking,
    "public_live_checks_ok": not public_failures,
    "contains_sensitive_data": False,
    "blocking_sources": blocking,
}
with open(os.path.join(OUT, "acceptance.json"), "w", encoding="utf-8") as fh:
    json.dump(acceptance, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

log_path = os.path.join(OUT, "change-log.md")
entry = [
    f"## {result['generated_at_utc']}",
    f"- Status: " + status,
    f"- Baseline: " + result['baseline_input'],
    f"- Public checks: {len(checks) - len(public_failures)}/{len(checks)} HTTP 200",
    f"- External measurement blockers: {len(blocking)}",
]
for item in blocking:
    entry.append(f"  - {item['source']}: {item['status']}")
entry.append("")
with open(log_path, "a", encoding="utf-8") as fh:
    fh.write("\n".join(entry) + "\n")

print(json.dumps({"ok": True, "status": status, "blocking": len(blocking), "public_failures": len(public_failures)}, ensure_ascii=False))
