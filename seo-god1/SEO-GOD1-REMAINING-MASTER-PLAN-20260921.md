# SEO God1 Remaining — Master Execution Plan

Date: 2026-09-21
Repository: calibra-dev/keshavarz20-actions
Mode: GitHub-first / evidence-first / no-repeat / no fabricated PASS

## Goal
Close every still-open SEO God1 gate across phases 1–25, without repeating completed audits and without inventing commercial, technical, review, case-study, video, or telemetry evidence.

## Current closed / do-not-repeat
- Phase 8: PASS_GUARDED
- Phase 9: PASS_GUARDED
- Phase 10: PASS
- Phase 14: PASS (9/9 tools)
- Phase 16: PASS (10/10 acceptance; manifest-first)
- Phase 17: PASS
- Phase 18: PASS (27/27 + production news publisher E2E)
- Phase 19: PASS (agentic/readiness governance; external feed eligibility gaps remain governed unknowns)

## Release-blocking waves

### Wave 1 — Supported runtime/theme remediation (P0)
Phases: 3 + 20; unlocks 21, 22, 23 and part of Phase25.
Work:
1. Establish one supported deployment path for IranKala/theme renderer fixes. No DB-injected arbitrary PHP/JS.
2. Fix accessible names: login/register, site-logo/image-only links, Owl dots.
3. Fix homepage heading hierarchy / duplicate H1 where still present in fresh evidence.
4. Resolve singular product/calculator no-cache root cause without caching cart/checkout/session pages.
5. Reduce PDP CLS and calculator/home LCP; profile cart/checkout TTFB.
6. Stage PHP 8.1 -> supported branch with compatibility validation before production.
Acceptance:
- Phase20 fresh accessibility gate PASS.
- Mobile performance targets improve materially and no commerce/session regression.
- Supported-code provenance documented.
Blocker/unlock:
- Requires vendor-supported IranKala update/hook or an explicitly allow-listed code deployment path in keshavarz20-git-ops.
- PHP upgrade requires hosting/staging control.

### Wave 2 — Commerce path + measurement truth (P0)
Phases: 1 + 2.
Work:
1. Approve/document nationwide shipping model: local pickup / parcel / freight / quote-only and ETA rules.
2. Expose a guarded shipping test/config path; do not guess freight or ETA.
3. Add/verify payment redundancy only after explicit policy authorization for payment-setting work.
4. Implement canonical analytics events: begin_checkout single-fire; add_shipping_info; add_payment_info; purchase deduped by transaction_id; whatsapp_click; call_click; request_quote; shipping_quote.
5. Validate with a safe sandbox/non-charged lifecycle where possible.
Acceptance:
- One controlled checkout => one begin_checkout.
- Successful test order => exactly one purchase.
- Shipping/payment events fire once with no PII/secrets.
- Phase1 checkout/order lifecycle and Phase2 attribution both PASS.
Blocker/unlock:
- Shipping business rules.
- Explicit payment-policy change if payment settings must be modified.
- Allow-listed tagging/configuration path.

### Wave 3 — Product truth + PDP/CRO + discovery (P1)
Phases: 4 + 6 + 7 + external-readiness gaps in 19.
Work:
1. Import only authoritative manufacturer/supplier data for GTIN/MPN/brand/specs.
2. Promote compatibility edges only with real evidence.
3. Expand real product galleries; priority Top20 currently mostly one-image.
4. Add truthful shipping/returns/warranty clarity only after policy/source exists.
5. Normalize search aliases: Persian/Latin digits, inch/mm, ZWNJ, PE/polyethylene, threaded variants.
6. Add structured technical attributes before exposing technical facets.
7. Implement mobile filter chips/drawer/clear-all/no-results recovery and decision-attribute compare.
8. Re-run feed/page/schema parity; resolve external feed currency/brand/description requirements without inventing identifiers.
Acceptance:
- Top30 PIM >=85 where evidence permits.
- No fabricated GTIN/MPN/spec/compatibility.
- Priority PDP CRO/media gates pass.
- Search/filter/compare implementation passes mobile QA.
Blocker/unlock:
- Manufacturer/supplier specs and real product media.
- Supported theme/plugin implementation path for facets/UI.

