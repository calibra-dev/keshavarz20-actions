# K20 Product Autopilot V1

Autonomous sequential remediation for the live WooCommerce catalog.

Primary flow:
Connected ChatGPT -> product-engine/queue/*.json -> GitHub queue publisher -> K20 Bridge 3.3 -> WooCommerce/WordPress -> readback -> Lighthouse x3 -> keep/rollback -> checkpoint.

The GitHub OpenAI-API autopilot workflow is manual fallback only and is not part of the automatic path.

Key guarantees:
- one product at a time
- frozen initial order, then append newly discovered products
- exact-product research with live web search
- no bulk boilerplate; repeated long sentences are rejected
- no price/stock/discount/checkout mutation
- no invented technical claims
- content/SEO target >=96
- mobile Lighthouse target >=96 for Performance, Accessibility, Best Practices and SEO
- automatic rollback on measured regression
- noncritical evidence/platform blockers are recorded and the engine continues
- critical Bridge/rollback failures engage a kill switch

Runtime state is stored in product-engine/state.json. Product-specific evidence is stored under product-engine/results/.


## Connected producer live-read

Connected ChatGPT no longer writes normal Product Engine reads into `bridge-v3-ops/`. It commits a minimal immutable request containing only `schema_version=product-producer-live-read-v1` and `product_id` under `product-engine/live-read-ops/`.

`.github/workflows/k20-product-producer-live-read.yml` performs the exact WooCommerce + SEO reads through Bridge 3.3 on the GitHub runner, sanitizes the evidence and commits `product-engine/live-read-results/*.json`. The result is accepted for producer freshness only when product and SEO IDs match, product status is `publish`, both Bridge reads are successful, and `product.result.data_date_modified_gmt` is present.

A fresh relay request/result is required immediately before every new immutable queue. Inventory timestamps, cached HTML and historical Bridge results are never valid freshness substitutes.

## Resilient queue transport

The queue payload and product contract never change just because one GitHub write surface is unavailable. Delivery uses a transport ladder:

`Contents API -> immutable Git blob + tiny queue-ingress manifest -> repo-native ingress validation/commit -> explicit publisher dispatch -> Git Data atomic fast-forward on main -> automation/product-* Git Data branch -> promoter -> explicit publisher dispatch`.

The Git Data fallback is allowed only as a transport for the exact already-validated immutable queue. It must use the latest main commit as the parent, must re-check main before moving the ref, and must never force-update main. A concurrent main change requires a new live-read freshness check before another delivery attempt.

Transport failures do not advance the product cursor and do not disable the recurring automation.


The queue-ingress relay exists specifically to remove connected-tool payload/write blocking from the critical path. The producer uploads the already validated queue as an immutable Git blob and writes only a small manifest. The runner retrieves the blob by SHA, sanitizes and validates it against the exact bound fresh live-read result, commits the canonical queue path to current main with retry/rebase, and explicitly dispatches the publisher. It never changes the queue content to make transport easier.

## Primary-route lock

The automatic Product Engine route is locked by `product-engine/PRIMARY_ROUTE_LOCK.json` and enforced by `scripts/check_product_engine_primary_route.py`.

Automatic production MUST remain:

`Connected ChatGPT -> product-engine/queue/*.json -> k20-product-queue-publisher.yml -> K20 Bridge 3.3 -> WooCommerce/WordPress -> readback/QA`.

`.github/workflows/k20-product-autopilot.yml` is manual API fallback only. It must never gain `schedule` or `push` triggers and must not become the primary producer.

CI workflow `.github/workflows/k20-product-route-guard.yml` fails if these routing invariants drift.


### Explicit promoter handoff

Branch fallback promotion is completed only after the promoter explicitly dispatches `k20-product-queue-publisher.yml` with `workflow_dispatch`. Do not rely on workflow-generated pushes to recursively trigger another workflow. The route guard fails if this explicit handoff is removed.


## Stale queue recovery

`expected_date_modified_gmt` is live-state evidence, not inventory metadata. Producers must populate it only from an immediately preceding Bridge/WooCommerce read and re-check it immediately before committing a queue.

Queue files remain immutable. A queue rejected solely because of a verified producer timestamp-source bug may be retried only through a separate immutable `product-engine/recovery/*-stale-recovery.json` assertion. The publisher binds that assertion to the exact queue and re-verifies the current product ID, live timestamp, status, name, permalink and featured attachment before any write. Missing or mismatched recovery evidence fails closed.
