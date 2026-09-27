# Keshavarz20 GrowthOS Master Closure Prompt — 2026-09-27

## Mission
Close every genuinely open Keshavarz20 GrowthOS phase from the earliest unresolved dependency to Phase 24 using verified evidence only.

## Execution path
ChatGPT -> GitHub -> calibra-dev/keshavarz20-actions -> Keshavarz20 Bridge v3.x -> WordPress/WooCommerce.

Use repository-native workflows first. Use Bridge for guarded site reads/writes. Do not use WPVibe unless the required capability is proven unavailable in GitHub/Bridge/WordPress/WooCommerce REST.

## Non-negotiable truth rules
1. Never claim a phase PASS from a plan, spec, code file, queued workflow, or stale summary alone.
2. A phase closes only when its current acceptance criteria are satisfied and a fresh readback/result is persisted.
3. Never invent technical dimensions, compatibility, GTIN/MPN, manufacturer identity, brand, test result, citation, review, customer evidence, price, stock, partner access, Merchant eligibility, or AI-surface observation.
4. Preserve UNKNOWN / SOURCE_BOUND_UNRESOLVED / EXTERNAL_GATE when evidence is missing.
5. Referral traffic, ordinary web search, Search Console, Bing Webmaster, snippets and search-result proxies are not direct AI citation evidence.
6. Candidate-only compatibility must never be promoted to verified compatibility.
7. Never change price, regular_price, sale_price, discounts, coupons, payment settings, users, roles, credentials, orders, or private customer data.
8. No fake country/address for Merchant Center or commerce eligibility.
9. Every site write must have readback; every high-impact change must preserve rollback/approval discipline.

## Ordered closure run

### Gate A — refresh stale upstream truth
1. Phase 2 Product Truth:
   - rerun live Product Truth Registry after SKU corrections and later brand work;
   - verify duplicate SKU blocker is actually gone;
   - persist fresh summary and registry.
2. Phase 3 HTML/Schema/Feed parity:
   - rerun against the refreshed Phase 2 truth;
   - zero hard parity failures required.

### Gate B — compatibility truth
3. Phase 4 Compatibility Graph:
   - rerun current graph first;
   - work only on current SOURCE_BOUND_UNRESOLVED products;
   - acquire exact manufacturer/first-party evidence where publicly obtainable;
   - populate dimensions only when source-backed;
   - create technical compatibility edges only when interface, size, pressure/material and use constraints support them;
   - unresolved items remain explicit backlog, never guessed.

### Gate C — intent/canonical ownership
4. Phase 5:
   - verify current owner map;
   - require unresolved canonical conflicts = 0;
   - do not create duplicate pages.

### Gate D — downstream readiness refresh
5. Revalidate Phases 6–10 only if an upstream change can materially affect them.
6. Phase 11 ChatGPT Search readiness:
   - rebuild current feed-readiness from fresh truth;
   - improve only source-backed missing fields;
   - partner feed submission remains external until approved access is proven.
7. Phase 12 Merchant/UCP:
   - rebuild after Phase 11;
   - respect Iran availability restrictions;
   - no fake eligibility;
   - UCP live publication only with real authenticated adapter and authorization.
8. Phase 13 WebMCP:
   - preserve current live verified state unless regression is detected.
9. Phase 14 GS1:
   - accept only manufacturer/GS1-issued identifiers;
   - never convert SKU to GTIN;
   - zero fabricated identifiers.
10. Phase 15 Entity OS:
   - resolve pseudo-brand and multi-brand ambiguity only from real sources;
   - never export ambiguous pseudo brand as a single commerce brand.
11. Phase 16 Editorial Trust:
   - keep fake authors/reviewers = 0;
   - retain provenance gates.

### Gate E — engines and decision intelligence
12. Phase 17 Question Engine:
   - compare current v18 runtime to the vNext requirements;
   - add the smallest backward-compatible upgrade required for intent registry, scenario/evidence classification and cross-engine feedback;
   - preserve synthetic-question classification; never call generated questions customer evidence;
   - run full regression and canary.
13. Phase 18 Recommendation/Basket intelligence:
   - consume verified compatibility only;
   - unknown compatibility must trigger clarification/expert review;
   - no unsupported exact SKU recommendation;
   - run guarded E2E and acceptance.

### Gate F — current v2 stack
14. Phase 20 Article/Intent engine:
   - verify canary and current production queue contract;
   - require score gate, canonical-intent gate, evidence gate, draft-only human review.
15. Phase 21 Authority:
   - preserve Iran-first source policy and no fabricated endorsements.
16. Phase 22 Farmer Decision Personalization:
   - preserve explainability, unknown handling and expert escalation.
17. Phase 23 Lifecycle/Freshness:
   - rerun after material changes;
   - do not equate out-of-stock with discontinued;
   - no fake dateModified, redirect, canonical or bulk rewrite.

### Gate G — Phase 24 direct AI measurement
18. Validate and ingest all existing DIRECT_SURFACE_CAPTURE evidence.
19. Execute the remaining assigned prompts only on the named real surfaces:
   - ChatGPT Search
   - Google AI Mode / AI Overviews
   - Microsoft Copilot / Bing
   - Perplexity
20. For every observation persist:
   - prompt_id
   - surface
   - observed_at_utc
   - answer_present
   - keshavarz20_cited
   - cited_url
   - brand_mentioned
   - recommendation_context
   - competitor_source_set
   - citation_urls
   - answer_url/session context when available
   - readback_verified
21. Do not substitute normal web search for a missing surface.
22. Recompute Citation Rate, Brand Mention Rate, Citation Influence and cited-page coverage only from direct captures.
23. Phase 24 closes only at 200/200 direct observations or remains explicitly EXTERNAL_SURFACE_PENDING with exact remaining counts.

## Final deliverables
- fresh per-phase acceptance/readback evidence;
- one canonical phase manifest with current numbering and status;
- exact remaining external blockers only;
- CI/regression evidence;
- no TODO hidden behind PASS;
- final closure report with commit/run/result references.
