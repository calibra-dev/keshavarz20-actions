# K20 Factor 1.0.4 hardening review

Status: release candidate; NOT deployed from this branch.

Live pre-fix evidence (2026-10-05):
- K20 Factor 1.0.3 active
- WordPress 7.1.2
- PHP 8.3.31
- WooCommerce 11.1.2
- Bridge 3.3.33
- K20 Factor bootstrap/diagnostics/connectors/documents read paths healthy through authenticated fallback after Bridge returned route_not_allowed for this plugin namespace.

Confirmed fixes in 1.0.4:
1. Save-only no longer generates/uploads PDF.
2. Save/Send is single-flight; both buttons lock and stay locked through redirect.
3. Quantity/price/discount/tax/shipping updates totals in-place instead of rebuilding the editor.
4. Product and customer search debounce timers are independent.
5. List search/status/kind/page state is URL-backed.
6. Pagination exposes first/current neighbors/last plus previous/next.
7. New-document delivery mode defaults to link, not link+PDF.
8. Empty delivery channels stay empty; no silent SMS fallback.
9. Paid/expired/cancelled resend is guarded in UI and server paths.
10. Admin/public clipboard fallback added.
11. REST/network errors surface parameter and permission details.
12. Client money math follows WooCommerce currency decimals.
13. Saved document ID is retained after downstream PDF/provider failure so retry updates the same order.
14. Downstream send/PDF errors keep the user in the editor.
15. Positive-ID route hardening remains in place to prevent /documents/0.

QA on source and exact extracted ZIP:
- PHP syntax 22/22 PASS
- JS syntax 4/4 PASS
- Static contracts 68/68 PASS
- JS runtime regressions 16/16 PASS
- PHP runtime regressions 3/3 PASS
- ZIP integrity PASS
- Source vs extracted ZIP PASS

Install artifact:
- K20-Factor-1.0.4.zip
- size 138226 bytes
- SHA256 c654470876051b2ee94f653cdc1490e5d6360947dbb9f0f7caad6e7588d5f182

Production acceptance remains pending installation of that exact artifact and post-install browser/provider/gateway checks.
