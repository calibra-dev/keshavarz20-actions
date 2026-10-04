#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc

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


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        x = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=UTC)
    except ValueError:
        return None


def validate_prompt_bank(bank: dict[str, Any]) -> dict[str, Any]:
    records = bank.get("records") or []
    if len(records) != 200 or int(bank.get("prompt_count") or 0) != 200:
        raise Phase24Error("prompt bank must contain exactly 200 prompts")

    ids = [x.get("prompt_id") for x in records]
    if None in ids or len(ids) != len(set(ids)):
        raise Phase24Error("prompt_id values must be present and unique")

    by_platform = {p: 0 for p in PLATFORMS}
    by_bucket = {b: 0 for b in BUCKETS}
    pending = 0
    for row in records:
        platform = row.get("planned_platform_model") or row.get("surface")
        bucket = row.get("intent_bucket")
        if platform not in by_platform:
            raise Phase24Error(f"unknown platform: {platform}")
        if bucket not in by_bucket:
            raise Phase24Error(f"unknown bucket: {bucket}")
        by_platform[platform] += 1
        by_bucket[bucket] += 1

        status = str(row.get("execution_status") or "")
        if status.startswith("PENDING_"):
            pending += 1
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

    return {
        "count": 200,
        "by_platform": by_platform,
        "by_bucket": by_bucket,
        "pending_in_bank": pending,
    }


