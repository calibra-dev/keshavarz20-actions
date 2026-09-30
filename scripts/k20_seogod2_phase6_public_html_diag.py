#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "seo-god2" / "phase6-public-html-diagnostic-135349-20260930.json"
PID = 135349

def fetch(url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], str]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45, context=ssl.create_default_context()) as r:
        body = r.read().decode("utf-8", errors="replace")
        return int(getattr(r, "status", 200)), {k.lower(): v for k, v in r.headers.items()}, body

def around(text: str, pattern: str, limit: int = 8, radius: int = 320) -> list[str]:
    out = []
    for m in re.finditer(pattern, text, re.I | re.S):
        a = max(0, m.start() - radius)
        b = min(len(text), m.end() + radius)
        snip = re.sub(r"\s+", " ", text[a:b]).strip()
        out.append(snip[:1200])
        if len(out) >= limit:
            break
    return out


def extract_related_widget(html: str) -> dict:
    opener = re.search(
        r'<div\\b[^>]*class=["\\'][^"\\']*\\bwidget-related-products\\b[^"\\']*["\\'][^>]*>',
        html,
        re.I | re.S,
    )
    if not opener:
        return {"present": False, "bytes": 0, "slider_items": 0, "product_links": [], "text_sample": ""}
    token_re = re.compile(r'<div\\b[^>]*>|</div\\s*>', re.I | re.S)
    depth = 0
    end = None
    for m in token_re.finditer(html, opener.start()):
        tok = m.group(0).lower()
        if tok.startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                end = m.end()
                break
    if end is None:
        block = html[opener.start():]
    else:
        block = html[opener.start():end]
    links = []
    for m in re.finditer(r'href=["\\']([^"\\']+/product/[^"\\']*)["\\']', block, re.I):
        url = m.group(1)
        if url not in links:
            links.append(url)
        if len(links) >= 20:
            break
    text_only = re.sub(r'<script\\b[^>]*>[\\s\\S]*?</script>', ' ', block, flags=re.I)
    text_only = re.sub(r'<style\\b[^>]*>[\\s\\S]*?</style>', ' ', text_only, flags=re.I)
    text_only = re.sub(r'<[^>]+>', ' ', text_only)
    text_only = re.sub(r'\\s+', ' ', text_only).strip()
    return {
        "present": True,
        "bytes": len(block.encode("utf-8")),
        "slider_items": len(re.findall(r'class=["\\'][^"\\']*\\bslider-item\\b', block, re.I)),
        "product_links": links,
        "product_link_count": len(links),
        "text_sample": text_only[:1200],
    }

def main() -> None:
    base = os.environ["WP_BASE_URL"].rstrip("/")
    user = os.environ["WP_USERNAME"]
    password = os.environ["WP_APP_PASSWORD"]
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()

    api_url = f"{base}/wp-json/wc/v3/products/{PID}?context=edit"
    status, _, raw = fetch(api_url, {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
        "User-Agent": "k20-phase6-html-diagnostic/1.0",
    })
    product = json.loads(raw)
    permalink = product["permalink"]

    sep = "&" if "?" in permalink else "?"
    bypass = permalink + sep + "k20_phase6_audit=20260930T1006Z"
    variants = {
        "normal": permalink,
        "bypass": bypass,
    }

    result = {
        "schema_version": "seo-god2-phase6-public-html-diagnostic-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "product_id": PID,
        "api_status": status,
        "permalink": permalink,
        "woo_fields": {
            "related_ids": product.get("related_ids") or [],
            "upsell_ids": product.get("upsell_ids") or [],
            "cross_sell_ids": product.get("cross_sell_ids") or [],
        },
        "variants": {},
    }

    for name, url in variants.items():
        http, headers, html = fetch(url, {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0 (compatible; K20Phase6HTMLDiagnostic/1.0)",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        })
        selected = {k: headers.get(k) for k in [
            "cache-control", "age", "server", "x-litespeed-cache",
            "x-litespeed-cache-control", "x-cache", "cf-cache-status", "vary"
        ] if headers.get(k) is not None}
        patterns = {
            "guard_marker": r"k20-phase6-related-guard-135349",
            "basket_heading": r"چک.{0,4}لیست\s+تکمیل\s+خرید",
            "class_related_products": r'class=["\'][^"\']*\brelated\b[^"\']*\bproducts\b[^"\']*["\']',
            "literal_related_products": r"related\.products",
            "woocommerce_related_function": r"woocommerce_(?:output_)?related_products",
        }
        result["variants"][name] = {
            "url": url,
            "http_status": http,
            "bytes": len(html.encode("utf-8")),
            "headers": selected,
            "marker_present": "k20-phase6-related-guard-135349" in html,
            "basket_heading_present": "چک‌لیست تکمیل خرید" in html,
            "matches": {key: len(list(re.finditer(pat, html, re.I | re.S))) for key, pat in patterns.items()},
            "snippets": {key: around(html, pat) for key, pat in patterns.items() if key not in ("guard_marker","basket_heading")},
            "related_widget": extract_related_widget(html),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "product_id": PID,
        "woo_fields": result["woo_fields"],
        "normal": result["variants"]["normal"]["matches"],
        "bypass": result["variants"]["bypass"]["matches"],
        "normal_marker": result["variants"]["normal"]["marker_present"],
        "bypass_marker": result["variants"]["bypass"]["marker_present"],
        "normal_headers": result["variants"]["normal"]["headers"],
        "bypass_headers": result["variants"]["bypass"]["headers"],
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
