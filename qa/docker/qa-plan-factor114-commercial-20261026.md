# Calibra Factor 1.1.4 — Docker QA gate (2026-10-26)

Target plugin archive: Calibra-Factor-1.1.4.zip
SHA-256 (validated in local runtime): 5318a699467e33944aeda3fd17a13b3baa7a1434ef93f9be54de685ef7bc54a4
Plugin version: 1.1.4; WordPress slug: calibra-factor.
Request: certify commercial readiness (not baseline only).

This branch triggers the existing disposable Docker baseline through the configured feat/** + qa/docker/** path.
**Important: This QA branch does not include the private ZIP or a GitHub Actions plugin artifact.**
The resulting baseline execution MUST NOT be described as a plugin install/upgrade test or commercial approval.

For plugin certification run the reusable workflow with an authenticated same-repository plugin artifact ID + exact SHA and add application-specific assertions:
- fresh install and reinstall of exact ZIP, genuine upgrade from previous ZIP; preservation of settings/docs.
- Legacy and HPOS WooCommerce order creation, subtotal/tax/discount/currency, guest order-pay and gateway authorization.
- Valid order key displays only that order's buyer details; invalid key reveals no personal data.
- Concurrent SMS + WhatsApp: each provider invoked exactly once, independent results, failures visible, timeout does not auto retry.
- PDF signed URL authorization and revocation, idempotency and permissions.
- Playwright 390/768/1366 RTL layouts, no overlap, console/network failures.
- PHP 8.3 and 8.4, WooCommerce active version and licensing/commercial rights.
Until those tests succeed and real SMS/gateway sandbox work is demonstrated: NOT READY FOR SALE.
