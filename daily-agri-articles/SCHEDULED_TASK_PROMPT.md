# Keshavarz20 Daily Long-form Agriculture Article — SEO God 2026

This is the canonical instruction for the automatic **daily long-form article** engine. It is separate from `daily-agri-news` and must never create a news item. It owns only normal WordPress `post` drafts.

## 0) Read policy first

Before research, read and obey:

1. `automation-policy/seo-god-2026.json`
2. this file
3. `daily-agri-articles/README.md`

The shared policy controls evidence quality, farmer decision value, GEO/AEO behavior, safety and automation governance. If this document conflicts with the shared policy, use the stricter rule.

## 1) Mission

Create at most **one** original Persian agriculture article per day that materially helps an Iranian farmer make a better decision. The article must not exist merely to fill a publishing calendar or target a keyword. It should reduce one or more of these risks:

- wrong product / wrong size / wrong connection
- wasted water or poor water-quality handling
- unnecessary input cost or incomplete cart
- installation/maintenance failure
- climate or seasonal decision risk
- uncertainty caused by weak or conflicting information

If no topic clears the quality gate, **skip the day**. A skipped weak article is better than a thin article.

## 2) Research and topic selection

Deep-search current web sources and inspect recent normal Keshavarz20 posts before choosing a topic. **Routing gate:** if a candidate is primarily a fresh event, announcement, outbreak/current incident, current policy action, or time-sensitive market/news development, reject it from this engine and leave it to `daily-agri-news`. Score durable candidates on:

- Iranian farmer relevance
- search intent and recurring question demand
- seasonality/timing
- practical decision value
- novelty versus existing Keshavarz20 content
- ability to support claims with credible evidence
- opportunity to connect naturally to existing tools, guides, categories or products
- potential to become a durable reference/citation source rather than a temporary keyword page

### Evidence hierarchy

Prefer, in order:

1. official government/regulator/standard or primary dataset
2. university, extension service or peer-reviewed research
3. manufacturer primary datasheet for claims about that manufacturer's own product
4. recognized industry body or reputable agriculture publication/newswire
5. secondary analysis with clear primary citations

Search result snippets, AI summaries and RSS headlines are **discovery tools, not evidence**.

For material claims use at least **three credible direct source URLs when available and at least two independent domains**. If sources conflict, say so and narrow the conclusion. Never invent a statistic, agronomic recommendation, dose, product specification, result, certification, price, stock or field test.

## 3) Article design

Write natural, expert-edited Persian for humans. Do not create a separate "AI version" and do not fragment content into artificial answer bait.

Target roughly **1,200–2,600 useful words** when the topic warrants it. Do not pad to reach a length.

Recommended structure, adapted to the topic:

- strong H1/title, non-clickbait
- concise direct answer / executive summary near the beginning
- who this is for and what decision it helps with
- 4–8 substantive H2 blocks covering the actual decision
- useful HTML table/list when comparison or steps genuinely benefit from it
- practical farmer context: water, pressure, field/crop, compatibility, cost, installation or maintenance where relevant
- explicit limitations / uncertainty
- useful internal links to at least two existing Keshavarz20 pages that genuinely help the reader
- `جمع‌بندی`
- clearly separated `نظر کارشناسی کشاورز بیست` as editorial analysis, never disguised as sourced fact
- visible source/reference section when appropriate


### Visual design contract

Before drafting `content_html`, also read and obey `daily-agri-articles/DESIGN_SYSTEM.md`.
All new long-form posts must use the premium RTL card-based visual system: a soft colored page wrapper, hero card, boxed H2 sections, distinct practical/warning/editorial callouts, styled tables, boxed FAQ when used, and a strong closing summary card. The visual system must improve scanning without turning every sentence into a separate box. Use inline styles so the design survives theme changes and remains mobile-friendly.

### FAQ rule — adaptive, not quota-driven

FAQ is optional. Never force FAQ merely for SEO or rich-result markup.

- If FAQ adds genuine value: include **3–8** distinct, substantive questions and answers.
- If the article does not need FAQ: use an empty `faq_items` array.
- Never create 15 repetitive FAQ items.
- Any FAQ question included in `faq_items` must also be visibly answered in `content_html`.

## 4) GEO / AEO / citation quality

Make the article citable by making it **useful and evidenced**, not by gaming an LLM.

For major claims:

- identify the source and date/context where relevant
- use exact units and definitions
- distinguish measurement from estimate
- distinguish manufacturer claim from independent evidence
- surface uncertainty instead of hiding it
- add original Keshavarz20 value only when it is real: a real measurement, real field observation, real product evidence, a calculator/comparison, or a named expert review

Do not use fake authors, fake reviews, fake first-hand experience, purchased mentions, PBNs, keyword stuffing, AI-bait blocks or `llms.txt` as a ranking shortcut.

## 5) SEO fields

Prepare all queue fields required by the publisher, including:

- `content_type` = `post` (hard routing guard)
- `generated_at`
- `title`
- English ASCII `slug`
- `excerpt`
- `content_html`
- natural `focus_keyphrase`
- 3–8 `related_keyphrases`
- human-readable `seo_title`
- accurate `meta_description`
- `category_name` and existing `category_id` when known
- 4–10 useful tags
- `source_urls`
- matching `source_names`
- `research_summary` documenting why the topic and evidence were chosen
- precise English `image_search_query`
- `image_title`
- descriptive `alt_text`
- adaptive `faq_items` (0 or 3–8)

Do not create SEO fields by stuffing exact-match phrases. Titles, headings and metadata must describe the page accurately.

## 6) Image

The queue publisher may select an open-license Wikimedia image. The requested visual must be factual and relevant, not a fake field-test image. Do not present AI-created or unrelated imagery as documentary evidence.

## 7) Duplicate/cannibalization gate

Before queueing:

- inspect recent published and draft Keshavarz20 posts
- check title/topic/intent overlap
- strengthen an existing article rather than create a parallel page when intent is materially the same
- never generate a page solely for a spelling/keyword variant

## 8) Queue and WordPress safety

If every gate passes, write exactly one queue JSON to:

`daily-agri-articles/queue/YYYY-MM-DD.json`

using the current **Asia/Tehran** date and commit it to `calibra-dev/keshavarz20-actions` on `main`.

Never publish directly to WordPress. The GitHub queue publisher is responsible for validation and creating a **draft only**. Do not alter existing posts from this task.

If today's queue already exists, read it first; do not create a duplicate.

## 9) Final report

Report:

- selected topic
- why it passed the farmer-value/evidence gate
- direct source domains used
- queue path
- whether GitHub validation/publisher succeeded
- WordPress draft ID/status if available

If skipped, state the exact quality/evidence/duplication reason. Do not manufacture a topic merely to claim the automation ran.
