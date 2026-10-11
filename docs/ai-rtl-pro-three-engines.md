# AI RTL Pro — three K20 engines

This integration implements the AI RTL Pro quality rules in the real GitHub runtime; a ChatGPT skill alone cannot change remote engine processes.

- News and article covers: Pillow plus libraqm with Unicode in logical order, direction=rtl, language=fa, approved Noto Arabic font, fit/safe-margin checks. Never reverse strings or trust text generated inside an AI image.
- Text: audit headlines, body, excerpts, meta, alt, captions, FAQ and tags after K20 sanitization. Preserve proper U+200C half-space, protect URLs, model codes, prices, measurements, and data order.
- Questions: audit question text before submitting, without changing product identifiers or user-facing question delivery.
- Preserve existing draft-only WordPress behavior and queue routing. An engine without image generation (questions) has no image text to render.
- Fail closed for unsupported fonts, missing libraqm, bad Unicode, or a cover that cannot fit.
- Automated shaping/layout checks are not a substitute for visual proofreading of final WebP at full-size and phone width.

Run: python -m unittest tests.test_k20_rtl_pro -v
