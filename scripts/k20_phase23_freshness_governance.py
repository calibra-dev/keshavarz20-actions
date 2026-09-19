#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

UTC = dt.timezone.utc


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        x = dt.datetime.fromisoformat(text)
        return x if x.tzinfo else x.replace(tzinfo=UTC)
    except ValueError:
        return None


def age_days(value: Any, now: dt.datetime) -> int | None:
    x = parse_time(value)
    if not x:
        return None
    return max(0, (now - x.astimezone(UTC)).days)


def classify(kind: str, item: Dict[str, Any], policy: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    threshold = int(policy["review_days"][kind])
    modified = item.get("modified_gmt") or item.get("date_modified_gmt") or item.get("modified")
    days = age_days(modified, now)
    status = str(item.get("status") or "unknown")
    actions: List[str] = []
    reasons: List[str] = []

    if status not in {"publish", "published"} and kind in {"posts", "pages"}:
        actions.append("no_public_freshness_action")
        reasons.append(f"status={status}; item is not a normal published public document")
    elif days is None:
        actions.append("manual_date_review")
        reasons.append("modified timestamp unavailable")
    elif days >= threshold:
        actions.append("substantive_review")
        reasons.append(f"last substantive modified timestamp is {days} days old (review interval {threshold} days)")

    if kind == "products":
        stock = str(item.get("stock_status") or "unknown")
        if stock == "outofstock":
            actions.append("verify_supply_state_keep_url")
            reasons.append("out-of-stock is a commerce state, not proof of discontinuation")
        elif stock == "onbackorder":
            actions.append("verify_backorder_copy")
            reasons.append("backorder state should be reflected accurately without claiming immediate availability")
        elif stock == "instock":
            reasons.append("stock state currently reports in-stock")
        else:
            actions.append("verify_stock_state")
            reasons.append(f"unrecognized/unknown stock_status={stock}")

    return {
        "id": item.get("id"),
        "kind": kind,
        "slug": item.get("slug"),
        "status": status,
        "modified_gmt": modified,
        "age_days": days,
        "stock_status": item.get("stock_status") if kind == "products" else None,
        "actions": sorted(set(actions)),
        "reasons": reasons,
        "dateModified_mutation_allowed": False,
        "discontinued_inferred": False,
    }


def _auth_header(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def fetch_json(url: str, auth: str) -> Tuple[Any, Dict[str, str]]:
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json", "User-Agent": "K20-Phase23/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return data, headers


def paginate(base: str, route: str, auth: str, params: Dict[str, str], max_pages: int = 40) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        q = dict(params)
        q.update({"per_page": "100", "page": str(page)})
        url = f"{base.rstrip('/')}{route}?{urllib.parse.urlencode(q)}"
        try:
            data, headers = fetch_json(url, auth)
        except urllib.error.HTTPError as e:
            if e.code == 400 and page > 1:
                break
            raise
        if not isinstance(data, list):
            raise RuntimeError(f"Expected list from {route}, got {type(data).__name__}")
        rows.extend(data)
        total_pages = int(headers.get("x-wp-totalpages", "0") or 0)
        if len(data) < 100 or (total_pages and page >= total_pages):
            break
    return rows


def build_report(posts: List[Dict[str, Any]], pages: List[Dict[str, Any]], products: List[Dict[str, Any]], policy: Dict[str, Any], dependency_status: str, now: dt.datetime | None = None) -> Dict[str, Any]:
    now = now or dt.datetime.now(UTC)
    queues = {
        "posts": [classify("posts", x, policy, now) for x in posts],
        "pages": [classify("pages", x, policy, now) for x in pages],
        "products": [classify("products", x, policy, now) for x in products],
    }
    due = [x for group in queues.values() for x in group if x["actions"]]
    out_of_stock = [x for x in queues["products"] if x.get("stock_status") == "outofstock"]
    backorder = [x for x in queues["products"] if x.get("stock_status") == "onbackorder"]
    checks = {
        "no_fake_freshness": policy["rules"].get("stale_review_does_not_touch_dateModified") is True,
        "outofstock_not_discontinued": policy["rules"].get("outofstock_is_not_discontinued") is True and all(not x["discontinued_inferred"] for x in out_of_stock),
        "explicit_discontinuation_evidence_required": policy["rules"].get("discontinued_requires_explicit_evidence") is True,
        "no_bulk_freshness_rewrite": policy["rules"].get("automatic_bulk_rewrite_for_freshness") is False,
        "live_inventory_nonempty": (len(posts) + len(pages) + len(products)) > 0,
    }
    functional = all(checks.values())
    dependency_pass = dependency_status == "PASS"
    return {
        "phase": 23,
        "title": "Lifecycle & Freshness Governance",
        "generated_at_utc": now.isoformat(),
        "status": "PASS" if functional and dependency_pass else ("READY_BLOCKED_BY_PHASE20" if functional else "FAIL"),
        "dependency_gate": {"phase20": dependency_status, "required_for_final_pass": True},
        "policy": policy,
        "checks": checks,
        "inventory": {"posts": len(posts), "pages": len(pages), "products": len(products)},
        "review_queue_count": len(due),
        "stock_transition_watch": {"outofstock": len(out_of_stock), "onbackorder": len(backorder)},
        "review_queue": due,
        "mutations": {"content": 0, "dateModified": 0, "stock": 0, "price": 0, "status": 0},
        "notes": [
            "A review-due flag never changes dateModified by itself.",
            "Out-of-stock never implies discontinued; explicit evidence is required.",
            "Merge/deprecate actions are recommendations only and require a separate canonical/redirect plan and verification.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--phase20", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    base = os.environ.get("WP_BASE_URL", "").strip()
    user = os.environ.get("WP_USERNAME", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not (base and user and password):
        raise SystemExit("WP_BASE_URL/WP_USERNAME/WP_APP_PASSWORD are required")

    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    phase20 = json.loads(Path(args.phase20).read_text(encoding="utf-8"))
    dep = str(phase20.get("status") or "UNKNOWN")
    auth = _auth_header(user, password)

    posts = paginate(base, "/wp-json/wp/v2/posts", auth, {"context": "edit", "status": "any"})
    pages = paginate(base, "/wp-json/wp/v2/pages", auth, {"context": "edit", "status": "any"})
    products = paginate(base, "/wp-json/wc/v3/products", auth, {"status": "any"})
    report = build_report(posts, pages, products, policy, dep)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "phase": 23,
        "status": report["status"],
        "inventory": report["inventory"],
        "review_queue_count": report["review_queue_count"],
        "stock_transition_watch": report["stock_transition_watch"],
        "dependency_gate": report["dependency_gate"],
    }, ensure_ascii=False))
    if report["status"] == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
