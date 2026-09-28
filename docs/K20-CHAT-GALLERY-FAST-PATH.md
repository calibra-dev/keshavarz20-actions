# K20 Chat Gallery Fast Path

Default route for approved Keshavarz20 product-gallery transfers:

`ChatGPT -> connected GitHub -> K20 Chat Gallery Publisher -> Bridge 3.3 -> WordPress/WooCommerce -> readback`

## Fast-path rules

- Reuse the exact approved image set; do not regenerate.
- Resolve the exact product ID before the write. If the same session already has a verified product ID/SKU and no conflicting evidence, do not repeat discovery/contract/connectivity checks.
- Package approved WebP files once and submit one gallery request.
- Prefer one atomic commit. Use a temporary branch/PR only when `main` is moving concurrently.
- Supported request operations:
  - `append` -> `asset.gallery.append`
  - `replace` -> `asset.gallery.replace`
- Preserve the current featured image unless the user explicitly requests a featured-image replacement.
- Default `upload_workers`: 4. The publisher uploads gallery media in parallel, then performs one Bridge bind.
- Read back the exact product after binding. Do not report success unless the expected attachment IDs are present and the featured image is preserved.
- Do not rerun a successful or still-running publish job; this prevents duplicate gallery images.

## Request example

```json
{
  "product_id": 135319,
  "product_name": "Exact product name",
  "expected_count": 8,
  "operation": "replace",
  "upload_workers": 4,
  "payload_dir": "gallery-chat-payloads/<request-id>",
  "existing_attachment_ids": []
}
```

## Performance target

Normal target for an already-approved 8-image gallery is about 30-60 seconds after the request reaches GitHub. This is a target, not a hard SLA; GitHub Actions queueing, WordPress media processing, network latency, or server load can extend the runtime.

## Verification evidence

A complete publish report must include:

- request/commit reference
- workflow terminal conclusion
- result JSON with `ok: true` and `verified: true`
- uploaded attachment IDs
- final product image IDs
- `featured_preserved: true` unless featured replacement was explicitly requested
