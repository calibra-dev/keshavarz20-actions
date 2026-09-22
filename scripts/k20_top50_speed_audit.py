import json
import os
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlsplit

ROOT = pathlib.Path(".")
BASELINE = ROOT / "phase45" / "input" / "gsc-baseline-2026-09-18.json"
REQUEST = pathlib.Path(os.environ.get("K20_SPEED_REQUEST", ""))
RESULT = pathlib.Path(os.environ.get("K20_SPEED_RESULT", ""))

if not REQUEST.is_file():
    raise SystemExit("K20_SPEED_REQUEST is missing or invalid")
if not RESULT:
    raise SystemExit("K20_SPEED_RESULT is missing")
if not BASELINE.is_file():
    raise SystemExit(f"Missing GSC baseline: {BASELINE}")

req = json.loads(REQUEST.read_text(encoding="utf-8"))
baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
site = str(req.get("site") or "https://keshavarz20.com").rstrip("/")
top_n = int(req.get("top_n", 50))
samples_per_url = int(req.get("samples_per_url", 3))
workers = min(max(int(req.get("workers", 4)), 1), 6)
lighthouse_count = min(max(int(req.get("lighthouse_count", 12)), 0), 15)
timeout_s = min(max(int(req.get("timeout_s", 45)), 10), 60)

if top_n != 50:
    raise SystemExit("This workflow is intentionally fixed to exactly 50 pages.")

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def clean_url(url):
    url = str(url or "").strip()
    if not url:
        return ""
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        return ""
    if p.netloc.lower() != urlsplit(site).netloc.lower():
        return ""
    return url.split("#", 1)[0]

core = []
for row in req.get("core_urls", []):
    url = clean_url(row.get("url") if isinstance(row, dict) else row)
    if url and url not in core:
        core.append(url)

rows = baseline.get("pages", {}).get("rows", [])
ranked = []
for row in rows:
    keys = row.get("keys") or []
    if not keys:
        continue
    url = clean_url(keys[0])
    if not url:
        continue
    ranked.append({
        "url": url,
        "clicks": float(row.get("clicks") or 0),
        "impressions": float(row.get("impressions") or 0),
        "position": float(row.get("position") or 0),
    })
ranked.sort(key=lambda x: (x["clicks"], x["impressions"]), reverse=True)

selected = []
seen = set()
for url in core:
    if url not in seen:
        selected.append({"url": url, "selection": "core", "gsc": None})
        seen.add(url)
for row in ranked:
    if len(selected) >= top_n:
        break
    if row["url"] not in seen:
        selected.append({"url": row["url"], "selection": "gsc_top", "gsc": row})
        seen.add(row["url"])
selected = selected[:top_n]
if len(selected) != top_n:
    raise SystemExit(f"Could only select {len(selected)} URLs; expected {top_n}")

def parse_header_file(path):
    text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    blocks = [b for b in re.split(r"\r?\n\r?\n", text) if b.strip()]
    block = blocks[-1] if blocks else text
    out = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out

def curl_once(url, seq, body=False):
    with tempfile.TemporaryDirectory(prefix="k20-speed-") as td:
        hdr = pathlib.Path(td) / "headers.txt"
        body_path = pathlib.Path(td) / "body.html"
        cmd = [
            "curl", "-L", "-sS", "--max-time", str(timeout_s),
            "-A", "K20-Top50-Speed-Audit/2026-09-22",
            "-H", "Cookie:",
            "-H", "Accept-Encoding: gzip, br",
            "-D", str(hdr),
            "-o", str(body_path if body else os.devnull),
            "-w", "%{http_code}|%{time_namelookup}|%{time_connect}|%{time_appconnect}|%{time_starttransfer}|%{time_total}|%{size_download}|%{num_redirects}|%{remote_ip}|%{content_type}",
            url,
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 10)
        if p.returncode != 0:
            return {"seq": seq, "ok": False, "error": p.stderr.strip()[:500]}
        parts = p.stdout.strip().split("|", 9)
        if len(parts) != 10:
            return {"seq": seq, "ok": False, "error": "unexpected curl metrics"}
        code, dns, connect, tls, ttfb, total, size, redirects, remote_ip, ctype = parts
        headers = parse_header_file(hdr)
        row = {
            "seq": seq,
            "ok": True,
            "http_code": int(code or 0),
            "dns_s": float(dns or 0),
            "connect_s": float(connect or 0),
            "tls_s": float(tls or 0),
            "ttfb_s": float(ttfb or 0),
            "total_s": float(total or 0),
            "html_bytes": int(float(size or 0)),
            "redirects": int(redirects or 0),
            "remote_ip": remote_ip,
            "content_type": ctype,
            "litespeed_cache": headers.get("x-litespeed-cache", ""),
            "litespeed_cache_control": headers.get("x-litespeed-cache-control", ""),
            "cache_control": headers.get("cache-control", ""),
            "set_cookie": headers.get("set-cookie", "")[:300],
            "vary": headers.get("vary", ""),
        }
        if body and body_path.exists():
            raw = body_path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            title = ""
            m = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
            if m:
                title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()
            row["page_read"] = {
                "bytes_read": len(raw),
                "title": title[:300],
                "img_tags": len(re.findall(r"<img\b", text, flags=re.I)),
                "script_tags": len(re.findall(r"<script\b", text, flags=re.I)),
                "style_links": len(re.findall(r"<link\b[^>]*rel=[\"']?stylesheet", text, flags=re.I)),
            }
        return row

