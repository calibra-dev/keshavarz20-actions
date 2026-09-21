#!/usr/bin/env python3
import os, json, re
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests

BASE = os.environ["WP_BASE_URL"].rstrip("/")
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
S = requests.Session()
S.auth = AUTH
S.headers.update({
    "Accept": "application/json",
    "User-Agent": "k20-seogod1-phase11-13-audit/1.0",
    "Cache-Control": "no-cache",
})

def req(method, path, params=None):
    url = urljoin(BASE + "/", path.lstrip("/"))
    r = S.request(method, url, params=params, timeout=120)
    return r

def jget(path, params=None):
    r = req("GET", path, params=params)
    data = None
    try:
        data = r.json()
    except Exception:
        pass
    return r, data

def total_from(r):
    try:
        return int(r.headers.get("X-WP-Total", "0") or 0)
    except Exception:
        return 0

def page_by_slug(slug):
    for typ in ("pages", "posts"):
        r, data = jget(f"wp-json/wp/v2/{typ}", {
            "slug": slug, "context": "edit", "per_page": 5,
            "_fields": "id,slug,status,link,title,content,modified_gmt,comment_status"
        })
        if r.ok and isinstance(data, list) and data:
            o = data[0]
            raw = ((o.get("content") or {}).get("raw") or "")
            return {
                "found": True,
                "type": typ[:-1],
                "id": o.get("id"),
                "slug": o.get("slug"),
                "status": o.get("status"),
                "link": o.get("link"),
                "modified_gmt": o.get("modified_gmt"),
                "comment_status": o.get("comment_status"),
                "chars": len(raw),
                "signals": {
                    "quote": bool(re.search(r"پیش.?فاکتور|استعلام", raw, re.I)),
                    "whatsapp": "wa.me/" in raw or "whatsapp" in raw.lower(),
                    "consent": bool(re.search(r"رضایت|حریم خصوصی|لغو|عدم.?تماس|unsubscribe", raw, re.I)),
                    "utm": "utm_" in raw.lower(),
                    "review": bool(re.search(r"نظر|تجربه خرید|امتیاز", raw, re.I)),
                    "shipping": bool(re.search(r"ارسال|باربری|حمل|زمان تحویل", raw, re.I)),
                }
            }
    return {"found": False}

# Bridge health: only capability summary, no secrets.
bridge = {}
r, data = jget("wp-json/keshavarz20-ops/v2/health")
bridge = {
    "http": r.status_code,
    "ok": bool(r.ok),
    "status": (data or {}).get("status") if isinstance(data, dict) else None,
    "auth": (data or {}).get("auth") if isinstance(data, dict) else None,
    "https": (data or {}).get("https") if isinstance(data, dict) else None,
}

# Route capability inventory, reduced to booleans only.
r, index = jget("wp-json/")
route_names = list((index or {}).get("routes", {}).keys()) if isinstance(index, dict) else []
route_text = "\n".join(route_names).lower()
caps = {
    "contact_form_route": any(k in route_text for k in ["contact-form-7", "wpforms", "fluentform", "forminator", "gravityforms"]),
    "crm_route": any(k in route_text for k in ["crm", "fluentcrm", "mailpoet"]),
    "quote_or_proforma_route": any(k in route_text for k in ["quote", "proforma", "rfq", "request-a-quote"]),
    "review_route": "/wc/v3/products/reviews" in route_text or "product-reviews" in route_text,
    "comments_route": "/wp/v2/comments" in route_text,
}

# Shipping settings, no commercial mutation.
shipping = {"zones": [], "gate_known": False}
rz, zones = jget("wp-json/wc/v3/shipping/zones", {"per_page": 100})
if rz.ok and isinstance(zones, list):
    for z in zones:
        zid = z.get("id")
        rm, methods = jget(f"wp-json/wc/v3/shipping/zones/{zid}/methods")
        method_rows = []
        if rm.ok and isinstance(methods, list):
            for m in methods:
                settings = m.get("settings") or {}
                # Keep only non-price operational state. Never persist costs.
                method_rows.append({
                    "id": m.get("id"),
                    "method_id": m.get("method_id"),
                    "title": m.get("title"),
                    "enabled": m.get("enabled"),
                    "supports": m.get("method_id") in ("flat_rate", "free_shipping", "local_pickup"),
                    "has_cost_setting": "cost" in settings,
                })
        shipping["zones"].append({
            "id": zid,
            "name": z.get("name"),
            "methods": method_rows,
        })
shipping["gate_known"] = bool(shipping["zones"])

# Review and order counts only. No names, emails, IDs, products, addresses, or notes are persisted.
reviews = {}
rr, rv = jget("wp-json/wc/v3/products/reviews", {"per_page": 1})
reviews["endpoint_http"] = rr.status_code
reviews["total_visible_records"] = total_from(rr) if rr.ok else None
reviews["endpoint_ok"] = bool(rr.ok)

