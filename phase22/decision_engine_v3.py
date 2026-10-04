#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CORE_REQUIRED = ("crop", "area_ha", "water_source", "region")
HYDRAULIC_REQUIRED = ("pressure_bar", "available_flow_m3h")
SURFACE_WATER = {"river", "canal", "surface", "رودخانه", "کانال", "آب سطحی"}
DIRTY_WATER_TOKENS = ("sediment", "turbid", "suspended", "sand", "شن", "گل", "رسوب", "کدر")
SALINITY_TOKENS = ("saline", "salinity", "ec", "شور", "شوری")
PII_KEYS = {"name", "phone", "mobile", "email", "address", "customer_id", "user_id"}
TOOL_URLS = {
    "hydraulic": "https://keshavarz20.com/polyethylene-pipe-size-flow-pressure-guide/",
    "filtration": "https://keshavarz20.com/irrigation-filter-selector/",
    "compatibility": "https://keshavarz20.com/irrigation-fittings-compatibility-selector/",
}
INTENT_ROUTES = {
    "water_quality": "ir-intent-water-quality-lab-reading",
    "fertigation": "ir-intent-fertigation-injection",
    "pressure": "ir-intent-pressure-regulator-selection",
    "dirty_water": "ir-intent-well-sand-drip-filtration",
}


class Phase22Error(RuntimeError):
    pass


def _present(v: Any) -> bool:
    return v is not None and (not isinstance(v, str) or bool(v.strip()))


def _num(v: Any) -> float | None:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _normalize(v: Any) -> str:
    return " ".join(str(v or "").strip().lower().split())


def context_id(case: dict[str, Any]) -> str:
    public_keys = (
        "crop", "area_ha", "water_source", "water_quality", "pressure_bar",
        "available_flow_m3h", "soil_texture", "region", "irrigation_system",
        "uneven_terrain", "fertigation", "mainline_length_m"
    )
    public = {k: case.get(k) for k in public_keys}
    compat = case.get("verified_compatibility_fields") or {}
    public["compatibility"] = {
        "nominal_size": compat.get("nominal_size"),
        "connection_type": compat.get("connection_type"),
        "evidence_status": compat.get("evidence_status"),
    }
    raw = json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "farmctx-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_intents() -> dict[str, dict[str, Any]]:
    data = json.loads((ROOT / "growth-os" / "intent-registry.json").read_text(encoding="utf-8"))
    return {x["canonical_intent_id"]: x for x in data.get("intents", [])}


