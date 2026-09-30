#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "seo-god2" / "phase5-tier-a-compatibility-graph-v2-20260930.json"
OUT = ROOT / "seo-god2" / "phase6-basket-intelligence-20260930.json"

ALLOWED_EDGE_STATUS = {"VERIFIED", "INCOMPATIBLE", "NEEDS_REVIEW"}
ALLOWED_LABELS = {"مکمل ضروری", "مکمل اختیاری", "جایگزین", "محصول مشابه", "نیازمند تأیید کارشناس"}

PROFILES = {
    "fertilizer": {
        "required_accessories": [],
        "optional_accessories": [],
        "installation_accessories": [],
        "filter_requirement": "NOT_APPLICABLE",
        "valve_requirement": "NOT_APPLICABLE",
        "connector_requirement": "NOT_APPLICABLE",
        "washer_requirement": "NOT_APPLICABLE",
        "drill_requirement": "NOT_APPLICABLE",
        "note": "اختلاط یا جایگزینی کود فقط با برچسب همین محصول یا منبع سازنده قابل توصیه است.",
    },
    "valve": {
        "required_accessories": ["قطعه مقابل و آب‌بندی متناسب با نوع اتصال واقعی"],
        "optional_accessories": ["ساپورت یا مهار خط در صورت نیاز پروژه"],
        "installation_accessories": ["ابزار نصب متناسب با نوع اتصال واقعی"],
        "filter_requirement": "CONDITIONAL_BY_SYSTEM_DESIGN",
        "valve_requirement": "SELF",
        "connector_requirement": "REQUIRED_CHECK",
        "washer_requirement": "DEPENDS_ON_CONNECTION_STANDARD",
        "drill_requirement": "NOT_APPLICABLE",
    },
    "fertigation_tank": {
        "required_accessories": ["اتصالات ورودی و خروجی متناسب با مدار واقعی"],
        "optional_accessories": ["شیر ایزوله و بای‌پس فقط در صورت تأیید طراحی"],
        "installation_accessories": ["آب‌بندی و مهار متناسب با استاندارد اتصال"],
        "filter_requirement": "CONDITIONAL_BY_SYSTEM_DESIGN",
        "valve_requirement": "REQUIRED_CHECK",
        "connector_requirement": "REQUIRED_CHECK",
        "washer_requirement": "DEPENDS_ON_CONNECTION_STANDARD",
        "drill_requirement": "NOT_APPLICABLE",
    },
    "drip_tape_connector": {
        "required_accessories": ["نوار تیپ سازگار با رابط دقیق"],
        "optional_accessories": [],
        "installation_accessories": ["واشر یا ابزار سوراخ‌کاری فقط اگر دیتاشیت همان رابط الزام کند"],
        "filter_requirement": "SYSTEM_LEVEL_CHECK",
        "valve_requirement": "CONDITIONAL_BY_ZONE_DESIGN",
        "connector_requirement": "SELF",
        "washer_requirement": "NEEDS_REVIEW",
        "drill_requirement": "NEEDS_REVIEW",
    },
    "drip_tape_valve": {
        "required_accessories": ["خط ورودی و نوار تیپ سازگار با دو سمت شیر"],
        "optional_accessories": [],
        "installation_accessories": ["واشر/پانچ فقط طبق رابط دقیق"],
        "filter_requirement": "SYSTEM_LEVEL_CHECK",
        "valve_requirement": "SELF",
        "connector_requirement": "NEEDS_REVIEW",
        "washer_requirement": "NEEDS_REVIEW",
        "drill_requirement": "NEEDS_REVIEW",
    },
    "drip_line_fitting": {
        "required_accessories": ["لوله ۱۶ میلی‌متری با هندسه اتصال سازگار"],
        "optional_accessories": [],
        "installation_accessories": ["ابزار نصب در صورت الزام سازنده"],
        "filter_requirement": "SYSTEM_LEVEL_CHECK",
        "valve_requirement": "CONDITIONAL_BY_ZONE_DESIGN",
        "connector_requirement": "SELF",
        "washer_requirement": "NOT_APPLICABLE",
        "drill_requirement": "NOT_APPLICABLE",
    },
    "emitter": {
        "required_accessories": ["خط لوله و رابط نصب سازگار با مدل دقیق دریپر"],
        "optional_accessories": [],
        "installation_accessories": ["پانچ یا ابزار نصب فقط طبق مدل دقیق"],
        "filter_requirement": "REQUIRED_CHECK",
        "valve_requirement": "CONDITIONAL_BY_ZONE_DESIGN",
        "connector_requirement": "NEEDS_REVIEW",
        "washer_requirement": "DEPENDS_ON_INSTALL_INTERFACE",
        "drill_requirement": "NEEDS_REVIEW",
    },
    "drip_tape": {
        "required_accessories": ["اتصال ابتدا و انتهای خط متناسب با مدل واقعی نوار تیپ"],
        "optional_accessories": ["شیر ردیفی در صورت نیاز به کنترل مستقل هر ردیف"],
        "installation_accessories": ["پانچ/واشر فقط مطابق رابط انتخاب‌شده"],
        "filter_requirement": "REQUIRED_CHECK",
        "valve_requirement": "CONDITIONAL_BY_ZONE_DESIGN",
        "connector_requirement": "REQUIRED_CHECK",
        "washer_requirement": "DEPENDS_ON_CONNECTOR",
        "drill_requirement": "DEPENDS_ON_CONNECTOR",
    },
    "rain_pipe": {
        "required_accessories": ["رابط/سرشلنگی و مهار متناسب با سایز و فشار واقعی خط"],
        "optional_accessories": ["شیر ایزوله در صورت نیاز طراحی"],
        "installation_accessories": ["بست یا مهار مناسب رابط"],
        "filter_requirement": "CONDITIONAL_BY_WATER_QUALITY",
        "valve_requirement": "CONDITIONAL_BY_ZONE_DESIGN",
        "connector_requirement": "REQUIRED_CHECK",
        "washer_requirement": "DEPENDS_ON_CONNECTOR",
        "drill_requirement": "NOT_APPLICABLE",
    },
    "layflat_reinforced_hose": {
        "required_accessories": ["سرشلنگی/رابط و مهار متناسب با قطر واقعی لوله"],
        "optional_accessories": ["شیر ایزوله در صورت نیاز طراحی"],
        "installation_accessories": ["بست یا مهار مناسب رابط"],
        "filter_requirement": "CONDITIONAL_BY_SYSTEM_USE",
        "valve_requirement": "CONDITIONAL_BY_ZONE_DESIGN",
        "connector_requirement": "REQUIRED_CHECK",
        "washer_requirement": "DEPENDS_ON_CONNECTOR",
        "drill_requirement": "NOT_APPLICABLE",
    },
}

