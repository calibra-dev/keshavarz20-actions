#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CORE_REQUIRED = ("crop", "area_ha", "water_source", "region")
HYDRAULIC_REQUIRED = ("pressure_bar", "available_flow_m3h")
VALID_SOILS = {"sandy", "loam", "clay", "شنی", "لومی", "رسی"}
SURFACE_WATER = {"river", "canal", "surface", "رودخانه", "کانال", "آب سطحی"}
DIRTY_WATER_TOKENS = ("sediment", "turbid", "suspended", "شن", "گل", "رسوب", "کدر")
SALINITY_TOKENS = ("saline", "salinity", "ec", "شور", "شوری")
INTENT_ROUTES = {
    "water_quality": "ir-intent-water-quality-lab-reading",
    "fertigation": "ir-intent-fertigation-injection",
    "pressure": "ir-intent-pressure-regulator-selection",
    "pump": "ir-intent-irrigation-pump-selection",
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
    public = {
        k: case.get(k)
        for k in (
            "crop", "area_ha", "water_source", "water_quality", "pressure_bar",
            "available_flow_m3h", "soil_texture", "region", "irrigation_system",
            "uneven_terrain", "fertigation"
        )
    }
    raw = json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "farmctx-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_intents() -> dict[str, dict[str, Any]]:
    p = ROOT / "growth-os" / "intent-registry.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return {x["canonical_intent_id"]: x for x in data.get("intents", [])}


def load_authority() -> dict[str, Any]:
    p = ROOT / "phase21-results" / "authority-network-2026-09-27.json"
    return json.loads(p.read_text(encoding="utf-8"))


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    intents = load_intents()
    authority = load_authority()

    missing_core = [x for x in CORE_REQUIRED if not _present(case.get(x))]
    invalid = []
    area = _num(case.get("area_ha"))
    pressure = _num(case.get("pressure_bar"))
    flow = _num(case.get("available_flow_m3h"))
    if area is not None and area <= 0:
        invalid.append("area_ha")
    if pressure is not None and pressure <= 0:
        invalid.append("pressure_bar")
    if flow is not None and flow <= 0:
        invalid.append("available_flow_m3h")

    hydraulic_missing = [x for x in HYDRAULIC_REQUIRED if not _present(case.get(x))]
    core_blocked = bool(missing_core or invalid)
    water_source = _normalize(case.get("water_source"))
    water_quality = _normalize(case.get("water_quality"))
    soil = _normalize(case.get("soil_texture"))
    fertigation = bool(case.get("fertigation"))
    uneven = bool(case.get("uneven_terrain"))

    dirty_water = water_source in SURFACE_WATER or any(t in water_quality for t in DIRTY_WATER_TOKENS)
    salinity_risk = any(t in water_quality for t in SALINITY_TOKENS)

    tracks: dict[str, dict[str, Any]] = {}

    tracks["hydraulic"] = {
        "state": "BLOCKED_MISSING_MEASUREMENT" if core_blocked or hydraulic_missing else "READY_FOR_DECISION_TOOL",
        "missing_inputs": sorted(set(missing_core + invalid + hydraulic_missing)),
        "tool_url": "https://keshavarz20.com/polyethylene-pipe-size-flow-pressure-guide/",
        "intent_id": INTENT_ROUTES["pressure"],
        "specific_product_allowed": False,
    }

    filtration_needs_quality = not _present(case.get("water_quality"))
    tracks["filtration"] = {
        "state": "NEEDS_WATER_QUALITY" if filtration_needs_quality else ("EXPERT_REVIEW" if dirty_water else "READY_FOR_SELECTOR"),
        "missing_inputs": ["water_quality"] if filtration_needs_quality else [],
        "tool_url": "https://keshavarz20.com/irrigation-filter-selector/",
        "intent_id": "ir-intent-well-sand-drip-filtration" if dirty_water else INTENT_ROUTES["water_quality"],
        "specific_product_allowed": False,
    }

    compat_fields = case.get("verified_compatibility_fields") or {}
    compat_ready = all(_present(compat_fields.get(k)) for k in ("nominal_size", "connection_type"))
    tracks["compatibility"] = {
        "state": "READY_FOR_SELECTOR" if compat_ready else "BLOCKED_UNVERIFIED_COMPATIBILITY",
        "missing_inputs": [k for k in ("nominal_size", "connection_type") if not _present(compat_fields.get(k))],
        "tool_url": "https://keshavarz20.com/irrigation-fittings-compatibility-selector/",
        "intent_id": None,
        "specific_product_allowed": False,
    }

    agronomy_reasons = []
    if not _present(case.get("soil_texture")):
        agronomy_reasons.append("soil_texture")
    if salinity_risk:
        agronomy_reasons.append("water_salinity_requires_lab_context")
    tracks["agronomy"] = {
        "state": "EXPERT_REVIEW" if agronomy_reasons or fertigation else "ADVISORY_ONLY",
        "missing_inputs": [x for x in agronomy_reasons if x == "soil_texture"],
        "intent_id": INTENT_ROUTES["fertigation"] if fertigation else None,
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

    escalation = core_blocked or dirty_water or salinity_risk or uneven or fertigation
    if core_blocked:
        overall = "NEEDS_MORE_INPUT"
    elif any(x["state"].startswith("BLOCKED") for x in tracks.values()):
        overall = "PARTIAL_DECISION_SUPPORT"
    elif escalation:
        overall = "ADVISORY_WITH_EXPERT_REVIEW"
    else:
        overall = "ADVISORY_READY"

    routed_intents = []
    for t in tracks.values():
        iid = t.get("intent_id")
        if iid and iid in intents:
            routed_intents.append({
                "canonical_intent_id": iid,
                "status": intents[iid].get("status"),
                "canonical_url": intents[iid].get("canonical_url") or None,
                "wordpress_post_id": intents[iid].get("wordpress_post_id") or None,
            })

    return {
        "decision_model_version": "farmer-decision-v2",
        "context_id": context_id(case),
        "state": overall,
        "confidence": "low" if core_blocked else ("medium" if escalation else "medium_high"),
        "input_quality": {
            "missing_core": missing_core,
            "invalid": invalid,
            "hydraulic_missing": hydraulic_missing,
            "unknowns_preserved": True,
        },
        "risk_flags": sorted(set(risk_flags)),
        "decision_tracks": tracks,
        "intent_routes": routed_intents,
        "authority_basis": {
            "phase21_status": authority.get("status"),
            "hard_fabrications": authority.get("evidence_layer", {}).get("hard_fabrications"),
            "verified_grade_a_cards": authority.get("evidence_layer", {}).get("verified_grade_a_first_party_cards"),
        },
        "scope": {
            "specific_product_recommendation": False,
            "sku_recommendation": False,
            "certified_hydraulic_design": False,
            "agronomic_prescription": False,
            "price_or_stock_decision": False,
        },
        "expert_escalation": bool(escalation),
        "privacy": {
            "stores_identity": False,
            "stores_contact_data": False,
            "context_id_is_non_identity_hash": True,
        },
        "guardrails": [
            "Unknown technical values remain unknown.",
            "Candidate-only compatibility is never promoted to verified.",
            "No SKU or exact product is selected without verified compatibility.",
            "The output is decision support, not certified hydraulic/agronomic design.",
            "No price, stock, customer identity or private support data is used.",
        ],
    }


def validate(result: dict[str, Any]) -> None:
    if result["authority_basis"]["phase21_status"] != "PASS_IRAN_FIRST_AUTHORITY_V2":
        raise Phase22Error("Phase 21 authority dependency is not passed")
    if result["authority_basis"]["hard_fabrications"] != 0:
        raise Phase22Error("authority layer reports fabrication")
    if result["scope"]["specific_product_recommendation"] or result["scope"]["sku_recommendation"]:
        raise Phase22Error("unverified product recommendation is forbidden")
    if result["scope"]["certified_hydraulic_design"] or result["scope"]["agronomic_prescription"]:
        raise Phase22Error("certified design/prescription claim is forbidden")
    if not result["privacy"]["context_id_is_non_identity_hash"]:
        raise Phase22Error("unsafe personalization identifier")
    for track in result["decision_tracks"].values():
        if track.get("specific_product_allowed"):
            raise Phase22Error("track enabled unsupported product selection")


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cases", required=True)
    p.add_argument("--output")
    args = p.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    results = []
    for case in cases:
        out = evaluate(case)
        validate(out)
        results.append({"case_id": case.get("case_id"), "result": out})
    report = {
        "phase": 22,
        "title": "Farmer Decision Personalization v2",
        "model_version": "farmer-decision-v2",
        "status": "PASS_MODEL_VALIDATION_V2",
        "case_count": len(results),
        "results": results,
        "site_mutations": 0,
        "commerce_mutations": 0,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "case_count": len(results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
