# Phase 24 — Direct Surface Execution Pack

## Purpose
Execute only the remaining direct AI answer-surface observations for Keshavarz20 without using proxy search evidence.

## Canonical queue
- Source: `phase24-results/remaining-direct-surface-queue.json`
- Remaining total: 130
- ChatGPT Search: 30
- Microsoft Copilot / Bing: 50
- Perplexity: 50
- Google AI Mode / AI Overviews: 0 remaining

## Required environment
Use ChatGPT Work Cloud Browser (or another explicitly authenticated browser session on the exact named surface). Log in directly on the provider site when required. Do not provide passwords, tokens, recovery codes, or 2FA secrets in chat.

## Evidence contract
For every queue item, record exactly:
- prompt_id
- surface
- observed_at_utc
- prompt
- evidence_type = DIRECT_SURFACE_CAPTURE
- answer_present
- keshavarz20_cited
- citation_urls
- cited_url
- brand_mentioned
- recommendation_context
- competitor_source_set
- readback_verified = true

## Prohibited substitutions
Do not count:
- ordinary web search
- generic Bing search results
- ChatGPT web-search proxy output from this control chat
- GSC, GA4, referral traffic, Bing Webmaster telemetry
- snippets or search-result previews
- inferred citation from rank/visibility
- manually invented answers

## Execution order
1. ChatGPT Search: execute the 30 queue rows assigned to ChatGPT Search.
2. Microsoft Copilot / Bing: execute the 50 queue rows assigned to that surface.
3. Perplexity: execute the 50 queue rows assigned to that surface.
4. Preserve the existing 70 canonical observations.
5. Append only validated direct captures.
6. Re-run `phase24/ingest_direct_observations.py`.
7. Acceptance requires exactly 200/200 canonical DIRECT_SURFACE_CAPTURE observations.

## Stop conditions
For a specific surface only:
- if login is required and no authenticated session is available, mark EXTERNAL_SESSION_REQUIRED;
- if the surface blocks automation, do not substitute another search tool;
- do not alter prompt wording unless the prompt bank itself is versioned and changed deliberately.

## Final acceptance
Phase 24 can be marked PASS only after:
- canonical observations = 200
- fabricated observations = 0
- all 4 planned surface cohorts = 50 each
- direct KPI report recomputed
- CI/readback succeeds
