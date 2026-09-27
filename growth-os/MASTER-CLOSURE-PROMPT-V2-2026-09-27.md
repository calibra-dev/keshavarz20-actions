# Keshavarz20 GrowthOS Closure Prompt v2 — Continue Only From Open Gates

## Mission
Continue the master closure from the exact current state without repeating any phase already verified or guarded. Work only on unresolved gates and stop promoting stale evidence.

## Source of truth
- growth-os/MASTER-CLOSURE-STATE-2026-09-27.json
- growth-os/MASTER-CLOSURE-PROMPT-2026-09-27.md
- latest per-phase result/readback artifacts
- live Keshavarz20 site through GitHub -> Bridge 3.3 -> WordPress/WooCommerce
- direct AI surface captures only for Phase 24 citation measurement

## No-repeat law
1. Do not rerun a closed or guarded phase unless a listed upstream dependency materially changed.
2. Do not replace a verified result with a plan, spec, code diff, queued workflow or stale summary.
3. Do not claim PASS until fresh readback satisfies the current acceptance criteria.
4. If a previous audit itself is incomplete, fix the audit before using its result.
5. Never fabricate technical specs, compatibility, GTIN, brand, customer evidence, citations, partner access, Merchant eligibility, price, stock or external surface observations.
6. Preserve UNKNOWN / SOURCE_BOUND / EXTERNAL_GATE explicitly.
7. Ordinary web search, referral traffic, GSC/Bing telemetry or snippets are not direct AI citation evidence.

## Open Gate 1 — Phase 17 Question Engine v19 production closure
Current state:
- v19 runtime is active in scheduler/manual/heartbeat.
- production status readback succeeded.
- production dry-run succeeded.
- a real ontology leak was detected for product 141442 (perlite classified as fitting).
- Bridge readback proved product 141442 is cultivation media / perlite.
- v19 was patched to classify perlite and the "بستر کشت" category as growing_media.
- QA was upgraded to require all 652 products, not only the first 1200 candidates.

Required work:
1. Run the full-catalog QA on all 652 published products.
2. Every product must produce at least one valid, non-contradictory candidate or an explicit governed exclusion state.
3. Require:
   - products_covered = catalog_products = 652, OR governed_exclusions + covered = 652;
   - blocker_count = 0;
   - semantic_duplicate_rate_last_200 < 0.10;
   - synthetic questions remain classified as synthetic editorial evidence, never real customer evidence;
   - cultivation-media products must not receive fitting/installation/waterproofing prompts.
4. Run status and dry-run production readback after the final ontology fix.
5. Only then mark Phase 17 PASS_V19_PRODUCTION.

## Open Gate 2 — Roadmap Phase 21 Membership Value Engine
Current state:
- verified account-backed saved project/calculation/question/proforma history does not exist.
- required qualified-member events are missing.
- Bridge generic page-search routes are not allow-listed.

Required work:
1. Reuse existing WooCommerce My Account/user primitives where possible; do not create a parallel identity store.
2. Implement the smallest secure membership-value layer:
   - saved project;
   - saved calculation;
   - proforma request/history reference;
   - technical question/history reference where a safe existing source exists.
3. Add event taxonomy:
   - registration_completed;
   - project_saved;
   - calculation_saved;
   - technical_question_submitted;
   - proforma_requested.
4. Avoid sensitive profiling and unnecessary personal data.
5. Use Bridge 3.3 Secure Relay for snippet/code work.
6. Snippet/code creation must remain draft/inactive unless a separately allowed reviewed activation path is explicitly supported.
7. If activation is blocked by the Bridge guard, persist the complete implementation artifact, tests, data model, rollback plan and exact activation blocker. Do not bypass via WPVibe, raw PHP, SQL or filesystem writes.
8. Phase 21 PASS requires live readback of account-backed value plus measurable events; otherwise status stays IMPLEMENTATION_READY_ACTIVATION_BLOCKED.

## Open Gate 3 — Roadmap Phase 22 Customer Lifecycle & Retention
Dependency: Roadmap Phase 21.
Required work:
1. Define consent-safe triggers only after qualified member events exist.
2. Separate transactional/service messaging from marketing.
3. Implement guarded lifecycle states:
   - project_saved_but_no_proforma;
   - proforma_created_but_no_purchase;
   - purchase_completed_followup;
   - seasonal_project_review_due.
4. No unsolicited bulk messaging.
5. No sensitive profile inference.
6. Phase 22 PASS requires end-to-end verified trigger execution; otherwise keep dependency-blocked.

## Open Gate 4 — Phase 24 Direct AI Measurement
Current verified state:
- canonical direct observations: 70/200.
- ChatGPT Search: 20/50.
- Google AI Mode / AI Overviews: 50/50.
- Microsoft Copilot / Bing: 0/50.
- Perplexity: 0/50.
- remaining: 130.
- current direct citation rate and brand-mention rate must be computed only from canonical direct captures.

Required work:
1. Preserve the 70 validated records and never overwrite them with proxy evidence.
2. Execute only the remaining assigned prompts on the actual named surfaces.
3. For every observation require DIRECT_SURFACE_CAPTURE and readback_verified=true.
4. ChatGPT Search: execute remaining 30 only through an actual ChatGPT Search answer surface.
5. Copilot/Bing: execute 50 only through the actual Copilot/Bing answer surface.
6. Perplexity: execute 50 only through the actual Perplexity answer surface.
7. If login/2FA/session access is required, mark the exact surface EXTERNAL_SESSION_REQUIRED. Do not substitute normal web search.
8. Phase 24 closes only at 200/200 direct observations.

## Final canonical manifest
After the open gates are processed:
- refresh MASTER-CLOSURE-STATE;
- record one canonical current status per phase;
- explicitly distinguish historical roadmap numbering from the newer Phase 21–23 stack;
- include only real remaining blockers;
- include exact evidence paths, commits and readbacks;
- no hidden TODO behind PASS.

## Definition of Done
- Phase 17 either verified PASS_V19_PRODUCTION or exact tested blocker recorded.
- Roadmap Phase 21 either live PASS or implementation-ready with activation guard explicitly recorded.
- Roadmap Phase 22 either live PASS or exact dependency blocker recorded.
- Phase 24 canonical count updated from direct evidence only.
- No closed/guarded phase rerun without dependency change.
- No fabricated evidence.