def load_authority() -> dict[str, Any]:
    p = ROOT / "phase21-results" / "authority-network-latest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _route(intents: dict[str, dict[str, Any]], iid: str | None) -> dict[str, Any] | None:
    if not iid or iid not in intents:
        return None
    x = intents[iid]
    url = x.get("canonical_url") or None
    status = str(x.get("status") or "")
    return {
        "canonical_intent_id": iid,
        "status": status,
        "canonical_url": url,
        "wordpress_post_id": x.get("wordpress_post_id") or None,
        "publicly_routable": bool(url and status not in {"draft", "draft-covered", "retired", "rejected"}),
    }


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    intents = load_intents()
    authority = load_authority()

    missing_core = [x for x in CORE_REQUIRED if not _present(case.get(x))]
    invalid = []
    area = _num(case.get("area_ha"))
    pressure = _num(case.get("pressure_bar"))
    flow = _num(case.get("available_flow_m3h"))
    if _present(case.get("area_ha")) and (area is None or area <= 0):
        invalid.append("area_ha")
    if _present(case.get("pressure_bar")) and (pressure is None or pressure <= 0):
        invalid.append("pressure_bar")
    if _present(case.get("available_flow_m3h")) and (flow is None or flow <= 0):
        invalid.append("available_flow_m3h")

    core_blocked = bool(missing_core or invalid)
    hydraulic_missing = [x for x in HYDRAULIC_REQUIRED if not _present(case.get(x))]

    water_source = _normalize(case.get("water_source"))
    water_quality = _normalize(case.get("water_quality"))
    fertigation = bool(case.get("fertigation"))
    uneven = bool(case.get("uneven_terrain"))

    dirty_water = water_source in SURFACE_WATER or any(t in water_quality for t in DIRTY_WATER_TOKENS)
    salinity_risk = any(t in water_quality for t in SALINITY_TOKENS)

    tracks: dict[str, dict[str, Any]] = {}

    tracks["hydraulic"] = {
        "state": "BLOCKED_MISSING_MEASUREMENT" if core_blocked or hydraulic_missing else "READY_FOR_DECISION_TOOL",
        "missing_inputs": sorted(set(missing_core + invalid + hydraulic_missing)),
        "tool_url": TOOL_URLS["hydraulic"],
        "intent_id": INTENT_ROUTES["pressure"],
        "specific_product_allowed": False,
    }

    filtration_missing = not _present(case.get("water_quality"))
    tracks["filtration"] = {
        "state": "NEEDS_WATER_QUALITY" if filtration_missing else ("EXPERT_REVIEW" if dirty_water else "READY_FOR_SELECTOR"),
        "missing_inputs": ["water_quality"] if filtration_missing else [],
        "tool_url": TOOL_URLS["filtration"],
        "intent_id": INTENT_ROUTES["dirty_water"] if dirty_water else (INTENT_ROUTES["water_quality"] if salinity_risk else None),
        "specific_product_allowed": False,
    }

    compat = case.get("verified_compatibility_fields") or {}
    compat_values_present = all(_present(compat.get(k)) for k in ("nominal_size", "connection_type"))
    compat_evidence_verified = _normalize(compat.get("evidence_status")) == "verified"
    compat_ready = compat_values_present and compat_evidence_verified
    compat_missing = [k for k in ("nominal_size", "connection_type") if not _present(compat.get(k))]
    if not compat_evidence_verified:
        compat_missing.append("verified_evidence")
    tracks["compatibility"] = {
        "state": "READY_FOR_SELECTOR" if compat_ready else "BLOCKED_UNVERIFIED_COMPATIBILITY",
        "missing_inputs": sorted(set(compat_missing)),
        "tool_url": TOOL_URLS["compatibility"],
        "intent_id": None,
        "specific_product_allowed": False,
        "evidence_verified": compat_evidence_verified,
    }

    agronomy_reasons = []
    if not _present(case.get("soil_texture")):
        agronomy_reasons.append("soil_texture")
    if salinity_risk:
        agronomy_reasons.append("water_salinity_requires_lab_context")
    if fertigation:
        agronomy_reasons.append("fertigation_requires_context")
    tracks["agronomy"] = {
        "state": "EXPERT_REVIEW" if agronomy_reasons else "ADVISORY_ONLY",
        "missing_inputs": ["soil_texture"] if "soil_texture" in agronomy_reasons else [],
        "intent_id": INTENT_ROUTES["fertigation"] if fertigation else (INTENT_ROUTES["water_quality"] if salinity_risk else None),
        "specific_product_allowed": False,
    }

    risk_flags = []
    if dirty_water:
        risk_flags.append("clogging_risk")
    if salinity_risk:
        risk_flags.append("salinity_risk")
    if uneven:
        risk_flags.append("terrain_pressure_variation")
    if fertigation:
        risk_flags.append("fertigation")
    if hydraulic_missing:
        risk_flags.append("hydraulic_measurements_missing")
    if not compat_ready:
        risk_flags.append("compatibility_unverified")

    escalation = core_blocked or dirty_water or salinity_risk or uneven or fertigation
    if core_blocked:
        overall = "NEEDS_MORE_INPUT"
    elif any(t["state"].startswith("BLOCKED") or t["state"].startswith("NEEDS_") for t in tracks.values()):
        overall = "PARTIAL_DECISION_SUPPORT"
    elif escalation:
        overall = "ADVISORY_WITH_EXPERT_REVIEW"
    else:
        overall = "ADVISORY_READY"

    routed = []
    seen = set()
    for track in tracks.values():
        rr = _route(intents, track.get("intent_id"))
        if rr and rr["canonical_intent_id"] not in seen:
            routed.append(rr)
            seen.add(rr["canonical_intent_id"])

    acc = authority.get("acceptance") or {}
    ptruth = authority.get("product_truth") or {}
    idtruth = authority.get("identifier_truth") or {}
    btruth = authority.get("brand_truth") or {}

    return {
        "decision_model_version": "farmer-decision-v3",
        "context_id": context_id(case),
        "state": overall,
        "confidence": "low" if core_blocked else ("medium" if escalation or any(t["state"].startswith("BLOCKED") or t["state"].startswith("NEEDS_") for t in tracks.values()) else "medium_high"),
        "input_quality": {
            "missing_core": missing_core,
            "invalid": sorted(set(invalid)),
            "hydraulic_missing": hydraulic_missing,
            "unknowns_preserved": True,
        },
        "risk_flags": sorted(set(risk_flags)),
        "decision_tracks": tracks,
        "intent_routes": routed,
        "authority_basis": {
            "phase21_version": authority.get("version"),
            "phase21_status": authority.get("status"),
            "phase21_checks_passed": int(acc.get("passed_checks") or 0),
            "phase21_checks_total": int(acc.get("check_count") or 0),
            "phase21_failed_checks": acc.get("failed_checks") or [],
            "hard_fabrications": int(ptruth.get("hard_fabrications") or 0),
            "gtins_fabricated": int(idtruth.get("gtins_fabricated") or 0),
            "skus_promoted_to_gtin": int(idtruth.get("skus_promoted_to_gtin") or 0),
            "brand_guard_policy": btruth.get("policy"),
        },
        "scope": {
            "specific_product_recommendation": False,
            "sku_recommendation": False,
            "certified_hydraulic_design": False,
            "agronomic_prescription": False,
            "price_or_stock_decision": False,
            "merchant_or_checkout_action": False,
        },
        "expert_escalation": bool(escalation),
        "privacy": {
            "stores_identity": False,
            "stores_contact_data": False,
            "context_id_is_non_identity_hash": True,
            "ignored_identity_keys": sorted(k for k in case if k in PII_KEYS),
        },
        "guardrails": [
            "Unknown technical values remain unknown.",
            "Candidate-only compatibility is never promoted to verified.",
            "Pseudo-brand, unbranded and multi-brand gaps are never converted into an exact product recommendation.",
            "No SKU or exact product is selected without verified compatibility and a separate commerce decision layer.",
            "The output is decision support, not certified hydraulic or agronomic design.",
            "No price, stock, checkout action, customer identity or private support data is used.",
        ],
    }


