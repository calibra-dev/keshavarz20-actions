# Authoritative prompt — K20 Daily Article Research & Draft Queue

Generate today's single best long-form agriculture article candidate for the Keshavarz20 “نوشته‌ها” section and enqueue it for draft creation.

Use connected web research and the connected GitHub repository `calibra-dev/keshavarz20-actions`. First inspect the live/recent Keshavarz20 normal posts and the article-engine README. Do not work in the news post type and do not use the news queue.

Deep-search agriculture developments and high-intent farmer questions from the last 24–72 hours, while also considering seasonal evergreen opportunities when they are more useful than a transient headline. Compare multiple credible sources. Score candidates for trend/freshness, Iranian relevance, practical farmer value, search-intent/CTR potential, seasonality, authority, visual potential and novelty against recent Keshavarz20 posts. Select one topic only. Never choose a duplicate or near-duplicate just to satisfy the daily schedule.

Fact-check all material numerical, scientific, regulatory and market claims. Use at least three independent credible sources; prefer official institutions, universities, extension services, standards bodies and established specialist publications. Do not invent statistics, prices, dates, product claims or citations. Where evidence is uncertain, state the uncertainty.

Write original Persian that reads like an experienced human agriculture editor: natural rhythm, specific field usefulness, varied sentence length, no AI clichés, no source-copying, no keyword stuffing and no generic filler. Produce a high-CTR but accurate title, strong lead, clear H2/H3 sections, actionable explanations, examples and decision guidance. Add 3–6 relevant internal links to existing Keshavarz20 content when they genuinely help the reader.

The finished article must include a clear `جمع‌بندی`, exactly 15 substantial question-and-answer items covering the topic from multiple practical angles, and finally a clearly separated `نظر کارشناسی کشاورز بیست`. Keep sourced facts separate from the Keshavarz20 opinion block.

Prepare complete SEO metadata: focus keyphrase, 3–8 related keyphrases, SEO title, 80–185 character meta description, concise excerpt, English ASCII slug, 4–10 useful tags, and one existing WordPress post category chosen from the site's actual categories. Never create a new category. Include the category ID when confidently verified; otherwise set category_id to 0 and use the exact existing category name.

Prepare the featured image brief using a concise English `image_search_query`, a short Persian `image_title` suitable for the branded cover, and natural descriptive Persian `alt_text`. The GitHub publisher will source an open-license related photograph and produce a branded 1280×720 WebP cover.

Build valid queue JSON matching `daily-agri-articles/README.md`. `content_html` must be fully formatted HTML and already contain the 15 FAQ questions/answers, `جمع‌بندی`, source links, and the final `نظر کارشناسی کشاورز بیست` section. Also include the same 15 items structurally in `faq_items` for validation. Add `research_summary` explaining why this topic won today, the key verification performed and any remaining uncertainty.

Before writing, verify the target queue path does not already exist for today. Then write exactly one file to:
`daily-agri-articles/queue/YYYY-MM-DD.json`
using today's date in Asia/Tehran. Do not touch `daily-agri-news/`, do not publish directly to WordPress, do not alter existing posts, and do not add credentials or API keys. GitHub Actions will validate the payload and create a WordPress draft only. If no topic meets the evidence, novelty and quality gates, do not create a low-quality queue file; instead report why the run was skipped.
