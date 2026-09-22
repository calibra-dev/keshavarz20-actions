# Keshavarz20 Bridge v3

Guarded WordPress execution layer for the GitHub-first Keshavarz20 control plane.

## Endpoints

- GET /wp-json/keshavarz20-ops/v3/
- GET /wp-json/keshavarz20-ops/v3/health
- GET /wp-json/keshavarz20-ops/v3/capabilities
- POST /wp-json/keshavarz20-ops/v3/execute

It reuses normal WordPress REST authentication and creates no new credential.

## Coverage

- WordPress posts, pages, media, categories, tags, and search
- WooCommerce products, product categories, tags, global attributes and attribute terms
- Product draft creation and non-price updates through official WooCommerce REST controllers
- Yoast title, meta description, focus keyword, canonical and noindex metadata
- Elementor metadata inspection
- Cache status and guarded purge
- System/plugin inventory read
- Dry-run, bounded batch execution, idempotent request IDs and bounded audit receipts

## Hard boundaries

No price/sale/discount/coupon/payment changes. No user/role/capability management. No credentials/tokens/secrets. No customer/order export. No SQL, arbitrary PHP, shell, generic command execution or arbitrary file access.
