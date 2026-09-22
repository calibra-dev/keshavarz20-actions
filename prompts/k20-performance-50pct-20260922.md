# Keshavarz20 Performance Acceleration Prompt — 50-page evidence gate

## Objective
Measure the homepage and 50 strategically important public pages, identify the dominant shared bottlenecks, and execute only safe, reversible, evidence-backed optimizations with a target of at least 50% reduction in median page-opening time where technically achievable.

The target is a goal, not a result. Never claim 50% until the same URLs are re-tested after the changes.

## Selection
Build the 50-page cohort from:
1. Strategic core pages and decision tools.
2. Highest-click / highest-impression pages from the latest first-party GSC baseline in the repository.
3. Ensure representation of homepage, articles, calculators/selectors, product categories, brands, and product detail pages.

## Baseline measurement
For every URL:
- Perform 3 anonymous GET samples with empty Cookie header.
- Record HTTP status, DNS, connect, TLS, TTFB, total transfer time, HTML bytes, redirects, remote IP, Content-Type.
- Record LiteSpeed cache state and LiteSpeed cache-control state.
- Read the rendered HTML at least once and record page title and basic resource counts.
- Run mobile Lighthouse performance diagnostics on the highest-priority strategic subset.
- Persist a sanitized baseline in GitHub.

## Optimization policy
Prioritize fixes by expected sitewide impact:
1. Public cacheability for safe anonymous GET requests.
2. Server/backend response time and runtime version.
3. LCP discovery and hero preload/eager-loading only when live acceptance proves a gain.
4. Large images and media payloads.
5. Render-blocking / excessive JS/CSS only through supported theme/plugin settings or safe content/template edits.
6. Redirect chains and avoidable origin work.
7. Repeated bottlenecks shared by many URLs before one-off cosmetic tuning.

## Hard guards
- Do not change product prices, coupons, payments, users, roles, credentials, or secrets.
- Do not disable WooCommerce reviews merely to win a speed benchmark.
- Do not remove useful content, structured data, SEO fields, schema, analytics, consent, cart, checkout, account protection, or security controls.
- Keep cart, checkout, account, logged-in, AJAX, and session-dependent routes private/no-cache.
- Do not edit ionCube-protected IranKala source files.
- Do not inject arbitrary PHP/JS or bypass the guarded bridge policy.
- Do not repeat previously rejected VPI or exact lazy-exclude experiments unless a materially different renderer/configuration state exists.
- Prefer snapshots, reversible media replacements, allow-listed Bridge actions, and cache purge/readback.
- Preserve all verified SEO/AEO/GEO work.

## Execution loop
1. Baseline the 50 pages.
2. Cluster slow pages by root cause.
3. Apply the smallest sitewide high-impact safe fix.
4. Purge relevant caches if needed.
5. Re-test the same 50-page cohort.
6. Calculate improvement per URL and cohort medians.
7. Keep a change only if it passes regression gates:
   - no broken HTTP or redirects,
   - no loss of product/session functionality,
   - no regression in cart/checkout/account privacy,
   - no material Lighthouse regression on strategic pages,
   - no SEO/AEO/GEO content or schema damage.
8. Roll back failed experiments.
9. Continue to the next safe root cause until the target is met or the remaining blockers require vendor/hosting/user approval.

## Acceptance
Report:
- baseline cohort median TTFB and total time,
- post-change cohort median TTFB and total time,
- percentage improvement,
- cache HIT/no-cache counts,
- Lighthouse deltas on the strategic subset,
- exact changes retained,
- exact experiments rolled back,
- unresolved blockers.

A 50% improvement may be declared only if the measured post-change median total opening time is <= 50% of baseline on the same 50 URLs, or an explicitly defined equivalent metric is met and documented.
