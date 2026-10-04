#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def dependency_snapshot() -> dict[str, Any]:
    p20 = load_json(ROOT / "phase20-results" / "final-closure-latest.json")
    p21 = load_json(ROOT / "phase21-results" / "authority-network-latest.json")
    p22 = load_json(ROOT / "phase22-results" / "acceptance-latest.json")
    return {
        "phase20": {
            "status": p20.get("status"),
            "generated_at_utc": p20.get("generated_at_utc"),
            "passed_checks": int(p20.get("passed_checks") or 0),
            "check_count": int(p20.get("check_count") or 0),
            "failed_checks": p20.get("failed_checks") or [],
            "full_wcag_automated_pass": p20.get("full_wcag_automated_pass"),
        },
        "phase21": {
            "version": p21.get("version"),
            "status": p21.get("status"),
            "generated_at_utc": p21.get("generated_at_utc"),
            "passed_checks": int((p21.get("acceptance") or {}).get("passed_checks") or 0),
            "check_count": int((p21.get("acceptance") or {}).get("check_count") or 0),
            "failed_checks": (p21.get("acceptance") or {}).get("failed_checks") or [],
            "candidate_rows": int((p21.get("full_catalog") or {}).get("candidate_rows") or 0),
        },
        "phase22": {
            "version": p22.get("version"),
            "status": p22.get("status"),
            "generated_at_utc": p22.get("generated_at_utc"),
            "passed_checks": int(p22.get("passed_checks") or 0),
            "check_count": int(p22.get("check_count") or 0),
            "failed_checks": p22.get("failed_checks") or [],
            "site_mutations": int(p22.get("site_mutations") or 0),
            "commerce_mutations": int(p22.get("commerce_mutations") or 0),
        },
    }


def _priority_max(current: str, candidate: str) -> str:
    order = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}
    return candidate if order[candidate] > order[current] else current


