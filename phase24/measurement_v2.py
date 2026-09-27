#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = (
    "ChatGPT Search",
    "Google AI Mode / AI Overviews",
    "Microsoft Copilot / Bing",
    "Perplexity",
)
BUCKETS = (
    "definitions_education",
    "product_selection",
    "comparison",
    "compatibility",
    "calculation_sizing",
    "troubleshooting",
    "buying_price_shipping",
    "crop_area_water",
    "brand_store_trust",
    "full_system_basket",
)


class Phase24Error(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_prompt_bank(bank: dict[str, Any]) -> dict[str, Any]:
    records = bank.get("records") or []
    if len(records) != 200 or int(bank.get("prompt_count") or 0) != 200:
        raise Phase24Error("prompt bank must contain exactly 200 prompts")

    ids = [x.get("prompt_id") for x in records]
    if len(ids) != len(set(ids)):
        raise Phase24Error("prompt_id values must be unique")

    by_platform = {p: 0 for p in PLATFORMS}
    by_bucket = {b: 0 for b in BUCKETS}
    for row in records:
        platform = row.get("planned_platform_model")
        bucket = row.get("intent_bucket")
        if platform not in by_platform:
            raise Phase24Error(f"unknown platform: {platform}")
        if bucket not in by_bucket:
            raise Phase24Error(f"unknown bucket: {bucket}")
        by_platform[platform] += 1
        by_bucket[bucket] += 1

        status = row.get("execution_status")
        if status == "PENDING_EXTERNAL_MEASUREMENT":
            result_fields = (
                "answer_present", "keshavarz20_cited", "cited_url",
                "brand_mentioned", "recommendation_context",
                "claim_or_data_reused", "link_click_potential",
                "landing_conversion",
            )
            if any(row.get(k) is not None for k in result_fields):
                raise Phase24Error(
                    f"{row.get('prompt_id')}: pending record contains fabricated result data"
                )

    if set(by_platform.values()) != {50}:
        raise Phase24Error(f"platform distribution must be 50 each: {by_platform}")
    if set(by_bucket.values()) != {20}:
        raise Phase24Error(f"bucket distribution must be 20 each: {by_bucket}")

    return {"count": 200, "by_platform": by_platform, "by_bucket": by_bucket}


def validate_observation(obs: dict[str, Any], prompt_ids: set[str]) -> None:
    required = (
        "observation_id", "prompt_id", "surface", "observed_at_utc",
        "evidence_type", "answer_present", "keshavarz20_cited",
        "brand_mentioned", "citation_urls",
    )
    missing = [x for x in required if x not in obs]
    if missing:
        raise Phase24Error("observation missing fields: " + ", ".join(missing))
    if obs["prompt_id"] not in prompt_ids:
        raise Phase24Error(f"unknown prompt_id: {obs['prompt_id']}")
    if obs["surface"] not in PLATFORMS:
        raise Phase24Error(f"unknown surface: {obs['surface']}")
    if obs["evidence_type"] != "DIRECT_SURFACE_CAPTURE":
        raise Phase24Error("citation KPI requires DIRECT_SURFACE_CAPTURE evidence")
    if not isinstance(obs["citation_urls"], list):
        raise Phase24Error("citation_urls must be a list")
    cited = bool(obs["keshavarz20_cited"])
    has_k20_url = any("keshavarz20.com" in str(u).lower() for u in obs["citation_urls"])
    if cited != has_k20_url:
        raise Phase24Error("keshavarz20_cited must match captured citation URLs")


def compute_direct_kpis(bank: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    prompt_ids = {x["prompt_id"] for x in bank["records"]}
    observations = registry.get("observations") or []
    for obs in observations:
        validate_observation(obs, prompt_ids)

    if not observations:
        return {
            "direct_observation_count": 0,
            "citation_rate": None,
            "brand_mention_rate": None,
            "cited_page_coverage": None,
            "observed_prompt_coverage": 0.0,
            "by_surface": {
                p: {"observations": 0, "citation_rate": None, "brand_mention_rate": None}
                for p in PLATFORMS
            },
        }

    citations = sum(bool(x["keshavarz20_cited"]) for x in observations)
    mentions = sum(bool(x["brand_mentioned"]) for x in observations)
    cited_urls = {
        u
        for x in observations
        for u in x.get("citation_urls", [])
        if "keshavarz20.com" in str(u).lower()
    }
    observed_prompts = {x["prompt_id"] for x in observations}

    by_surface = {}
    for p in PLATFORMS:
        rows = [x for x in observations if x["surface"] == p]
        by_surface[p] = {
            "observations": len(rows),
            "citation_rate": (
                sum(bool(x["keshavarz20_cited"]) for x in rows) / len(rows)
                if rows else None
            ),
            "brand_mention_rate": (
                sum(bool(x["brand_mentioned"]) for x in rows) / len(rows)
                if rows else None
            ),
        }

    return {
        "direct_observation_count": len(observations),
        "citation_rate": citations / len(observations),
        "brand_mention_rate": mentions / len(observations),
        "cited_page_coverage": len(cited_urls),
        "observed_prompt_coverage": len(observed_prompts) / 200,
        "by_surface": by_surface,
    }


def dependency_snapshot() -> dict[str, Any]:
    p20 = load(ROOT / "growth-os" / "phase20-acceptance-2026-09-27.json")
    p21 = load(ROOT / "phase21-results" / "authority-network-2026-09-27.json")
    p22 = load(ROOT / "phase22-results" / "acceptance-v2-2026-09-27.json")
    p23 = load(ROOT / "phase23-results" / "lifecycle-freshness-v2-latest.json")
    return {
        "phase20": p20.get("status"),
        "phase21": p21.get("status"),
        "phase22": p22.get("status"),
        "phase23": p23.get("status"),
    }


def build_report() -> dict[str, Any]:
    bank = load(ROOT / "phase24" / "prompt-bank-200-fa.json")
    registry = load(ROOT / "phase24" / "direct-observations-v2.json")
    telemetry = load(ROOT / "phase24-results" / "telemetry-2026-09-27.json")

    bank_check = validate_prompt_bank(bank)
    kpis = compute_direct_kpis(bank, registry)
    deps = dependency_snapshot()

    dep_ok = (
        deps["phase20"] == "PASS_CANARY_DRAFT"
        and deps["phase21"] == "PASS_IRAN_FIRST_AUTHORITY_V2"
        and deps["phase22"] == "PASS_FUNCTIONAL_V2_GUARDED_DEPLOYMENT"
        and deps["phase23"] == "PASS_LIFECYCLE_GOVERNANCE_V2"
    )

    return {
        "phase": 24,
        "title": "AI Citation Experimentation & Influence Measurement v2",
        "status": (
            "PASS_DIRECT_SURFACE_MEASUREMENT"
            if dep_ok and kpis["direct_observation_count"] == 200
            else "CONTROL_PLANE_COMPLETE_EXTERNAL_SURFACE_PENDING"
        ),
        "dependencies_current": dep_ok,
        "dependencies": deps,
        "prompt_bank": bank_check,
        "direct_surface_kpis": kpis,
        "telemetry": telemetry,
        "measurement_rules": {
            "referral_is_not_citation": True,
            "web_search_proxy_is_not_ai_surface_citation": True,
            "null_means_unobserved_not_zero": True,
            "citation_requires_direct_surface_capture": True,
            "brand_mention_requires_direct_surface_capture": True,
            "recommendation_is_not_inferred_from_citation": True,
        },
    }


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output")
    args = p.parse_args()
    report = build_report()
    if not report["dependencies_current"]:
        raise Phase24Error("Phase 20-23 dependency stack is not current")
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "status": report["status"],
        "prompt_count": report["prompt_bank"]["count"],
        "direct_observations": report["direct_surface_kpis"]["direct_observation_count"],
        "citation_rate": report["direct_surface_kpis"]["citation_rate"],
        "chatgpt_referral_sessions_30d": report["telemetry"]["ga4"]["chatgpt_referral"]["sessions"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
