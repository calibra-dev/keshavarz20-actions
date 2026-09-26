#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

import requests

MAX_ASSETS = 20
MAX_BYTES = 20 * 1024 * 1024
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
TARGET_ACTIONS = {
    "featured_replace": "asset.featured.set",
    "gallery_append": "asset.gallery.append",
    "gallery_replace": "asset.gallery.replace",
    "content_insert": "asset.content.insert",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_blob(session: requests.Session, repo: str, sha: str) -> bytes:
    if len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
        fail("invalid detached Git blob SHA")
    url = f"https://api.github.com/repos/{repo}/git/blobs/{sha}"
    r = session.get(url, timeout=90)
    r.raise_for_status()
    payload = r.json()
    if payload.get("encoding") != "base64":
        fail("Git blob encoding is not base64")
    raw = base64.b64decode((payload.get("content") or "").replace("\n", ""), validate=True)
    if not raw or len(raw) > MAX_BYTES:
        fail("asset size is outside the 1 byte..20 MiB limit")
    return raw


def post_json(session: requests.Session, url: str, body: dict) -> dict:
    r = session.post(url, json=body, timeout=180)
    data = r.json() if r.content else {}
    if r.status_code < 200 or r.status_code >= 300 or not data.get("ok"):
        code = data.get("code") or f"http_{r.status_code}"
        message = data.get("message") or "Bridge request failed"
        err = RuntimeError(f"{code}: {message}")
        setattr(err, "payload", data)
        raise err
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("output")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    out_path = Path(args.output)
    req = json.loads(manifest_path.read_text(encoding="utf-8"))

    repo = os.environ["GITHUB_REPOSITORY"]
    gh_token = os.environ["GH_TOKEN"]
    wp_base = os.environ["WP_BASE_URL"].rstrip("/")
    wp_user = os.environ["WP_USERNAME"]
    wp_pass = os.environ["WP_APP_PASSWORD"]

    request_id = str(req.get("request_id") or manifest_path.stem)[:80]
    assets = req.get("assets") or []
    if not isinstance(assets, list) or not (1 <= len(assets) <= MAX_ASSETS):
        fail(f"assets must contain 1..{MAX_ASSETS} items")

    transform = req.get("transform") or {}
    output_mime = str(transform.get("output_mime") or "image/webp")
    if output_mime not in ALLOWED_MIMES:
        fail("transform.output_mime is not allowed")
    quality = max(40, min(95, int(transform.get("quality", 88))))
    max_dimension = max(256, min(4096, int(transform.get("max_dimension", 1600))))

    target = req.get("target") or {}
    operation = str(target.get("operation") or "")
    if operation not in TARGET_ACTIONS:
        fail("target.operation is not allow-listed")
    target_id = int(target.get("id") or 0)
    if target_id <= 0:
        fail("target.id is required")

    gh = requests.Session()
    gh.headers.update(
        {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "k20-bridge-v33-chat-asset-relay",
        }
    )
    wp = requests.Session()
    wp.auth = (wp_user, wp_pass)
    wp.headers.update({"Accept": "application/json"})

    uploaded = []
    upload_url = wp_base + "/wp-json/keshavarz20-ops/v3/asset"

    for index, item in enumerate(assets, 1):
        if not isinstance(item, dict):
            fail("asset entry must be an object")
        blob_sha = str(item.get("blob_sha") or "")
        chunk_shas = item.get("base64_chunk_blob_shas") or []
        filename = str(item.get("filename") or f"k20-chat-{index}.webp")
        mime_type = str(item.get("mime_type") or "image/webp")
        if mime_type not in ALLOWED_MIMES:
            fail("asset mime_type is not allowed")
        if blob_sha and chunk_shas:
            fail("asset must use blob_sha or base64_chunk_blob_shas, not both")
        if chunk_shas:
            if not isinstance(chunk_shas, list) or not (1 <= len(chunk_shas) <= 32):
                fail("base64_chunk_blob_shas must contain 1..32 items")
            encoded = b"".join(load_blob(gh, repo, str(sha)) for sha in chunk_shas)
            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise RuntimeError("invalid base64 chat asset chunks") from exc
            if not raw or len(raw) > MAX_BYTES:
                fail("decoded asset size is outside the 1 byte..20 MiB limit")
        else:
            if not blob_sha:
                fail("asset requires blob_sha or base64_chunk_blob_shas")
            raw = load_blob(gh, repo, blob_sha)
        expected_sha256 = str(item.get("sha256") or "").lower()
        actual_sha256 = hashlib.sha256(raw).hexdigest()
        if expected_sha256 and expected_sha256 != actual_sha256:
            fail("asset sha256 mismatch")

        data = {
            "filename": filename,
            "title": str(item.get("title") or ""),
            "alt_text": str(item.get("alt_text") or ""),
            "caption": str(item.get("caption") or ""),
            "post_id": str(target_id),
            "output_mime": output_mime,
            "quality": str(quality),
            "max_dimension": str(max_dimension),
        }
        files = {"file": (filename, raw, mime_type)}
        r = wp.post(upload_url, data=data, files=files, timeout=180)
        payload = r.json() if r.content else {}
        if r.status_code < 200 or r.status_code >= 300 or not payload.get("ok"):
            code = payload.get("code") or f"http_{r.status_code}"
            message = payload.get("message") or "asset upload failed"
            fail(f"{code}: {message}")
        result = payload.get("result") or {}
        attachment_id = int(result.get("attachment_id") or 0)
        if attachment_id <= 0:
            fail("asset upload returned no attachment_id")
        uploaded.append(
            {
                "attachment_id": attachment_id,
                "sha256": result.get("sha256"),
                "mime": result.get("mime"),
                "bytes": result.get("bytes"),
                "width": result.get("width"),
                "height": result.get("height"),
            }
        )

    attachment_ids = [x["attachment_id"] for x in uploaded]
    action = TARGET_ACTIONS[operation]
    body = {"action": action, "request_id": request_id + "-bind", "payload": {}}
    if action == "asset.featured.set":
        body["payload"] = {"target_id": target_id, "attachment_id": attachment_ids[0]}
    elif action in {"asset.gallery.append", "asset.gallery.replace"}:
        body["payload"] = {"product_id": target_id, "attachment_ids": attachment_ids}
    elif action == "asset.content.insert":
        body["payload"] = {
            "target_id": target_id,
            "attachment_ids": attachment_ids,
            "position": str(target.get("position") or "append"),
        }
        if target.get("after_text") is not None:
            body["payload"]["after_text"] = str(target.get("after_text"))
        if target.get("expected_sha256") is not None:
            body["payload"]["expected_sha256"] = str(target.get("expected_sha256"))

    execute_url = wp_base + "/wp-json/keshavarz20-ops/v3/execute"
    binding = post_json(wp, execute_url, body)

    result = {
        "ok": True,
        "request_id": request_id,
        "operation": operation,
        "target_id": target_id,
        "asset_count": len(uploaded),
        "uploaded": uploaded,
        "binding": binding.get("result"),
        "bridge_version": binding.get("version"),
        "contract": binding.get("contract"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
