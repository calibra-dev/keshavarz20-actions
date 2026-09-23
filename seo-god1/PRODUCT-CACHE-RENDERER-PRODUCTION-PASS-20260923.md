# Product singular cache renderer — production acceptance CORRECTION

Date: 2026-09-23
Target: K60 product ID 140856

## Status
**NOT PASS.**

The earlier apparent `MISS -> HIT -> HIT` result was produced by testing the non-canonical query URL:
`https://keshavarz20.com/?post_type=product&p=140856`

That request redirects to the canonical PDP. The probe parsed the final `x-litespeed-cache-control` but also observed cache state from the redirect chain, creating a false-positive acceptance.

## Canonical re-test
Direct canonical URL:
`https://keshavarz20.com/product/کا-۶۰-ایکس-گرین/`

Three direct requests:
- seq1: no `x-litespeed-cache`; `x-litespeed-cache-control: no-cache,esi=on`
- seq2: no `x-litespeed-cache`; `x-litespeed-cache-control: no-cache,esi=on`
- seq3: no `x-litespeed-cache`; `x-litespeed-cache-control: no-cache,esi=on`

Hyper 40-0-1 canonical PDP showed the same behavior.

## Broad cohort
The post-renderer Top50 audit also confirms canonical product URLs remain no-cache while many non-product guides are HIT.

## Review-template change
The WooCommerce standard review template remains live because:
- Review UI/functionality readback passed.
- Canonical/Yoast/schema readback passed.
- It did not itself solve the cache blocker.
- A backup exists as `irankala-wpvibe-backup`.

## Root-cause progress
LiteSpeed scoped debug on canonical K60 reports:
`forced no cache [reason] DONOTCACHEPAGE const`

So LiteSpeed is reacting to a pre-existing `DONOTCACHEPAGE` constant set elsewhere.

Snippet 25 (`K20 K21 Verified Review Capture v1`) was temporarily disabled with reviews still enabled. K60 remained no-cache on all three canonical requests, so snippet 25 is not the owner and was reactivated.

## Correct release state
`PRODUCT_SINGULAR_CACHE_RENDERER = OPEN`

Do not use the earlier non-canonical MISS/HIT/HIT result as acceptance evidence.
Use only direct canonical PDP URLs for future cache acceptance.
