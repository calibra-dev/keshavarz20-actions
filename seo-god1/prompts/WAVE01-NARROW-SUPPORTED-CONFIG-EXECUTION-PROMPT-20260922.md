# WAVE 1 — Narrow Supported Config Unlock Execution Prompt

## Mission
Continue SEO God1 Wave 1 from the exact verified state. Do not repeat any closed work. Execute only the remaining highest-leverage, reversible, supported remediation for the verified LCP path, then re-measure. Preserve all hard safety guards.

## Verified completed work — DO NOT REPEAT
- IranKala 10.10.0 is active.
- Calculator singular no-cache root cause was resolved and warm cache HIT is proven.
- Calculator featured image payload was reduced.
- Homepage IranKala promotion images for terms 722 and 793 were replaced with verified WebP assets and live frontend readback passed.
- The prior heavy ~550 KB / ~716 KB homepage PNG render path is closed.
- Existing Phase20 exact-node accessibility audit is valid; do not rerun it unless an accessibility renderer/config mutation is actually applied.

## Current verified residuals
1. Homepage LCP image: `polyetilenetesal.keshavarz20-768x225.jpg`
   - still lazy-loaded
   - no `fetchpriority=high`
2. Calculator featured image:
   - `k20-calculator-featured-optimized-1200-768x432.webp`
   - still lazy-loaded
3. LiteSpeed current exact option:
   - key: `litespeed.conf.media-lazy_exc`
   - scalar JSON text value: `["polyetilenetesal.keshavarz20.jpg"]`
4. Phase20 accessibility residuals:
   - Owl carousel buttons lack accessible names
   - login/register link lacks accessible name
   - homepage image-only links lack discernible names
   - IranKala renderer PHP remains ionCube-protected
5. PHP runtime remains 8.1.34 and must not be upgraded without a hosting/staging compatibility path.

## Authorized narrow exception
Keep `admin_settings` blocked globally. Add only one explicit reversible exception:
- scope: `performance.litespeed_lcp_exclusions`
- option key: `litespeed.conf.media-lazy_exc`
- current required value: `["polyetilenetesal.keshavarz20.jpg"]`
- exact append-only additions:
  - `polyetilenetesal.keshavarz20-768x225.jpg`
  - `k20-calculator-featured-optimized-1200-768x432.webp`
- do not disable lazy-load globally
- do not enable VPI globally
- do not add class-wide or wildcard exclusions
- rollback must restore the exact original one-item JSON string

## Execution order
1. Re-read the exact option and abort if the precondition changed.
2. Apply only the exact append-only option mutation above through the GitHub-controlled workflow using the existing WordPress connection.
3. Read the option back byte-logically and verify all three entries, no extras.
4. Purge LiteSpeed page cache, Elementor CSS cache, and object cache.
5. Verify live HTML:
   - homepage target LCP image is no longer emitted as a LiteSpeed lazy placeholder/data-src path
   - calculator target image is no longer emitted as a LiteSpeed lazy placeholder/data-src path
   - unrelated images remain lazy-loaded; broad lazy-load must still be enabled
6. Run fresh performance/LCP verification only for the changed surfaces:
   - homepage
   - calculator
7. Compare against the latest pre-change evidence. Record:
   - cache HIT/MISS behavior
   - warm TTFB
   - LCP
   - CLS
   - TBT
   - total bytes
   - image bytes
8. If the expected LCP behavior is not improved or live HTML fails verification, rollback the exact option to the original value, purge caches, and record rollback evidence.
9. Do not modify protected IranKala PHP, inject arbitrary PHP/JS, alter price/payment/users/roles/secrets, or change unrelated options.
10. Do not claim Wave 1 PASS if Phase20 accessible-name defects or PHP/runtime blockers remain.

## Accessibility branch
After the LCP config change:
- do not inject runtime code to fix accessibility.
- search only for a vendor-supported setting/hook/ability that directly governs accessible names.
- if none exists, keep the Phase20 accessibility residual as a documented blocker.
- do not repeat the exact-node audit unless an actual accessibility mutation is made.

## Acceptance criteria
PASS for this narrow action requires:
- exact LiteSpeed option mutation verified
- cache purge verified
- live HTML confirms both verified target images are excluded from LiteSpeed lazy loading
- unrelated lazy loading remains enabled
- post-change performance/LCP evidence committed
- rollback path proven and documented
- no forbidden mutation
- master plan/current state/remaining gate updated from fresh evidence

## No-repeat rule
Do not redo:
- IranKala update verification
- calculator cache A/B
- calculator featured-image compression
- homepage promotion image source tracing
- homepage promotion WebP replacement
- Phase20 exact-node audit without a new accessibility mutation
