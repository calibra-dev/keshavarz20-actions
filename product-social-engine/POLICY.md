# K20 Product Social Engine Policy

## Human approval gate

- Every day at 22:45 Asia/Tehran the engine prepares tomorrow's candidate so ChatGPT can show it at 23:00.
- Preparation never publishes to WhatsApp, Telegram, or Instagram.
- Morning publication is allowed only when `product-social-engine/approvals/YYYY-MM-DD.json` exists and exactly matches the candidate date, product ID, and `candidate_hash`.
- No approval, stale approval, wrong product, or changed candidate hash means **skip publication**.
- Replacing the candidate changes its hash and invalidates every older approval.

## Product and content rules

- Select only products that are currently published/visible, in stock, and have a real product image.
- Re-check eligibility immediately before every morning publication.
- Never invent specifications, certifications, stock claims, prices, discounts, agronomic outcomes, warranty terms, or customer experience.
- Do not hard-code a sale price in social copy.
- WhatsApp and Telegram text must include the direct WooCommerce product URL for that exact product.
- Avoid immediate product repetition using persisted history.

## Channel schedule

- 08:45 Asia/Tehran: WhatsApp group image + text + direct product URL.
- 08:50 Asia/Tehran: Telegram image + text + direct product URL.
- 08:55 Asia/Tehran: Instagram Story image only.

## Platform and credential rules

- Telegram uses the official Bot API. The bot must have posting permission on `@keshavarz_20`.
- WhatsApp uses the official Cloud API Groups path only. A public invite link is not a publish credential and must never be committed. Required IDs and tokens stay in GitHub Secrets.
- Instagram Story uses the official Instagram/Meta content publishing flow. Tokens and Instagram user IDs stay in GitHub Secrets.
- Existing WordPress secrets may be used only to host the generated Story JPEG at a public HTTPS media URL required by Meta.
- Never print, commit, upload as an artifact, or expose access tokens, app passwords, or private group identifiers.

## Failure rules

- If the approved product becomes unavailable or its product URL changes before publication, block the post and require a new review.
- A channel failure must remain visible in the workflow result; do not claim success without a platform response ID.
- Successful state is recorded per channel and publish date for auditability and repeat protection.
