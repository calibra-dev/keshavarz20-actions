# Keshavarz20 Bridge v3.2

GitHub-first guarded execution layer for keshavarz20.com. Version 3.2 keeps the existing `/keshavarz20-ops/v3` namespace and is backward-compatible with the v3.1 action surface.

## Added in 3.2

- Snapshot and rollback for post fields, Elementor data, Yoast SEO metadata and media metadata.
- Two-phase approval with frozen request fingerprint for high-impact operations.
- Background jobs with retry, backoff, dead-letter queue and failed-item replay.
- Gutenberg block inspect/patch with stale-block SHA protection.
- Elementor structural editor: update settings, remove, duplicate, insert and move.
- Media Pro: SHA-256 fingerprint, duplicate lookup, WebP/JPEG/PNG optimization, focal crop and non-destructive watermark via Imagick.
- Observability status: job queue, dead letters, approvals, snapshots, update marker, cache and cron state.
- Lifecycle self-test using temporary draft resources with cleanup.
- Self-update: trusted GitHub release manifest, SHA-256 verification, staged package, backup before apply and explicit rollback.
- API contract 3.2 with v3.1 compatibility guarantee.
- Unified GitHub Engine Router schema for Question, News, Article and Product Social engines.

## Existing capabilities retained

Products, posts, pages, media, taxonomies, WooCommerce catalog operations, Yoast SEO, Elementor text edits, content patch, cache, audit, dry-run, idempotency, batch and four GitHub engines.

## Update flow

1. Install v3.2 ZIP over v3.1 in WordPress, or after v3.2 is active use `update.check`.
2. `update.stage` downloads only the allow-listed release package and verifies its SHA-256.
3. `update.apply` is approval-gated, backs up the current plugin folder, then copies verified files.
4. The next request verifies the running version.
5. `update.rollback` is approval-gated and restores the last plugin backup.

## Hard boundaries

No price, sale price, discounts, coupons, payment settings, users, roles, capabilities, credentials, customer/order exports, arbitrary SQL/PHP/shell/WP-CLI, or arbitrary file access.
