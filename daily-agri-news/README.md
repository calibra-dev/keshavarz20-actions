# Keshavarz20 Daily Agriculture News Engine

Daily editorial automation for the `news` post type on keshavarz20.com.

## What it does

At 08:00 Asia/Tehran every day it:

1. Searches the previous 24 hours of agriculture news using Google News RSS plus OpenAI web search.
2. Removes weak/social-only sources and recent duplicates already present in WordPress.
3. Scores candidates for freshness, agricultural relevance, publisher quality and practical impact on Iranian farmers.
4. Uses a second model pass to choose one lead story.
5. Cross-checks dates, numbers, organizations and key claims against web sources.
6. Rewrites the story in Persian as original editorial copy rather than copying the source.
7. Adds:
   - strong news headline
   - lead
   - structured H2 sections
   - `این خبر برای کشاورزان چه معنایی دارد؟`
   - `جمع‌بندی`
   - `نظر کارشناسی کشاورز بیست`
   - source links
8. Generates a new photorealistic 16:9 featured image with no text/watermark.
9. Uploads that image to the WordPress media library and sets title + alt text.
10. Creates **one WordPress draft only** in post type `news`.
11. Assigns news category `کشاورزی` (`news_cat` term ID 839) and 4–8 relevant `news_tag` terms.
12. Writes Yoast metadata:
    - `_yoast_wpseo_title`
    - `_yoast_wpseo_metadesc`
    - `_yoast_wpseo_focuskw`
    - `_yoast_wpseo_focuskeywords`
    - `_yoast_wpseo_keywordsynonyms`
    - `_yoast_wpseo_primary_news_cat`
13. Verifies that the new object is still `draft`, is post type `news`, and contains the required Yoast fields.
14. Uploads sanitized run artifacts to GitHub Actions for audit/debugging.

The engine never publishes a news item. Human review in wp-admin remains mandatory.

## Schedule

GitHub Actions uses UTC. Iran is UTC+03:30, so the workflow uses:

```cron
30 4 * * *
```

This targets 08:00 Tehran. GitHub scheduled workflows are best-effort and can occasionally start a few minutes late.

## Required GitHub repository secrets

These must exist in `calibra-dev/keshavarz20-actions`:

- `WP_BASE_URL` — normally `https://keshavarz20.com`
- `WP_USERNAME`
- `WP_APP_PASSWORD`
- `OPENAI_API_KEY`

Do not commit any of those values to the repository.

## Optional repository variables

- `OPENAI_TEXT_MODEL` — default: `gpt-5.6`
- `OPENAI_IMAGE_MODEL` — default: `gpt-image-2`

## Manual test

Use `Actions -> Keshavarz20 Daily Agriculture News Draft -> Run workflow`.

Recommended first run:

- `lookback_hours = 24`
- `dry_run = true`

A dry run performs research, selection, fact-checking, writing and image generation but does **not** create a WordPress post.

After reviewing the action artifacts, run again with `dry_run = false`. The result should create one draft in:

`wp-admin/edit.php?post_type=news`

## Editorial safeguards

- Only stories inside the requested freshness window are eligible.
- A duplicate guard compares against recent WordPress news titles.
- Social posts are not accepted as stand-alone evidence.
- Important factual claims are cross-checked before writing.
- Unverified claims must not be upgraded into facts.
- Government/political agriculture stories are written neutrally and descriptively.
- The expert-opinion block is visibly separated from reported facts.
- No auto-publish is implemented.
- Failure to verify required WordPress/Yoast fields makes the workflow fail rather than silently creating an incomplete post.

## Output artifacts

The workflow stores for 14 days:

- `selected-story.json` — chosen story, ranking and verification data
- `article.json` — generated editorial/SEO fields
- `result.json` — final draft status / IDs
- `summary.md` — concise workflow summary
- `featured-news.webp` — generated 1280×720 WebP image

No WordPress credentials, application passwords or OpenAI keys are written to these files.

## WordPress facts verified during implementation

Current site configuration used by the engine:

- Custom post type: `news`
- Agricultural news taxonomy: `news_cat`
- Agricultural term: `کشاورزی`, term ID `839`
- News tags taxonomy: `news_tag`
- Yoast SEO Premium is active and existing news posts use the Yoast fields listed above.

## Failure behavior

The engine intentionally stops without creating a draft when:

- there is no credible new story,
- every candidate duplicates recent site news,
- fact-checking fails,
- article structure is incomplete,
- image generation fails,
- WordPress credentials are missing,
- XML-RPC publishing methods are unavailable,
- or the final draft does not contain the required Yoast metadata.

This is deliberate: a missing daily draft is safer than silently publishing or saving low-quality/unverified content.
