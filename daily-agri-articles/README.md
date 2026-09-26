# Keshavarz20 Daily Agriculture Article Engine

This is the separate long-form «نوشته‌ها» engine for keshavarz20.com. It does not share the news queue, news post type or news category.

## Architecture

`ChatGPT Scheduled Task (09:00 Asia/Tehran)` → `daily-agri-articles/queue/YYYY-MM-DD.json` → `k20-article-queue-publisher.yml` → `publish_queue_v5.py` → WordPress **post draft**.

The scheduled research/writing task must read `automation-policy/seo-god-2026.json`, `automation-policy/editorial-trust-2026.json`, and `SCHEDULED_TASK_PROMPT.md`. GitHub Actions is the deterministic validator/publisher; it does not need an OpenAI API key for this queue path.

## Editorial contract

Each run must:

1. inspect recent Keshavarz20 normal posts before topic selection;
2. deep-search current and seasonal farmer decision needs; reject fresh event/news topics and leave those to `daily-agri-news`;
3. optimize for real farmer value, not publishing frequency;
4. prefer primary/official/university/research evidence;
5. verify material claims with at least three direct source URLs when available and at least two independent domains;
6. preserve uncertainty and source disagreements;
7. reject thin, duplicate, sensational, generic AI or weakly sourced ideas;
8. write original, natural Persian and useful decision guidance;
9. connect naturally to water, compatibility, total cost, installation, maintenance or practical risk when relevant;
10. include `جمع‌بندی` and clearly separated `نظر کارشناسی کشاورز بیست`;
11. use **adaptive FAQ**: none when unnecessary, otherwise 3–8 substantive visible Q&As;
12. create draft only, never auto-publish;
13. visibly include `منابع`, `روش تهیه و بازبینی`, and a link to the public editorial policy;
14. never invent a human author, reviewer, credential, field experience or review event.

Missing a day is better than a weak article.

## Queue payload

Core fields:

```json
{
  "content_type": "post",
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
  "editorial_disclosure": "Truthful explanation of how sources, automation and review are handled.",
  "review_status": "human_review_required_before_publish",
  "image_search_query": "precise factual agriculture editorial photo query",
  "image_title": "عنوان رسانه",
  "cover_title": "تیتر کوتاه 2 تا 8 کلمه برای کاور",
  "cover_subtitle": "زیرعنوان اختیاری، حداکثر 12 کلمه",
  "alt_text": "توضیح دقیق و طبیعی تصویر",
  "faq_items": []
}
```

`faq_items` may be empty. If used, it must contain **3–8** complete Q&A objects and each question must be visibly present in `content_html`. The category must already exist in WordPress; the publisher never creates a new category automatically.

## Publisher safeguards

- normal WordPress `post` only; payloads without `content_type=post` are rejected before any WordPress write
- `draft` only
- duplicate and near-duplicate protection
- minimum long-form content threshold
- at least three direct research URLs and at least two independent domains
- source_names/source_urls alignment
- Phase 16 editorial disclosure + human-review gate
- visible sources, review-method block and editorial-policy link
- adaptive FAQ instead of quota-driven FAQ
- at least two useful internal Keshavarz20 links
- Yoast title/description/focus keyphrase/primary category fields
- existing category validation
- 4–10 useful tags
- open-license Wikimedia source image only
- text-free source/background image; never rely on AI-generated Persian lettering
- deterministic Persian overlay using approved Noto Arabic font + Pillow + arabic-reshaper + python-bidi
- fail closed if the Persian shaping/font stack is unavailable
- branded 1280×720 WebP cover generation with controlled cinematic grading
- title max 8 words / 2 lines; subtitle max 12 words / 2 lines; overflow fails closed
- safe margins, high-contrast editorial panel and deterministic visual QA manifest
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


## Automatic schedule and recovery

- Primary ChatGPT research/writing task: **09:00 Asia/Tehran**
- Recovery check: **09:20 Asia/Tehran**
- Both first check for `daily-agri-articles/queue/YYYY-MM-DD.json`; if it already exists, they must not rewrite or duplicate it.

## Cover quality hard rule

The background must be factual, realistic, text-free and relevant. Restrained cinematic treatment is allowed for clarity and editorial polish, but fake documentary drama is not. Persian text is rendered only by the deterministic GitHub cover renderer; no image model may spell Persian. `cover_title` should be 2–8 words and materially shorter than the H1.
