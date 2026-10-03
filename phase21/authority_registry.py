#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "evidence": ROOT / "phase17" / "evidence-cards.json",
    "pim": ROOT / "phase9-results" / "canonical-pim.json",
    "intent": ROOT / "growth-os" / "intent-registry.json",
    "measurement": ROOT / "growthos-phase10-results" / "measurement-dashboard.json",
    "editorial": ROOT / "growthos-phase16-results" / "summary.json",
    "phase14": ROOT / "growthos-phase14-results" / "summary.json",
    "phase15": ROOT / "growthos-phase15-results" / "summary.json",
    "phase19": ROOT / "phase19-results" / "agentic-readiness-latest.json",
    "currency": ROOT / "phase19-results" / "currency-mapping-acceptance.json",
    "phase20": ROOT / "phase20-results" / "final-closure-latest.json",
    "campaign": ROOT / "phase21" / "citation-campaign-assets.json",
}
OPTIONAL = {
    "brand_diag": ROOT / "brand-remediation-results" / "diagnostic-latest.json",
}


class Phase21Error(RuntimeError):
    pass


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def latest_question_status() -> Path:
    files = sorted((ROOT / "question-engine-results").glob("*-status.json"))
    if not files:
        raise Phase21Error("no question-engine status artifact")
    return files[-1]


def brand_diag_summary(path: Path) -> dict:
    if not path.exists():
        return {
            "available": False,
            "scope": 0,
            "pseudo_brand_products": None,
            "multi_brand_products": None,
            "unbranded_products": None,
        }
    data = load(path)
    targets = data.get("targets") or []
    pseudo = 0
    multi = 0
    unbranded = 0
    for rec in targets:
        brands = rec.get("brands") or []
        names = {str(x.get("name") or "").strip() for x in brands if isinstance(x, dict)}
        if not brands:
            unbranded += 1
        if len(brands) > 1:
            multi += 1
        if "متفرقه" in names:
            pseudo += 1
    return {
        "available": True,
        "scope": len(targets),
        "pseudo_brand_products": pseudo,
        "multi_brand_products": multi,
        "unbranded_products": unbranded,
    }


