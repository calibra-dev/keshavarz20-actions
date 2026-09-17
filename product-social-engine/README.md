# K20 Daily Product Social Engine

Daily zero-API-cost social publisher for Keshavarz20.

## What it does

1. Reads published products from the public WooCommerce Store API.
2. Keeps in-stock products that have a real product image.
3. Rotates products and avoids repeats using `state.json`.
4. Uses the real product image to render a Persian 1080x1350 branded creative.
5. Builds a factual Persian caption from the live product data; it does not invent technical claims and does not advertise a price.
6. Publishes to a Telegram channel or group through the official Telegram Bot API.
7. Uploads the same image and caption as a workflow artifact for WhatsApp use until an official programmable WhatsApp destination is configured for the account.

## Required GitHub configuration

Repository secrets:

- `TELEGRAM_BOT_TOKEN`: token created by BotFather.
- `TELEGRAM_CHAT_ID`: target channel username such as `@channelname`, or the numeric channel/group chat id.

Repository variable:

- `PRODUCT_SOCIAL_ENABLED=true` enables scheduled publishing. Until this variable is true, scheduled runs only generate a dry-run artifact and never post.

The Telegram bot must be added to the target channel/group with permission to post messages. For a channel, make it an administrator with post permission.

## Schedule

The workflow runs every day at 05:30 UTC, which is 09:00 Iran Standard Time (UTC+03:30). It can also be started manually in `dry_run` or `publish` mode.

## WhatsApp

The engine deliberately does not use unofficial WhatsApp Web browser automation. Such sessions are fragile and can stop after logout, QR/session changes, or platform enforcement. The workflow always produces a WhatsApp-ready image and caption artifact. If the connected WhatsApp Business account exposes an official supported endpoint for the intended destination, add it as a publisher adapter without changing the product-selection/rendering pipeline.

## Local checks

```bash
cd product-social-engine
python -m pip install -r requirements.txt
pytest -q
python main.py --dry-run
```
