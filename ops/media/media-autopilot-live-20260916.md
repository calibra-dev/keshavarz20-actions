# Keshavarz20 Media Autopilot — Live 2026-09-16

## Goal

Continuously migrate every published WooCommerce product image reference that is still JPG/JPEG/PNG to verified WebP, one image at a time inside small sequential cycles, without QUIC.cloud quota dependency.

## Control plane

`ChatGPT -> GitHub -> calibra-dev/keshavarz20-actions -> GitHub Actions -> guarded WordPress/WooCommerce APIs / Keshavarz20 Bridge`

WPVibe is not used by this automation.

## Files

- Workflow: `.github/workflows/k20-media-autopilot.yml`
- Worker: `scripts/k20_media_autopilot.py`
- Config: `media-autopilot/config.json`
- Checkpoint: `media-autopilot/state.json`
- Per-cycle evidence: `media-autopilot-results/run-<run_id>.json`

## Self-chaining model

- Each run reads the live published-product image inventory.
- Primary images are processed before gallery images.
- Up to 20 references are processed sequentially per cycle.
- Each image is re-read immediately before write.
- The cycle commits a checkpoint and sanitized evidence.
- If state remains `running`, the workflow dispatches the next workflow run itself.
- Concurrency is locked to one autopilot run at a time (`cancel-in-progress: false`).
- A critical rollback failure changes state to `halted`; no next cycle is dispatched.

## Quality guards

### JPEG

- Start WebP quality 88.
- Retry quality 92 and 95 when necessary.
- Require PSNR >= 40 dB for lossy replacement.
- Require >= 15% size saving for lossy replacement.
- If lossy cannot pass the quality/saving guards, try pixel-exact lossless WebP.

### PNG

- Use WebP lossless.
- Require decoded `pixel_exact=true`.
- Require >= 5% size saving.

If no candidate meets the guards, leave the original reference unchanged and record a terminal safe skip. Never lower quality guards just to force a conversion.

## Reference/write guards

Before each write:

- Confirm product is readable live.
- Confirm expected attachment is still at the expected product image position.
- Require the source attachment to occur exactly once in the product image array.
- Verify source attachment through the Bridge.
- Verify new attachment mime is `image/webp`.
- Preserve dimensions.
- Verify public WebP URL and content type.
- Copy and verify ALT text.

Primary image replacement uses WordPress XML-RPC `post_thumbnail`, because this path was verified to solve WooCommerce image-reference persistence issues on older products.

Gallery replacement uses guarded WooCommerce image-array update while preserving image order.

Every replacement requires WooCommerce readback. On failure, restore the previous image reference and delete the failed temporary WebP upload.

## Original files

Old JPG/PNG attachments are NOT automatically deleted after a successful migration. They remain until a separate zero-reference audit proves they are safe to delete across product/gallery references, content, Elementor/meta, options/theme settings, term meta, and attachment URL/ID references.

## Verified first live cycle

Initial run: `35030881916`

- 20 selected.
- 20 successful migrations.
- 0 failures/skips.
- 0 critical events.
- All 20 used guarded lossy WebP and passed PSNR >= 40 dB.
- ALT preservation succeeded.
- Inventory before: 683 JPG/PNG refs, 621 primary refs, 636 distinct attachment IDs.
- Inventory after: 663 JPG/PNG refs, 601 primary refs, 617 distinct attachment IDs.

The workflow successfully queued run 2 through `workflow_dispatch`, proving the self-chaining mechanism works.

## Stop conditions

The chain stops automatically when one of these conditions is reached:

1. No JPG/JPEG/PNG product image references remain -> `completed`.
2. Only terminal safe skips remain -> `completed_with_skips` for focused manual review.
3. A critical rollback failure occurs -> `halted` and the chain stops immediately.
4. The configured maximum cycle count is reached -> `halted`.

## Hard safety boundaries

Do not modify prices, sale prices, discounts, coupons, payments, stock, users, roles, capabilities, credentials, secrets, or broad WordPress administration as part of this automation.