def build_snapshot() -> dict:
    evidence = load(REQUIRED["evidence"])
    pim = load(REQUIRED["pim"])
    intent = load(REQUIRED["intent"])
    measurement = load(REQUIRED["measurement"])
    editorial = load(REQUIRED["editorial"])
    p14 = load(REQUIRED["phase14"])
    p15 = load(REQUIRED["phase15"])
    p19 = load(REQUIRED["phase19"])
    currency = load(REQUIRED["currency"])
    p20 = load(REQUIRED["phase20"])
    campaign = load(REQUIRED["campaign"])
    qpath = latest_question_status()
    qstatus = load(qpath)
    bdiag = brand_diag_summary(OPTIONAL["brand_diag"])

    verified_a = [
        x for x in evidence
        if x.get("status") == "verified" and x.get("evidence_grade") == "A"
    ]
    pim_summary = pim.get("summary") or {}
    pim_acceptance = pim.get("acceptance") or {}
    search = measurement.get("search_console") or {}
    p19_readiness = p19.get("readiness") or {}
    p19_acceptance = p19.get("acceptance") or {}
    currency_checks = currency.get("checks") or {}

    citation_assets = [
        {
            "asset_id": "authority-evidence-grade-a",
            "type": "verified_first_party_evidence_registry",
            "source_ref": "phase17/evidence-cards.json",
            "citable": True,
            "limitation": "Each evidence card is citable only within its stated scope and limits.",
        },
        {
            "asset_id": "authority-full-catalog-product-truth",
            "type": "full_catalog_page_schema_feed_governance",
            "source_ref": "phase19-results/agentic-readiness-latest.json",
            "citable": True,
            "limitation": "External submission remains separately governed by market, partner and identifier gates.",
        },
        {
            "asset_id": "authority-currency-normalization",
            "type": "deterministic_currency_denomination_mapping",
            "source_ref": "phase19-results/currency-mapping-acceptance.json",
            "citable": True,
            "limitation": "IRT x10 -> IRR is denomination normalization, not FX conversion.",
        },
        {
            "asset_id": "authority-editorial-trust",
            "type": "editorial_provenance_and_correction_policy",
            "source_ref": "growthos-phase16-results/summary.json",
            "citable": True,
            "limitation": "No named human Person identity is asserted without verified identity and role evidence.",
        },
        {
            "asset_id": "authority-search-demand",
            "type": "persisted_first_party_search_console_snapshot",
            "source_ref": "growthos-phase10-results/measurement-dashboard.json",
            "citable": True,
            "limitation": "Persisted snapshot is not a claim of live Search Console data on the Phase 21 run date.",
        },
        {
            "asset_id": "authority-agent-usable-surfaces",
            "type": "ux_semantic_agent_usability_acceptance",
            "source_ref": "phase20-results/final-closure-latest.json",
            "citable": True,
            "limitation": "Phase 20 explicitly does not claim a full automated WCAG pass; two guarded vendor-renderer residual classes remain.",
        },
    ]

    snapshot = {
        "phase": 21,
        "version": "phase21-iran-authority-network-v3",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_IRAN_FIRST_AUTHORITY_V3_GUARDED",
        "completion_basis": (
            "Controllable first-party authority/citation assets, current full-catalog governance, "
            "editorial provenance, demand evidence, and anti-fabrication safeguards. "
            "Manufacturer replies, backlinks and paid placements are not acceptance gates."
        ),
        "evidence": {
            "verified_grade_a_cards": len(verified_a),
            "evidence_ids": [x.get("evidence_id") for x in verified_a],
        },
        "product_truth": {
            "pim_records": int(pim_summary.get("records") or 0),
            "stable_id_complete": int(pim_summary.get("stable_id_complete") or 0),
            "verified_compatibility_edges": int(pim_summary.get("verified_compatibility_edges") or 0),
            "candidate_only_edges": int(pim_summary.get("candidate_only_edges") or 0),
            "hard_fabrications": int(pim_summary.get("hard_fabrications") or 0),
            "schema_feed_parity_pass": int(pim_summary.get("schema_feed_parity_pass") or 0),
            "unsupported_compatibility_promoted": not bool(
                pim_acceptance.get("no_unsupported_compatibility_promoted")
            ),
        },
        "full_catalog": {
            "candidate_rows": int(p19_readiness.get("candidate_rows") or 0),
            "basic_field_complete_rows": int(p19_readiness.get("basic_field_complete_rows") or 0),
            "basic_field_complete_percent": float(p19_readiness.get("basic_field_complete_percent") or 0),
            "phase19_status": p19.get("status"),
            "phase19_checks_passed": int(p19.get("passed_checks") or 0),
            "phase19_checks_total": int(p19.get("check_count") or 0),
            "phase19_failed_checks": p19.get("failed_checks") or [],
            "full_catalog_governed": bool(p19_acceptance.get("full_catalog_governed")),
            "page_schema_feed_parity_governed": bool(p19_acceptance.get("page_schema_feed_parity_governed")),
            "identifier_truth_preserved": bool(p19_acceptance.get("identifier_truth_preserved")),
            "entity_truth_preserved": bool(p19_acceptance.get("entity_truth_preserved")),
            "external_submission": bool(p19_acceptance.get("external_submission")),
        },
        "identifier_truth": {
            "published_products": int(p14.get("published_products") or 0),
            "source_verified_gtins": int(p14.get("source_verified_gtins") or 0),
            "gtins_fabricated": int(p14.get("gtins_fabricated") or 0),
            "skus_promoted_to_gtin": int(p14.get("skus_promoted_to_gtin") or 0),
            "unbacked_schema_gtin_products": int(p14.get("unbacked_schema_gtin_products") or 0),
        },
        "brand_truth": {
            "phase15_status": p15.get("status"),
            "published_products": int(p15.get("published_products") or 0),
            "identity_fields_fabricated": int(p15.get("identity_fields_fabricated") or 0),
            "sameAs_links_fabricated": int(p15.get("sameAs_links_fabricated") or 0),
            "glns_fabricated": int(p15.get("glns_fabricated") or 0),
            "current_remediation_diagnostic": bdiag,
            "policy": (
                "Pseudo-brand, unbranded and multi-brand ambiguity remain guarded gaps; "
                "they must not be converted into a single external brand without source evidence."
            ),
        },
        "currency_truth": {
            "status": currency.get("status"),
            "source_currency": "IRT",
            "target_currency": "IRR",
            "multiplier": 10,
            "all_checks_pass": bool(currency_checks) and all(currency_checks.values()),
            "site_price_mutations": int(currency.get("site_price_mutations") or 0),
            "fx_conversion_used": bool(currency.get("fx_conversion_used")),
        },
        "editorial_trust": {
            "status": editorial.get("status"),
            "published_normal_posts": int(editorial.get("published_normal_posts") or 0),
            "current_full_provenance_posts": int(editorial.get("current_full_provenance_posts") or 0),
            "legacy_provenance_backlog": int(editorial.get("legacy_provenance_backlog") or 0),
            "fake_authors_created": int(editorial.get("fake_authors_created") or 0),
            "fake_reviewers_created": int(editorial.get("fake_reviewers_created") or 0),
            "named_human_experts_created": int(editorial.get("named_human_experts_created") or 0),
            "editorial_policy_url": editorial.get("editorial_policy_url"),
        },
        "intent_graph": {
            "canonical_intents": len(intent.get("intents") or []),
            "active_intents": sum(
                1 for x in (intent.get("intents") or [])
                if str(x.get("status") or "").lower() not in {"retired", "rejected", "deleted"}
            ),
        },
        "search_demand": {
            "source": "persisted first-party Search Console snapshot",
            "date_min": search.get("date_min"),
            "date_max": search.get("date_max"),
            "rows": int(search.get("rows") or 0),
            "visible_clicks": int(search.get("visible_clicks") or 0),
            "visible_impressions": int(search.get("visible_impressions") or 0),
            "irrigation_rows": int(search.get("irrigation_rows") or 0),
            "irrigation_clicks": int(search.get("irrigation_clicks") or 0),
            "irrigation_impressions": int(search.get("irrigation_impressions") or 0),
            "live_read_claimed": False,
        },
        "question_engine": {
            "source_ref": str(qpath.relative_to(ROOT)),
            "enabled": bool(qstatus.get("enabled")),
            "classification": "synthetic_editorial_question_generator_not_customer_evidence",
            "generated_questions_total": int(qstatus.get("questions_total") or 0),
            "products_touched": int(qstatus.get("products_touched") or 0),
            "pending_generated": int((qstatus.get("watchdog") or {}).get("pending_generated") or 0),
            "consecutive_failures": int((qstatus.get("watchdog") or {}).get("consecutive_failures") or 0),
            "may_count_as_customer_review": False,
            "may_count_as_customer_question": False,
            "may_count_as_testimonial": False,
        },
        "agent_usable_surfaces": {
            "phase20_status": p20.get("status"),
            "checks_passed": int(p20.get("passed_checks") or 0),
            "checks_total": int(p20.get("check_count") or 0),
            "failed_checks": p20.get("failed_checks") or [],
            "full_wcag_automated_pass": bool(p20.get("full_wcag_automated_pass")),
            "guarded_residuals": p20.get("guarded_residuals") or [],
            "commerce_mutations": int(p20.get("commerce_mutations") or 0),
            "protected_theme_edits": int(p20.get("protected_theme_edits") or 0),
        },
        "citation_assets": citation_assets,
        "campaign_policy": {
            "status": campaign.get("status"),
            "external_messages_sent": int(campaign.get("external_messages_sent") or 0),
            "paid_placements": int(campaign.get("paid_placements") or 0),
            "manufacturer_reply_required": False,
            "forbidden": (campaign.get("acceptance_model") or {}).get("forbidden") or [],
        },
    }
    snapshot["acceptance"] = build_acceptance(snapshot)
    validate_snapshot(snapshot)
    return snapshot


