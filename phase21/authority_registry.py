#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "evidence": ROOT / "phase17" / "evidence-cards.json",
    "pim": ROOT / "phase9-results" / "canonical-pim.json",
    "intent": ROOT / "growth-os" / "intent-registry.json",
    "measurement": ROOT / "growthos-phase10-results" / "measurement-dashboard.json",
    "question_status": ROOT / "question-engine-results" / "20260921T094817Z-status.json",
}


class Phase21Error(RuntimeError):
    pass


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_snapshot() -> dict:
    evidence = load(REQUIRED["evidence"])
    pim = load(REQUIRED["pim"])
    intent = load(REQUIRED["intent"])
    measurement = load(REQUIRED["measurement"])
    qstatus = load(REQUIRED["question_status"])

    verified_a = [
        x for x in evidence
        if x.get("status") == "verified" and x.get("evidence_grade") == "A"
    ]
    pim_summary = pim.get("summary") or {}
    pim_acceptance = pim.get("acceptance") or {}
    search = measurement.get("search_console") or {}

    snapshot = {
        "phase": 21,
        "version": "phase21-iran-authority-network-v2",
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
        },
        "question_engine": {
            "classification": "synthetic_editorial_question_generator_not_customer_evidence",
            "generated_questions_total": int(qstatus.get("questions_total") or 0),
            "products_touched": int(qstatus.get("products_touched") or 0),
            "pending_generated": int((qstatus.get("watchdog") or {}).get("pending_generated") or 0),
            "may_count_as_customer_review": False,
            "may_count_as_customer_question": False,
        },
    }
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(s: dict) -> None:
    if s["evidence"]["verified_grade_a_cards"] < 1:
        raise Phase21Error("no verified Grade-A first-party evidence cards")
    p = s["product_truth"]
    if p["pim_records"] <= 0 or p["stable_id_complete"] != p["pim_records"]:
        raise Phase21Error("PIM stable-ID coverage incomplete")
    if p["hard_fabrications"] != 0:
        raise Phase21Error("hard fabrication detected")
    if p["unsupported_compatibility_promoted"]:
        raise Phase21Error("unsupported compatibility was promoted")
    if p["schema_feed_parity_pass"] != p["pim_records"]:
        raise Phase21Error("schema/feed parity incomplete")
    if s["intent_graph"]["active_intents"] <= 0:
        raise Phase21Error("no active canonical intents")
    if s["search_demand"]["rows"] <= 0:
        raise Phase21Error("no persisted Search Console demand evidence")
    if s["question_engine"]["may_count_as_customer_review"]:
        raise Phase21Error("synthetic questions must never count as customer reviews")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write")
    args = parser.parse_args()

    snapshot = build_snapshot()
    if args.write:
        Path(args.write).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
