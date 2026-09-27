#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "growthos-phase4-results" / "compatibility-summary.json"
OUT = ROOT / "growthos-phase18-results" / "recommendation-basket-guard.json"


def load():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def build():
    p4 = load()
    s = p4.get("summary") or {}
    verified = int(s.get("verified_technical_compatibility_edges") or 0)
    candidates = int(s.get("candidate_only_edges") or 0)
    unresolved = int(s.get("source_bound_unresolved_products") or 0)
    if int(s.get("hard_fabrications") or 0) != 0:
        raise RuntimeError("Phase 4 has hard fabrications")
    return {
        "phase": 18,
        "title": "Recommendation & Basket Intelligence",
        "version": "growthos-recommendation-basket-guard-v1",
        "source_phase4_status": p4.get("status"),
        "verified_technical_compatibility_edges": verified,
        "candidate_only_edges": candidates,
        "source_bound_unresolved_products": unresolved,
        "policy": {
            "exact_sku_recommendation_requires_verified_technical_edge": True,
            "same_size_candidate_is_not_compatibility": True,
            "explicit_reference_is_not_technical_compatibility": True,
            "unknown_routes_to_expert_review": True,
            "no_price_discount_or_stock_mutation": True,
        },
        "runtime_mode": (
            "VERIFIED_COMPATIBILITY_RECOMMENDATIONS_ENABLED"
            if verified > 0 else
            "GUARDED_EXPERT_REVIEW_ONLY"
        ),
        "automatic_exact_sku_recommendation_enabled": verified > 0,
        "acceptance": {
            "candidate_edges_not_promoted": True,
            "unsupported_exact_sku_recommendation_disabled": verified == 0,
            "expert_review_fallback_active": True,
            "phase4_source_gaps_preserved": unresolved >= 0,
        },
        "status": (
            "PASS_VERIFIED_COMPATIBILITY_BASKET"
            if verified > 0 else
            "PASS_GUARDED_NO_VERIFIED_TECHNICAL_EDGES"
        ),
        "next_gate": (
            None if verified > 0 else
            "Acquire exact SKU/manufacturer interface evidence in Phase 4 before enabling automatic exact product-to-product basket recommendations."
        ),
    }


def main():
    report = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "verified_edges": report["verified_technical_compatibility_edges"],
        "exact_sku_auto": report["automatic_exact_sku_recommendation_enabled"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
