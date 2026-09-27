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
    "approval.status",
    "approval.execute",
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
