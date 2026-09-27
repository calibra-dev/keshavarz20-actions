# Phase 22 — Farmer Decision Personalization v2

Phase 22 provides explainable, privacy-safe decision support for Iranian farmers.

It does **not** select a SKU, claim a certified irrigation design, prescribe agronomy, or use price/stock as a technical decision.

## Inputs
Core: crop, area, water source, region.
Technical inputs are evaluated per decision track rather than forcing all-or-nothing answers.

## Decision tracks
- Hydraulic
- Filtration
- Compatibility
- Agronomy

Each track can independently be ready, blocked for missing evidence, or escalated for expert review.

## Dependencies
- Phase 20 canonical Intent Graph
- Phase 21 Authority Network
- Existing live decision-tool routes

## Safety
Unknowns remain unknown. Candidate-only compatibility never becomes verified compatibility. Personalization context IDs hash only non-identity farm inputs; names, phone numbers and customer identity are neither required nor stored.
