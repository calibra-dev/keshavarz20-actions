# engine-gallery-product-creator

Safe two-stage product gallery infographic engine for Keshavarz20.

## Non-negotiable rule

Preview generation and gallery publication are separate workflows.

- Preview workflow may READ WooCommerce product data and download public product/reference images.
- Preview workflow MUST NOT upload media or modify a product.
- Publish workflow runs only from an explicit approval file and verifies the exact preview hashes before any write.
- Existing gallery images are preserved and new images are appended.
- Price, stock, coupons, users, orders, payment settings and unrelated product fields are never written.

## Flow

1. Put one JSON request in `engine-gallery-product-creator/queue/`.
2. `K20 Gallery Product Creator Preview` reads the product and creates exactly 5 square 1000x1000 WebP previews.
3. The workflow validates the five files and commits them under `engine-gallery-product-creator/previews/<batch_id>/` with a manifest.
4. ChatGPT shows the five previews to the site operator.
5. Nothing is published until the site operator explicitly approves that exact batch.
6. After approval, ChatGPT creates `engine-gallery-product-creator/approvals/<batch_id>.json` with the exact hashes from the manifest and `approved: true`.
7. `K20 Gallery Product Creator Publish` revalidates product ID, batch ID and all five SHA-256 hashes, uploads the five WebP files, appends them to the existing WooCommerce gallery, and verifies readback.
8. The publisher records evidence under `engine-gallery-product-creator/publish-results/`. On readback failure it attempts to restore the previous gallery IDs.

## Queue request example

```json
{
  "engine": "engine-gallery-product-creator",
  "mode": "preview",
  "batch_id": "p140014-mehpash-v1",
  "product_id": 140014,
  "category_key": "mist-pipe",
  "reference_image_url": null,
  "notes": "Use current product image when no category reference image is supplied."
}
```

`reference_image_url` is optional. When the operator supplies a category reference image, use its stable URL here. The engine never invents technical values.

## Approval example

```json
{
  "engine": "engine-gallery-product-creator",
  "batch_id": "p140014-mehpash-v1",
  "product_id": 140014,
  "approved": true,
  "approved_by": "user_chat_confirmation",
  "approval_phrase": "APPROVED_FOR_GALLERY",
  "asset_sha256": [
    "... five hashes copied exactly from manifest ..."
  ]
}
```

The publish workflow refuses missing, false, malformed, stale or hash-mismatched approvals.

## Slide contract

Each product gets five independent square slides:

1. Hero / product identity.
2. Verified specifications and dimensions.
3. Use-case / field-context explanation without fabricated performance numbers.
4. Buying and installation checklist.
5. Compatibility / CTA summary.

Category-specific rules can override labels and known mappings but cannot create unsupported technical claims.

## Safety

- No automatic publish from preview.
- No automatic gallery modification from a queue request.
- No gallery delete/reorder in the initial version.
- Append only.
- Existing gallery IDs are read immediately before publish.
- Exact SHA-256 verification is mandatory.
- Publication is idempotent by committed publish evidence.
- All uploaded files are WebP, 1000x1000.
