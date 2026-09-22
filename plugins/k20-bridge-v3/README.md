# Keshavarz20 Bridge v3.1

GitHub-first guarded execution layer for keshavarz20.com.

## WordPress actions

- system.info
- rest.proxy
- seo.read / seo.update
- content.search / content.patch
- elementor.inspect / elementor.search / elementor.edit
- media.import / media.transform / media.metadata
- cache.status / cache.purge
- audit.tail / batch
- job.create / job.status / job.run

### Content and Elementor safety

Content edits use exact search/replace, optional expected SHA-256 stale-write protection, match-once by default, and JSON validation for Elementor data. Elementor edits clear Elementor/object cache after a successful write.

### Media

HTTPS image import supports JPEG, PNG and WebP with a 15 MiB bound. Image transforms create a new attachment instead of overwriting the source. Supported transforms: resize, crop, rotate, horizontal/vertical flip, and quality.

### Background jobs

Jobs store bounded progress and receipts in WordPress options, process in small chunks, schedule continuation through WP-Cron, and can be resumed manually. Maximum: 500 items/job. Job-control actions cannot recursively enqueue themselves.

## GitHub-side actions

The GitHub client additionally supports:
- engine.status
- engine.run
- gitops.profile

Allow-listed engines:
- question -> k20-customer-question-engine.yml
- news -> k20-daily-agri-news.yml
- article -> k20-article-queue-publisher.yml
- social -> k20-daily-product-social.yml

The WordPress plugin never stores a GitHub token. Engine routing runs in GitHub Actions with the repository token.

## keshavarz20-git-ops alignment

The gateway follows the same operating model:
ChatGPT -> GitHub -> guarded gateway -> WordPress/WooCommerce/K20 Bridge.

## Hard boundaries

No price/sale/discount/coupon/payment mutation. No users/roles/capabilities. No credentials/tokens/secrets. No customer/order export. No arbitrary SQL/PHP/shell/WP-CLI or arbitrary file access.
