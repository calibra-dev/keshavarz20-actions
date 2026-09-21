# Keshavarz20 Daily Agriculture News Engine

Daily editorial automation for the `news` post type on keshavarz20.com.

## Primary automatic architecture

`ChatGPT Scheduled Task (08:00 Asia/Tehran)` → live deep research → `daily-agri-news/queue/YYYY-MM-DD.json` → `k20-news-queue-publisher.yml` → `publish_queue_v2.py` → WordPress **news draft**.

The automatic research task must read `automation-policy/seo-god-2026.json`. The queue publisher is deterministic and does not call an LLM. The old API-mode workflow remains available as a **manual fallback only** and has no daily cron, preventing duplicate daily drafts and avoiding unnecessary API dependence.

## Daily research contract

Each automatic run must:

1. research the previous 24 hours using live web search;
2. treat search snippets, RSS, social posts and AI summaries as discovery only;
3. verify material claims from direct sources;
4. use at least two source URLs from at least two independent domains;
5. prefer official/government/regulator/standards, university/extension/research, primary datasets, recognized agricultural bodies and reputable newswires/publications;
6. use queue/public-web history for pre-selection dedupe; the publisher performs the final authenticated duplicate check against the real `news` CPT through the guarded WPVibe WP-native CLI route because `/wp-json/wp/v2/news` is not exposed on this site;
7. select at most one story using freshness, direct farmer impact, verifiability, seasonality/search interest and practical value;
8. preserve uncertainty when evidence conflicts;
9. reject rumor, source-less reposts, advertorials, sensationalism and low-value filler;
10. create a draft only. Human review remains mandatory.

If no story clears the gate, the correct result is to skip that day.

## Visual design

Every new news draft must also read and follow `daily-agri-news/DESIGN_SYSTEM.md`. The default output is a premium RTL editorial page with a soft colored wrapper, green hero, boxed H2 sections, meaningful callouts, a clean sources card, and a visually separated Keshavarz20 editorial-analysis card. Inline styles are preferred for Classic Editor compatibility.

## Article structure

The generated news should include, when applicable:

- accurate non-clickbait headline
- concise lead
- what happened
- what is confirmed
- material numbers only when verified
- what remains uncertain
- `این خبر برای کشاورزان چه معنایی دارد؟`
- practical next step/watch-point when justified
- `جمع‌بندی`
- clearly separated `نظر کارشناسی کشاورز بیست`
- `منابع` with direct source links

Sourced facts and editorial interpretation must remain visibly separate. Political/government stories must remain neutral and attribute disputed claims to identified sources.

## Queue fields

The scheduled task supplies:

- `content_type` = `news` (hard routing guard)
- `generated_at`
- `title`
- English ASCII `slug`
- `excerpt`
- `content_html`
- `focus_keyphrase`
- 1–8 `related_keyphrases`
- `seo_title`
- accurate `meta_description`
- 3–10 useful tags
- `source_urls`
- matching `source_names`
- `published_at` when known
- `image_search_query`
- `image_title`
- `alt_text`
- `selection_reason`
- `fact_check_notes`

## Publisher safeguards

`publish_queue_v2.py` adds the SEO-God evidence gate while preserving the original publisher:

- WordPress custom post type `news` only; payloads without `content_type=news` are rejected before any WordPress write
- `draft` only
- category `کشاورزی` / `news_cat` ID 839
- at least two direct sources from at least two independent domains
- matching source names
- duplicate and near-duplicate title/topic protection
- minimum useful content threshold
- required `جمع‌بندی`, `نظر کارشناسی کشاورز بیست` and `منابع`
- open-license Wikimedia image selection and 1280×720 WebP treatment
- Yoast metadata
- post-write draft/type/ASCII-slug/image/SEO verification
- no credentials in queue or artifacts

## Automatic schedule

The connected ChatGPT task is enabled for **08:00 Asia/Tehran every day**. It writes the queue JSON. GitHub Actions triggers automatically when that queue file is committed.

There is intentionally **no second daily GitHub cron** on the API-mode generator. `k20-daily-agri-news.yml` is manual fallback/testing only.

## Manual API fallback

Use `Actions -> Keshavarz20 Daily Agriculture News Draft (API fallback) -> Run workflow` only when the primary queue automation cannot be used.

Recommended diagnostic run:

- `lookback_hours = 24`
- `dry_run = true`

The fallback requires `OPENAI_API_KEY`; the normal queue publisher does not.

## WordPress execution path

The publisher uses authenticated WordPress REST for media and the allow-listed `/wpvibe/v1/cli/run` route for the custom `news` CPT. XML-RPC is no longer required by the primary publisher path.

## Required WordPress secrets

- `WP_BASE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`

Do not commit secret values.

## Failure behavior

The engine intentionally stops without creating a draft when evidence is insufficient, sources are not independent, the topic duplicates recent news, structure is incomplete, image acquisition fails, WordPress credentials are unavailable, or post-write verification fails. A skipped day is safer than a weak or misleading draft.
