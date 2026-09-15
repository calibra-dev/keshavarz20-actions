# Keshavarz20 No-Quota WebP / Media Runbook

## Control plane

Primary path only:

`ChatGPT -> GitHub -> calibra-dev/keshavarz20-actions -> GitHub Actions -> guarded WordPress/WooCommerce APIs / Keshavarz20 Bridge`

WPVibe is not required for this workflow. QUIC.cloud is not required for local WebP migration.

## Verified cleanup state

The approved zero-reference manifest contains 111 image attachments. All 111 have been permanently deleted through the guarded XML-RPC workflow with post-delete Bridge readback / 404 evidence. Attachments with real content, meta, option, or term references were protected.

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

### Primary featured-image XML-RPC fallback

Workflow: `.github/workflows/k20-local-webp-primary-xmlrpc.yml`

Use for a current product primary image when a valid WebP is generated but WooCommerce `images[]` reference replacement does not persist reliably.

- Re-read the product before every write.
- Require the expected attachment to be the current primary image and to occur exactly once.
- Encode with the same quality/PSNR/saving guards.
- Upload a new `image/webp` attachment and verify mime, dimensions, public HTTP response, content type, and byte size.
- Change only WordPress `post_thumbnail` through XML-RPC.
- Read the product back through WooCommerce up to three times and require the new media ID in primary position.
- On any failure after upload, restore the old primary attachment ID and remove the temporary WebP.
- Never modify price, stock, product content, taxonomies, users, settings, or unrelated fields in this workflow.

This fallback was production-verified and is now the preferred primary-image replacement path for legacy products that did not persist Woo `images[]` updates.

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

## Verified primary JPEG migrations

### Original guarded Woo path

Four products migrated successfully before the XML-RPC primary fallback was introduced:

- 134980 / 139862 -> 144291: 75,110 -> 23,780 bytes, 68.34% saving, PSNR 43.93 dB.
- 134982 / 139863 -> 144292: 75,110 -> 23,780 bytes, 68.34% saving, PSNR 43.93 dB.
- 134984 / 139857 -> 144293: 74,553 -> 23,438 bytes, 68.56% saving, PSNR 43.79 dB.
- 134994 / 139856 -> 144295: 73,547 -> 24,882 bytes, 66.17% saving, PSNR 43.76 dB.

### XML-RPC primary fallback pilot and legacy-failure recovery

The new primary fallback succeeded on all 8 targeted legacy/reference-persistence cases:

- 135010 / 139796 -> 144310: 69,507 -> 24,060 bytes, 65.38% saving, PSNR 43.93 dB.
- 134992 / 139855 -> 144311: 73,547 -> 24,882 bytes, 66.17% saving, PSNR 43.76 dB.
- 134996 / 139853 -> 144312: 73,547 -> 24,882 bytes, 66.17% saving, PSNR 43.76 dB.
- 135000 / 139292 -> 144313: 62,057 -> 26,194 bytes, 57.79% saving, PSNR 43.94 dB.
- 135002 / 139293 -> 144314: 62,057 -> 26,194 bytes, 57.79% saving, PSNR 43.94 dB.
- 135004 / 139291 -> 144315: 62,057 -> 26,194 bytes, 57.79% saving, PSNR 43.94 dB.
- 135006 / 139297 -> 144316: 62,057 -> 26,194 bytes, 57.79% saving, PSNR 43.94 dB.
- 135008 / 139294 -> 144317: 62,057 -> 26,194 bytes, 57.79% saving, PSNR 43.94 dB.

All eight returned XML-RPC edit success, public WebP HTTP verification, and WooCommerce primary-image readback; each verified on readback attempt 1.

### XML-RPC primary continuation batches

Batch 03 succeeded 5/5:

- 135020 / 139315 -> 144318: 67.58% saving, PSNR 43.42 dB.
- 135044 / 139380 -> 144319: 70.62% saving, PSNR 42.34 dB.
- 135050 / 139377 -> 144320: 70.62% saving, PSNR 42.34 dB.
- 135056 / 139373 -> 144321: 69.26% saving, PSNR 42.27 dB.
- 135058 / 139374 -> 144322: 69.26% saving, PSNR 42.27 dB.

Batch 04 succeeded 5/5:

