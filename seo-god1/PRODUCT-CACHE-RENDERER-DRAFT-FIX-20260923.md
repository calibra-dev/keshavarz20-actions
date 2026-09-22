# Product singular cache renderer — draft remediation prepared

Date: 2026-09-23
Site: https://keshavarz20.com
Target: K60 product ID 140856

## Verified current evidence
- LiteSpeed Cache 7.9.1 and WooCommerce 11.1.1 are active.
- LiteSpeed ESI is enabled.
- `litespeed.conf.esi-cache_commform = 1`.
- LiteSpeed's own ESI implementation renders `comment_form` as an ESI block and only marks that block no-cache when comment-form caching is disabled.
- The IranKala product review override `themes/irankala/woocommerce/single-product-reviews.php` is ionCube-protected.
- The live K60 page remains a known `no-cache,esi=on` product singular while reviews are enabled.
- Prior A/B evidence showed K60 became MISS/HIT/HIT only when product reviews were temporarily disabled, and reverted after reviews were restored.
- Exact force-public was already tested and rejected; do not repeat.

## Draft remediation
Because Bridge v3.2 does not expose safe theme/template file writes, the renderer-only change was prepared through the WPVibe draft-theme sandbox.

Draft:
- `irankala-wpvibe-draft`

Changed draft file only:
- `woocommerce/single-product-reviews.php`

Change:
- Replaced the ionCube-protected IranKala review template override in the draft with the current WooCommerce 11.1.1 core template (template version 9.7.0).
- No live theme file was changed.
- No price, stock, coupon, payment, user, role, or product data was changed.

## Draft verification
Rendered K60 through the draft using product ID 140856.
Verified present:
- review tab
- review list empty-state
- rating select
- review textarea
- author and email fields
- WordPress comment cookies consent
- review nonce
- K20 custom real-experience review fields
- comment_post_ID = 140856

This proves the standard WooCommerce review template remains functionally compatible with the current review extensions in the draft.

## Release gate
NOT LIVE YET.

The final production acceptance must only run after:
1. human preview of the draft,
2. a recent site/host backup is confirmed,
3. explicit publish/go-live approval,
4. draft publish,
5. LiteSpeed purge,
6. K60 anonymous cache sequence acceptance: MISS -> HIT -> HIT,
7. review form/list remains functional,
8. Cart / Checkout / My Account remain private/no-cache,
9. canonical/schema/SEO output is unchanged.

If K60 still returns full-page no-cache after the standard template is live, the next step is not another force-cache experiment. Instrument the exact caller/reason that sets `DONOTCACHEPAGE` or `litespeed_control_set_nocache` on the product request.
