# K20 Approved Product Social Engine

Human-approved daily product promotion for Keshavarz20.

## Daily flow

- **22:55 Asia/Tehran**: GitHub prepares tomorrow's product, factual caption, 1080x1350 ad, and 1080x1920 Story image.
- **23:00 Asia/Tehran**: ChatGPT shows the prepared image/text to the user for review.
- Approval is stored as `product-social-engine/approvals/YYYY-MM-DD.json` and must match the exact date, product ID, and `candidate_hash`.
- **08:45**: approved WhatsApp group image + caption + direct product link.
- **08:50**: approved Telegram image + caption + direct product link.
- **08:55**: approved Instagram Story image only.
- Without an exact approval, every morning publisher skips safely.

## Product rules

The engine reads the public WooCommerce Store API, keeps only currently visible/in-stock products with a real image, rotates them using `state.json`, and re-checks product eligibility immediately before publication.

The WhatsApp and Telegram caption always includes the exact WooCommerce product permalink under:

`🛒 خرید و مشاهده مشخصات کامل محصول:`

No price, discount, certification, agronomic result, warranty claim, or technical fact may be invented.

## Required GitHub Secrets

Telegram:

- `TELEGRAM_BOT_TOKEN`
- The workflow target is `@keshavarz_20`.

Official WhatsApp Cloud API Groups:

- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_GROUP_ID`

Instagram Story:

- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`

Existing WordPress secrets:

- `WP_BASE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`

WordPress is used only to host the generated Story JPEG at a public HTTPS URL required for Meta ingestion.

## Security

Do not commit access tokens, app passwords, WhatsApp group IDs, or WhatsApp invite URLs. The public invite link is a human join link, not an API publishing credential.

## Approval JSON

When the user approves the exact preview shown in ChatGPT, create:

```json
{
  "status": "approved",
  "publish_date": "2026-09-19",
  "product_id": 123,
  "candidate_hash": "exact hash copied from the prepared candidate",
  "approved_at": "2026-09-18T23:05:00+03:30",
  "approved_via": "chatgpt-user-confirmation"
}
```

Changing the product, caption, link, or candidate invalidates the old approval because the hash changes.

## Manual commands

```bash
python product-social-engine/approval_pipeline.py prepare
python product-social-engine/approval_pipeline.py status --publish-date 2026-09-19
python product-social-engine/approval_pipeline.py whatsapp --publish-date 2026-09-19
python product-social-engine/approval_pipeline.py telegram --publish-date 2026-09-19
python product-social-engine/approval_pipeline.py instagram --publish-date 2026-09-19
```

See `POLICY.md` for the non-negotiable approval, content, credential, and failure rules.
