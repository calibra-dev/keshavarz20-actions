#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "bridge-v3-ops"
OUT = ROOT / "k21-top30-results"

PILOT_ID = 135311
CUSTOM_GENERATED_MEDIA = {
    140014: {145715, 145716, 145717, 145718},
}

FAMILY_VIDEO_URL_RE = re.compile(
    r'https://keshavarz20\.com/wp-content/uploads/2026/09/video(?:-\d+)?\.mp4',
    re.I,
)

VIDEO_BLOCK_PATTERNS = [
    re.compile(
        r'<h2>ویدئوی راهنمای این خانواده محصول</h2>\s*'
        r'<video\b[\s\S]*?</video>\s*'
        r'<p>این ویدئو یک راهنمای تصمیم‌گیری برای خانواده همین محصول است و جایگزین کنترل سایز، فشار، قطعه مقابل و مشخصات نمونه تحویلی نیست\.</p>',
        re.I,
    ),
    re.compile(
        r'<h2>ویدئوی راهنمای انتخاب سایز لوله نخدار</h2>\s*'
        r'<video\b[\s\S]*?</video>\s*'
        r'<p>این ویدئوی آموزشی با استفاده از تصویر واقعی همین محصول تهیه شده و اصول عمومی انتخاب سایز لوله نخدار و لی‌فلت را توضیح می‌دهد\. '
        r'ویدئو جایگزین محاسبه دبی، افت فشار، طول مسیر و اختلاف ارتفاع پروژه نیست\.</p>',
        re.I,
    ),
]

ORPHAN_VIDEO_TEXT = [
    '<h2>ویدئوی راهنمای این خانواده محصول</h2>',
    '<p>این ویدئو یک راهنمای تصمیم‌گیری برای خانواده همین محصول است و جایگزین کنترل سایز، فشار، قطعه مقابل و مشخصات نمونه تحویلی نیست.</p>',
    '<h2>ویدئوی راهنمای انتخاب سایز لوله نخدار</h2>',
    '<p>این ویدئوی آموزشی با استفاده از تصویر واقعی همین محصول تهیه شده و اصول عمومی انتخاب سایز لوله نخدار و لی‌فلت را توضیح می‌دهد. ویدئو جایگزین محاسبه دبی، افت فشار، طول مسیر و اختلاف ارتفاع پروژه نیست.</p>',
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_generated_gallery_image(product_id: int, image: dict) -> bool:
    src = str(image.get("src") or "")
    media_id = int(image.get("id") or 0)
    if f"/k21-p{product_id}-card-" in src:
        return True
    if f"/k21-{product_id}-decision-" in src:
        return True
    if media_id in CUSTOM_GENERATED_MEDIA.get(product_id, set()):
        return True
    return False


def remove_generated_video_content(html: str) -> tuple[str, bool]:
    original = html or ""
    cleaned = original

    for pattern in VIDEO_BLOCK_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Remove any remaining generated video element that points to our September K21/pilot media.
    cleaned = re.sub(
        r'<video\b[^>]*\bsrc=["\']https://keshavarz20\.com/wp-content/uploads/2026/09/video(?:-\d+)?\.mp4["\'][^>]*>[\s\S]*?</video>',
        "",
        cleaned,
        flags=re.I,
    )

    for text in ORPHAN_VIDEO_TEXT:
        cleaned = cleaned.replace(text, "")

    # Only collapse whitespace introduced by removals; do not rewrite the rest of the product copy.
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned, cleaned != original.strip()


def main() -> int:
    media_manifest = load_json(ROOT / "k21-top30-results" / "top30-media-batch.json")
    top30_ids = [int(x["product_id"]) for x in media_manifest.get("products", [])]
    if len(top30_ids) != 30:
        raise RuntimeError(f"Expected 30 Top30 products, got {len(top30_ids)}")

    OPS.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)

    summary = {
        "ok": True,
        "scope": "detach generated images/videos from products; keep original product media",
        "top30_products": len(top30_ids),
        "pilot_video_cleanup_product_id": PILOT_ID,
        "products": [],
        "guardrails": [
            "Original/non-generated product images remain attached.",
            "No price, stock, taxonomy, title, SKU, or SEO field is changed.",
            "Generated attachments are detached from products but not permanently deleted from Media Library.",
            "Only known generated video blocks/text are removed.",
        ],
    }

    request_count = 0
    for product_id in top30_ids + [PILOT_ID]:
        read_path = ROOT / "bridge-v3-results" / f"20260923-cleanup-read-{product_id}.json"
        if not read_path.exists():
            raise RuntimeError(f"Missing current Bridge readback for {product_id}")
        result = load_json(read_path).get("result") or {}
        current_desc = str(result.get("data_description") or "")
        cleaned_desc, video_removed = remove_generated_video_content(current_desc)

        current_images = result.get("data_images") or []
        removed_images = []
        kept_images = []

        if product_id in top30_ids:
            for image in current_images:
                if is_generated_gallery_image(product_id, image):
                    removed_images.append({
                        "id": int(image.get("id") or 0),
                        "src": image.get("src"),
                        "name": image.get("name"),
                    })
                else:
                    kept_images.append({"id": int(image.get("id") or 0)})

            if not kept_images:
                raise RuntimeError(f"Refusing cleanup for {product_id}: no original image would remain")
        else:
            kept_images = [{"id": int(image.get("id") or 0)} for image in current_images]

        payload = {}
        if product_id in top30_ids and removed_images:
            payload["images"] = kept_images
        if video_removed:
            payload["description"] = cleaned_desc

        if payload:
            request = {
                "action": "rest.proxy",
                "request_id": f"remove-generated-media-{product_id}-20260923",
                "method": "PUT",
                "path": f"/wc/v3/products/{product_id}",
                "payload": payload,
            }
            (OPS / f"20260923-remove-generated-media-{product_id}.json").write_text(
                json.dumps(request, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            request_count += 1

        summary["products"].append({
            "product_id": product_id,
            "name": result.get("data_name"),
            "removed_generated_image_ids": [x["id"] for x in removed_images],
            "kept_image_ids": [x["id"] for x in kept_images],
            "video_content_removed": video_removed,
            "request_generated": bool(payload),
        })

    summary["bridge_requests"] = request_count
    summary["generated_images_detached"] = sum(
        len(x["removed_generated_image_ids"]) for x in summary["products"]
    )
    summary["products_with_video_content_removed"] = sum(
        1 for x in summary["products"] if x["video_content_removed"]
    )

    (OUT / "generated-media-cleanup-plan.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "ok": True,
        "bridge_requests": request_count,
        "generated_images_detached": summary["generated_images_detached"],
        "products_with_video_content_removed": summary["products_with_video_content_removed"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
