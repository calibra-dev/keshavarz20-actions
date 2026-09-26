#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, io, json, os, time, zipfile
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SITE = os.environ.get("WP_BASE_URL", "https://keshavarz20.com").rstrip("/")
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

def wp(method: str, path: str, **kwargs):
    r = requests.request(method, SITE + "/wp-json" + path, auth=AUTH, timeout=180, **kwargs)
    r.raise_for_status()
    return r.json()

def build_assets(req: dict, expected_count: int):
    source_urls = req.get("source_urls") or []
    if source_urls:
        if len(source_urls) != expected_count:
            raise RuntimeError(f"expected {expected_count} source URLs, got {len(source_urls)}")
        assets = []
        for idx, url in enumerate(source_urls, 1):
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            with Image.open(io.BytesIO(r.content)) as im:
                im = im.convert("RGB")
                if im.size != (640, 640):
                    im = im.resize((640, 640), Image.Resampling.LANCZOS)
                out = io.BytesIO()
                im.save(out, format="WEBP", quality=88, method=6)
                assets.append((f"source-{idx:02d}.webp", out.getvalue()))
        return assets

    payload_dir = ROOT / req["payload_dir"]
    parts = sorted(payload_dir.glob("part*.txt"))
    if not parts:
        raise RuntimeError(f"no payload parts in {payload_dir}")
    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    raw = base64.b64decode(encoded, validate=True)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        names = sorted(n for n in zf.namelist() if n.lower().endswith(".webp"))
        if len(names) != expected_count:
            raise RuntimeError(f"expected {expected_count} webp files, got {len(names)}")
        return [(name, zf.read(name)) for name in names]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    a = ap.parse_args()
    req_path = Path(a.request)
    req = json.loads(req_path.read_text(encoding="utf-8"))

    product_id = int(req["product_id"])
    expected_count = int(req.get("expected_count", 8))
    result_path = ROOT / "gallery-chat-results" / (req_path.stem + ".json")
    result_path.parent.mkdir(parents=True, exist_ok=True)
    assets = build_assets(req, expected_count)

    before = wp("GET", f"/wc/v3/products/{product_id}")
    if int(before.get("id", 0)) != product_id:
        raise RuntimeError("product readback mismatch")
    before_ids = [int(x["id"]) for x in before.get("images", [])]
    product_name = before.get("name") or req.get("product_name") or f"Product {product_id}"

    uploaded = []
    try:
        for idx, (_, data) in enumerate(assets, 1):
            filename = f"k20-p{product_id}-gallery-{idx:02d}.webp"
            headers = {
                "Content-Type": "image/webp",
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
            media = wp("POST", "/wp/v2/media", headers=headers, data=data)
            mid = int(media["id"])
            title = f"{product_name} - تصویر گالری {idx} از {expected_count}"
            wp("POST", f"/wp/v2/media/{mid}", json={"title": title, "alt_text": title})
            uploaded.append({"id": mid, "url": media.get("source_url"), "file": filename})

        new_ids = [x["id"] for x in uploaded]
        merged_ids = before_ids + [i for i in new_ids if i not in before_ids]
        wp("PUT", f"/wc/v3/products/{product_id}", json={"images": [{"id": i} for i in merged_ids]})

        final_ids = []
        verified = False
        for _ in range(12):
            time.sleep(3)
            final = wp("GET", f"/wc/v3/products/{product_id}")
            final_ids = [int(x["id"]) for x in final.get("images", [])]
            if all(i in final_ids for i in before_ids) and all(i in final_ids for i in new_ids):
                verified = True
                break

        if not verified:
            wp("PUT", f"/wc/v3/products/{product_id}", json={"images": [{"id": i} for i in before_ids]})
            result = {
                "ok": False,
                "verified": False,
                "product_id": product_id,
                "product_name": product_name,
                "before_image_ids": before_ids,
                "uploaded": uploaded,
                "final_image_ids": final_ids,
                "restored_previous_gallery": True,
                "error": "gallery readback missing one or more expected ids",
            }
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            raise RuntimeError(result["error"])

        result = {
            "ok": True,
            "verified": True,
            "product_id": product_id,
            "product_name": product_name,
            "before_image_ids": before_ids,
            "uploaded": uploaded,
            "final_image_ids": final_ids,
            "append_only": True,
            "featured_preserved": bool(before_ids and final_ids and before_ids[0] == final_ids[0]),
            "expected_count": expected_count,
            "format": "webp",
            "dimensions": "640x640",
            "source_mode": "urls" if req.get("source_urls") else "payload_dir",
            "published_at_epoch": int(time.time()),
        }
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        if not result_path.exists():
            result = {
                "ok": False,
                "verified": False,
                "product_id": product_id,
                "product_name": product_name,
                "before_image_ids": before_ids,
                "uploaded": uploaded,
                "error": str(e),
            }
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        raise

if __name__ == "__main__":
    main()
