# Phase 24 — AI Citation Experimentation & Influence Measurement v2

Phase 24 measures whether Keshavarz20 is actually cited or mentioned on named AI answer surfaces.

## Non-negotiable measurement rule

A referral visit, Google Search Console row, Bing Webmaster row, ordinary web search result, or model assumption is **not** direct citation evidence.

Citation and brand-mention KPIs are populated only from a captured result for the exact prompt on the exact assigned surface with `evidence_type=DIRECT_SURFACE_CAPTURE`.

## Prompt bank

- 200 Persian prompts
- 10 intent buckets × 20
- 4 surfaces × 50

## Current telemetry

Telemetry is useful for influence/downstream measurement but remains separate from direct answer-surface evidence.

The 2026-09-27 snapshot contains:
- GA4 ChatGPT referral evidence
- Google Search Console settled search performance
- Bing Webmaster connection state/provider throttle
- a small public-web-search proxy sample, explicitly excluded from citation KPI calculations

## Completion semantics

`CONTROL_PLANE_COMPLETE_EXTERNAL_SURFACE_PENDING` means all controllable measurement infrastructure and telemetry are complete, while direct multi-surface answer captures remain unavailable in this execution environment.

`PASS_DIRECT_SURFACE_MEASUREMENT` is reserved for the completed 200-prompt direct-observation dataset.
