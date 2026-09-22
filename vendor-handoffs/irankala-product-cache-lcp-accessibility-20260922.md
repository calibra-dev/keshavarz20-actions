# IranKala / WooCommerce renderer handoff — product cache, homepage LCP, accessibility

Date: 2026-09-22  
Site: https://keshavarz20.com  
Theme: IranKala (ionCube-protected renderer paths)  
Control plane: GitHub -> Keshavarz20 Bridge v3.2 -> WordPress/WooCommerce

## Why this handoff exists

The remaining high-impact performance/accessibility work cannot be solved safely by editing protected theme source or by repeating rejected LiteSpeed experiments.

The site must preserve:
- WooCommerce product reviews and review submission.
- Cart / checkout / account / logged-in / session privacy.
- Product schema, visible content, SEO fields and analytics.
- Theme updateability.

## Verified product-cache root cause

Current production evidence shows:

1. Anonymous product singular requests remain explicit LiteSpeed `no-cache,esi=on`.
2. The sampled K60 product becomes cacheable when WooCommerce product reviews/comments are temporarily disabled.
3. The same product returns to explicit no-cache after reviews are restored.
4. Product reviews were restored immediately; disabling them is rejected as a production optimization.
5. The `woocommerce_recently_viewed` cookie A/B did not remove the product no-cache condition.
6. ESI, exact force-public, current VPI and exact lazy-exclude experiments do not provide an acceptable production fix.
7. Non-product posts with open comments and zero approved comments became cacheable after comments were safely closed, confirming that the comment/review renderer path can control cacheability.

Primary evidence:
- `seo-god1/STAGE00-PERFORMANCE-GATE-RESULT-20260922.json`
- `diagnostics/cache-rootcause/20260922-k60-reviews-disabled-cache-ab-v1.json`
- `diagnostics/cache-rootcause/20260922-k60-reviews-restored-cache-verify-v1.json`
- `phase7-results/closure-20260919-final.json`

## Verified homepage LCP renderer issue

The above-the-fold IranKala homepage slider emits the hero with native/theme `loading="lazy"` and without a supported direct `fetchpriority="high"` control in the current protected renderer.

Rejected/no-repeat experiments:
- VPI on the current hero: worsened measured homepage LCP and was rolled back.
- Exact LiteSpeed lazy-exclude experiment: did not safely clear the theme-emitted behavior.

Primary evidence:
- `results/frontend-rootcause-20260918-phase7-lcp-banner-context-v2.json`
- `seo-god1/STAGE11-RENDERER-ACCESSIBILITY-GATE-20260922.json`

## Verified accessibility residuals

Current residuals are renderer-generated:
- Owl carousel dot buttons without accessible names.
- Site-logo / image-only theme links without discernible accessible names.

No supported option/hook was found in the current guarded path, and no arbitrary JS/PHP injection is permitted.

Primary evidence:
- `phase20-results/final-remediation-20260921.json`

## Requested supported vendor capabilities

Please provide one or more supported, update-safe mechanisms for the following:

### A. Product reviews without forcing the whole anonymous PDP to no-cache
Preferred outcomes, in order:
1. Keep the anonymous PDP cacheable while rendering review form/list via a supported cache-compatible fragment/ESI strategy.
2. Expose a theme option/filter/action that prevents the review renderer from setting the whole product request no-cache when no private/session state is required.
3. Provide an official theme update that makes this behavior LiteSpeed/WooCommerce compatible.

### B. Homepage hero priority control
Expose a supported option/filter for the first above-the-fold slider image so the renderer can:
- omit lazy loading for the initial visible hero only,
- emit `fetchpriority="high"` where appropriate,
- preserve lazy loading for below-the-fold slides.

### C. Accessible names
Expose or fix:
- Owl carousel dot/button labels,
- site-logo link accessible name,
- image-only theme/widget link names.

## Acceptance tests

A vendor-supported fix is acceptable only if all of these pass:

### Product cache
- First anonymous K60 PDP request: MISS is allowed.
- Subsequent anonymous request: HIT.
- Product review list/form remains visible and functional.
- Product review submission still works.
- Logged-in / WooCommerce session requests do not leak private content through shared cache.
- Cart, checkout and account remain private/no-cache.
- Product structured data, canonical and SEO output are unchanged except where intentionally modified.

### Homepage
- No regression in homepage LCP compared with the current accepted baseline.
- Initial visible hero is discoverable early without preloading an unnecessarily oversized source.
- Below-the-fold media remains lazy where appropriate.

### Accessibility
- Carousel controls have accessible names.
- Logo and image-only interactive links have discernible names.
- Keyboard interaction remains functional.

## Do not repeat

Do not repeat these experiments on the current renderer unless the renderer/configuration materially changes:
- VPI current-hero experiment.
- Exact LiteSpeed lazy-exclude experiment.
- ESI toggle experiment.
- `woocommerce_recently_viewed` A/B.
- Disabling product reviews for speed.
- Protected IranKala source modification.

## Current priority

This vendor-supported renderer/cache path is the highest-impact unresolved internal blocker. Once an official hook/update is available, re-run the same product/cache acceptance and the same homepage/accessibility checks—only then.
