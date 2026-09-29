# K20 Calculator Safe Performance Optimization Prompt

Target:
- URL: https://keshavarz20.com/drip-tape-length-fittings-calculator/
- WordPress post ID: 143698
- Current LCP element: featured image above the fold.
- Stack: WordPress + WooCommerce + IranKala theme + LiteSpeed Cache + Yoast + Elementor.
- Execution path: GitHub -> Keshavarz20 Bridge 3.3.x -> WordPress -> readback.

Mission:
Improve mobile Lighthouse / Core Web Vitals with priority on LCP and Speed Index while preserving all UI, calculator logic, SEO, mobile bottom navigation, cart/account/navigation behavior, analytics integrity, and current content.

Hard guards:
1. Never remove jQuery globally.
2. Never use blanket Delay All JS / Remove Unused CSS / async-all / dequeue-all techniques.
3. Never disable WooCommerce/cart fragments/theme assets globally without dependency proof.
4. Never change prices, checkout, payment, users, roles, credentials, or customer/order data.
5. Never accept a performance gain that causes visual/functional regression.
6. Every live change must be narrow, reversible, and followed by cache purge + readback.
7. One optimization class at a time. Do not bundle unrelated writes.
8. If a patch worsens median LCP by >250 ms, Speed Index by >500 ms, CLS above 0.10, causes console/UI/navigation/calculator regression, or lowers SEO, rollback immediately.
9. Preserve fetchpriority=high, loading=eager, data-no-lazy, explicit width/height, responsive srcset/sizes for the LCP image.
10. Do not claim success from a single Lighthouse outlier.

Execution loop:
A. Baseline
- Run 3 mobile Lighthouse samples.
- Record Performance, FCP, LCP, CLS, TBT, Speed Index, TTFB, render-blocking savings, unused CSS/JS, LCP breakdown, LCP element.
- Use median/representative values plus all 3 raw samples.

B. LCP asset optimization
- Inspect exact current featured attachment and generated sizes.
- Do not replace the featured attachment unless a dry-run confirms target/current IDs and the candidate has valid responsive derivatives.
- After any replacement: cache purge, exact attachment readback, public HTML readback, then 3 Lighthouse samples.
- Roll back on regression.

C. Critical rendering path
- Map LiteSpeed hashed CSS/JS to actual originating handles/components before any unload/defer.
- Apply route-specific changes only for post 143698 when proof shows the asset is unused before first paint.
- Preserve IranKala header, mobile nav, WooCommerce/cart, calculator form, buttons and footer.
- Avoid global plugin/theme setting changes if a page-specific alternative exists.

D. JavaScript / analytics
- Keep calculator runtime and jQuery dependencies intact.
- Only defer/delay third-party analytics after proving page_view/event integrity and no impact on measurement.
- Do not optimize unused bytes merely for score if Lighthouse reports no FCP/LCP saving.

E. Fonts / images
- Keep visual typography identical.
- Only preload fonts actually required above the fold; do not preload unnecessary weights.
- Fix responsive image sizing without changing displayed dimensions.

F. Validation after each patch
- Purge LiteSpeed + object/page cache.
- Verify: calculator inputs/results, copy/cart/quote controls, bottom nav, home/cart/account links, header, mobile layout, raw-code absence, console errors.
- Run 3 mobile Lighthouse samples.
- Keep only patches that improve or preserve the representative result with no regression.

Acceptance target:
- SEO = 100.
- CLS <= 0.10.
- LCP <= 2.5 s target; no regression allowed.
- Speed Index <= 3.4 s target.
- TBT <= 200 ms target or materially stable near it.
- Performance target >= 90 representative/median where repeatable.
- No visual or functional regression.
- Final report must include applied changes, rejected/rolled-back experiments, request/commit evidence, readback, 3-run metrics, and the public page URL.
