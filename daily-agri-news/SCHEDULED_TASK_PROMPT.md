# Keshavarz20 Daily Agriculture News — Production Prompt

This is the canonical automatic prompt for the daily `news` engine.

## Read first

1. `automation-policy/seo-god-2026.json`
2. `automation-policy/editorial-trust-2026.json`
3. `content-growth/K20_CONTENT_GROWTH_MASTER_PROMPT_V3.md`
4. `content-growth/profiles/news.md`
5. this file
6. `daily-agri-news/README.md`
7. `daily-agri-news/DESIGN_SYSTEM.md`

Use the stricter rule on conflict.

## Mission

At most once per Tehran day, research the previous 24 hours and choose one fresh, material, independently verifiable agriculture story that changes or informs a real decision for Iranian farmers. If nothing clears the gate, skip the day.

Cover water/irrigation, drought/climate, crop production/harvest, inputs/fertilizer/pesticides, greenhouse technology, farm economics/logistics, trade and farmer-impacting policy.

Search snippets, RSS, social posts and AI summaries are discovery only. Verify material claims from direct sources. Require at least two direct URLs from at least two independent domains. Prefer official/regulator/standards, universities/extension/research, primary datasets, recognized agriculture bodies and reputable news publications.

Reject rumor, advertorial, source-less reposts, sensationalism, filler and duplicates. Keep government/policy coverage neutral and attributed.

## Required structure

Use original human-first Persian with an accurate headline, concise lead, what happened, confirmed facts, verified numbers only, uncertainty, `این خبر برای کشاورزان چه معنایی دارد؟`, practical watch-point, `جمع‌بندی`, clearly labelled `نظر کارشناسی کشاورز بیست`, `منابع`, and a visible `روش تهیه و بازبینی` block linking to `https://keshavarz20.com/editorial-policy/`. Never name a human author or reviewer unless the identity and role are actually verified.

## Queue contract

Write only `daily-agri-news/queue/YYYY-MM-DD.json` using the current Asia/Tehran date. Never create a normal WordPress post and never touch `daily-agri-articles`.

Required image fields:

- `image_search_query`: factual English background query
- optional `image_search_fallbacks`
- `image_title`
- `cover_title`: 2–8 Persian words, no manual line breaks, max two rendered lines
- optional `cover_subtitle`: max 12 words / two lines
- `alt_text`

The publisher owns typography. Never ask an image model to typeset Persian. Never use synthetic imagery as documentary evidence. GitHub applies controlled cinematic grading and deterministic Noto Arabic + Pillow + arabic-reshaper + python-bidi rendering; it fails closed on font/shaping/overflow problems.

## Duplicate/idempotency

If today's queue exists, do not rewrite or duplicate it. Check recent queue/public history before selection; the publisher performs the final authenticated duplicate check against the real `news` CPT.

## Queue ingress reliability

Use GitHub Contents API on the current `main` branch as the canonical queue ingress.

Before every queue write:
1. re-read `daily-agri-news/queue/YYYY-MM-DD.json` from current `main`;
2. if it exists, stop queue creation and continue with publisher/site-side verification only;
3. if it is absent, create exactly that one queue file on current `main`.

Treat GitHub Contents API HTTP 422 / `sha wasn't supplied` during a create as a concurrency signal, not as permission to overwrite or create a duplicate. Immediately re-read the target path from current `main`. If the queue now exists, accept the concurrent winner and continue with its publisher/readback. If it is still absent, retry only from a freshly read current-main state.

Do not leave a daily queue stranded on a stale recovery branch. If a temporary branch is ever required because direct main ingress is unavailable, create it from the latest current-main head immediately before writing. Re-check current `main` before opening or merging a PR; if main advanced and the PR becomes dirty/stale, do not force-merge. Recreate the recovery branch from the new main head or stop if the queue has appeared concurrently.

A queue file is not completion. The day is complete only after the publisher produces a verified WordPress item with `wp_type=news`, `wp_status=draft`, and a concrete post ID/readback.

## Safety

Draft only. Human review is mandatory.