### Wave 4 — Quote / Review / CRM / Retention backend (P1)
Phases: 11 + 12 + 13.
Work:
1. Structured quote/proforma backend with status pipeline and lost-reason taxonomy.
2. Shipping quote + evidence-backed ETA handoff.
3. Consent-aware post-delivery review request; never fabricate reviews/AggregateRating.
4. CRM/form backend with consent/no-contact enforcement.
5. WhatsApp/Telegram provider integration for contextual, consented automation.
6. Abandoned-cart/post-purchase flows only after consent state is enforceable.
7. Connect request_quote/purchase/whatsapp_click attribution to the Phase2 canonical contract.
Acceptance:
- Quote submission/status/readback works.
- Review outreach is consent-aware.
- CRM stop/unsubscribe state enforced.
- No PII committed to public repo.
Blocker/unlock:
- CRM/form endpoint or connected CRM.
- Approved messaging provider.
- Phase2 tagging implementation path.

### Wave 5 — Visual / Video / Video Sitemap (P1)
Phase: 15.
Work:
1. Render 20 real videos from the prepared scripts.
2. Host stable public video + thumbnail URLs.
3. Fill landing_page, duration_seconds, publication_date, title, description.
4. Run Video Sitemap Gate.
Acceptance:
- registered=20, ready=20, blocked=0.
- No fake URLs/metadata.
Blocker/unlock:
- Rendering capacity/credits or external render pipeline.
- Current evidence: InVideo insufficient credits; Higgsfield credits insufficient for 20 videos.

### Wave 6 — External authority + AI influence measurement (P1)
Phases: 21 + 22 + 23 + 24.
Work:
1. After Phase20 PASS, re-run 21/22/23 dependency gates.
2. Execute real citation/outreach assets only where appropriate; no PBN/fake review/dealership claims.
3. Collect direct observations across required AI answer surfaces from the 200-prompt bank.
4. Re-check settled post-change GSC data for the drip-tape calculator once enough data exists.
5. Measure AI citation/brand/landing-page coverage only from observed results; null stays null when unavailable.
Acceptance:
- Phase21/22/23 dependency gate cleared.
- Phase24 source influence/citation observations are evidence-backed.
- No citation or recommendation claims inferred from referrals alone.
Blocker/unlock:
- Phase20 PASS.
- Access to required external AI answer surfaces / telemetry.
- Settled GSC window after calculator changes.

## Post-PASS controlled backlog

### Wave 7 — Phase16 link-graph application waves (P2)
Current manifest: sitemap URLs 1103; indexable canonical pages 493; internal edges 2913; priority-zero/orphan targets 308; broken proposed priority links 0.
Rules:
- Apply in controlled waves only after destination/source content is stable.
- No mass body rewrite.
- Each wave requires donor/receiver canonical readback, link verification and cannibalization check.
- Rebuild manifest after each wave.

## Final release

### Wave 8 — Phase25 Final 10/10 Gate
Run only after Waves 1–6 required gates are closed.
Must verify performance/runtime; accessibility/agent usability; commerce path + measurement; product truth/CRO/discovery; quote/review/CRM; video readiness; AI influence evidence; no hard fabrication; no unauthorized commercial/security mutations.

## Explicit no-repeat rule
Do not re-run phases 8, 9, 10, 14, 16, 17, 18, or 19 unless a later mutation affects their governed resources or their evidence becomes stale.

## Immediate next action
WAVE_1_SUPPORTED_RUNTIME_THEME_REMEDIATION
Reason: it is the highest-leverage release blocker and unlocks Phase20 -> Phase21/22/23, while also addressing Phase3/Phase25 performance and accessibility blockers.