def audit_url(item):
    url = item["url"]
    samples = []
    for seq in range(1, samples_per_url + 1):
        samples.append(curl_once(url, seq, body=(seq == 1)))
    good = [s for s in samples if s.get("ok") and s.get("http_code") == 200]
    med_ttfb = statistics.median([s["ttfb_s"] for s in good]) if good else None
    med_total = statistics.median([s["total_s"] for s in good]) if good else None
    cache_states = sorted({s.get("litespeed_cache", "") for s in good if s.get("litespeed_cache")})
    cache_ctl = sorted({s.get("litespeed_cache_control", "") for s in good if s.get("litespeed_cache_control")})
    return {
        **item,
        "samples": samples,
        "median_ttfb_s": med_ttfb,
        "median_total_s": med_total,
        "cache_states": cache_states,
        "cache_controls": cache_ctl,
        "read_ok": bool(good),
    }

audited = []
with ThreadPoolExecutor(max_workers=workers) as pool:
    futures = {pool.submit(audit_url, item): item["url"] for item in selected}
    for future in as_completed(futures):
        audited.append(future.result())

order = {item["url"]: i for i, item in enumerate(selected)}
audited.sort(key=lambda x: order[x["url"]])

def run_lighthouse(url, name):
    report = pathlib.Path(tempfile.gettempdir()) / f"k20-lh-{name}.json"
    cmd = [
        "lighthouse", url,
        "--quiet",
        "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
        "--only-categories=performance",
        "--output=json",
        f"--output-path={report}",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if p.returncode != 0 or not report.is_file():
            return {"ok": False, "error": (p.stderr or p.stdout)[-1000:]}
        j = json.loads(report.read_text(encoding="utf-8"))
        audits = j.get("audits", {})
        cats = j.get("categories", {})
        return {
            "ok": True,
            "performance_score": round(float(cats.get("performance", {}).get("score") or 0) * 100, 1),
            "fcp_s": round(float(audits.get("first-contentful-paint", {}).get("numericValue") or 0) / 1000, 3),
            "lcp_s": round(float(audits.get("largest-contentful-paint", {}).get("numericValue") or 0) / 1000, 3),
            "speed_index_s": round(float(audits.get("speed-index", {}).get("numericValue") or 0) / 1000, 3),
            "tbt_ms": round(float(audits.get("total-blocking-time", {}).get("numericValue") or 0), 1),
            "cls": round(float(audits.get("cumulative-layout-shift", {}).get("numericValue") or 0), 4),
            "total_bytes": int(float(audits.get("total-byte-weight", {}).get("numericValue") or 0)),
            "request_count": len(audits.get("network-requests", {}).get("details", {}).get("items", []) or []),
            "server_response_time_ms": round(float(audits.get("server-response-time", {}).get("numericValue") or 0), 1),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:1000]}
    finally:
        try:
            report.unlink(missing_ok=True)
        except Exception:
            pass

for idx, row in enumerate(audited[:lighthouse_count], start=1):
    row["lighthouse"] = run_lighthouse(row["url"], f"{idx:02d}")
for row in audited[lighthouse_count:]:
    row["lighthouse"] = None

good_rows = [r for r in audited if r.get("median_total_s") is not None]
summary = {
    "pages_requested": top_n,
    "pages_read_ok": len(good_rows),
    "pages_failed": top_n - len(good_rows),
    "median_of_page_median_ttfb_s": round(statistics.median([r["median_ttfb_s"] for r in good_rows]), 4) if good_rows else None,
    "median_of_page_median_total_s": round(statistics.median([r["median_total_s"] for r in good_rows]), 4) if good_rows else None,
    "p75_page_median_total_s": None,
    "cache_hit_pages": sum(1 for r in good_rows if any(str(x).lower() == "hit" for x in r.get("cache_states", []))),
    "explicit_no_cache_pages": sum(1 for r in good_rows if any("no-cache" in str(x).lower() for x in r.get("cache_controls", []))),
    "lighthouse_pages": sum(1 for r in audited if isinstance(r.get("lighthouse"), dict) and r["lighthouse"].get("ok")),
}
if good_rows:
    vals = sorted(r["median_total_s"] for r in good_rows)
    pos = min(len(vals) - 1, max(0, int(round(0.75 * (len(vals) - 1)))))
    summary["p75_page_median_total_s"] = round(vals[pos], 4)

slowest = sorted(
    [
        {"url": r["url"], "median_total_s": r["median_total_s"], "median_ttfb_s": r["median_ttfb_s"], "cache_states": r["cache_states"], "cache_controls": r["cache_controls"]}
        for r in good_rows
    ],
    key=lambda x: x["median_total_s"],
    reverse=True,
)[:15]

result = {
    "program": "Keshavarz20 Top50 Speed Audit",
    "executed_at_utc": now_iso(),
    "read_only": True,
    "selection_source": {
        "gsc_file": str(BASELINE),
        "gsc_generated_at": baseline.get("generated_at"),
        "core_urls_from_request": len(core),
        "rule": "Core strategic URLs first, then highest-click/highest-impression GSC pages until exactly 50 unique URLs.",
    },
    "measurement": {
        "samples_per_url": samples_per_url,
        "workers": workers,
        "lighthouse_count": lighthouse_count,
        "curl_cookie_header": "empty",
        "target_improvement": ">=50% reduction in median opening time where safely achievable; target is not pre-declared as achieved without post-change evidence.",
    },
    "summary": summary,
    "slowest": slowest,
    "pages": audited,
}
RESULT.parent.mkdir(parents=True, exist_ok=True)
RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"result": str(RESULT), "summary": summary, "slowest": slowest[:10]}, ensure_ascii=False, indent=2))
