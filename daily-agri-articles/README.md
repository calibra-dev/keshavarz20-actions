# Keshavarz20 Daily Agriculture Article Engine

This is the **separate long-form “نوشته‌ها” engine** for keshavarz20.com. It intentionally does not share the news queue, news post type, news category 839, or news tags.

## Architecture

`ChatGPT Scheduled Task (08:20 Asia/Tehran)` → `daily-agri-articles/queue/YYYY-MM-DD.json` → `k20-article-queue-publisher.yml` → `publish_queue.py` → WordPress **post draft**.

GitHub Actions is only the deterministic publisher/validator. Research, topic selection, fact checking, editorial reasoning, Persian writing and SEO planning are performed by the connected ChatGPT Scheduled Task, so this path does **not** require `OPENAI_API_KEY` in GitHub.

## Editorial contract

Each daily run must:

1. Inspect recent Keshavarz20 normal posts and their visual/editorial patterns before choosing a topic.
2. Deep-search the current agriculture landscape, prioritizing Iran and adding relevant global evidence where useful.
3. Rank candidates for freshness/trend, practical importance, search-intent potential, seasonality, Iranian farmer relevance, authority of evidence and novelty versus recent Keshavarz20 posts.
4. Reject thin, duplicated, sensational or weakly-sourced ideas. Missing a day is preferable to a weak draft.
5. Fact-check material claims against at least three independent credible sources.
6. Write original, natural Persian with varied sentence structure; never translate or stitch source text.
7. Produce a compelling non-clickbait title, strong lead, H2/H3 structure, practical examples, decision guidance and internal links to relevant Keshavarz20 pages/posts.
8. Include a clear `جمع‌بندی` section.
9. Include exactly **15 substantive FAQs with answers**, covering buying/usage/cost/risk/maintenance/science/field practice as relevant to the topic.
10. End with a clearly separated `نظر کارشناسی کشاورز بیست` section. Opinion must not be presented as sourced fact.
11. Fill SEO title, meta description, focus keyphrase, related keyphrases, English ASCII slug, excerpt, existing category and 4–10 useful tags.
12. Supply a concise English `image_search_query`, Persian `image_title` and accurate Persian `alt_text`.
13. Create **draft only**. Never auto-publish.

## Queue payload

Required fields:

```json
{
  "title": "...",
  "slug": "english-ascii-slug",
  "excerpt": "...",
  "content_html": "<p>...</p><h2>...</h2>...",
  "focus_keyphrase": "...",
  "seo_title": "...",
  "meta_description": "...",
  "related_keyphrases": ["...", "...", "..."],
  "category_name": "an existing WordPress post category",
  "category_id": 0,
  "tags": ["...", "...", "...", "..."],
  "source_urls": ["https://...", "https://...", "https://..."],
  "source_names": ["...", "...", "..."],
  "research_summary": "Why this topic won today, what was verified, and what uncertainty remains.",
  "image_search_query": "agriculture topic photorealistic field irrigation",
  "image_title": "عنوان کوتاه و جذاب برای کاور",
  "alt_text": "توضیح دقیق و طبیعی تصویر",
  "faq_items": [
    {"question": "سؤال ۱؟", "answer": "پاسخ..."}
  ],
  "generated_at": "2026-09-18T08:20:00+03:30"
}
```

`faq_items` must contain exactly 15 objects. `category_name` must already exist in WordPress; the publisher never creates a new category automatically.

## Publisher safeguards

- normal WordPress `post` only (the homepage “نوشته‌ها” stream)
- draft only
- recent title/slug duplicate and near-duplicate protection
- minimum long-form content threshold
- exactly 15 FAQs required in the payload
- minimum three research sources
- Yoast title, description, focus keyphrase and primary category written as custom fields
- existing category validation before write
- 4–10 tags
- free/open-license Wikimedia source image only
- deterministic branded 1280×720 WebP cover generation
- image title + ALT metadata
- post-write verification of draft status, post type, featured image, category and required SEO/audit fields
- sanitized GitHub artifact output retained for 14 days

## Required GitHub secrets

The publisher reuses the WordPress secrets already used by the news publisher:

- `WP_BASE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`

No OpenAI API secret is required by this queue publisher.

## Manual test

Use `Actions -> Keshavarz20 ChatGPT Pro Article Queue Publisher -> Run workflow` and provide a queue file path. The publisher must stop rather than create an incomplete draft when any quality gate fails.