DEFAULT_PROFILE = {
    "required_accessories": [],
    "optional_accessories": [],
    "installation_accessories": [],
    "filter_requirement": "NEEDS_REVIEW",
    "valve_requirement": "NEEDS_REVIEW",
    "connector_requirement": "NEEDS_REVIEW",
    "washer_requirement": "NEEDS_REVIEW",
    "drill_requirement": "NEEDS_REVIEW",
}


def load_graph(path: Path = GRAPH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def edge_label(edge: dict) -> str | None:
    label = edge.get("recommendation_type")
    return label if label in ALLOWED_LABELS else None


def build(graph: dict) -> dict:
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if len(nodes) != 20:
        raise RuntimeError(f"Phase 6 requires exactly 20 Tier A nodes, got {len(nodes)}")
    invalid_status = [e for e in edges if e.get("status") not in ALLOWED_EDGE_STATUS]
    if invalid_status:
        raise RuntimeError("Unsupported compatibility edge status")
    node_ids = {int(n["id"]) for n in nodes}
    exact = []
    blocked = []
    expert_review = []
    for e in edges:
        a, b = int(e["from"]), int(e["to"])
        if a not in node_ids or b not in node_ids:
            continue
        status = e["status"]
        if status == "VERIFIED":
            label = edge_label(e)
            if label is None:
                expert_review.append({
                    "from": a, "to": b, "relation": e.get("relation"),
                    "label": "نیازمند تأیید کارشناس",
                    "reason": "Edge is VERIFIED but lacks an approved Phase 6 recommendation label.",
                })
                continue
            exact.append({
                "from": a, "to": b, "relation": e.get("relation"),
                "label": label, "evidence": e.get("evidence") or [],
            })
        elif status == "INCOMPATIBLE":
            blocked.append({
                "from": a, "to": b, "relation": e.get("relation"),
                "reason": e.get("reason"),
            })
        else:
            expert_review.append({
                "from": a, "to": b, "relation": e.get("relation"),
                "label": "نیازمند تأیید کارشناس",
                "reason": e.get("reason"),
                "evidence_needed": e.get("evidence_needed") or [],
            })

    baskets = []
    for n in nodes:
        pid = int(n["id"])
        family = n.get("family") or "unknown"
        profile = dict(DEFAULT_PROFILE)
        profile.update(PROFILES.get(family, {}))
        baskets.append({
            "product_id": pid,
            "family": family,
            "required_accessories": profile["required_accessories"],
            "optional_accessories": profile["optional_accessories"],
            "installation_accessories": profile["installation_accessories"],
            "compatible_alternatives": [],
            "replacement_product": None,
            "filter_requirement": profile["filter_requirement"],
            "valve_requirement": profile["valve_requirement"],
            "connector_requirement": profile["connector_requirement"],
            "washer_requirement": profile["washer_requirement"],
            "drill_requirement": profile["drill_requirement"],
            "exact_sku_recommendations": [r for r in exact if r["from"] == pid or r["to"] == pid],
            "blocked_pairs": [r for r in blocked if r["from"] == pid or r["to"] == pid],
            "expert_review_pairs": [r for r in expert_review if r["from"] == pid or r["to"] == pid],
            "ui_policy": (
                "SHOW_VERIFIED_EXACT_SKU_CARDS"
                if any(r["from"] == pid or r["to"] == pid for r in exact)
                else "SHOW_REQUIREMENT_CHECKLIST_AND_EXPERT_REVIEW_ONLY"
            ),
            "profile_note": profile.get("note"),
        })

    return {
        "schema_version": "seo-god2-phase6-basket-intelligence-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_graph": str(GRAPH.relative_to(ROOT)),
        "status": "PASS_GUARDED_BASKET_INTELLIGENCE",
        "policy": {
            "random_woocommerce_recommendations_allowed": False,
            "same_size_recommendation_allowed": False,
            "exact_sku_requires_verified_edge_and_approved_label": True,
            "incompatible_edges_blocked": True,
            "needs_review_routes_to_expert": True,
            "fertilizer_mix_requires_exact_label_or_manufacturer_evidence": True,
            "no_price_discount_or_stock_mutation": True,
        },
        "metrics": {
            "tier_a_products": len(nodes),
            "verified_exact_recommendations": len(exact),
            "incompatible_pairs_blocked": len(blocked),
            "expert_review_pairs": len(expert_review),
            "random_recommendations": 0,
            "same_size_only_recommendations": 0,
        },
        "recommendation_labels": sorted(ALLOWED_LABELS),
        "products": baskets,
        "runtime": {
            "exact_sku_cards_enabled": len(exact) > 0,
            "fallback": "REQUIREMENT_CHECKLIST_AND_EXPERT_REVIEW",
            "legacy_same_size_writer_must_remain_disabled": True,
        },
    }


def main() -> None:
    report = build(load_graph())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