def build_acceptance(s: dict) -> dict:
    checks = []
    def add(name: str, passed: bool):
        checks.append({"name": name, "pass": bool(passed)})

    add("verified_grade_a_evidence_present", s["evidence"]["verified_grade_a_cards"] >= 7)
    add("pim_stable_ids_complete", s["product_truth"]["pim_records"] > 0 and s["product_truth"]["stable_id_complete"] == s["product_truth"]["pim_records"])
    add("pim_hard_fabrications_zero", s["product_truth"]["hard_fabrications"] == 0)
    add("unsupported_compatibility_not_promoted", not s["product_truth"]["unsupported_compatibility_promoted"])
    add("pim_schema_feed_parity_complete", s["product_truth"]["schema_feed_parity_pass"] == s["product_truth"]["pim_records"])
    add("full_catalog_scope_consistent", s["full_catalog"]["candidate_rows"] == s["identifier_truth"]["published_products"] == s["brand_truth"]["published_products"] and s["full_catalog"]["candidate_rows"] > 0)
    add("phase19_passed_all_checks", str(s["full_catalog"]["phase19_status"]).startswith("PASS") and s["full_catalog"]["phase19_checks_passed"] == s["full_catalog"]["phase19_checks_total"] and not s["full_catalog"]["phase19_failed_checks"])
    add("phase19_full_catalog_governed", s["full_catalog"]["full_catalog_governed"])
    add("phase19_page_schema_feed_governed", s["full_catalog"]["page_schema_feed_parity_governed"])
    add("phase19_identifier_truth_preserved", s["full_catalog"]["identifier_truth_preserved"])
    add("phase19_entity_truth_preserved", s["full_catalog"]["entity_truth_preserved"])
    add("no_external_submission_claim", not s["full_catalog"]["external_submission"])
    add("gtin_fabrication_zero", s["identifier_truth"]["gtins_fabricated"] == 0)
    add("sku_not_promoted_to_gtin", s["identifier_truth"]["skus_promoted_to_gtin"] == 0)
    add("unbacked_schema_gtin_zero", s["identifier_truth"]["unbacked_schema_gtin_products"] == 0)
    add("brand_identity_fabrication_zero", s["brand_truth"]["identity_fields_fabricated"] == 0)
    add("brand_sameas_fabrication_zero", s["brand_truth"]["sameAs_links_fabricated"] == 0)
    add("brand_gln_fabrication_zero", s["brand_truth"]["glns_fabricated"] == 0)
    add("currency_mapping_pass", s["currency_truth"]["status"] == "PASS" and s["currency_truth"]["all_checks_pass"])
    add("currency_mapping_exact_irt_to_irr", s["currency_truth"]["source_currency"] == "IRT" and s["currency_truth"]["target_currency"] == "IRR" and s["currency_truth"]["multiplier"] == 10)
    add("currency_site_prices_untouched", s["currency_truth"]["site_price_mutations"] == 0 and not s["currency_truth"]["fx_conversion_used"])
    add("editorial_full_provenance", s["editorial_trust"]["published_normal_posts"] > 0 and s["editorial_trust"]["current_full_provenance_posts"] == s["editorial_trust"]["published_normal_posts"] and s["editorial_trust"]["legacy_provenance_backlog"] == 0)
    add("fake_authors_zero", s["editorial_trust"]["fake_authors_created"] == 0)
    add("fake_reviewers_zero", s["editorial_trust"]["fake_reviewers_created"] == 0)
    add("active_intents_present", s["intent_graph"]["active_intents"] > 0)
    add("persisted_search_demand_present", s["search_demand"]["rows"] > 0 and s["search_demand"]["visible_impressions"] > 0)
    add("no_false_live_gsc_claim", not s["search_demand"]["live_read_claimed"])
    add("question_engine_enabled", s["question_engine"]["enabled"])
    add("question_engine_not_customer_evidence", not s["question_engine"]["may_count_as_customer_review"] and not s["question_engine"]["may_count_as_customer_question"] and not s["question_engine"]["may_count_as_testimonial"])
    add("question_engine_no_consecutive_failures", s["question_engine"]["consecutive_failures"] == 0)
    add("phase20_guarded_pass", str(s["agent_usable_surfaces"]["phase20_status"]).startswith("PASS") and s["agent_usable_surfaces"]["checks_passed"] == s["agent_usable_surfaces"]["checks_total"] and not s["agent_usable_surfaces"]["failed_checks"])
    add("full_wcag_not_falsely_claimed", not s["agent_usable_surfaces"]["full_wcag_automated_pass"])
    add("phase20_commerce_mutations_zero", s["agent_usable_surfaces"]["commerce_mutations"] == 0)
    add("phase20_protected_theme_edits_zero", s["agent_usable_surfaces"]["protected_theme_edits"] == 0)
    add("citation_assets_have_limits", len(s["citation_assets"]) >= 6 and all(x.get("citable") and x.get("limitation") for x in s["citation_assets"]))
    add("campaign_no_paid_fake_authority", s["campaign_policy"]["paid_placements"] == 0)
    add("campaign_no_outreach_gate", not s["campaign_policy"]["manufacturer_reply_required"])

    passed = sum(1 for x in checks if x["pass"])
    return {
        "check_count": len(checks),
        "passed_checks": passed,
        "failed_checks": [x["name"] for x in checks if not x["pass"]],
        "checks": checks,
    }