def classify(kind: str, item: dict[str, Any], policy: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    status = str(item.get("status") or "unknown").lower()
    modified = item.get("modified_gmt") or item.get("date_modified_gmt") or item.get("modified")
    days = age_days(modified, now)
    threshold = int(policy["review_days"][kind])
    public = status in {"publish", "published"}

    actions: list[str] = []
    reasons: list[str] = []
    priority = "P3"

    if not public:
        actions.append("internal_lifecycle_only")
        reasons.append(f"status={status}; no public freshness/URL action is allowed")
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
        if public:
            if stock == "outofstock":
                actions.append("verify_supply_state_keep_url")
                reasons.append("out-of-stock is not evidence of discontinuation")
                priority = _priority_max(priority, "P2")
            elif stock == "onbackorder":
                actions.append("verify_backorder_copy_and_schema")
                reasons.append("backorder must be represented accurately and is not in-stock")
                priority = _priority_max(priority, "P2")
            elif stock == "instock":
                pass
            else:
                actions.append("verify_stock_state")
                reasons.append(f"unknown stock_status={stock}")
                priority = "P1"
        elif stock not in {"instock", "outofstock", "onbackorder"}:
            actions.append("verify_internal_stock_state")
            reasons.append(f"non-public product has unknown stock_status={stock}")
            priority = _priority_max(priority, "P2")

    if not actions:
        actions.append("no_action_due")

    return {
        "id": item.get("id"),
        "kind": kind,
        "slug": item.get("slug"),
        "status": status,
        "public": public,
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
        "deletion_allowed": False,
    }


def governance_assets(policy: dict[str, Any], now: dt.datetime, deps: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [
        ("phase20-final-closure", "phase20", "phase20", "UX/CRO/accessibility/agent-usability evidence or renderer state changes"),
        ("phase21-authority-network", "phase21", "phase21", "authority sources, brand/identifier truth, or citation evidence materially changes"),
        ("phase22-farmer-decision", "phase22", "phase22", "decision rules, compatibility evidence, or tool routes materially change"),
    ]
    assets = []
    for asset_id, dep_key, review_key, trigger in specs:
        last_verified = deps[dep_key].get("generated_at_utc")
        days = age_days(last_verified, now)
        review_days = int(policy["governance_review_days"][review_key])
        assets.append({
            "asset_id": asset_id,
            "kind": "governance_asset",
            "last_verified": last_verified,
            "review_days": review_days,
            "age_days": days,
            "review_due": days is None or days >= review_days,
            "trigger": trigger,
            "dateModified_mutation_allowed": False,
        })
    return assets


def _state_row(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": item.get("id"),
        "slug": item.get("slug"),
        "status": str(item.get("status") or "unknown").lower(),
        "modified_gmt": item.get("modified_gmt") or item.get("date_modified_gmt") or item.get("modified"),
        "stock_status": str(item.get("stock_status") or "").lower() if kind == "products" else None,
    }


def build_state_snapshot(
    posts: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    products: list[dict[str, Any]],
    now: dt.datetime,
) -> dict[str, Any]:
    rows = (
        [_state_row("posts", x) for x in posts]
        + [_state_row("pages", x) for x in pages]
        + [_state_row("products", x) for x in products]
    )
    rows.sort(key=lambda x: (x["kind"], int(x.get("id") or 0)))
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "phase": 23,
        "version": "phase23-lifecycle-state-v3",
        "generated_at_utc": now.isoformat(),
        "row_count": len(rows),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "fields": ["kind", "id", "slug", "status", "modified_gmt", "stock_status"],
        "contains_price": False,
        "contains_stock_quantity": False,
        "contains_customer_data": False,
        "rows": rows,
    }


def detect_transitions(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {
            "baseline_mode": "INITIAL_V3_BASELINE",
            "previous_state_available": False,
            "transition_count": 0,
            "transitions": [],
        }
    old = {(x["kind"], x["id"]): x for x in previous.get("rows") or []}
    new = {(x["kind"], x["id"]): x for x in current.get("rows") or []}
    transitions = []
    for key in sorted(set(old) | set(new), key=lambda x: (x[0], int(x[1] or 0))):
        before = old.get(key)
        after = new.get(key)
        changes = {}
        if before is None:
            changes["record"] = {"from": None, "to": "added"}
        elif after is None:
            changes["record"] = {"from": "present", "to": "missing"}
        else:
            for field in ("status", "stock_status", "modified_gmt"):
                if before.get(field) != after.get(field):
                    changes[field] = {"from": before.get(field), "to": after.get(field)}
        if changes:
            actions = []
            priority = "P3"
            if "record" in changes:
                actions.append("inventory_membership_change_review")
                priority = "P1"
            if "status" in changes:
                actions.append("publication_state_changed_manual_review")
                priority = "P1"
            if "stock_status" in changes and key[0] == "products":
                actions.append("stock_state_changed_review_availability_parity")
                priority = "P1"
            if "modified_gmt" in changes:
                actions.append("modified_timestamp_changed_verify_substantive_change")
                priority = _priority_max(priority, "P2")
            transitions.append({
                "kind": key[0],
                "id": key[1],
                "priority": priority,
                "changes": changes,
                "actions": sorted(set(actions)),
                "dateModified_mutation_allowed": False,
                "redirect_inferred": False,
                "canonical_change_allowed": False,
            })
    return {
        "baseline_mode": "DIFF_AGAINST_PREVIOUS_V3",
        "previous_state_available": True,
        "transition_count": len(transitions),
        "transitions": transitions,
    }


def build_report(
    posts: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    products: list[dict[str, Any]],
    policy: dict[str, Any],
    previous_state: dict[str, Any] | None = None,
    now: dt.datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or dt.datetime.now(UTC)
    deps = dependency_snapshot()

    queues = {
        "posts": [classify("posts", x, policy, now) for x in posts],
        "pages": [classify("pages", x, policy, now) for x in pages],
        "products": [classify("products", x, policy, now) for x in products],
    }
    all_rows = [x for group in queues.values() for x in group]
    due = [x for x in all_rows if x["actions"] != ["no_action_due"]]
    published_products = [x for x in queues["products"] if x["public"]]
    nonpublic_products = [x for x in queues["products"] if not x["public"]]
    assets = governance_assets(policy, now, deps)
    state = build_state_snapshot(posts, pages, products, now)
    transition = detect_transitions(previous_state, state)

    priority_counts = {p: sum(1 for x in due if x["priority"] == p) for p in ("P0", "P1", "P2", "P3")}
    stock = published_products

    checks: dict[str, bool] = {
        "phase20_current_guarded_pass": (
            str(deps["phase20"]["status"] or "").startswith("PASS")
            and deps["phase20"]["passed_checks"] == deps["phase20"]["check_count"]
            and not deps["phase20"]["failed_checks"]
        ),
        "phase21_v3_current_pass": (
            deps["phase21"]["version"] == "phase21-iran-authority-network-v3"
            and deps["phase21"]["status"] == "PASS_IRAN_FIRST_AUTHORITY_V3_GUARDED"
            and deps["phase21"]["passed_checks"] == deps["phase21"]["check_count"]
            and not deps["phase21"]["failed_checks"]
        ),
        "phase22_v3_current_pass": (
            deps["phase22"]["version"] == "phase22-farmer-decision-v3"
            and deps["phase22"]["status"] == "PASS_PHASE22_FARMER_DECISION_V3_GUARDED"
            and deps["phase22"]["passed_checks"] == deps["phase22"]["check_count"]
            and not deps["phase22"]["failed_checks"]
        ),
        "phase22_read_only": deps["phase22"]["site_mutations"] == 0 and deps["phase22"]["commerce_mutations"] == 0,
        "published_product_count_matches_phase21": len(published_products) == deps["phase21"]["candidate_rows"] and len(published_products) > 0,
        "no_fake_freshness": policy["rules"].get("stale_review_does_not_touch_dateModified") is True and policy["rules"].get("dateModified_requires_substantive_content_change") is True,
        "outofstock_not_discontinued": policy["rules"].get("outofstock_is_not_discontinued") is True and all(not x["discontinued_inferred"] for x in stock),
        "nonpublic_no_public_url_actions": all("verify_supply_state_keep_url" not in x["actions"] and "verify_backorder_copy_and_schema" not in x["actions"] for x in nonpublic_products),
        "no_auto_redirect_inference": all(not x["redirect_inferred"] for x in all_rows),
        "no_auto_canonical_change": all(not x["canonical_change_allowed"] for x in all_rows),
        "no_auto_deletion": all(not x["deletion_allowed"] for x in all_rows),
        "no_bulk_rewrite": policy["rules"].get("automatic_bulk_rewrite_for_freshness") is False,
        "live_inventory_nonempty": len(all_rows) > 0,
        "state_snapshot_minimal": state["contains_price"] is False and state["contains_stock_quantity"] is False and state["contains_customer_data"] is False,
        "governance_assets_current": all(not x["review_due"] for x in assets),
        "transition_layer_read_only": all(not x["dateModified_mutation_allowed"] and not x["redirect_inferred"] and not x["canonical_change_allowed"] for x in transition["transitions"]),
    }

    failed = [k for k, v in checks.items() if not v]
    report = {
        "phase": 23,
        "title": "Lifecycle & Freshness Governance",
        "model_version": "k20-lifecycle-governance-v3",
        "generated_at_utc": now.isoformat(),
        "status": "PASS_PHASE23_LIFECYCLE_FRESHNESS_V3_GUARDED" if not failed else "FAIL_PHASE23_LIFECYCLE_FRESHNESS_V3",
        "dependencies": deps,
        "check_count": len(checks),
        "passed_checks": len(checks) - len(failed),
        "failed_checks": failed,
        "checks": checks,
        "inventory": {
            "posts_total": len(posts),
            "pages_total": len(pages),
            "products_total": len(products),
            "products_published": len(published_products),
            "products_nonpublic": len(nonpublic_products),
        },
        "review_queue_count": len(due),
        "priority_counts": priority_counts,
        "stock_transition_watch": {
            "published_outofstock": sum(1 for x in stock if x.get("stock_status") == "outofstock"),
            "published_onbackorder": sum(1 for x in stock if x.get("stock_status") == "onbackorder"),
            "published_unknown": sum(1 for x in stock if x.get("stock_status") not in {"outofstock", "onbackorder", "instock"}),
        },
        "governance_assets": assets,
        "transition_monitor": transition,
        "review_queue": due,
        "mutations": {
            "content": 0,
            "dateModified": 0,
            "stock": 0,
            "price": 0,
            "status": 0,
            "redirect": 0,
            "canonical": 0,
            "delete": 0,
        },
        "rules": policy["rules"],
        "completion_basis": (
            "Live read-only WordPress/WooCommerce lifecycle audit with current Phase 20/21/22 dependencies, "
            "public/non-public separation, no fake dateModified freshness, no discontinuation inference from stock, "
            "and a minimal state baseline for future transition detection."
        ),
    }
    return report, state


def validate_report(report: dict[str, Any]) -> None:
    if report["status"] != "PASS_PHASE23_LIFECYCLE_FRESHNESS_V3_GUARDED":
        raise Phase23Error("failed checks: " + ", ".join(report["failed_checks"]))
    if any(report["mutations"].values()):
        raise Phase23Error("Phase 23 audit must be read-only")


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
                "User-Agent": "Keshavarz20-Phase23-v3/1.0",
                "Cache-Control": "no-cache",
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


def paginate(base: str, route: str, auth: str, params: dict[str, str], max_pages: int = 60) -> list[dict[str, Any]]:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--state-output", required=True)
    ap.add_argument("--previous-state")
    args = ap.parse_args()

    base = os.environ.get("WP_BASE_URL", "").strip()
    user = os.environ.get("WP_USERNAME", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not (base and user and password):
        raise SystemExit("WP_BASE_URL/WP_USERNAME/WP_APP_PASSWORD are required")

    policy = load_json(Path(args.policy))
    previous_state = None
    if args.previous_state and Path(args.previous_state).exists():
        try:
            candidate = load_json(Path(args.previous_state))
            if candidate.get("version") == "phase23-lifecycle-state-v3":
                previous_state = candidate
        except (json.JSONDecodeError, OSError):
            previous_state = None

    auth = _auth_header(user, password)
    posts = paginate(base, "/wp-json/wp/v2/posts", auth, {"context": "edit", "_fields": "id,slug,status,modified_gmt"})
    pages = paginate(base, "/wp-json/wp/v2/pages", auth, {"context": "edit", "_fields": "id,slug,status,modified_gmt"})
    products = paginate(base, "/wp-json/wc/v3/products", auth, {"status": "any", "_fields": "id,slug,status,date_modified_gmt,stock_status"})

    report, state = build_report(posts, pages, products, policy, previous_state=previous_state)
    validate_report(report)

    out = Path(args.output)
    state_out = Path(args.state_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    state_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state_out.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "checks": f"{report['passed_checks']}/{report['check_count']}",
        "inventory": report["inventory"],
        "review_queue_count": report["review_queue_count"],
        "priority_counts": report["priority_counts"],
        "stock_transition_watch": report["stock_transition_watch"],
        "transition_count": report["transition_monitor"]["transition_count"],
        "baseline_mode": report["transition_monitor"]["baseline_mode"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
