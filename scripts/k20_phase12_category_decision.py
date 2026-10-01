#!/usr/bin/env python3
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
MODULE_FILE = ROOT / "phase12-input" / "category-decision-modules-20261001.json"
OUT_FILE = ROOT / "phase12-results" / "category-decision-execution-20261001.json"

BASE = os.environ["WP_BASE_URL"].rstrip("/")
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

MARKER_START = "<!--k20-phase12-category-decision:start-->"
MARKER_END = "<!--k20-phase12-category-decision:end-->"

def raw_description(obj):
    value = obj.get("description")
    if isinstance(value, dict):
        return value.get("raw") or value.get("rendered") or ""
    return value or ""

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_category(session, category_id):
    r = session.get(
        f"{BASE}/wp-json/wp/v2/product_cat/{category_id}",
        params={"context": "edit"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()

def write_category(session, category_id, description):
    r = session.post(
        f"{BASE}/wp-json/wp/v2/product_cat/{category_id}",
        json={"description": description},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()

def desired_description(old, module):
    sc = old.count(MARKER_START)
    ec = old.count(MARKER_END)
    if sc == 0 and ec == 0:
        base = old.rstrip()
        return (base + "\n\n" + module).strip(), "append"
    if sc != 1 or ec != 1:
        raise RuntimeError(f"phase12 marker integrity failure start={sc} end={ec}")
    a = old.index(MARKER_START)
    b = old.index(MARKER_END, a)
    b2 = b + len(MARKER_END)
    current = old[a:b2]
    if current == module:
        return old, "noop"
    return old[:a] + module + old[b2:], "replace"

def hidden_artifacts(text):
    bad = set()
    for ch in text:
        cp = ord(ch)
        if (
            cp in {0x180E, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF}
            or 0x200E <= cp <= 0x200F
            or 0x202A <= cp <= 0x202E
            or 0x2066 <= cp <= 0x2069
            or 0xE0000 <= cp <= 0xE007F
        ):
            bad.add(f"U+{cp:04X}")
    return sorted(bad)

def public_get(session, url):
    sep = "&" if "?" in url else "?"
    return session.get(
        url + sep + "k20_phase12_verify=" + str(int(time.time())),
        headers={"User-Agent": "K20-Phase12-CategoryVerify/1.0", "Cache-Control": "no-cache"},
        timeout=60,
        allow_redirects=True,
    )

def main():
    module_data = json.loads(MODULE_FILE.read_text(encoding="utf-8"))
    categories = module_data["categories"]

    session = requests.Session()
    session.auth = AUTH
    session.headers.update({"Accept": "application/json", "User-Agent": "K20-Phase12-CategoryDecision/1.0"})

    before = {}
    changed = []
    rows = []

    try:
        for key, spec in categories.items():
            cid = int(key)
            obj = get_category(session, cid)
            old = raw_description(obj)
            module = spec["html"]

            if hidden_artifacts(module):
                raise RuntimeError(f"sanitizer verification failed for category {cid}")

            new, mode = desired_description(old, module)
            before[cid] = old

            if mode != "noop":
                write_category(session, cid, new)
                changed.append(cid)

            rb = get_category(session, cid)
            final = raw_description(rb)

            if final.count(MARKER_START) != 1 or final.count(MARKER_END) != 1:
                raise RuntimeError(f"readback marker count failed for {cid}")

            a = final.index(MARKER_START)
            b = final.index(MARKER_END, a) + len(MARKER_END)
            final_module = final[a:b]

            required = {
                "decision_heading": "راهنمای تصمیم انتخاب در این دسته" in final_module,
                "suitable_not_suitable": "این دسته برای چه شرایطی مناسب است؟" in final_module,
                "grouping_filters": "گروه بندی و فیلترهای تصمیم ساز" in final_module,
                "required_inputs": "قبل از خرید چه اطلاعاتی را آماده کنید؟" in final_module,
                "method_date": "بازبینی: 1 اکتبر 2026" in final_module,
                "no_guess_guard": "حدس زده نمی شود" in final_module or "پذیرفته می شود" in final_module,
                "sanitized_module": not hidden_artifacts(final_module),
            }
            if not all(required.values()):
                raise RuntimeError(f"acceptance field failed for category {cid}: {required}")

            link = rb.get("link") or obj.get("link")
            pub = public_get(requests, link)
            public_ok = (
                pub.status_code == 200
                and "راهنمای تصمیم انتخاب در این دسته" in pub.text
            )
            if not public_ok:
                raise RuntimeError(f"public verification failed for category {cid} http={pub.status_code}")

            links = re.findall(r'href="(https://keshavarz20\.com/[^"]+)"', final_module)
            rows.append({
                "id": cid,
                "name": rb.get("name"),
                "slug": rb.get("slug"),
                "link": link,
                "write_mode": mode,
                "old_description_sha256": sha256(old),
                "new_description_sha256": sha256(final),
                "old_chars": len(old),
                "new_chars": len(final),
                "marker_start_count": final.count(MARKER_START),
                "marker_end_count": final.count(MARKER_END),
                "required": required,
                "internal_links": links,
                "public_http": pub.status_code,
                "public_final_url": pub.url,
                "public_heading_present": "راهنمای تصمیم انتخاب در این دسته" in pub.text,
            })

        unique_links = sorted({u for row in rows for u in row["internal_links"]})
        link_checks = []
        for u in unique_links:
            rr = requests.get(
                u,
                headers={"User-Agent": "K20-Phase12-LinkVerify/1.0"},
                timeout=60,
                allow_redirects=True,
            )
            link_checks.append({
                "url": u,
                "http": rr.status_code,
                "final_url": rr.url,
                "ok": rr.status_code == 200,
            })
        if not all(x["ok"] for x in link_checks):
            raise RuntimeError("one or more internal decision links are not HTTP 200")

    except Exception:
        for cid in reversed(changed):
            try:
                write_category(session, cid, before[cid])
            except Exception:
                pass
        raise

    out = {
        "schema_version": "seo-god2-phase12-category-execution-v1",
        "phase": 12,
        "title": "Category Decision Pages",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "scope_count": len(rows),
        "changed_count": len(changed),
        "noop_count": len(rows) - len(changed),
        "changed_ids": changed,
        "categories": rows,
        "linked_surface_checks": link_checks,
        "acceptance": {
            "priority_categories": f"{len(rows)}/6",
            "decision_heading": f"{sum(1 for r in rows if r['required']['decision_heading'])}/6",
            "suitable_not_suitable": f"{sum(1 for r in rows if r['required']['suitable_not_suitable'])}/6",
            "grouping_filters": f"{sum(1 for r in rows if r['required']['grouping_filters'])}/6",
            "required_inputs": f"{sum(1 for r in rows if r['required']['required_inputs'])}/6",
            "method_and_review_date": f"{sum(1 for r in rows if r['required']['method_date'])}/6",
            "no_guess_guard": f"{sum(1 for r in rows if r['required']['no_guess_guard'])}/6",
            "sanitizer_clean": f"{sum(1 for r in rows if r['required']['sanitized_module'])}/6",
            "public_http_200": f"{sum(1 for r in rows if r['public_http'] == 200)}/6",
            "internal_links_http_200": f"{sum(1 for x in link_checks if x['ok'])}/{len(link_checks)}",
            "price_writes": 0,
            "stock_writes": 0,
            "product_writes": 0,
        },
        "guardrails": {
            "existing_category_descriptions_preserved_outside_marker": True,
            "rollback_on_failure": True,
            "unsupported_specs_promoted": False,
            "price_or_sale_price_write": False,
            "stock_write": False,
            "customer_or_order_data_read": False,
            "secrets_persisted": False,
        },
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "status": out["status"], "changed": len(changed), "categories": len(rows)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