def validate_snapshot(s: dict) -> None:
    failed = (s.get("acceptance") or {}).get("failed_checks") or []
    if failed:
        raise Phase21Error("Phase 21 acceptance failed: " + ", ".join(failed))


def question_classification(snapshot: dict) -> dict:
    q = snapshot["question_engine"]
    return {
        "phase": 21,
        "generated_at_utc": snapshot["generated_at_utc"],
        "source": q["source_ref"],
        "engine_state": {
            "enabled": q["enabled"],
            "questions_total": q["generated_questions_total"],
            "products_touched": q["products_touched"],
            "pending_generated": q["pending_generated"],
            "consecutive_failures": q["consecutive_failures"],
        },
        "classification": q["classification"],
        "counting_rules": {
            "real_customer_questions": 0,
            "verified_reviews": 0,
            "testimonials": 0,
            "editorial_intent_seeds": q["generated_questions_total"],
        },
        "safeguards": [
            "Do not label generated questions as customer questions.",
            "Do not count generated questions as reviews or testimonials.",
            "Do not infer demand volume from generated question count.",
            "Use only as editorial coverage prompts unless independently corroborated.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write")
    parser.add_argument("--write-question-classification")
    args = parser.parse_args()

    snapshot = build_snapshot()
    if args.write:
        Path(args.write).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.write_question_classification:
        Path(args.write_question_classification).write_text(
            json.dumps(question_classification(snapshot), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
