# DIGITS global PDP cache blocker — verified 2026-09-23

## Scope
Site: https://keshavarz20.com
Product population: 653 canonical product URLs in the live product sitemap.
Primary acceptance product: K60 ID 140856.

## Broad audit
Post-review-renderer Top50 audit:
- 50 requested
- 46 readable
- 21 cache HIT pages
- 25 explicit no-cache pages
- non-product guides largely remain HIT
- product PDPs remain the dominant no-cache cohort

## False-positive correction
Do not use `/?post_type=product&p=140856` for cache acceptance because it redirects.
Only direct canonical PDP URLs are valid acceptance targets.

## Canonical evidence
Direct canonical K60 and Hyper product URLs repeatedly returned:
- no `x-litespeed-cache`
- `x-litespeed-cache-control: no-cache,esi=on`

## LiteSpeed debug
Scoped production debug on canonical K60 recorded:
`forced no cache [reason] DONOTCACHEPAGE const`

LiteSpeed is therefore honoring a pre-existing third-party cache opt-out.

## Eliminated owners
- IranKala review template: replacing it with current WooCommerce core review template did not remove canonical no-cache.
- K20 Code Snippet #25 (Verified Review Capture): temporary deactivation with WooCommerce reviews still enabled did not remove canonical no-cache. It was reactivated.
- WooCommerce core normal product path does not ordinarily mark product pages no-cache; Cart/Checkout/My Account remain the expected private surfaces.
- WooCommerce Builder Elementor readable product/review files contained no direct no-cache setter.

## Confirmed owner: DIGITS
Active plugin:
- DIGITS 9.2.1

Reversible one-request A/B:
- DIGITS active before test.
- DIGITS temporarily deactivated.
- one direct canonical K60 anonymous request returned:
  - HTTP 200
  - `x-litespeed-cache: miss`
  - no `x-litespeed-cache-control: no-cache,esi=on`
- DIGITS was reactivated in the workflow finally block.
- live readback after test confirms DIGITS status = active.

This is direct site-specific evidence that DIGITS is the component causing the product cache opt-out.

## External compatibility evidence
Independent cache-plugin documentation also lists DIGITS among plugins that set `DONOTCACHEPAGE=true`. This corroborates, but does not replace, the local A/B evidence.

## Current safety decision
Do NOT:
- disable DIGITS in production,
- globally ignore `DONOTCACHEPAGE`,
- extend force-public blindly,
- cache Cart/Checkout/My Account,
- repeat review-disable, VPI, lazy-exclude, ESI toggle, recently-viewed, or force-public experiments.

No supported DIGITS setting was found that narrows this cache opt-out to login/account/checkout while keeping the plugin active.
DIGITS 9.2.1 has no currently offered plugin update on this installation.

## Release state
`PRODUCT_SINGULAR_CACHE_RENDERER = VENDOR_COMPATIBILITY_BLOCKED_DIGITS`

## Exact next safe action
Obtain a vendor-supported DIGITS compatibility method/filter/configuration that allows anonymous public WooCommerce product pages to remain cacheable while:
- DIGITS stays active,
- login/OTP/modal behavior remains correct,
- logged-in/user-specific responses remain private,
- Cart/Checkout/My Account remain no-cache/private.

Then apply only that supported method and validate canonical K60:
MISS -> HIT -> HIT, followed by Hyper/Mesi and the existing Top50 cohort.

Do not modify all 653 products individually. The blocker is global runtime behavior, not per-product data.