orders = {}
ro, ov = jget("wp-json/wc/v3/orders", {"status": "completed", "per_page": 1})
orders["completed_endpoint_http"] = ro.status_code
orders["completed_total"] = total_from(ro) if ro.ok else None
orders["completed_orders_exist"] = bool((total_from(ro) if ro.ok else 0) > 0)
orders["pii_persisted"] = False

# Products review readiness count only.
rp, products = jget("wp-json/wc/v3/products", {"status": "publish", "per_page": 100, "page": 1})
product_review_readiness = {
    "endpoint_http": rp.status_code,
    "sample_size": 0,
    "reviews_allowed_count": 0,
}
if rp.ok and isinstance(products, list):
    product_review_readiness["sample_size"] = len(products)
    product_review_readiness["reviews_allowed_count"] = sum(1 for p in products if p.get("reviews_allowed"))

slugs = [
    "drip-tape-length-fittings-calculator",
    "one-hectare-drip-irrigation-basket",
    "irrigation-product-comparator",
    "contact-us",
    "shipping",
    "privacy-policy",
    "return-policy",
]
pages = {slug: page_by_slug(slug) for slug in slugs}

# Public probes for the three commerce tools.
public = {}
for key, slug in {
    "calculator": "drip-tape-length-fittings-calculator",
    "basket": "one-hectare-drip-irrigation-basket",
    "comparator": "irrigation-product-comparator",
}.items():
    url = BASE + "/" + slug + "/"
    try:
        pr = requests.get(url, timeout=45, headers={"User-Agent": "k20-seogod1-phase11-13-audit/1.0", "Cache-Control": "no-cache"})
        body = pr.text or ""
        public[key] = {
            "http": pr.status_code,
            "quote_signal": bool(re.search(r"پیش.?فاکتور|استعلام", body, re.I)),
            "whatsapp_signal": "wa.me/" in body or "whatsapp" in body.lower(),
            "utm_signal": "utm_" in body.lower(),
        }
    except Exception as e:
        public[key] = {"http": 0, "error": type(e).__name__}

# Gate decisions are evidence-driven and intentionally conservative.
active_shipping_methods = []
for z in shipping["zones"]:
    for m in z["methods"]:
        if m.get("enabled"):
            active_shipping_methods.append({"zone": z.get("name"), "method_id": m.get("method_id"), "title": m.get("title")})

phase11 = {
    "shipping_model_known": shipping["gate_known"],
    "active_shipping_method_count": len(active_shipping_methods),
    "active_shipping_methods": active_shipping_methods,
    "quote_backend_capability": caps["quote_or_proforma_route"],
    "quote_frontend_entrypoints": {
        k: {"quote_signal": v.get("quote_signal"), "whatsapp_signal": v.get("whatsapp_signal")}
        for k, v in public.items()
    },
}
phase12 = {
    "reviews_endpoint_ok": reviews["endpoint_ok"],
    "existing_review_count": reviews["total_visible_records"],
    "completed_orders_exist": orders["completed_orders_exist"],
    "sample_products_review_enabled": product_review_readiness,
    "form_capability": caps["contact_form_route"],
    "comments_capability": caps["comments_route"],
}
phase13 = {
    "crm_backend_capability": caps["crm_route"],
    "form_capability": caps["contact_form_route"],
    "known_lead_entrypoints_have_utm": {k: v.get("utm_signal") for k, v in public.items()},
    "known_lead_entrypoints_have_whatsapp": {k: v.get("whatsapp_signal") for k, v in public.items()},
    "privacy_consent_signal_on_known_pages": any(
        (p.get("signals") or {}).get("consent") for p in pages.values() if p.get("found")
    ),
}

out = {
    "program": "SEO God1",
    "phases": [11, 12, 13],
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "privacy": {
        "customer_pii_persisted": False,
        "order_ids_persisted": False,
        "customer_messages_persisted": False,
    },
    "bridge": bridge,
    "capabilities": caps,
    "shipping": shipping,
    "reviews": reviews,
    "orders": orders,
    "pages": pages,
    "public_tools": public,
    "phase11_baseline": phase11,
    "phase12_baseline": phase12,
    "phase13_baseline": phase13,
}

os.makedirs("seo-god1-results", exist_ok=True)
with open("seo-god1-results/phase11-13-baseline.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("SEO_GOD1_PHASE11_13_BASELINE_OK", json.dumps({
    "bridge": bridge,
    "caps": caps,
    "shipping_active": len(active_shipping_methods),
    "reviews_total": reviews["total_visible_records"],
    "completed_orders_exist": orders["completed_orders_exist"],
    "public": public,
}, ensure_ascii=False))