- 135060 / 139372 -> 144323: 69.26% saving, PSNR 42.27 dB.
- 135064 / 139370 -> 144324: 69.26% saving, PSNR 42.27 dB.
- 135066 / 139369 -> 144325: 69.26% saving, PSNR 42.27 dB.
- 135068 / 139368 -> 144326: 69.26% saving, PSNR 42.27 dB.
- 135092 / 139954 -> 144327: 63.83% saving, PSNR 42.07 dB.

Batch 05 succeeded 5/5:

- 135098 / 144087 -> 144328: 63.83% saving, PSNR 42.07 dB.
- 135100 / 139325 -> 144329: 67.84% saving, PSNR 42.68 dB.
- 135102 / 139324 -> 144330: 67.84% saving, PSNR 42.68 dB.
- 135104 / 144228 -> 144331: 67.84% saving, PSNR 42.68 dB.
- 135106 / 139322 -> 144332: 68.09% saving, PSNR 42.30 dB.

All 15 continuation items passed public WebP checks and Woo primary-image readback on attempt 1.

## Product image inventory

Workflow: `.github/workflows/k20-product-image-inventory.yml`

Baseline inventory before the verified migration sequence:

- 653 published products read.
- 713 JPG/PNG product-image references.
- 663 distinct JPG/PNG attachment IDs.
- 648 JPG/PNG primary-image references.

Latest verified inventory checkpoint (`20260915-2135-published-products-final-checkpoint.json`):

- 653 published products read.
- 683 JPG/PNG product-image references.
- 636 distinct JPG/PNG attachment IDs.
- 621 JPG/PNG primary-image references.

Verified delta from the baseline inventory:

- JPG/PNG references: 713 -> 683, reduction of 30.
- Distinct JPG/PNG attachments: 663 -> 636, reduction of 27.
- JPG/PNG primary references: 648 -> 621, reduction of 27.

The 30-reference reduction matches 27 verified primary migrations plus 3 verified lossless gallery migrations. Do not infer attachment deletion from these counts; original source attachments remain until a separate zero-reference deletion audit proves they are safe to remove.

## Current execution checkpoint

The first remaining JPG primary in the latest inventory is:

- Product 135108 / attachment 139321 / `2101991094-1-1.jpg`.

Continue from the latest inventory rather than replaying completed products. Process primary JPEGs in small guarded batches, route PNG/transparent/line-art items through the lossless path when appropriate, and refresh inventory periodically.

## Batch policy

1. Read current product before each image migration.
2. Confirm the expected source attachment occurs exactly once and is in the expected product image position.
3. For current primary JPEGs, prefer the production-verified XML-RPC primary workflow.
4. For normal JPEG/product photography, use quality 88 as the starting point.
5. Prefer PSNR >=40 dB; absolute configured floor is 36 dB. Never lower the guard just to force a conversion.
6. For PNG, transparent assets, line-art, or any image where zero visual change is required, use pixel-exact lossless WebP.
7. If lossy quality guard fails, route to pixel-exact lossless WebP.
8. If neither candidate meets quality and size-saving guards, leave the original unchanged.
9. If a new WebP cannot be verified in the product primary/gallery position, rollback to the original attachment ID and remove the temporary upload.
10. If the same reference write fails repeatedly after the appropriate fallback, mark it skip-safe and continue rather than forcing it.
11. Keep the old source attachment until a fresh independent zero-reference audit proves it is safe to delete.
12. Record exact original bytes, new bytes, saving percentage, PSNR or `pixel_exact`, new media ID, public URL verification, and product readback.
13. Use small batches (maximum 10 migration items per request; current primary workflow is intentionally capped at 5) and never duplicate an active batch.

## Safe deletion policy

Before permanent attachment deletion, verify zero references across relevant WordPress/WooCommerce locations, including featured/product gallery references, post/page content, postmeta/Elementor data, options/theme settings, term meta, and attachment-ID or upload-URL/file references. Create an approved zero-reference manifest first, then delete only manifest-listed image IDs through the guarded XML-RPC deletion workflow and verify attachment/file disappearance afterward.

Do not infer deletion safety from `post_parent=0`, duplicate-looking filenames, or the presence of a WebP replacement.

## Safety boundaries

Do not modify prices, sale prices, discounts, coupons, payment settings, users, roles, capabilities, credentials, API keys, secrets, or broad WordPress administration. Keep workflows narrow and allow-listed.
