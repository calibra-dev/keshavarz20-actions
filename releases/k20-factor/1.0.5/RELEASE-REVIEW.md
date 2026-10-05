# K20 Factor 1.0.5 — Responsive & Commercial UX Hardening

Status: RELEASE CANDIDATE; not deployed from this branch.

Base/live evidence before build:
- K20 Factor 1.0.4 was active on keshavarz20.com.
- WordPress 7.1.2
- PHP 8.3.31
- WooCommerce 11.1.2
- PWSMS/KaveNegar reported ready.
- HPOS was disabled on the live baseline.

Fixed in 1.0.5:
1. Tablet 901–1100 navigation class mismatch.
2. Real off-canvas overlay, click-outside, Escape, body scroll lock, focus trap/restore.
3. Correct RTL/right and LTR/left sidebar motion.
4. Create/Edit line items become responsive cards at tablet/mobile widths.
5. Detail line items become responsive cards at tablet/mobile widths.
6. Public checkout item table becomes cards at <=820px.
7. Conflicting product-search grid removed/overridden.
8. Product/customer debounce paths remain independent.
9. Tablet/mobile editor footer no longer overlays content.
10. Critical touch targets raised to ~44px.
11. Semantic responsive labels added, including English.
12. Long product/SKU/note strings wrap without page overflow.
13. Existing empty delivery channels stay empty.
14. Server notification dispatch no longer silently falls back to SMS.
15. 1.0.4 positive-ID, single-flight save/send and paid/expired guards retained.

QA:
- PHP source syntax 22/22 PASS
- JavaScript source syntax 4/4 PASS
- Static contracts 81/81 PASS
- Responsive browser cases 52/52 PASS
- Dark/contrast browser cases 19/19 PASS
- Viewports: 360, 375, 390, 412, 768, 820, 1024, 1280, 1440, 1920
- ZIP integrity PASS
- Extracted PHP syntax 22/22 PASS
- Extracted JS syntax 4/4 PASS
- Source vs extracted ZIP PASS

Install artifact:
- K20-Factor-1.0.5.zip
- size: 143756 bytes
- SHA256: 713f5a1e4cb30bd40499fe57c76c1c0323333239d77557382a89d281436a2808

Production acceptance is intentionally pending installation of this exact artifact and real PWSMS/gateway/expiry/HPOS staging gates.
