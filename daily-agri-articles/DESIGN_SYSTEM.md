# Keshavarz20 Article Visual Design System

Use this visual contract for all new long-form WordPress Posts created by the daily article engine.

## Goal
Make each article feel like a polished RTL editorial landing page, not a plain text post. It should remain readable, fast, responsive and compatible with WordPress content.

## Required layout
1. Wrap the article in a single RTL container with a soft agriculture-themed background.
2. Add a strong hero card at the top with:
   - deep green or green-gradient background
   - white heading and short summary
   - one concise status/benefit label
3. Put every major H2 section inside its own rounded card.
4. Use visually distinct callout cards:
   - green for practical tips
   - amber for warnings/uncertainty
   - red-tint for common mistakes
   - dark green for Keshavarz20 editorial recommendations
5. Tables must be inside a scroll-safe card with rounded borders and readable spacing.
6. Formula or calculator sections must use a dedicated highlighted card.
7. FAQ must use a dedicated section with each Q&A visibly separated.
8. Finish with a high-contrast summary/CTA card.
9. Keep RTL alignment and mobile readability.

## Inline style baseline
Prefer inline styles so rendering does not depend on theme CSS.

Recommended colors:
- primary: #17653A
- dark: #11492A
- accent: #2E8B57
- light green: #EAF6EE
- page background: #F5FBF7
- cream: #FFF9F0
- warning: #FFF6D8
- danger tint: #FFF0F0
- text: #1F2937
- border: #D7E9DD

Recommended card:
`background:#fff;border:1px solid #D7E9DD;border-radius:18px;padding:24px;margin:22px 0;box-shadow:0 10px 30px rgba(20,83,45,.08)`

Recommended main wrapper:
`direction:rtl;background:linear-gradient(180deg,#F3FAF5 0%,#FFFFFF 100%);padding:28px;border-radius:24px`

## Editorial constraints
- Do not sacrifice factual accuracy for visual design.
- Do not use excessive emojis.
- Do not put every sentence in a separate box.
- Do not use unreadable dark backgrounds for long body text.
- Keep paragraphs normal inside cards.
- No fake metrics, fake badges, fake ratings or fabricated CTAs.
- Use visuals to improve scanning and decision-making.


## Seller-aware editorial voice

Keshavarz20 is a specialist agricultural retailer. Content should help the reader diagnose and choose correctly before buying. Do not force a purchase into every section. When a replacement or purchase is genuinely relevant, state the exact information needed for a correct recommendation (pressure, flow, size, connection, water source, crop, field conditions, existing model, etc.). Avoid empty CTAs, fake scarcity, exaggerated superiority and generic "buy now" language.

For full troubleshooting, buying, calculator, maintenance and agronomy guides, the default finish includes 15 useful FAQs plus a clearly separated «نظر کارشناسی کشاورز بیست» card.
