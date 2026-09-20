# Keshavarz20 Phase 7 Final Supported Performance Closure — 2026-09-21

Mission: exhaust every supported non-destructive performance path without editing protected IranKala/ionCube renderer code.

Verified prior evidence:
- mobile field LCP ~9.753s
- lab LCP ~4.4s
- active LCP image snippets already set eager/fetchpriority for WooCommerce images where WordPress filters receive the image
- protected IranKala renderer can bypass those attachment filters
- singular no-cache behavior remains a known theme/runtime constraint
- official IranKala updater 10.10.0 previously returned HTTP Forbidden

Execution:
1. Inspect current active snippets and cache/theme state; do not duplicate existing LCP snippets.
2. Re-test the supported updater path/version availability once.
3. Inspect whether LiteSpeed safe settings can improve the affected renderer without paid QUIC.cloud/VPI and without changing dynamic WooCommerce safety.
4. Do not enable guest-mode/UCSS/JS-delay or other broad performance features blindly.
5. Do not edit protected theme files or inject arbitrary executable code via DB/options.
6. If no supported route can reach the renderer, preserve POLICY_GUARD_VENDOR_THEME and record exact closure condition.
7. Do not claim field LCP recovery without new field data.

Required evidence:
- phase7-results/final-supported-closure-20260921.json
- Phase25 v10 only if state/evidence materially changes.
