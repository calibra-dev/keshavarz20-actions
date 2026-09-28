# K20 Calculator Safe Performance Execution Prompt

Target:
- URL: https://keshavarz20.com/drip-tape-length-fittings-calculator/
- WordPress post ID: 143698
- Theme: IranKala
- WooCommerce site; preserve all cart/account/mobile navigation behavior.

Primary goals:
- LCP <= 2.5s on repeatable mobile Lighthouse runs.
- Speed Index <= 3.4s where practical.
- Preserve SEO=100, CLS < 0.1, TBT <= 200ms where possible.
- No visual or functional regression in the calculator, header, bottom navigation, cart, account link, WooCommerce, WhatsApp, or Persian RTL UI.

Hard constraints:
1. Never use broad global dequeue/delay rules.
2. Never remove jQuery, WooCommerce, IranKala core CSS, Digits, WhatsApp, analytics, or mobile navigation globally.
3. Never reactivate historical aggressive snippets 47/48.
4. Every production change must be scoped to post 143698, reversible, and followed by cache purge + readback.
5. Do not modify price, checkout/payment settings, users, roles, secrets, or customer/order data.
6. Prefer source-handle mapping over LiteSpeed hashed filenames.
7. Keep the original featured attachment 145308 as the canonical featured/OG/schema image unless an explicitly verified page-only rendering filter is used.
8. Run at least 3 mobile Lighthouse samples after each accepted patch; use the median/representative run, and note cold-cache outliers separately.

Known measured baseline:
- Representative pre-patch: Performance ~71, FCP ~2.59s, LCP ~4.44s, CLS ~0.095, TBT ~287ms, Speed Index ~3.73s, TTFB ~361ms.
- Post-purge warm representative: Performance ~79, FCP ~2.52s, LCP ~4.27s, CLS ~0.067, TBT ~154ms, Speed Index ~3.44s, TTFB ~325ms.
- Cold-cache outlier observed: TTFB ~4.0s, Speed Index ~9.59s.
- LCP element: featured image attachment 145308.
- LCP discovery already passes: fetchpriority=high, eager loading, initial-document discoverability.
- Render-blocking opportunity ~440ms.
- Unused CSS ~56 KiB.
- Unused JS ~75 KiB, dominated by Google tag manager.
- Page has ~31 scripts / 10 stylesheets.
- LiteSpeed Cache is active; object cache is not active.

Known source-handle map:
- irk-common-css -> IranKala common.css
- irk-woocommerce-css -> IranKala woocommerce.css
- mega-theme-icon-css -> Elementor Pro MegaTheme icon CSS
- digits-style-css / digits-login-style-rtl-css -> Digits
- nta-css-popup-rtl-css and nta-* JS -> WhatsApp plugin
- jquery-core-js / jquery-migrate-js -> WordPress jQuery
- google-tag-manager-js -> Google tag manager
- libphonenumber-mobile-js -> Digits
- pDate / pDatepicker / pDatepickerLoader -> Elementor Pro MegaTheme
- persian-datepicker / persian-datepicker-custom -> AvayNil Email Subscriber
- slick / venobox / dtwcbe -> WooCommerce Builder for Elementor
- sourcebuster / wc-order-attribution -> WooCommerce attribution

Execution sequence:
A. Deploy only low-risk phase-1 guard:
   - Add a 672x378 WebP LCP candidate generated from attachment 145308.
   - Keep attachment 145308 as canonical featured image.
   - Inject the 672w candidate only into the calculator featured-image srcset.
   - Correct the calculator featured-image sizes attribute to viewport width minus 40px mobile gutters.
   - Keep fetchpriority=high/loading=eager/decoding=async.
   - Set fetchpriority=low on google-tag-manager-js only on this post; keep async and keep analytics functioning.
   - Dequeue only the clearly irrelevant payment-gateway help CSS handle help_style on this post.
B. Purge LiteSpeed and object cache only after successful deploy.
C. Verify HTML readback:
   - 672w candidate present.
   - original 1200 canonical/OG/schema image unchanged.
   - google-tag-manager-js remains present and async, with low fetch priority.
   - calculator UI and bottom navigation markers remain present.
D. Run 3 mobile Lighthouse samples and compare against baseline.
E. If LCP remains >2.5s, do not guess. Identify the next safe asset by handle and prove it is unused in this page/interactions before page-specific dequeue.
F. Never trade visual/functional correctness for a Lighthouse score.

Rollback:
- If any UI/function regression is detected, restore the previous Bridge plugin backup via update.rollback and purge cache.
