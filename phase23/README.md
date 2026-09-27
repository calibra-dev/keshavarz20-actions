# Phase 23 — Lifecycle & Freshness Governance v2

Phase 23 governs review, freshness, availability transitions and deprecation decisions without creating fake freshness signals.

## What v2 changes

The legacy gate treated Phase 20 accessibility as a hard dependency. v2 uses the current growth stack instead:
- Phase 20 Intent Graph
- Phase 21 Authority Network
- Phase 22 Farmer Decision v2

Accessibility remains a deployment concern, but it is not evidence that content is fresh or stale.

## Hard rules

- A review-due flag never changes `dateModified`.
- Out of stock never means discontinued.
- A 301, 410, canonical change or merge requires explicit evidence and a separate verified plan.
- Stock transitions do not create content freshness.
- No bulk rewrite exists merely to reset dates.
- Governance assets themselves have review triggers and review intervals.
- The live audit is read-only.

## Live audit scope

The live audit reads WordPress posts, pages and WooCommerce products through authenticated REST, classifies the review queue, records stock-transition watch counts, and persists a sanitized evidence snapshot.
