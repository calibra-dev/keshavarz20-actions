#!/usr/bin/env python3
"""Calibra exact installed files, read only; checksum-gated for disposable Docker QA."""
import base64
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SITE = os.environ.get("WP_BASE_URL", "").rstrip("/")
USER = os.environ.get("WP_USERNAME", "")
PASSWORD = os.environ.get("WP_APP_PASSWORD", "")
if not all((SITE, USER, PASSWORD)):
    raise SystemExit("SITE_READ_AUTH_UNAVAILABLE")
AUTH = "Basic " + base64.b64encode((USER + ":" + PASSWORD).encode()).decode()
ENDPOINT = SITE + "/wp-json/keshavarz20-ops/v3/execute"

def sha256(blob):
    return hashlib.sha256(blob).hexdigest()

def bridge(action, payload, tag):
    body = json.dumps({"action": action, "request_id": "calibra1817-qa-" + tag,
                       "payload": payload}, ensure_ascii=False).encode()
    req = urllib.request.Request(ENDPOINT, data=body,
        headers={"Authorization": AUTH, "Accept": "application/json",
                 "Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "K20-Calibra-Readonly-ReleaseQA"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit("BRIDGE_" + action + "_HTTP_" + str(exc.code))
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise SystemExit("BRIDGE_" + action + "_FAILED_" + str(result.get("code")))
    return result.get("result") or {}

inventory = bridge("plugin.assets", {"plugin": "k20-dashboard/k20-dashboard.php"}, "inventory")
if inventory.get("version") != "1.8.17":
    raise SystemExit("INSTALLED_VERSION_NOT_1_8_17")
entries = inventory.get("files") or []
if not 40 < len(entries) < 125:
    raise SystemExit("FILE_COUNT_OUTSIDE_EXPECTED_RANGE")
by_path = {x["path"]: x for x in entries}
for required in ("k20-dashboard.php", "assets/js/admin.js", "assets/js/iran-cities.js"):
    if required not in by_path:
        raise SystemExit("MISSING_REQUIRED_FILE_" + required)
print("LIVE_1817_ASSET_INVENTORY_OK files=" + str(len(entries)))

def read_code(path, idx):
    result = bridge("code.read", {"root": "k20-dashboard", "path": path},
                    "source-" + str(idx))
    text = result.get("source_text", "")
    if not isinstance(text, str) or not text:
        raise SystemExit("CODE_SOURCE_EMPTY:" + path)
    return text.encode()

def restore_known_empty_product_token(text, expected_hash):
    # The vendor token is explicitly empty in the 1.8.17 preview release.
    # Bridge masks define(*TOKEN*, '') as define(*TOKEN*, '***').
    # Restore only the known declaration; verify against original file hash.
    pattern = re.compile(r"""(define\s*\(\s*['"]K20D_ZHAKET_PRODUCT_TOKEN['"]\s*,\s*)['"]\*\*\*['"]""")
    for quote in ("'", '"'):
        restored, n = pattern.subn(lambda m: m.group(1) + quote + quote, text)
        if n == 1 and sha256(restored.encode()) == expected_hash:
            return restored.encode()
    return text.encode()

main = read_code("k20-dashboard.php", "main")
main_expected = by_path["k20-dashboard.php"]["sha256"]
if sha256(main) != main_expected:
    main = restore_known_empty_product_token(main.decode(), main_expected)
print("MAIN_CODE_READ_OK sha_match=" + str(sha256(main) == main_expected))
if len(sys.argv) < 2 or sys.argv[1] != "build":
    print("LIVE_1817_PREFLIGHT_DONE")
    sys.exit(0)

root = pathlib.Path(os.environ.get("CALIBRA_QA_DIR", "/tmp/calibra1817qa"))
stage = root / "k20-dashboard"
stage.mkdir(parents=True, exist_ok=True)
text_extensions = {"php", "js", "css", "json", "html", "htm", "txt", "md", "yml", "yaml"}
for i, row in enumerate(entries):
    rel = row["path"]
    if (not rel or rel.startswith("/") or "\\" in rel
            or any(part in ("", ".", "..") for part in rel.split("/"))):
        raise SystemExit("INVALID_PLUGIN_PATH")
    ext = rel.rsplit(".", 1)[-1].lower()
    if rel == "k20-dashboard.php":
        data = main
    elif ext in text_extensions:
        data = read_code(rel, str(i))
    else:
        url = SITE + "/wp-content/plugins/k20-dashboard/" + "/".join(
            urllib.parse.quote(part) for part in rel.split("/"))
        request = urllib.request.Request(url, headers={"User-Agent": "K20-Calibra-QA"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(12000000)
        except urllib.error.HTTPError as exc:
            raise SystemExit("ASSET_DOWNLOAD_HTTP_" + str(exc.code) + ":" + rel)
    if sha256(data) != row["sha256"] and ext != "php":
        # Bridge sanitizes documentation/code examples. Retrieve the public static
        # installed file instead, and only trust it when its byte hash agrees.
        url = SITE + "/wp-content/plugins/k20-dashboard/" + "/".join(
            urllib.parse.quote(part) for part in rel.split("/"))
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"User-Agent": "K20-Calibra-QA"}), timeout=60) as response:
                candidate = response.read(12000000)
            if sha256(candidate) == row["sha256"]:
                data = candidate
                print("STATIC_SOURCE_RECOVERED_AND_HASH_VERIFIED:" + rel)
        except urllib.error.HTTPError:
            pass
    if sha256(data) != row["sha256"]:
        raise SystemExit("SOURCE_HASH_MISMATCH:" + rel)
    dest = stage / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
target = root / "Calibra-Dashboard-1.8.17-VERIFIED-LIVE.zip"
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED,
                     compresslevel=6) as archive:
    for file in sorted(stage.rglob("*")):
        if file.is_file():
            archive.write(file, file.relative_to(root).as_posix())
with zipfile.ZipFile(target) as archive:
    if len(archive.namelist()) != len(entries) or archive.testzip() is not None:
        raise SystemExit("ZIP_INTEGRITY_FAILURE")
print("LIVE_1817_ALL_FILE_HASHES_VERIFIED count=" + str(len(entries)))
print("LIVE_1817_DISPOSABLE_INSTALL_ZIP_READY bytes=" + str(target.stat().st_size))
