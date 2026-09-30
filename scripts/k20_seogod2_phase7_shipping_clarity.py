#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "seo-god2" / "phase7-shipping-truth-20260930.json"
OUT = ROOT / "seo-god2" / "phase7-shipping-clarity-plan-20260930.json"

TIER_A = [
    140856, 140718, 135339, 135349, 140853,
    140406, 140760, 140816, 140407, 135337,
    135353, 140454, 135381, 135361, 140674,
    135235, 140014, 135309, 135359, 135667,
]

FORBIDDEN_PUBLIC_CLAIMS = [
    "ارسال رایگان",
    "رایگان ارسال",
    "تحویل ۱ روزه",
    "تحویل یک روزه",
    "تحویل ۲ روزه",
    "تحویل دو روزه",
    "تحویل ۳ روزه",
    "تحویل سه روزه",
]

BLOCK = """<!-- k20-phase7-shipping-clarity -->
<div dir="rtl" class="k20-shipping-clarity" style="direction:rtl;text-align:right;margin:14px 0;padding:13px 15px;border:1px solid #dfe5ef;border-radius:14px;background:#fafcff;line-height:1.9">
<p style="margin:0 0 8px"><strong>ارسال و تحویل سفارش</strong></p>
<ul style="margin:8px 18px 0 0;padding:0">
<li>ارسال به سراسر کشور از طریق <strong>باربری یا تیپاکس</strong> انجام می‌شود.</li>
<li>هزینه حمل <strong>پس‌کرایه</strong> و مطابق تعرفه شرکت حمل از گیرنده دریافت می‌شود.</li>
<li>روش نهایی حمل با توجه به نوع و ابعاد کالا، مقصد و امکان پذیرش مرسوله توسط شرکت حمل تعیین می‌شود.</li>
<li>زمان تحویل به مقصد و شبکه توزیع شرکت حمل وابسته است و بدون اطلاعات همان سفارش، زمان قطعی اعلام نمی‌شود.</li>
</ul>
<p style="margin:9px 0 0"><a href="/shipping/" rel="nofollow">جزئیات روش‌های ارسال سفارش</a></p>
</div>
<!-- /k20-phase7-shipping-clarity -->"""


def main() -> None:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    page = truth["shipping_page"]
    zones = truth.get("shipping_zones") or []
    iran = next((z for z in zones if z.get("name") == "ایران"), None)
    if not iran:
        raise RuntimeError("Iran shipping zone missing")
    methods = iran.get("methods") or []
    enabled = [m for m in methods if m.get("enabled") is True]
    titles = [m.get("title") or "" for m in enabled]

    if len(enabled) != 1 or enabled[0].get("method_id") != "flat_rate":
        raise RuntimeError("Expected exactly one enabled flat-rate shipping method for Iran")
    if "باربری" not in titles[0] or "تیپاکس" not in titles[0] or "پس‌کرایه" not in titles[0]:
        raise RuntimeError("Enabled shipping method title does not match public shipping truth")
    if page.get("keyword_signals", {}).get("ارسال رایگان"):
        raise RuntimeError("Shipping page claims free shipping")
    if page.get("keyword_signals", {}).get("تیپاکس") is not True:
        raise RuntimeError("Tipax evidence missing")
    if page.get("keyword_signals", {}).get("باربری") is not True:
        raise RuntimeError("Freight evidence missing")
    if page.get("keyword_signals", {}).get("پس‌کرایه") is not True:
        raise RuntimeError("Collect-on-delivery freight evidence missing")

    report = {
        "schema_version": "seo-god2-phase7-shipping-clarity-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_SHIPPING_TRUTH_LOCKED",
        "scope": {"tier_a_products": len(TIER_A), "product_ids": TIER_A},
        "canonical_policy": {
            "country_scope": "Iran / سراسر کشور",
            "allowed_methods": ["باربری", "تیپاکس"],
            "shipping_charge": "پس‌کرایه مطابق تعرفه شرکت حمل",
            "free_shipping": False,
            "local_pickup": False,
            "fixed_delivery_promise": False,
            "method_selection": "بر اساس نوع و ابعاد کالا، مقصد و پذیرش شرکت حمل",
            "delivery_time": "وابسته به مقصد، روش حمل، زمان تحویل به شرکت حمل و شبکه توزیع",
            "policy_page": "/shipping/",
        },
        "guardrails": {
            "forbidden_claims": FORBIDDEN_PUBLIC_CLAIMS,
            "fixed_shipping_price_allowed": False,
            "fixed_delivery_days_allowed": False,
            "per_sku_carrier_guarantee_allowed": False,
            "shipping_method_must_be_selected_from_live_policy": True,
        },
        "render": {
            "marker": "k20-phase7-shipping-clarity",
            "block_html": BLOCK,
            "placement": "product short_description after product/basket content",
            "idempotent": True,
        },
        "truth_source": "seo-god2/phase7-shipping-truth-20260930.json",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "tier_a_products": len(TIER_A)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
