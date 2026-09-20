# SEO God — Phase 25 Final Release Gate v5 (2026-09-20)

## Mission
Execute the final evidence-based release gate for Keshavarz20 SEO God without repeating closed audits, without inventing evidence, and without claiming 10/10 unless every required hard gate is actually closed or explicitly waived by the active rubric.

## Source of truth
Repository: calibra-dev/keshavarz20-actions
Site: https://keshavarz20.com
Primary execution path: ChatGPT -> GitHub -> GitHub Actions / guarded gateway -> WordPress / WooCommerce / Keshavarz20 Bridge
WPVibe is fallback only when the GitHub path lacks a required safe capability.

## Non-negotiable guards
- Do not expose or request secrets, tokens, credentials, or application passwords.
- Do not bypass ionCube or patch protected theme/plugin files arbitrarily.
- Do not change price, sale price, discounts, coupons, users, roles, capabilities, payment settings, or credentials.
- Do not invent GTIN/MPN, compatibility, reviews, endorsements, field results, AI citations, GSC/Bing/GA data, or performance results.
- Do not delete or force-convert protected media IDs 141437, 141441, 142597.
- Do not repeat a closed audit unless there is fresh regression evidence or stale/missing evidence.

## Closed/guarded work that must not be re-run from zero
Treat the following as already completed unless new evidence proves regression:
- Phase 3 root-cause performance audit
- Phase 6 technical indexability
- Phase 8 Entity & Trust
- Phase 9 PIM/Compatibility architecture
- Phase 11 product decision modules
- Phase 12 Category Decision Page
- Phase 13 content/guide ownership
- Phase 14 tools/calculators
- Phase 16 internal-link authority graph build
- Phase 17 evidence framework
- Phase 18 governance
- Phase 19 internal feed/API parity
- IndexNow site-side setup
- duplicate H1 remediation
- heading-order remediation

## Current known unresolved gates to verify, not assume
1. Phase 7:
   - field LCP previously about 9.753s
   - latest lab LCP previously about 4.4s
   - hero image lazy-loading behavior tied to protected IranKala renderer
   - singular no-cache path unresolved
   - official IranKala 10.10.0 updater previously returned HTTP Forbidden
2. Phase 20:
   - Owl-dot button-name
   - login/register link-name
   - site-logo accessible name
   - image-only product/promo link names
3. Phase 10 external read access:
   - GA4 collection exists site-side, but external Analytics OAuth/read scope must be verified independently
   - Bing Webmaster API connection must be verified independently
   - CrUX API connector/key only if required by the active rubric
4. Phase 24:
   - real observations across named AI answer/search surfaces must exist before claiming measurement complete
5. 30-day plan:
   - remaining priority internal-link applications
   - reconciliation of the original 60-product workbook against already-modified products
   - brand/entity collision delta audit
   - 404/soft-404 technical delta cleanup
   - fresh Coverage/Internal Links comparison against baseline
6. Phase 25:
   - final verdict must be derived from evidence above, not from intent.

## Execution sequence
A. Verify control plane
- Inspect current gateway/workflow implementation before relying on remembered behavior.
- Run bridge.health through the guarded GitHub path.
- Record request commit, workflow run ID, conclusion, and result/readback.

B. Evidence freshness scan
- Inspect latest evidence in phase7-results, phase20-results, phase24-results, phase25-results and relevant 30-day/GSC evidence paths.
- Determine whether any evidence newer than the previous Phase 25 gate materially changes a blocker.
- Do not rerun closed audits merely because the date changed.

C. Gate evaluation
Classify each phase as exactly one of:
PASS
PASS_GUARDED
WAITING_EXTERNAL
POLICY_GUARD
OPEN
SKIPPED_BY_USER

For every non-PASS item, include:
- exact blocker
- latest evidence path/commit/run
- whether ChatGPT/GitHub can act now
- exact next action, if any

D. Release rule
Return RELEASED_10_OF_10 only if:
- no hard internal blocker remains,
- all required external measurement dependencies in the active rubric have verified evidence,
- Phase 24 real-surface measurement is actually complete,
- the final 30-day validation delta is complete,
- no unresolved blocker is being hidden behind a guarded status.

Otherwise return NOT_RELEASED_10_OF_10.

E. Output
Write one new immutable result file under phase25-results with:
- generated_at_utc
- source commits/runs
- bridge health
- phase-by-phase state
- deltas since previous Phase 25 result
- hard blockers
- actionable next steps
- release verdict
- no-repeat ledger

## Required behavior
Be strict with evidence. A blocked external dependency is not a failure of completed internal work, but it is still a blocker if the active release rubric requires it. Never convert missing evidence into a pass.
