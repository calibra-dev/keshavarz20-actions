#!/usr/bin/env python3
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "seo-god2" / "phase6-public-recommendation-audit-20260930.json"

TIER_A = [
    140856, 140718, 135339, 135349, 140853, 140406, 140760, 140816, 140407, 135337,
    135353, 140454, 135381, 135361, 140674, 135235, 140014, 135309, 135359, 135667,
]
PHYSICAL = {
    140674, 140454, 140407, 140406, 140014, 135235, 135381, 135361, 135359, 135353,
    135349, 135339, 135337, 135309, 135667,
}
FERTILIZER = set(TIER_A) - PHYSICAL

RELATED_PATTERNS = {
    "related_products": re.compile(r'class=["\'][^"\']*(?:\brelated\b[^"\']*\bproducts\b|\bproducts\b[^"\']*\brelated\b)[^"\']*["\']', re.I),
    "upsells": re.compile(r'class=["\'][^"\']*\bupsells?\b[^"\']*["\']', re.I),
    "cross_sells": re.compile(r'class=["\'][^"\']*\bcross-sells?\b[^"\']*["\']', re.I),
}

def fetch_json(url: str, auth: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": auth,
            "Accept": "application/json",
            "User-Agent": "k20-seogod2-phase6-audit/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_html(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0 (compatible; Keshavarz20Phase6Audit/1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
            return int(getattr(r, "status", 200)), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return int(e.code), body

def main() -> None:
    base = os.environ["WP_BASE_URL"].rstrip("/")
    user = os.environ["WP_USERNAME"]
    password = os.environ["WP_APP_PASSWORD"]
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    auth = f"Basic {token}"

    def audit_one(pid: int) -> dict:
        product = fetch_json(
            f"{base}/wp-json/wc/v3/products/{pid}?context=edit",
            auth,
        )
        permalink = product.get("permalink") or ""
        http_status, html = fetch_html(permalink)
        return {
            "product_id": pid,
            "name": product.get("name"),
            "family_scope": "physical" if pid in PHYSICAL else "fertilizer",
            "permalink": permalink,
            "explicit_upsell_ids": product.get("upsell_ids") or [],
            "explicit_cross_sell_ids": product.get("cross_sell_ids") or [],
            "woocommerce_related_ids": product.get("related_ids") or [],
            "public_http_status": http_status,
            "public_phase6_marker_present": "k20-phase6-basket-intelligence" in html,
            "public_phase6_heading_present": "چک‌لیست تکمیل خرید" in html,
            "public_related_guard_present": f"k20-phase6-related-guard-{pid}" in html,
            "public_related_section_present": bool(RELATED_PATTERNS["related_products"].search(html)),
            "public_upsells_section_present": bool(RELATED_PATTERNS["upsells"].search(html)),
            "public_cross_sells_section_present": bool(RELATED_PATTERNS["cross_sells"].search(html)),
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(audit_one, TIER_A))

    explicit_nonempty = [
        r["product_id"] for r in rows
        if r["explicit_upsell_ids"] or r["explicit_cross_sell_ids"]
    ]
    public_recommendation_sections = [
        r["product_id"] for r in rows
        if r["public_related_section_present"]
        or r["public_upsells_section_present"]
        or r["public_cross_sells_section_present"]
    ]
    public_recommendation_unsuppressed = [
        r["product_id"] for r in rows
        if (
            r["public_related_section_present"]
            or r["public_upsells_section_present"]
            or r["public_cross_sells_section_present"]
        )
        and not r["public_related_guard_present"]
    ]
    related_guard_missing = [
        r["product_id"] for r in rows if not r["public_related_guard_present"]
    ]
    physical_marker_missing = [
        r["product_id"] for r in rows
        if r["product_id"] in PHYSICAL
        and not r["public_phase6_heading_present"]
    ]
    fertilizer_marker_unexpected = [
        r["product_id"] for r in rows
        if r["product_id"] in FERTILIZER and r["public_phase6_marker_present"]
    ]
    non_200 = [r["product_id"] for r in rows if r["public_http_status"] != 200]

    report = {
        "schema_version": "seo-god2-phase6-public-recommendation-audit-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "All 20 Tier A products; read-only WooCommerce fields plus public rendered HTML",
        "metrics": {
            "tier_a_products": len(rows),
            "explicit_recommendation_fields_nonempty": len(explicit_nonempty),
            "public_recommendation_sections_present_raw": len(public_recommendation_sections),
            "public_recommendation_sections_unsuppressed": len(public_recommendation_unsuppressed),
            "phase6_related_guard_missing": len(related_guard_missing),
            "physical_heading_missing": len(physical_marker_missing),
            "fertilizer_marker_unexpected": len(fertilizer_marker_unexpected),
            "public_non_200": len(non_200),
        },
        "failures": {
            "explicit_recommendation_fields_nonempty_product_ids": explicit_nonempty,
            "public_recommendation_section_product_ids_raw": public_recommendation_sections,
            "public_recommendation_unsuppressed_product_ids": public_recommendation_unsuppressed,
            "phase6_related_guard_missing_product_ids": related_guard_missing,
            "physical_heading_missing_product_ids": physical_marker_missing,
            "fertilizer_marker_unexpected_product_ids": fertilizer_marker_unexpected,
            "public_non_200_product_ids": non_200,
        },
        "rows": rows,
    }
    blocking_metrics = [
        "explicit_recommendation_fields_nonempty",
        "public_recommendation_sections_unsuppressed",
        "phase6_related_guard_missing",
        "physical_heading_missing",
        "fertilizer_marker_unexpected",
        "public_non_200",
    ]
    report["status"] = (
        "PASS"
        if all(report["metrics"][key] == 0 for key in blocking_metrics)
        else "FAIL"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "metrics": report["metrics"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
