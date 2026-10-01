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
