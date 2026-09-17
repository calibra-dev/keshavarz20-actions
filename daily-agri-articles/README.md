# Keshavarz20 Daily Agriculture Article Engine

This is the separate long-form «نوشته‌ها» engine for keshavarz20.com. It does not share the news queue, news post type or news category.

## Architecture

`ChatGPT Scheduled Task (08:20 Asia/Tehran)` → `daily-agri-articles/queue/YYYY-MM-DD.json` → `k20-article-queue-publisher.yml` → `publish_queue_v2.py` → WordPress **post draft**.

The scheduled research/writing task must read `automation-policy/seo-god-2026.json` and `SCHEDULED_TASK_PROMPT.md`. GitHub Actions is the deterministic validator/publisher; it does not need an OpenAI API key for this queue path.

## Editorial contract

Each run must:

1. inspect recent Keshavarz20 normal posts before topic selection;
2. deep-search current and seasonal farmer decision needs;
3. optimize for real farmer value, not publishing frequency;
4. prefer primary/official/university/research evidence;
5. verify material claims with at least three direct source URLs when available and at least two independent domains;
6. preserve uncertainty and source disagreements;
7. reject thin, duplicate, sensational, generic AI or weakly sourced ideas;
8. write original, natural Persian and useful decision guidance;
9. connect naturally to water, compatibility, total cost, installation, maintenance or practical risk when relevant;
10. include `جمع‌بندی` and clearly separated `نظر کارشناسی کشاورز بیست`;
11. use **adaptive FAQ**: none when unnecessary, otherwise 3–8 substantive visible Q&As;
12. create draft only, never auto-publish.

Missing a day is better than a weak article.

## Queue payload

Core fields:

```json
{
  "generated_at": "2026-09-18T08:20:00+03:30",
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
  "source_urls": ["https://source-one.example/...", "https://source-two.example/...", "https://source-three.example/..."],
  "source_names": ["Source One", "Source Two", "Source Three"],
  "research_summary": "Why the topic passed the evidence and farmer-decision gate, including uncertainty.",
  "image_search_query": "precise factual agriculture editorial photo query",
  "image_title": "عنوان کوتاه کاور",
  "alt_text": "توضیح دقیق و طبیعی تصویر",
  "faq_items": []
}
```

`faq_items` may be empty. If used, it must contain **3–8** complete Q&A objects and each question must be visibly present in `content_html`. The category must already exist in WordPress; the publisher never creates a new category automatically.

## Publisher safeguards

- normal WordPress `post` only
- `draft` only
- duplicate and near-duplicate protection
- minimum long-form content threshold
- at least three direct research URLs and at least two independent domains
- source_names/source_urls alignment
- adaptive FAQ instead of quota-driven FAQ
- at least two useful internal Keshavarz20 links
- Yoast title/description/focus keyphrase/primary category fields
- existing category validation
- 4–10 useful tags
- open-license Wikimedia source image only
- branded 1280×720 WebP cover generation
- image title + ALT metadata
- post-write verification of draft status/type/featured image/category/SEO fields
- sanitized artifact output only

## Required GitHub secrets

- `WP_BASE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`

No OpenAI API secret is required by the queue publisher.

## Safety

Never add secrets to queue files. Never invent product specifications, prices, stock, field-test results, authors, customer experiences or citations. Never use FAQ count, keyword repetition or `llms.txt` as a ranking shortcut.
