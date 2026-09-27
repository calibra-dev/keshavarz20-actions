# Keshavarz20 Bridge v3.3

GitHub-first guarded execution layer for keshavarz20.com. Version 3.3 keeps the existing `/keshavarz20-ops/v3` namespace and remains backward-compatible with the v3.1/v3.2 action surface.

## Added in 3.3

### Chat Asset Relay
- New authenticated multipart route: `POST /wp-json/keshavarz20-ops/v3/asset`.
- ChatGPT-created images can be transferred through detached Git blobs and uploaded directly by GitHub Actions.
- No public temporary media URL and no manual user upload is required.
- JPEG, PNG and WebP are accepted; the relay can normalize to WebP/JPEG/PNG, set quality/max dimension, title, caption and alt text.
- Uploaded files are SHA-256 fingerprinted.

### Asset binding
- `asset.featured.set`: set/replace the featured image for a product, post, page or custom post type.
- `asset.gallery.append`: append one or more images to a WooCommerce product gallery without dropping existing gallery items.
- `asset.gallery.replace`: replace a product gallery. This is approval-gated and snapshot-backed.
- `asset.content.insert`: insert one or more Gutenberg image blocks into post content with optional stale-SHA protection.
- Featured image, gallery and content changes create rollback snapshots where applicable.

### Code Snippets secure operations
- `snippet.list`
- `snippet.read`
- `snippet.validate`
- `snippet.create_draft`
- `snippet.update_draft`
- `snippet.deactivate`

Snippet creation/update is forced inactive. Active snippets cannot be edited until separately deactivated, and deactivation is approval-gated. Bridge does not expose snippet activation. Guard rules reject arbitrary execution primitives, raw SQL, filesystem mutation, user/role administration and product-price mutation.

Sensitive snippet payloads/results are designed to use the secure GitHub relay and are not committed to public result folders.

### Guarded code inspection
- `code.read`
- `code.search`

Read/search is limited to allow-listed roots and file types, rejects secret/config paths and redacts common secret assignments. Live arbitrary filesystem code writes remain disabled. Source-code writes continue through the GitHub-first review/package path.

## Retained from 3.2

- Snapshot and rollback.
- Two-phase approval.
- Background jobs with retry/backoff/dead-letter/failed-item replay.
- Gutenberg block inspect/patch.
- Elementor inspect/search/edit/structural operations.
- Media import, transform, metadata, hash, duplicate lookup, optimization, focal crop and watermark.
- Observability, self-test and guarded self-update.
- Products, posts, pages, taxonomies, WooCommerce catalog metadata and Yoast SEO.
- Question, News, Article and Product Social GitHub engines.

## Chat Asset Relay request model

The repository-side relay receives a small manifest under `bridge-v3-asset-ops/`. The actual image bytes live in detached immutable Git blobs, not in the repository tree.

Typical manifest:

```json
{
  "request_id": "p144248-gallery-20260924",
  "assets": [
    {
      "blob_sha": "<git-blob-sha>",
      "filename": "loole-nakhdar-moj-4-5-01.webp",
      "mime_type": "image/webp",
      "alt_text": "لوله نخدار آبیاری موج 4.5 اینچ"
    }
  ],
  "transform": {
    "output_mime": "image/webp",
    "quality": 88,
    "max_dimension": 1600
  },
  "target": {
    "operation": "gallery_append",
    "type": "product",
    "id": 144248
  }
}
```

Supported target operations are `featured_replace`, `gallery_append`, `gallery_replace`, and `content_insert`.

## Secure payload relay

Sensitive operations use `bridge-v3-secure-ops/`. The committed manifest contains only an immutable detached Git blob SHA and checksum. The real JSON request, including snippet source code, stays outside the repository tree. The workflow posts it to Bridge and stores the full response only as a short-lived GitHub Actions artifact.

## Update flow

1. Install the v3.3 ZIP over v3.2, or after the v3.3.0 release/manifest lands on `main`, use `update.check`.
2. `update.stage` downloads only the allow-listed GitHub release asset and verifies SHA-256.
3. `update.apply` is approval-gated, backs up the current plugin folder, then copies verified files.
4. The next request verifies the running version.
5. `update.rollback` is approval-gated and restores the last plugin backup.

## Hard boundaries

No price/sale-price changes, discounts, coupons, payment settings, users, roles, capabilities, credentials, customer/order exports, arbitrary SQL/PHP/shell/WP-CLI execution, arbitrary file access, or live arbitrary filesystem code writes.