def prompt_index(bank: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {x["prompt_id"]: x for x in bank.get("records") or []}


def validate_observations(bank: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    prompts = prompt_index(bank)
    observations = registry.get("observations") or []

    obs_ids: set[str] = set()
    prompt_ids: set[str] = set()
    observed_times: list[dt.datetime] = []

    for obs in observations:
        required = (
            "observation_id", "prompt_id", "surface", "observed_at_utc",
            "evidence_type", "answer_present", "keshavarz20_cited",
            "brand_mentioned", "citation_urls", "readback_verified",
        )
        missing = [x for x in required if x not in obs]
        if missing:
            raise Phase24Error("observation missing fields: " + ", ".join(missing))

        oid = str(obs["observation_id"])
        pid = str(obs["prompt_id"])
        if oid in obs_ids:
            raise Phase24Error(f"duplicate observation_id: {oid}")
        if pid in prompt_ids:
            raise Phase24Error(f"duplicate direct observation for prompt_id: {pid}")
        obs_ids.add(oid)
        prompt_ids.add(pid)

        if pid not in prompts:
            raise Phase24Error(f"unknown prompt_id: {pid}")
        surface = obs["surface"]
        if surface not in PLATFORMS:
            raise Phase24Error(f"unknown surface: {surface}")

        planned = prompts[pid].get("planned_platform_model") or prompts[pid].get("surface")
        if surface != planned:
            raise Phase24Error(
                f"{pid}: observed surface {surface!r} does not match planned surface {planned!r}"
            )

        if obs["evidence_type"] != "DIRECT_SURFACE_CAPTURE":
            raise Phase24Error("citation KPI requires DIRECT_SURFACE_CAPTURE evidence")
        if obs["readback_verified"] is not True:
            raise Phase24Error(f"{oid}: direct capture is not readback verified")
        if not isinstance(obs["citation_urls"], list):
            raise Phase24Error("citation_urls must be a list")

        cited = bool(obs["keshavarz20_cited"])
        has_domain_url = any(
            "keshavarz20.com" in str(u).lower()
            for u in obs["citation_urls"]
        )
        if cited != has_domain_url:
            raise Phase24Error(
                f"{oid}: keshavarz20_cited must match captured citation URLs"
            )

        t = parse_time(obs["observed_at_utc"])
        if t is None:
            raise Phase24Error(f"{oid}: invalid observed_at_utc")
        observed_times.append(t)

    oldest = min(observed_times).isoformat() if observed_times else None
    newest = max(observed_times).isoformat() if observed_times else None
    return {
        "count": len(observations),
        "unique_observation_ids": len(obs_ids),
        "unique_prompt_ids": len(prompt_ids),
        "oldest_observation_utc": oldest,
        "newest_observation_utc": newest,
        "readback_verified_count": len(observations),
    }


def compute_direct_kpis(bank: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    validate_observations(bank, registry)
    observations = registry.get("observations") or []

    if not observations:
        return {
            "direct_observation_count": 0,
            "citation_rate": None,
            "brand_mention_rate": None,
            "recommendation_context_rate": None,
            "cited_page_coverage": None,
            "observed_prompt_coverage": 0.0,
            "remaining_prompt_count": 200,
            "by_surface": {
                p: {
                    "observations": 0,
                    "coverage": 0.0,
                    "citation_rate": None,
                    "brand_mention_rate": None,
                }
                for p in PLATFORMS
            },
        }

    citations = sum(bool(x["keshavarz20_cited"]) for x in observations)
    mentions = sum(bool(x["brand_mentioned"]) for x in observations)
    recommendation_context = sum(bool(x.get("recommendation_context")) for x in observations)
    cited_urls = {
        str(u)
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
            "coverage": len(rows) / 50,
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
        "recommendation_context_rate": recommendation_context / len(observations),
        "cited_page_coverage": len(cited_urls),
        "observed_prompt_coverage": len(observed_prompts) / 200,
        "remaining_prompt_count": 200 - len(observed_prompts),
        "by_surface": by_surface,
    }


def dependency_snapshot() -> dict[str, Any]:
    p20 = load(ROOT / "phase20-results" / "final-closure-latest.json")
    p21 = load(ROOT / "phase21-results" / "authority-network-latest.json")
    p22 = load(ROOT / "phase22-results" / "acceptance-latest.json")
    p23 = load(ROOT / "phase23-results" / "acceptance-latest.json")
    return {
        "phase20": {
            "status": p20.get("status"),
            "passed_checks": int(p20.get("passed_checks") or 0),
            "check_count": int(p20.get("check_count") or 0),
            "failed_checks": p20.get("failed_checks") or [],
        },
        "phase21": {
            "version": p21.get("version"),
            "status": p21.get("status"),
            "passed_checks": int((p21.get("acceptance") or {}).get("passed_checks") or 0),
            "check_count": int((p21.get("acceptance") or {}).get("check_count") or 0),
            "failed_checks": (p21.get("acceptance") or {}).get("failed_checks") or [],
        },
        "phase22": {
            "version": p22.get("version"),
            "status": p22.get("status"),
            "passed_checks": int(p22.get("passed_checks") or 0),
            "check_count": int(p22.get("check_count") or 0),
            "failed_checks": p22.get("failed_checks") or [],
        },
        "phase23": {
            "version": p23.get("version"),
            "status": p23.get("status"),
            "passed_checks": int(p23.get("passed_checks") or 0),
            "check_count": int(p23.get("check_count") or 0),
            "failed_checks": p23.get("failed_checks") or [],
        },
    }


def dependencies_current(deps: dict[str, Any]) -> bool:
    return (
        str(deps["phase20"]["status"] or "").startswith("PASS")
        and deps["phase20"]["passed_checks"] == deps["phase20"]["check_count"]
        and not deps["phase20"]["failed_checks"]
        and deps["phase21"]["version"] == "phase21-iran-authority-network-v3"
        and deps["phase21"]["status"] == "PASS_IRAN_FIRST_AUTHORITY_V3_GUARDED"
        and deps["phase21"]["passed_checks"] == deps["phase21"]["check_count"]
        and not deps["phase21"]["failed_checks"]
        and deps["phase22"]["version"] == "phase22-farmer-decision-v3"
        and deps["phase22"]["status"] == "PASS_PHASE22_FARMER_DECISION_V3_GUARDED"
        and deps["phase22"]["passed_checks"] == deps["phase22"]["check_count"]
        and not deps["phase22"]["failed_checks"]
        and deps["phase23"]["version"] == "phase23-lifecycle-freshness-v3"
        and deps["phase23"]["status"] == "PASS_PHASE23_LIFECYCLE_FRESHNESS_V3_GUARDED"
        and deps["phase23"]["passed_checks"] == deps["phase23"]["check_count"]
        and not deps["phase23"]["failed_checks"]
    )


def remaining_queue(bank: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    observed = {x["prompt_id"] for x in registry.get("observations") or []}
    rows = []
    by_surface = {p: 0 for p in PLATFORMS}
    by_bucket = {b: 0 for b in BUCKETS}
    for row in bank.get("records") or []:
        if row["prompt_id"] in observed:
            continue
        surface = row.get("planned_platform_model") or row.get("surface")
        bucket = row["intent_bucket"]
        rec = {
            "prompt_id": row["prompt_id"],
            "surface": surface,
            "intent_bucket": bucket,
            "prompt": row["prompt"],
            "required_evidence_type": "DIRECT_SURFACE_CAPTURE",
            "status": "PENDING_EXTERNAL_SURFACE_CAPTURE",
        }
        rows.append(rec)
        by_surface[surface] += 1
        by_bucket[bucket] += 1
    return {
        "remaining_count": len(rows),
        "by_surface": by_surface,
        "by_bucket": by_bucket,
        "queue": rows,
    }


def build_report(now: dt.datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or dt.datetime.now(UTC)
    bank = load(ROOT / "phase24" / "prompt-bank-200-fa.json")
    registry = load(ROOT / "phase24" / "direct-observations-v3.json")
    telemetry = load(ROOT / "phase24-results" / "telemetry-2026-09-27.json")

    bank_check = validate_prompt_bank(bank)
    observation_check = validate_observations(bank, registry)
    kpis = compute_direct_kpis(bank, registry)
    deps = dependency_snapshot()
    dep_ok = dependencies_current(deps)
    queue = remaining_queue(bank, registry)

    telemetry_time = parse_time(telemetry.get("generated_at_utc"))
    telemetry_age_days = None
    if telemetry_time is not None:
        telemetry_age_days = max(0, (now - telemetry_time.astimezone(UTC)).days)

    checks = {
        "dependency_stack_20_23_current": dep_ok,
        "prompt_bank_exact_200": bank_check["count"] == 200,
        "platform_distribution_50_each": set(bank_check["by_platform"].values()) == {50},
        "intent_bucket_distribution_20_each": set(bank_check["by_bucket"].values()) == {20},
        "direct_observations_valid": observation_check["count"] == kpis["direct_observation_count"],
        "direct_observation_ids_unique": observation_check["unique_observation_ids"] == observation_check["count"],
        "direct_prompt_ids_unique": observation_check["unique_prompt_ids"] == observation_check["count"],
        "all_direct_captures_readback_verified": observation_check["readback_verified_count"] == observation_check["count"],
        "citation_requires_direct_surface_capture": True,
        "referral_not_counted_as_citation": True,
        "web_search_proxy_not_counted_as_ai_citation": True,
        "null_unobserved_not_zero": all(
            row["observations"] > 0 or (row["citation_rate"] is None and row["brand_mention_rate"] is None)
            for row in kpis["by_surface"].values()
        ),
        "remaining_queue_math": queue["remaining_count"] + observation_check["count"] == 200,
        "no_fabricated_completion": (
            kpis["direct_observation_count"] < 200
            and queue["remaining_count"] > 0
        ) or (
            kpis["direct_observation_count"] == 200
            and queue["remaining_count"] == 0
        ),
    }
    failed = [k for k, v in checks.items() if not v]

    full_measurement_complete = (
        not failed
        and kpis["direct_observation_count"] == 200
        and queue["remaining_count"] == 0
        and all(x["observations"] == 50 for x in kpis["by_surface"].values())
    )

    status = (
        "PASS_PHASE24_DIRECT_SURFACE_MEASUREMENT_V3"
        if full_measurement_complete
        else "PASS_PHASE24_CONTROL_PLANE_V3_GUARDED_EXTERNAL_CAPTURE_BACKLOG"
        if not failed
        else "FAIL_PHASE24_MEASUREMENT_V3"
    )

    report = {
        "phase": 24,
        "title": "AI Citation Experimentation & Influence Measurement",
        "version": "phase24-ai-citation-measurement-v3",
        "generated_at_utc": now.isoformat(),
        "status": status,
        "control_plane_complete": not failed,
        "full_direct_surface_measurement_complete": full_measurement_complete,
        "check_count": len(checks),
        "passed_checks": len(checks) - len(failed),
        "failed_checks": failed,
        "checks": checks,
        "dependencies": deps,
        "prompt_bank": bank_check,
        "observation_integrity": observation_check,
        "direct_surface_kpis": kpis,
        "remaining_external_capture": {
            "remaining_count": queue["remaining_count"],
            "by_surface": queue["by_surface"],
            "blocker": (
                None
                if queue["remaining_count"] == 0
                else "Direct capture on the remaining AI answer surfaces is required. Ordinary web search, referral telemetry, or inferred citations are not acceptable substitutes."
            ),
        },
        "telemetry": {
            "source_file": "phase24-results/telemetry-2026-09-27.json",
            "generated_at_utc": telemetry.get("generated_at_utc"),
            "age_days_at_run": telemetry_age_days,
            "historical_baseline_only": True,
            "data": telemetry,
        },
        "measurement_rules": {
            "referral_is_not_citation": True,
            "web_search_proxy_is_not_ai_surface_citation": True,
            "null_means_unobserved_not_zero": True,
            "citation_requires_direct_surface_capture": True,
            "brand_mention_requires_direct_surface_capture": True,
            "recommendation_is_not_inferred_from_citation": True,
            "historical_direct_capture_is_not_relabelled_as_current": True,
            "full_phase_measurement_requires_200_of_200_direct_captures": True,
        },
    }
    return report, queue


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output")
    p.add_argument("--queue-output")
    args = p.parse_args()

    report, queue = build_report()
    if report["failed_checks"]:
        raise Phase24Error("failed checks: " + ", ".join(report["failed_checks"]))

    if args.output:
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.queue_output:
        Path(args.queue_output).write_text(
            json.dumps(
                {
                    "phase": 24,
                    "version": "phase24-remaining-direct-surface-queue-v3",
                    "generated_at_utc": report["generated_at_utc"],
                    "source_prompt_bank_count": 200,
                    "validated_observed_count": report["direct_surface_kpis"]["direct_observation_count"],
                    **queue,
                    "rules": report["measurement_rules"],
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "status": report["status"],
        "checks": f"{report['passed_checks']}/{report['check_count']}",
        "direct_observations": report["direct_surface_kpis"]["direct_observation_count"],
        "remaining": report["remaining_external_capture"]["remaining_count"],
        "citation_rate": report["direct_surface_kpis"]["citation_rate"],
        "brand_mention_rate": report["direct_surface_kpis"]["brand_mention_rate"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
