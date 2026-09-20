# Keshavarz20 SEO God — Remaining Closure Stage v1 — 2026-09-20

## Mission
Finish every remaining SEO God / 30-day validation item that is safely executable now, without repeating closed audits, without fabricating external evidence, and without forcing protected IranKala/theme code changes.

## Current release state
Phase 25 v7 is NOT_RELEASED_10_OF_10.

Already closed or not to repeat:
- Phase 10 GA4 + GSC connectivity and live reads
- fresh sitemap-derived crawl delta: 839/839 rendered, 0 failures
- drip-tape calculator recovery action is APPLIED_WAITING_GSC
- Phase 16 graph build
- duplicate H1 / heading-order content remediation already closed
- previously completed technical/indexability/trust/PIM/governance audits

## Remaining work to execute now

### 1) Brand / entity collision delta — execute now
Audit live WordPress taxonomy state for product_brand versus product_cat.
- Identify exact same-name / same-slug collisions.
- Record term IDs, names, counts and whether both public archive surfaces coexist.
- Do NOT merge, delete, redirect, noindex, or rewrite taxonomy structures automatically.
- Reason: taxonomy ownership/intent must be explicit before structural SEO mutation.
- Classify each collision:
  - DUPLICATE_SURFACE_CONFIRMED
  - SAME_LABEL_DIFFERENT_INTENT
  - UNUSED_TERM
  - NEEDS_OWNER_POLICY
- Write immutable evidence under validation-results.

### 2) 60-product reconciliation — evidence-first
- Search repository/project sources for the authoritative original 60-product workbook/list.
- If the authoritative list is present, compare only those 60 products against current live WordPress state and existing SEO modifications.
- Do not re-edit already-complete products.
- Do not infer membership from random product sets or from unrelated copy-ready documents.
- If the authoritative 60-item source is absent, mark WAITING_SOURCE_ARTIFACT and do not fabricate a 60-item list.
- Record exactly what source was checked and why reconciliation can or cannot proceed.

### 3) Phase 24 direct AI-surface observation gate
- Preserve live GA4 evidence: chatgpt.com / ai-assistant referral sessions are observed.
- Retry Bing live telemetry once; if provider returns ThrottleIP again, retain CONNECTED_PROVIDER_THROTTLED.
- Do not equate referral with citation.
- Do not claim citation_rate, brand_mention_rate, share-of-voice, or recommendation unless direct answer-surface observations are actually captured.
- If direct authenticated observation channels for ChatGPT/Perplexity/Gemini/Copilot/Google AI Overview are unavailable, mark WAITING_EXTERNAL_SURFACE_OBSERVATION rather than zero.

### 4) Phase 20 / Phase 7 guard
- Do not repeat diagnostics.
- Phase 20 remaining failures are theme/Owl accessible-name issues.
- Phase 7 remaining blockers are IranKala protected renderer + singular no-cache behavior.
- No protected-code modification, no arbitrary JS/PHP injection, no paid QUIC.cloud/VPI activation without explicit user approval.
- Keep as POLICY_GUARD unless a supported vendor/theme route appears.

### 5) Final gate update
Write a new Phase 25 result only because brand/entity collision evidence and source-artifact status materially change the remaining validation ledger.
Final verdict rules:
- RELEASED_10_OF_10 only if every active hard gate is truly closed or explicitly waived.
- Missing 60-product source is not PASS.
- Missing direct AI-surface observations are not PASS.
- Protected theme blockers are not hidden behind PASS.
- Calculator remains WAITING_GSC until settled data exists.

## Safety
- No price/sale/payment/user/role/credential changes.
- No taxonomy delete/merge/redirect in this execution.
- No protected theme/plugin modifications.
- No broad page rewrites.
- No fabricated analytics, rankings, citations, or product membership.

## Required outputs
1. validation-results/brand-entity-collision-delta-20260920.json
2. validation-results/60-product-reconciliation-status-20260920.json
3. phase24-results/direct-surface-observation-gate-20260920.json
4. phase25-results/final-release-gate-v8-20260920.json
