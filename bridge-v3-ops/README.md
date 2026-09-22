# Keshavarz20 Bridge v3 requests

Commit a uniquely named JSON file under this folder to trigger the guarded Bridge v3 workflow.

Example read:

```json
{
  "action": "rest.proxy",
  "method": "GET",
  "path": "/wc/v3/products/123"
}
```

Example safe draft creation:

```json
{
  "action": "rest.proxy",
  "method": "POST",
  "path": "/wc/v3/products",
  "payload": {
    "name": "Temporary product",
    "status": "draft"
  }
}
```

Example SEO dry-run:

```json
{
  "action": "seo.update",
  "id": 123,
  "dry_run": true,
  "payload": {
    "title": "SEO title",
    "description": "SEO description"
  }
}
```

Supported families include WordPress posts/pages/media/search/categories/tags, WooCommerce products/product categories/tags/attributes, Yoast metadata, Elementor inspection, cache status/purge, bounded batch execution, audit receipts, dry-run, and idempotent request IDs.

Hard denied: prices, discounts/coupons, payment data, users/roles/capabilities, credentials/secrets, customer/order data, SQL, arbitrary PHP/shell/commands.
