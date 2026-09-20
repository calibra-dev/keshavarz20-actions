# Keshavarz20 News Visual Design System

Use this visual contract for every new WordPress `news` draft created by the daily news engine.

## Visual goal
A premium Persian RTL editorial-news page: stronger than a plain Classic Editor article, visually rich but still fast, readable and credible.

## Required layout
1. One RTL wrapper with a very light agriculture-green background.
2. Hero card at top:
   - dark green / green gradient
   - white headline
   - short lead
   - compact factual label such as «راهنمای کاربردی» or «خبر کشاورزی»
3. Every major H2 section in its own rounded white card.
4. Use callout cards only when they add meaning:
   - green = practical takeaway
   - amber = caution / uncertainty
   - red tint = common mistake / risk
   - dark green = Keshavarz20 editorial analysis
5. Tables must be responsive and boxed.
6. Formula, checklist or calculator-like blocks must be visually distinct.
7. FAQ, when present, must be boxed and easy to scan.
8. Final summary and «نظر کارشناسی کشاورز بیست» must be visually separated.
9. Keep source links in a clean source card at the end.

## Inline style baseline
Main wrapper:
`direction:rtl;background:linear-gradient(180deg,#F3FAF5 0%,#FFFFFF 100%);padding:28px;border-radius:24px;color:#1F2937;line-height:2`

Normal section card:
`background:#fff;border:1px solid #D7E9DD;border-radius:18px;padding:24px;margin:22px 0;box-shadow:0 10px 30px rgba(20,83,45,.08)`

Colors:
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

## Editorial constraints
- Do not make a news story look like an advertisement.
- Do not hide uncertainty inside decorative cards.
- Never add fake badges, fake ratings or fabricated metrics.
- Do not put every sentence in a separate box.
- Keep sourced fact, uncertainty and editorial analysis visibly distinct.
- Avoid scripts and theme-dependent CSS in the news body; prefer inline HTML/CSS that survives Classic Editor.
