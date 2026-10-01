# Keshavarz20 Product Autopilot — Connected ChatGPT Queue Producer

This is the canonical producer prompt for the primary Product Engine path.

## Primary architecture

ChatGPT Deep Research -> product-engine/queue/*.json -> GitHub queue publisher -> K20 Bridge 3.3 -> WooCommerce/WordPress -> readback -> Lighthouse x3 -> keep/rollback.

The primary product engine does not require OpenAI API credits inside GitHub. Connected ChatGPT performs the research and content generation with its own live web access, then commits one immutable queue file. GitHub validates and applies it. Never call product-engine/ai_runtime.py or require OPENAI_API_KEY on the primary path.

## Mission

Process exactly one published WooCommerce product at a time, in the frozen catalog order. Every product must be researched and rewritten as its own commercial page. Never reuse another product's prose, paragraph openings, section sequence, FAQ wording or CTA wording merely because products are related.

Before queueing:
1. read product-engine/state.json and product-engine/inventory.json;
2. select the first product in frozen inventory order that is not already in a terminal processed state (ACCEPTED, PLATFORM_BLOCKED, NEEDS_EVIDENCE, QA_BLOCKED, ROLLED_BACK, SKIPPED or FAILED) and does not already have a pending queue; MODEL_ACCESS_BLOCKED is retryable and must not advance the cursor;
3. read the exact live product and SEO state through Bridge 3.3;
4. inspect the public product URL and current HTML;
5. deep-search the exact product/model/brand and market terminology;
6. prefer manufacturer/official/datasheet/regulator sources, then independent technical sources;
7. separate FACT / MANUFACTURER_CLAIM / ESTIMATE / ENGINEERING_REQUIRED / EXPERT_INTERPRETATION;
8. build product-specific commercial copy that helps the buyer choose correctly;
9. run the product QA contract and require >=96 with zero blockers;
10. commit exactly one immutable queue JSON to current main.

## Product-page writing rules

This is a product page, not a blog post.

Good product-page content:
- direct commercial opening;
- exact verified buying/use-case distinction;
- who this product is for;
- what must be checked before buying;
- compatibility and installation considerations only when evidenced;
- useful specification table only when facts are verified;
- real purchase objections;
- relevant complementary decision points;
- natural CTA such as selection check, quotation or technical consultation.

Do not use:
- generic catalog filler;
- "در این مقاله";
- "در ادامه";
- "روش تهیه و بازبینی";
- "نظر کارشناسی کشاورز بیست";
- fake reviews, fake field tests or fake scarcity;
- unsupported superlatives;
- copied text from another product;
- repeated boilerplate that makes catalog pages look templated.

Do not mutate protected commerce data:
- price / regular_price / sale_price;
- stock;
- SKU / GTIN / MPN;
- slug / canonical;
- product type / variations;
- categories / brand / attributes without a separate verified operation;
- gallery binding.

## Queue contract

Path:
product-engine/queue/YYYY-MM-DD-product-<PRODUCT_ID>.json

Root structure:

{
  "content_type": "product",
  "schema_version": "product-queue-v1",
  "producer": "connected_chatgpt_deep_research",
  "generated_at": "ISO-8601",
  "product_id": 0,
  "expected_date_modified_gmt": "string or null",
  "strict_acceptance": true,
  "source_urls": ["https://..."],
  "source_names": ["string"],
  "research_summary": "string",
  "candidate": {
    "family": "string",
    "commercial_angle": "string",
    "short_description_html": "string",
    "description_html": "string",
    "seo_title": "string",
    "meta_description": "string",
    "focus_keyphrase": "string",
    "related_keyphrases": ["string"],
    "image_alt_suggestions": [{"attachment_id": 0, "alt_text": "string"}],
    "claims": [
      {
        "claim": "string",
        "class": "FACT|MANUFACTURER_CLAIM|ESTIMATE|ENGINEERING_REQUIRED|EXPERT_INTERPRETATION",
        "evidence_url": "https://... or empty",
        "evidence_note": "string"
      }
    ],
    "source_urls": ["https://..."],
    "buyer_decision": {
      "best_for": "string",
      "main_risk_before_purchase": "string",
      "next_action": "string"
    }
  }
}

Queue files are immutable. Immediately before commit, re-fetch current main and verify the exact queue path does not exist.

## Publisher responsibility

The GitHub publisher, not the ChatGPT producer, owns:
- stale-write protection;
- sanitizer;
- uniqueness check against accepted products;
- publisher QA >=96;
- Lighthouse mobile x3 baseline;
- WordPress/WooCommerce write through Bridge 3.3;
- SEO write/readback;
- image ALT updates;
- conservative featured-image performance repair when proven useful;
- cache purge;
- final HTML/schema readback;
- Lighthouse mobile x3 after;
- regression detection;
- rollback.

Do not claim a product is published until the publisher result and live readback prove it.


## Queue delivery and branch fallback

Primary delivery is a direct immutable queue commit onto current `main`.

If the connected GitHub execution environment cannot place the queue directly on `main` and instead creates a branch named `automation/product-*`, do not stop the engine and do not require a pull request. Commit exactly one new immutable `product-engine/queue/*.json` file on that branch. The guarded `.github/workflows/k20-product-queue-promoter.yml` must validate and promote that single queue onto current `main`, after which `k20-product-queue-publisher.yml` owns publication/readback.

Never rewrite an existing queue on either branch or main. Verify promoter/publisher terminal state before claiming completion.


## Publisher handoff invariant

When a queue is created on an `automation/product-*` branch, the promoter must not rely on the resulting `GITHUB_TOKEN` push to `main` to trigger the publisher. After promotion, it must explicitly invoke `k20-product-queue-publisher.yml` through `workflow_dispatch` with the exact immutable `queue_file`. This handoff is mandatory and is enforced by the route guard.

If the queue already exists on `main` but `product-engine/results/<PRODUCT_ID>.json` does not exist, the promoter may dispatch the publisher for that existing queue. If the result already exists, the promoter must skip duplicate publication.
