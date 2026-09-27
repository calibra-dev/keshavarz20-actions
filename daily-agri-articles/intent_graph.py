#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

SCORE_WEIGHTS = {
    "farmer_decision_value": 20,
    "independent_intent": 15,
    "evidence_strength": 15,
    "demand_signal": 15,
    "seasonal_relevance": 10,
    "business_relevance": 10,
    "original_value_potential": 10,
    "cannibalization_safety": 5,
}
PASS_SCORE = 85
BLOCKERS = {
    "keyword_variant",
    "existing_intent_overlap",
    "insufficient_evidence",
    "fabricated_claim_required",
    "news_routing",
    "sales_only",
    "generic_ai",
    "scaled_geo_variant",
}
SCENARIO_DIMENSIONS = (
    "crop", "province_or_climate", "season", "area", "water", "soil",
    "irrigation_system", "problem", "decision",
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value or ""))
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def canonical_intent_id(topic_cluster: str, decision: str, scenario: dict[str, Any]) -> str:
    raw = "|".join([
        normalize_text(topic_cluster),
        normalize_text(decision),
        *[normalize_text(scenario.get(k, "")) for k in SCENARIO_DIMENSIONS],
    ])
    return "ir-intent-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def score_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    raw_scores = candidate.get("scores") or {}
    scores: dict[str, int] = {}
    for key, maximum in SCORE_WEIGHTS.items():
        val = int(raw_scores.get(key, 0))
        if val < 0 or val > maximum:
            raise ValueError(f"score {key} must be between 0 and {maximum}")
        scores[key] = val
    blockers = sorted(set(candidate.get("blockers") or []) & BLOCKERS)
    total = sum(scores.values())
    decision = "PASS" if total >= PASS_SCORE and not blockers else "SKIP"
    return {"total": total, "scores": scores, "blockers": blockers, "decision": decision}


def route_signal(signal_type: str, has_strong_existing_url: bool = False) -> str:
    signal_type = normalize_text(signal_type)
    if has_strong_existing_url:
        return "update_existing"
    if signal_type in {"event", "time-sensitive", "news", "رویداد", "خبر"}:
        return "news"
    if signal_type in {"product-question", "product_uncertainty", "سوال محصول"}:
        return "question"
    if signal_type in {"compatibility", "compatibility_gap", "سازگاری"}:
        return "product_data_backlog"
    return "article"


def registry_overlap(candidate: dict[str, Any], registry: dict[str, Any]) -> list[dict[str, Any]]:
    topic = normalize_text(candidate.get("topic_cluster", ""))
    decision = normalize_text(candidate.get("scenario_dimensions", {}).get("decision", ""))
    matches = []
    for item in registry.get("intents", []):
        same_topic = normalize_text(item.get("topic_cluster", "")) == topic and topic
        same_decision = normalize_text((item.get("scenario_dimensions") or {}).get("decision", "")) == decision and decision
        if same_topic and same_decision:
            matches.append(item)
    return matches


def validate_phase20_metadata(payload: dict[str, Any], registry: dict[str, Any] | None = None) -> None:
    required = [
        "phase20_schema_version", "canonical_intent_id", "parent_hub", "scenario_dimensions",
        "source_strength", "question_engine_intents_covered", "compatibility_rules_referenced",
        "membership_cta_type", "update_triggers", "topic_score",
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError("missing Phase 20 metadata: " + ", ".join(missing))
    if str(payload["phase20_schema_version"]) != "1":
        raise ValueError("phase20_schema_version must be '1'")
    scenario = payload.get("scenario_dimensions")
    if not isinstance(scenario, dict):
        raise ValueError("scenario_dimensions must be an object")
    unknown = sorted(set(scenario) - set(SCENARIO_DIMENSIONS))
    if unknown:
        raise ValueError("unknown scenario dimensions: " + ", ".join(unknown))
    score = payload.get("topic_score")
    if not isinstance(score, dict) or int(score.get("total", -1)) < PASS_SCORE:
        raise ValueError(f"topic_score.total must be >= {PASS_SCORE}")
    if score.get("blockers"):
        raise ValueError("topic_score contains blockers")
    faq = payload.get("faq_items", []) or []
    if faq and not (3 <= len(faq) <= 8):
        raise ValueError("Phase 20 FAQ must be empty or contain 3 to 8 intent-backed items")
    if registry is not None:
        cid = str(payload.get("canonical_intent_id") or "")
        for item in registry.get("intents", []):
            if str(item.get("canonical_intent_id") or "") != cid:
                continue
            status = str(item.get("status") or "").strip().lower()
            is_active = status not in {"retired", "rejected", "deleted"}
            has_existing_asset = bool(item.get("canonical_url") or item.get("wordpress_post_id") or is_active)
            if has_existing_asset and not payload.get("update_post_id"):
                raise ValueError("canonical intent already exists in the registry; update/merge required instead of a new URL")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("candidate_file", nargs="?")
    p.add_argument("--shadow", action="store_true")
    args = p.parse_args()
    if args.shadow:
        data = load_json(Path(args.candidate_file))
        out = []
        for c in data.get("candidates", []):
            result = score_candidate(c)
            out.append({"id": c.get("id"), "title": c.get("title"), **result})
        print(json.dumps({"evaluated": len(out), "results": out}, ensure_ascii=False, indent=2))
        return 0
    p.error("use --shadow <file>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
