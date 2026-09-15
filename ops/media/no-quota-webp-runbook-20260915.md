# Keshavarz20 No-Quota WebP / Media Runbook

## Control plane

Primary path only:

`ChatGPT -> GitHub -> calibra-dev/keshavarz20-actions -> GitHub Actions -> guarded WordPress/WooCommerce APIs / Keshavarz20 Bridge`

WPVibe is not required for this workflow. QUIC.cloud is not required for local WebP migration.

## Verified cleanup state

The approved zero-reference manifest contains 111 image attachments. All 111 have now been permanently deleted through the guarded XML-RPC workflow with post-delete Bridge readback / 404 evidence. Attachments with real content, meta, option, or term references were protected.

Never delete an attachment because `post_parent=0` alone, because the filename looks duplicated, or because a WebP replacement exists.

## No-quota WebP architecture

### High-quality lossy path

Workflow: `.github/workflows/k20-local-webp.yml`

- Encode on GitHub-hosted runner with Pillow/WebP.
- Start at quality 88; retry higher quality when needed.
- Minimum PSNR guard: 36 dB. Prefer materially higher values when available.
- Require material byte saving before replacement.
- Upload as a new WordPress `image/webp` attachment.
- Preserve exact dimensions, ALT where supplied by WooCommerce, and product image order.
- Verify Bridge mime/dimensions, public HTTP 200 + `image/webp`, and WooCommerce product readback.
- On failure, restore original product image IDs and remove the failed new upload.
- Do not delete the old source attachment merely because migration succeeded.

### Pixel-exact lossless fallback

Workflow: `.github/workflows/k20-local-webp-lossless.yml`

Use when zero visual/pixel loss is required or the lossy path cannot pass the quality threshold.

- WebP lossless, method 6.
- Require `pixel_exact=true` by decoded pixel comparison.
- Require a real size reduction before replacement.
- Same upload, dimension, public URL, product position, readback, rollback, and cleanup guards as the lossy path.

## Verified pilots

### Product 144248 / attachment 144275

- Old primary PNG: 1,879,817 bytes, 1254x1254.
- New primary attachment: 144289, WebP.
- Final WebP: 162,580 bytes.
- Reduction: about 91.35%.
- It passed the configured lossy quality guard.
- WordPress generated responsive WebP sizes for the new attachment.

### Product 144249 / attachment 144276

- Old primary PNG: 1,889,319 bytes, 1254x1254.
- Lossy attempt was rejected because it could not reach PSNR 36 dB.
- Lossless fallback created attachment 144290.
- Final WebP: 1,301,840 bytes.
- Reduction: 31.09%.
- `pixel_exact=true`.
- Product readback confirmed attachment 144290 in the original primary-image position.
- WordPress generated responsive WebP sizes.

### Pilot galleries: pixel-exact lossless

- Product 144248 / old attachment 144271 -> new attachment 144303.
  - 2,600,602 -> 1,847,492 bytes.
  - Reduction 28.96%.
  - `pixel_exact=true`.
- Product 144249 / old attachment 144277 -> new attachment 144305.
  - 1,995,785 -> 1,354,746 bytes.
  - Reduction 32.12%.
  - `pixel_exact=true`.
- Product 144249 / old attachment 144278 -> new attachment 144307.
  - 2,021,244 -> 1,440,842 bytes.
  - Reduction 28.72%.
  - `pixel_exact=true`.

All three lossless gallery replacements passed public WebP verification and product readback.

## Verified primary JPEG batch 01

Four products migrated successfully through the lossy quality-guarded path:

- 134980 / 139862 -> 144291: 75,110 -> 23,780 bytes, 68.34% saving, PSNR 43.93 dB.
- 134982 / 139863 -> 144292: 75,110 -> 23,780 bytes, 68.34% saving, PSNR 43.93 dB.
- 134984 / 139857 -> 144293: 74,553 -> 23,438 bytes, 68.56% saving, PSNR 43.79 dB.
- 134994 / 139856 -> 144295: 73,547 -> 24,882 bytes, 66.17% saving, PSNR 43.76 dB.

Two products repeatedly failed only the product image-reference readback after valid WebP generation and upload:

- 134992 / 139855.
- 134996 / 139853.

For both, rollback succeeded and the temporary WebP was removed. Treat these as skip-safe reference-write edge cases for the current workflow; do not repeatedly force them without first diagnosing why WooCommerce does not retain that image-reference update.

## Product image inventory

Workflow: `.github/workflows/k20-product-image-inventory.yml`

Latest published-product inventory:

- 653 published products read.
- 713 JPG/PNG product-image references.
- 663 distinct JPG/PNG attachment IDs.
- 648 JPG/PNG primary-image references.

Process primary images first, then gallery images. Work in small guarded batches and verify each batch before expanding.

## Current execution checkpoint

- Primary batch 02 request: `local-webp-ops/20260915-primary-webp-batch02.json`.
- GitHub Actions run: `35018181845`.
- At the last verified checkpoint, this run was still in the conversion/upload/verification step. Before creating any duplicate request for these six items, inspect this run and its matching result file first.

## Batch policy

1. Read current product before each image migration.
2. Confirm the expected source attachment occurs exactly once in that product image array.
3. For normal JPEG/product photography, try guarded high-quality lossy WebP.
4. Prefer PSNR >=40 dB; absolute configured floor is 36 dB. Never lower the guard just to force a conversion.
5. For PNG, transparent assets, line-art, or any image where zero visual change is required, use pixel-exact lossless WebP.
6. If lossy quality guard fails, route to pixel-exact lossless WebP.
7. If neither candidate meets quality and size-saving guards, leave the original unchanged.
8. If a valid WebP upload cannot be confirmed in the product image array, rollback the product to its original image IDs and remove the temporary upload.
9. If the same image-reference write fails repeatedly on a product, mark it skip-safe and continue with other products instead of forcing it.
10. Keep the old source attachment until a fresh independent zero-reference audit proves it is safe to delete.
11. Record exact original bytes, new bytes, saving percentage, PSNR or `pixel_exact`, new media ID, public URL verification, and product readback.
12. Use small batches (maximum 10 migration items per request) and never duplicate an active batch.

## Safe deletion policy

Before permanent attachment deletion, verify zero references across relevant WordPress/WooCommerce locations, including featured/product gallery references, post/page content, postmeta/Elementor data, options/theme settings, term meta, and attachment-ID or upload-URL/file references. Create an approved zero-reference manifest first, then delete only manifest-listed image IDs through the guarded XML-RPC deletion workflow and verify attachment/file disappearance afterward.

Do not infer deletion safety from `post_parent=0`, duplicate-looking filenames, or the presence of a WebP replacement.

## Safety boundaries

Do not modify prices, sale prices, discounts, coupons, payment settings, users, roles, capabilities, credentials, API keys, secrets, or broad WordPress administration. Keep workflows narrow and allow-listed.
