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
- Minimum PSNR guard: 36 dB.
- Require material byte saving before replacement.
- Upload as a new WordPress `image/webp` attachment.
- Preserve exact dimensions and product image order.
- Verify Bridge mime/dimensions, public HTTP 200 + `image/webp`, and WooCommerce product readback.
- On failure, restore original product image IDs and remove the failed new upload.
- Do not delete the old source attachment merely because migration succeeded.

### Pixel-exact lossless fallback

Workflow: `.github/workflows/k20-local-webp-lossless.yml`

Use when the lossy path cannot pass the quality threshold.

- WebP lossless, method 6.
- Require `pixel_exact=true` by decoded pixel comparison.
- Require a real size reduction before replacement.
- Same upload, dimension, public URL, product position, readback, rollback, and cleanup guards as the lossy path.

## Verified pilots

### Product 144248 / attachment 144275

- Old PNG: 1,879,817 bytes, 1254x1254.
- New primary attachment: 144289, WebP.
- Final WebP: 162,580 bytes.
- Reduction: about 91.35%.
- It passed the configured lossy quality guard.
- WordPress generated responsive WebP sizes for the new attachment.

### Product 144249 / attachment 144276

- Old PNG: 1,889,319 bytes, 1254x1254.
- Lossy attempt was rejected because it could not reach PSNR 36 dB.
- Lossless fallback created attachment 144290.
- Final WebP: 1,301,840 bytes.
- Reduction: 31.09%.
- `pixel_exact=true`.
- Product readback confirmed attachment 144290 in the original primary-image position.
- WordPress generated responsive WebP sizes.

## Product image inventory

Workflow: `.github/workflows/k20-product-image-inventory.yml`

Latest published-product inventory:

- 653 published products read.
- 713 JPG/PNG product-image references.
- 663 distinct JPG/PNG attachment IDs.
- 648 JPG/PNG primary-image references.

Process primary images first, then gallery images. Work in small guarded batches and verify each batch before expanding.

## Batch policy

1. Read current product before each image migration.
2. Confirm the expected source attachment occurs exactly once in that product image array.
3. Try guarded high-quality lossy WebP.
4. If quality guard fails, try pixel-exact lossless WebP.
5. If neither candidate meets the configured quality/saving guards, leave the original unchanged.
6. Never lower the quality guard merely to force a conversion.
7. Keep old source attachment until a fresh independent zero-reference audit proves it is safe to delete.
8. Record exact original bytes, new bytes, saving percentage, quality/pixel-exact evidence, new media ID, and product readback.

## Safety boundaries

Do not modify prices, sale prices, discounts, coupons, payment settings, users, roles, capabilities, credentials, API keys, secrets, or broad WordPress administration. Keep workflows narrow and allow-listed.
