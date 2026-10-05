#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

import requests

MAX_REQUEST_BYTES = 262144
ALLOWED_ACTIONS = {
    "snippet.list",
    "snippet.read",
    "snippet.validate",
    "snippet.create_draft",
    "snippet.update_draft",
    "snippet.deactivate",
    "code.read",
    "code.search",
    "plugin.rest.get",
    "approval.status",
    "approval.execute",
    "recovery.deactivate_failing_plugin",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("output")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    out_path = Path(args.output)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    base = os.environ["WP_BASE_URL"].rstrip("/")
    auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

    blob_sha = str(manifest.get("request_blob_sha") or "")
    if len(blob_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in blob_sha):
        fail("request_blob_sha must be a 40-character Git blob SHA")

    gh = requests.Session()
    gh.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "k20-bridge-v33-secure-relay",
        }
    )
    r = gh.get(f"https://api.github.com/repos/{repo}/git/blobs/{blob_sha}", timeout=90)
    r.raise_for_status()
    payload = r.json()
    if payload.get("encoding") != "base64":
        fail("request blob encoding is not base64")
    raw = base64.b64decode((payload.get("content") or "").replace("\n", ""), validate=True)
    if not raw or len(raw) > MAX_REQUEST_BYTES:
        fail("secure request payload is empty or exceeds 256 KiB")

    expected = str(manifest.get("request_sha256") or "").lower()
    actual = hashlib.sha256(raw).hexdigest()
    if expected and expected != actual:
        fail("secure request sha256 mismatch")

    request = json.loads(raw.decode("utf-8"))
    if not isinstance(request, dict):
        fail("secure request must be a JSON object")
    action = str(request.get("action") or "")
    if action not in ALLOWED_ACTIONS:
        fail("secure request action is not allow-listed")

    if action == "recovery.deactivate_failing_plugin":
        from urllib.parse import urlparse

        recovery_url = str(request.get("recovery_url") or "")
        expected_dir = str(request.get("expected_plugin_dir") or "k20-ai-press").strip("/")
        base_parts = urlparse(base)
        rec_parts = urlparse(recovery_url)
        if (
            rec_parts.scheme != "https"
            or rec_parts.netloc.lower() != base_parts.netloc.lower()
            or rec_parts.path != "/wp-login.php"
            or "action=enter_recovery_mode" not in rec_parts.query
            or "rm_token=" not in rec_parts.query
            or "rm_key=" not in rec_parts.query
        ):
            fail("Recovery URL is invalid or not scoped to the configured WordPress site.")

        wp = requests.Session()
        wp.headers.update({"Accept": "application/json", "User-Agent": "k20-recovery-secure-relay/1.0"})
        enter = wp.get(recovery_url, allow_redirects=True, timeout=90)
        recovery_cookie_names = [name for name in wp.cookies.get_dict().keys() if name.startswith("wordpress_rec_")]
        if not recovery_cookie_names:
            body = {
                "ok": False,
                "code": "recovery_cookie_missing",
                "message": "WordPress did not establish a recovery-mode session.",
                "result": {"recovery_http": enter.status_code},
            }
            response = enter
        else:
            wp.auth = auth
            plugins_url = base + "/wp-json/wp/v2/plugins"
            listing = wp.get(plugins_url, timeout=120)
            try:
                plugins = listing.json()
            except Exception:
                plugins = None

            if listing.status_code < 200 or listing.status_code >= 300 or not isinstance(plugins, list):
                body = {
                    "ok": False,
                    "code": "plugin_inventory_failed",
                    "message": "Recovery mode was established, but the plugin inventory could not be read.",
                    "result": {"inventory_http": listing.status_code},
                }
                response = listing
            else:
                target = None
                for row in plugins:
                    plugin_key = str(row.get("plugin") or "")
                    plugin_name = str(row.get("name") or "")
                    if plugin_key == expected_dir or plugin_key.startswith(expected_dir + "/") or plugin_name == "K20 AI Press":
                        target = row
                        break

                if not target:
                    body = {
                        "ok": False,
                        "code": "failing_plugin_not_found",
                        "message": "The expected failing plugin was not found in the plugin inventory.",
                        "result": {"inventory_count": len(plugins)},
                    }
                    response = listing
                else:
                    plugin_key = str(target.get("plugin") or "")
                    plugin_route = plugins_url.rstrip("/") + "/" + plugin_key
                    deact = wp.post(plugin_route, json={"status": "inactive"}, timeout=120)
                    try:
                        deact_body = deact.json()
                    except Exception:
                        deact_body = {}

                    verify = wp.get(plugins_url, timeout=120)
                    try:
                        verify_rows = verify.json()
                    except Exception:
                        verify_rows = []
                    verify_target = next(
                        (row for row in verify_rows if str(row.get("plugin") or "") == plugin_key),
                        {},
                    ) if isinstance(verify_rows, list) else {}
                    final_status = str(verify_target.get("status") or deact_body.get("status") or "")

                    home = wp.get(base + "/", timeout=120)
                    rest = wp.get(base + "/wp-json/", timeout=120)

                    ok = (
                        200 <= deact.status_code < 300
                        and final_status == "inactive"
                        and 200 <= home.status_code < 400
                        and 200 <= rest.status_code < 400
                    )
                    body = {
                        "ok": ok,
                        "code": "ok" if ok else "deactivation_verification_failed",
                        "message": "Failing plugin deactivated and site bootstrap recovered." if ok else "Plugin deactivation did not fully recover the site.",
                        "result": {
                            "plugin": plugin_key,
                            "status": final_status,
                            "deactivate_http": deact.status_code,
                            "home_http": home.status_code,
                            "rest_http": rest.status_code,
                            "recovery_cookie_established": True,
                        },
                    }
                    response = deact
    else:
        wp = requests.Session()
        wp.auth = auth
        wp.headers.update({"Accept": "application/json"})
        response = wp.post(
            base + "/wp-json/keshavarz20-ops/v3/execute",
            json=request,
            timeout=180,
        )
        try:
            body = response.json()
        except Exception:
            body = {"ok": False, "code": "non_json_response", "message": "Bridge returned a non-JSON response."}

    record = {
        "http_code": response.status_code,
        "request_id": request.get("request_id"),
        "action": action,
        "bridge_response": body,
        "request_sha256": actual,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = 200 <= response.status_code < 300 and bool(body.get("ok"))
    code = "ok" if ok else str(body.get("code") or f"http_{response.status_code}")
    print(f"K20 secure relay action={action} status={code}")
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
