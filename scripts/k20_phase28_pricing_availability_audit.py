#!/usr/bin/env python3
import json
import os
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "phase28-results" / "pricing-availability-audit-20261010.json"
BASE = os.environ.get("WP_BASE_URL", "https://keshavarz20.com").rstrip("/")

FIELDS = "id,name,slug,permalink,is_purchasable,is_in_stock,prices,categories"

def price_state(product):
    value = (product.get("prices") or {}).get("price")
    if value is None or str(value).strip() == "":
        return "missing"
    try:
        return "zero" if Decimal(str(value)) == 0 else "positive"
    except InvalidOperation:
        return "invalid"

def category_names(product):
    return [str(x.get("name") or "").strip() for x in (product.get("categories") or []) if str(x.get("name") or "").strip()]

def category_breakdown(rows):
    c = Counter()
    for row in rows:
        for name in category_names(row):
            c[name] += 1
    return [{"name": k, "count": v} for k, v in c.most_common()]

def compact(product):
    return {
        "id": int(product.get("id")),
        "name": product.get("name"),
        "permalink": product.get("permalink"),
        "is_purchasable": bool(product.get("is_purchasable")),
        "is_in_stock": bool(product.get("is_in_stock")),
        "price": (product.get("prices") or {}).get("price"),
        "price_state": price_state(product),
        "categories": category_names(product),
    }

def page_check(session, product, kind):
    url = product.get("permalink")
    if not url:
        return {"id": product.get("id"), "kind": kind, "ok": False, "reason": "no_permalink"}
    sep = "&" if "?" in url else "?"
    r = session.get(
        url + sep + "k20_phase28_verify=1",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "K20-Phase28-Audit/1.0"},
        timeout=60,
        allow_redirects=True,
    )
    text = r.text
    row = {"id": int(product.get("id")), "kind": kind, "http": r.status_code, "final_url": r.url}
    if kind == "zero_price_in_stock":
        row["inquiry_heading"] = "قیمت فعلی نیازمند استعلام است" in text
        row["inquiry_action"] = "استعلام قیمت این محصول" in text
        row["ok"] = r.status_code == 200 and row["inquiry_heading"] and row["inquiry_action"]
    else:
        row["out_of_stock_marker"] = "ناموجود" in text
        row["has_quote_or_supply_path"] = any(token in text for token in ("پیش‌فاکتور", "پیش فاکتور", "استعلام تأمین", "استعلام تامین", "محصول جایگزین"))
        row["ok"] = r.status_code == 200 and row["out_of_stock_marker"]
    return row

def main():
    session = requests.Session()
    retry = Retry(total=4, connect=4, read=4, status=4, backoff_factor=1.0, status_forcelist=[429,500,502,503,504], allowed_methods=frozenset(["GET"]))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))

    products = []
    page_counts = []
    for page in range(1, 21):
        r = session.get(
            BASE + "/wp-json/wc/store/v1/products",
            params={"per_page": 100, "page": page, "_fields": FIELDS},
            headers={"User-Agent": "K20-Phase28-Catalog/1.0"},
            timeout=90,
        )
        if r.status_code == 400 and page > 1:
            break
        r.raise_for_status()
        batch = r.json()
        page_counts.append({"page": page, "count": len(batch)})
        if not batch:
            break
        products.extend(batch)
        if len(batch) < 100:
            break

    unique = {int(p["id"]): p for p in products}
    products = list(unique.values())

    positive = [p for p in products if price_state(p) == "positive"]
    zero = [p for p in products if price_state(p) == "zero"]
    missing = [p for p in products if price_state(p) == "missing"]
    invalid = [p for p in products if price_state(p) == "invalid"]
    oos = [p for p in products if not bool(p.get("is_in_stock"))]
    in_stock = [p for p in products if bool(p.get("is_in_stock"))]
    nonp = [p for p in products if not bool(p.get("is_purchasable"))]
    purch = [p for p in products if bool(p.get("is_purchasable"))]
    zero_in_stock = [p for p in zero if bool(p.get("is_in_stock"))]
    zero_oos = [p for p in zero if not bool(p.get("is_in_stock"))]
    oos_positive = [p for p in oos if price_state(p) == "positive"]
    anomalies = [p for p in products if bool(p.get("is_in_stock")) and price_state(p) == "positive" and not bool(p.get("is_purchasable"))]

    zero_samples = sorted(zero_in_stock, key=lambda p: int(p["id"]), reverse=True)[:5]
    oos_samples = sorted(oos_positive, key=lambda p: int(p["id"]), reverse=True)[:5]
    ui_checks = [page_check(session, p, "zero_price_in_stock") for p in zero_samples]
    ui_checks += [page_check(session, p, "out_of_stock_positive_price") for p in oos_samples]

    out = {
        "schema_version": "k20-phase28-pricing-availability-audit-v1",
        "phase": 28,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not invalid and not anomalies else "REVIEW",
        "page_counts": page_counts,
        "summary": {
            "published_products": len(products),
            "in_stock": len(in_stock),
            "out_of_stock": len(oos),
            "purchasable": len(purch),
            "non_purchasable": len(nonp),
            "price_positive": len(positive),
            "price_zero": len(zero),
            "price_missing": len(missing),
            "price_invalid": len(invalid),
            "zero_price_in_stock": len(zero_in_stock),
            "zero_price_out_of_stock": len(zero_oos),
            "out_of_stock_positive_price": len(oos_positive),
            "in_stock_positive_price_non_purchasable": len(anomalies),
        },
        "invariants": {
            "all_non_purchasable_are_zero_or_missing_price": all(price_state(p) in ("zero","missing") for p in nonp),
            "no_positive_price_in_stock_purchasability_bug": len(anomalies) == 0,
            "no_missing_price_records": len(missing) == 0,
            "no_invalid_price_records": len(invalid) == 0,
        },
        "zero_price_category_breakdown": category_breakdown(zero),
        "out_of_stock_category_breakdown": category_breakdown(oos),
        "zero_price_products": [compact(p) for p in sorted(zero, key=lambda p: int(p["id"]), reverse=True)],
        "out_of_stock_products": [compact(p) for p in sorted(oos, key=lambda p: int(p["id"]), reverse=True)],
        "technical_anomalies": [compact(p) for p in anomalies],
        "ui_sample_checks": ui_checks,
        "guardrails": {
            "price_writes": 0,
            "stock_writes": 0,
            "product_status_writes": 0,
            "catalog_visibility_writes": 0,
            "customer_or_order_data_read": False,
        },
        "interpretation": {
            "zero_price": "Requires verified price-source remediation; do not invent or auto-fill price.",
            "out_of_stock": "Preserve useful SEO pages unless discontinuation is verified; prioritize supply/alternative CTA rather than blind deletion.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "status": out["status"], "summary": out["summary"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