def validate(result: dict[str, Any]) -> None:
    a = result["authority_basis"]
    if a["phase21_version"] != "phase21-iran-authority-network-v3":
        raise Phase22Error("Phase 21 current authority v3 dependency missing")
    if a["phase21_status"] != "PASS_IRAN_FIRST_AUTHORITY_V3_GUARDED":
        raise Phase22Error("Phase 21 authority dependency is not passed")
    if a["phase21_checks_total"] <= 0 or a["phase21_checks_passed"] != a["phase21_checks_total"] or a["phase21_failed_checks"]:
        raise Phase22Error("Phase 21 acceptance is incomplete")
    if a["hard_fabrications"] != 0 or a["gtins_fabricated"] != 0 or a["skus_promoted_to_gtin"] != 0:
        raise Phase22Error("upstream truth layer reports fabrication")
    if any(result["scope"].values()):
        raise Phase22Error("Phase 22 scope escaped advisory-only mode")
    if not result["privacy"]["context_id_is_non_identity_hash"] or result["privacy"]["stores_identity"] or result["privacy"]["stores_contact_data"]:
        raise Phase22Error("unsafe personalization identifier")
    for track in result["decision_tracks"].values():
        if track.get("specific_product_allowed"):
            raise Phase22Error("track enabled unsupported product selection")
    for route in result["intent_routes"]:
        if route["status"] == "draft-covered" and route["publicly_routable"]:
            raise Phase22Error("draft intent exposed as public route")


def run_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        out = evaluate(case)
        validate(out)
        results.append({"case_id": case.get("case_id"), "result": out})
    checks = {
        "all_cases_validated": len(results) == len(cases) and len(results) >= 16,
        "all_cases_guarded": all(x["result"].get("guardrails") for x in results),
        "all_cases_use_phase21_v3": all(x["result"]["authority_basis"]["phase21_version"] == "phase21-iran-authority-network-v3" for x in results),
        "no_specific_product_or_sku": all(not x["result"]["scope"]["specific_product_recommendation"] and not x["result"]["scope"]["sku_recommendation"] for x in results),
        "no_price_stock_checkout_action": all(not x["result"]["scope"]["price_or_stock_decision"] and not x["result"]["scope"]["merchant_or_checkout_action"] for x in results),
        "no_certified_design_claim": all(not x["result"]["scope"]["certified_hydraulic_design"] and not x["result"]["scope"]["agronomic_prescription"] for x in results),
        "unknowns_preserved": all(x["result"]["input_quality"]["unknowns_preserved"] for x in results),
        "privacy_identity_not_stored": all(not x["result"]["privacy"]["stores_identity"] and not x["result"]["privacy"]["stores_contact_data"] for x in results),
    }
    return {
        "phase": 22,
        "title": "Farmer Decision Personalization",
        "model_version": "farmer-decision-v3",
        "status": "PASS_MODEL_VALIDATION_V3" if all(checks.values()) else "FAIL_MODEL_VALIDATION_V3",
        "case_count": len(results),
        "checks": checks,
        "results": results,
        "site_mutations": 0,
        "commerce_mutations": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cases", required=True)
    p.add_argument("--output")
    args = p.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise SystemExit("cases must be a JSON array")
    report = run_cases(cases)
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "case_count": report["case_count"], "checks": report["checks"]}, ensure_ascii=False))
    if report["status"] != "PASS_MODEL_VALIDATION_V3":
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
