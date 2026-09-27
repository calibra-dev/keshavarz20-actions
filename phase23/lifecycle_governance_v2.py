#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


class Phase23Error(RuntimeError):
    pass


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        x = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=UTC)
    except ValueError:
        return None


def age_days(value: Any, now: dt.datetime) -> int | None:
    x = parse_time(value)
    return None if x is None else max(0, (now - x.astimezone(UTC)).days)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dependency_snapshot() -> dict[str, Any]:
    p20 = load_json(ROOT / "growth-os" / "phase20-acceptance-2026-09-27.json")
    p21 = load_json(ROOT / "phase21-results" / "authority-network-2026-09-27.json")
    p22 = load_json(ROOT / "phase22-results" / "acceptance-v2-2026-09-27.json")
    return {
        "phase20_intent_graph": p20.get("status"),
        "phase21_authority_network": p21.get("status"),
        "phase22_decision_model": p22.get("status"),
    }


def classify(kind: str, item: dict[str, Any], policy: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    status = str(item.get("status") or "unknown").lower()
    modified = item.get("modified_gmt") or item.get("date_modified_gmt") or item.get("modified")
    days = age_days(modified, now)
    threshold = int(policy["review_days"][kind])

    actions: list[str] = []
    reasons: list[str] = []
    priority = "P3"

    public = status in {"publish", "published"}
    if kind in {"posts", "pages"} and not public:
        actions.append("no_public_freshness_action")
        reasons.append(f"status={status}; not a normal published public document")
    elif days is None:
        actions.append("manual_date_review")
        reasons.append("modified timestamp unavailable or invalid")
        priority = "P1"
    elif days >= threshold:
        actions.append("substantive_review")
        reasons.append(f"age={days}d >= review interval={threshold}d")
        priority = "P2"

    if kind == "products":
        stock = str(item.get("stock_status") or "unknown").lower()
        if stock == "outofstock":
            actions.append("verify_supply_state_keep_url")
            reasons.append("out-of-stock is not evidence of discontinuation")
            priority = "P2" if priority == "P3" else priority
        elif stock == "onbackorder":
            actions.append("verify_backorder_copy_and_schema")
            reasons.append("backorder must be represented accurately")
            priority = "P2" if priority == "P3" else priority
        elif stock == "instock":
            pass
        else:
            actions.append("verify_stock_state")
            reasons.append(f"unknown stock_status={stock}")
            priority = "P1"

    if not actions:
        actions.append("no_action_due")

    return {
        "id": item.get("id"),
        "kind": kind,
        "slug": item.get("slug"),
        "status": status,
        "modified_gmt": modified,
        "age_days": days,
        "stock_status": item.get("stock_status") if kind == "products" else None,
        "priority": priority,
        "actions": sorted(set(actions)),
        "reasons": reasons,
        "dateModified_mutation_allowed": False,
        "discontinued_inferred": False,
        "redirect_inferred": False,
        "canonical_change_allowed": False,
    }


def governance_assets(policy: dict[str, Any], now: dt.datetime) -> list[dict[str, Any]]:
    authority = load_json(ROOT / "phase21-results" / "authority-network-2026-09-27.json")
    p20 = load_json(ROOT / "growth-os" / "phase20-acceptance-2026-09-27.json")
    p22 = load_json(ROOT / "phase22-results" / "acceptance-v2-2026-09-27.json")

    assets = [
        {
            "asset_id": "phase20-intent-graph",
            "kind": "governance_asset",
            "last_verified": p20.get("verified_at"),
            "review_days": policy["governance_review_days"]["intent_graph"],
            "trigger": "intent conflict, duplicate URL attempt, material routing change",
        },
        {
            "asset_id": "phase21-authority-network",
            "kind": "governance_asset",
            "last_verified": authority.get("generated_at_utc"),
            "review_days": policy["governance_review_days"]["authority_network"],
            "trigger": "source invalidation, manufacturer evidence change, new first-party evidence",
        },
        {
            "asset_id": "phase22-decision-model",
            "kind": "governance_asset",
            "last_verified": p22.get("verified_at"),
            "review_days": policy["governance_review_days"]["decision_model"],
            "trigger": "decision rule change, compatibility schema change, tool-route change",
        },
    ]

    for a in assets:
        a["age_days"] = age_days(a["last_verified"], now)
        a["review_due"] = a["age_days"] is None or a["age_days"] >= int(a["review_days"])
        a["dateModified_mutation_allowed"] = False
    return assets


def build_report(
    posts: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    products: list[dict[str, Any]],
    policy: dict[str, Any],
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    now = now or dt.datetime.now(UTC)
    deps = dependency_snapshot()

    queues = {
        "posts": [classify("posts", x, policy, now) for x in posts],
        "pages": [classify("pages", x, policy, now) for x in pages],
        "products": [classify("products", x, policy, now) for x in products],
    }
    all_rows = [x for group in queues.values() for x in group]
    due = [x for x in all_rows if x["actions"] != ["no_action_due"]]
    assets = governance_assets(policy, now)

    priority_counts = {p: sum(1 for x in due if x["priority"] == p) for p in ("P0", "P1", "P2", "P3")}
    stock = queues["products"]

    checks = {
        "dependencies_current": (
            deps["phase20_intent_graph"] == "PASS_CANARY_DRAFT"
            and deps["phase21_authority_network"] == "PASS_IRAN_FIRST_AUTHORITY_V2"
            and deps["phase22_decision_model"] == "PASS_FUNCTIONAL_V2_GUARDED_DEPLOYMENT"
        ),
        "no_fake_freshness": policy["rules"].get("stale_review_does_not_touch_dateModified") is True,
        "outofstock_not_discontinued": all(not x["discontinued_inferred"] for x in stock),
        "no_auto_redirect_inference": all(not x["redirect_inferred"] for x in all_rows),
        "no_auto_canonical_change": all(not x["canonical_change_allowed"] for x in all_rows),
        "no_bulk_rewrite": policy["rules"].get("automatic_bulk_rewrite_for_freshness") is False,
        "live_inventory_nonempty": len(all_rows) > 0,
    }

    return {
        "phase": 23,
        "title": "Lifecycle & Freshness Governance v2",
        "model_version": "k20-lifecycle-governance-v2",
        "generated_at_utc": now.isoformat(),
        "status": "PASS_LIFECYCLE_GOVERNANCE_V2" if all(checks.values()) else "FAIL_LIFECYCLE_GOVERNANCE_V2",
        "dependencies": deps,
        "checks": checks,
        "inventory": {"posts": len(posts), "pages": len(pages), "products": len(products)},
        "review_queue_count": len(due),
        "priority_counts": priority_counts,
        "stock_transition_watch": {
            "outofstock": sum(1 for x in stock if x.get("stock_status") == "outofstock"),
            "onbackorder": sum(1 for x in stock if x.get("stock_status") == "onbackorder"),
            "unknown": sum(1 for x in stock if x.get("stock_status") not in {"outofstock", "onbackorder", "instock"}),
        },
        "governance_assets": assets,
        "review_queue": due,
        "mutations": {
            "content": 0,
            "dateModified": 0,
            "stock": 0,
            "price": 0,
            "status": 0,
            "redirect": 0,
            "canonical": 0,
        },
        "rules": policy["rules"],
    }


def _auth_header(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def fetch_json(url: str, auth: str) -> tuple[Any, dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(1, 5):
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": auth,
                "Accept": "application/json",
                "User-Agent": "K20-Phase23-v2/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "replace")
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return json.loads(raw), headers
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 4:
                time.sleep(attempt * 2)
    raise Phase23Error(f"REST fetch failed after retries: {url}: {last_error}")


def paginate(base: str, route: str, auth: str, params: dict[str, str], max_pages: int = 50) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        q = dict(params)
        q.update({"per_page": "100", "page": str(page)})
        url = f"{base.rstrip('/')}{route}?{urllib.parse.urlencode(q)}"
        try:
            data, headers = fetch_json(url, auth)
        except Phase23Error as exc:
            if "HTTP Error 400" in str(exc) and page > 1:
                break
            raise
        if not isinstance(data, list):
            raise Phase23Error(f"Expected list from {route}, got {type(data).__name__}")
        rows.extend(data)
        total_pages = int(headers.get("x-wp-totalpages", "0") or 0)
        if len(data) < 100 or (total_pages and page >= total_pages):
            break
    return rows


def validate_report(report: dict[str, Any]) -> None:
    if report["status"] != "PASS_LIFECYCLE_GOVERNANCE_V2":
        failed = [k for k, v in report["checks"].items() if not v]
        raise Phase23Error("failed checks: " + ", ".join(failed))
    if any(report["mutations"].values()):
        raise Phase23Error("Phase 23 audit must be read-only")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    base = os.environ.get("WP_BASE_URL", "").strip()
    user = os.environ.get("WP_USERNAME", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not (base and user and password):
        raise SystemExit("WP_BASE_URL/WP_USERNAME/WP_APP_PASSWORD are required")

    policy = load_json(Path(args.policy))
    auth = _auth_header(user, password)

    posts = paginate(base, "/wp-json/wp/v2/posts", auth, {"context": "edit", "_fields": "id,slug,status,modified_gmt"})
    pages = paginate(base, "/wp-json/wp/v2/pages", auth, {"context": "edit", "_fields": "id,slug,status,modified_gmt"})
    products = paginate(base, "/wp-json/wc/v3/products", auth, {"status": "any", "_fields": "id,slug,status,date_modified_gmt,stock_status"})

    report = build_report(posts, pages, products, policy)
    validate_report(report)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "inventory": report["inventory"],
        "review_queue_count": report["review_queue_count"],
        "priority_counts": report["priority_counts"],
        "stock_transition_watch": report["stock_transition_watch"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
