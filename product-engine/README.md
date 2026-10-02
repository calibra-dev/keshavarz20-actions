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

The Connected ChatGPT producer reads the exact current product through the existing Bridge 3.3 gateway before generating a queue:

`bridge-v3-ops/*-product-<ID>-live-read.json` -> `rest.proxy GET /wc/v3/products/<ID>` -> `bridge-v3-results/*.json`

and reads SEO separately with `seo.read`. The safe Bridge projection must expose WooCommerce `date_modified_gmt` as `result.data_date_modified_gmt`; this fresh value is the only valid source for queue `expected_date_modified_gmt`.

This route intentionally reuses the proven Bridge gateway instead of introducing a second producer workflow or direct WordPress credential path.

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
