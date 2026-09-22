import json
import os
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(".")
REQUEST = pathlib.Path(os.environ.get("K20_COMMENT_AUDIT_REQUEST", ""))
RESULT = pathlib.Path(os.environ.get("K20_COMMENT_AUDIT_RESULT", ""))
if not REQUEST.is_file():
    raise SystemExit("Missing K20_COMMENT_AUDIT_REQUEST")
req = json.loads(REQUEST.read_text(encoding="utf-8"))
source_path = ROOT / str(req.get("speed_result") or "")
if not source_path.is_file():
    raise SystemExit(f"Missing speed result: {source_path}")
speed = json.loads(source_path.read_text(encoding="utf-8"))
site = str(req.get("site") or "https://keshavarz20.com").rstrip("/")

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def get_json(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": "K20-Comment-Cache-Candidate-Audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            raw = r.read()
            headers = dict(r.headers)
            return int(r.status), json.loads(raw.decode("utf-8")), headers
    except Exception as e:
        return 0, None, {"error": str(e)[:500]}

def resolve_wp_object(url):
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(p.path).strip("/")
    if not path:
        return None
    first = path.split("/", 1)[0]
    if first in {"product", "product-category", "product_brand", "product-tag", "cart", "checkout", "my-account"}:
        return None
    slug = path.split("/")[-1]
    for kind in ("posts", "pages"):
        q = urllib.parse.urlencode({"slug": slug, "_fields": "id,slug,status,link,comment_status,type"})
        status, data, _ = get_json(f"{site}/wp-json/wp/v2/{kind}?{q}")
        if status == 200 and isinstance(data, list) and data:
            row = data[0]
            row["_rest_kind"] = kind
            return row
    return None

def comment_total(post_id):
    q = urllib.parse.urlencode({"post": int(post_id), "per_page": 1, "_fields": "id"})
    status, data, headers = get_json(f"{site}/wp-json/wp/v2/comments?{q}")
    if status != 200:
        return None
    for key, value in headers.items():
        if key.lower() == "x-wp-total":
            try:
                return int(value)
            except Exception:
                return None
    return 0 if isinstance(data, list) and not data else len(data)

rows = []
for page in speed.get("pages", []):
    url = page.get("url")
    obj = resolve_wp_object(url)
    if not obj:
        continue
    total = comment_total(obj.get("id"))
    rows.append({
        "url": url,
        "id": obj.get("id"),
        "kind": obj.get("_rest_kind"),
        "slug": obj.get("slug"),
        "status": obj.get("status"),
        "comment_status": obj.get("comment_status"),
        "approved_public_comments": total,
        "median_ttfb_s": page.get("median_ttfb_s"),
        "median_total_s": page.get("median_total_s"),
        "cache_states": page.get("cache_states"),
        "cache_controls": page.get("cache_controls"),
        "safe_close_candidate": bool(
            obj.get("_rest_kind") == "posts"
            and obj.get("status") == "publish"
            and obj.get("comment_status") == "open"
            and total == 0
            and any("no-cache" in str(x).lower() for x in (page.get("cache_controls") or []))
        ),
    })

candidates = [r for r in rows if r["safe_close_candidate"]]
candidates.sort(key=lambda x: float(x.get("median_total_s") or 0), reverse=True)
result = {
    "program": "K20 Comment Cache Candidate Audit",
    "executed_at_utc": now_iso(),
    "read_only": True,
    "speed_result": str(source_path),
    "resolved_wp_objects": len(rows),
    "safe_close_candidate_count": len(candidates),
    "policy": "Only published non-product WordPress posts with comment_status=open, zero approved public comments, and explicit no-cache in the measured cohort are candidates. Products/reviews are excluded.",
    "candidates": candidates,
    "all_resolved": rows,
}
RESULT.parent.mkdir(parents=True, exist_ok=True)
RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"candidate_count": len(candidates), "candidates": candidates}, ensure_ascii=False, indent=2))
