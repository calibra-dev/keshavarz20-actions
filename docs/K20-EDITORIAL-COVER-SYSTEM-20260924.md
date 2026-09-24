# Keshavarz20 Editorial Cover System — 2026-09-24

## Goal

News and long-form article covers must look premium, cinematic and consistent **without ever relying on an image model to spell Persian**.

## Architecture

`verified factual background → controlled cinematic grade → deterministic Persian overlay → fit/safe-margin QA → WebP → WordPress draft`

### Background
- 16:9
- factual/relevant agriculture scene
- text-free
- open-license or otherwise verified reusable source
- no fake field-test evidence
- no synthetic documentary claims
- restrained cinematic color/contrast only

### Persian typography
- Noto Sans Arabic / Noto Naskh Arabic
- Pillow + arabic-reshaper + python-bidi
- title: max 8 words / 2 lines
- subtitle: max 12 words / 2 lines
- high-contrast dark-green editorial panel
- safe margins
- no manual line breaks / bidi control characters
- fail closed if text cannot fit cleanly

## Engine mapping
- Article publisher: `daily-agri-articles/publish_queue_v5.py`
- News publisher: `daily-agri-news/publish_queue_v3.py`
- Questions engine has no image generation; it remains text-only and persistent.

## Fail-closed behavior

The draft must not be created if the approved Persian font/shaping stack is unavailable or copy overflows the safe layout. A broken Persian cover is a publishing failure, not a cosmetic warning.

## Human review

All generated editorial content remains draft/hold. Visual QA does not change the human-review requirement.
