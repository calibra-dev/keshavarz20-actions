# Keshavarz20 Chat Control

This repository is the cloud/fallback automation layer for keshavarz20.com. The preferred path for normal chat-driven site work is the private connected WordPress/WPVibe Abilities API. The on-site Keshavarz20 bridge is the second path for Keshavarz20-specific operations. GitHub-hosted Actions is the cloud runner/fallback for repeatable jobs and health checks.

## Execution order

1. WPVibe / WordPress Abilities API (private, no PC required)
2. Keshavarz20 on-site abilities and bridge endpoints
3. GitHub-hosted Actions in this public repository
4. The old Windows self-hosted runner only as an emergency fallback

## Allowed chat operations

- Read/search products
- Create a product as draft
- Update product name, slug, descriptions, status, SKU where appropriate
- Update product stock state and quantity
- Update product categories, tags, images and safe media metadata
- Update product Yoast SEO fields through the Keshavarz20 allow-listed SEO ability
- Read/create/update posts and pages, with new content defaulting to draft
- Read/upload media from a URL and update title/alt/caption/description
- Read/create/update categories and tags
- Read/create/update navigation menus and menu items
- Read/create/update comments when explicitly requested
- Run internal-link/content/frontend audits
- Purge caches after content changes when useful

## Hard blocks

Chat automation must not modify or expose:

- product prices, regular prices or sale prices
- discounts, coupons or promotions
- users, passwords, roles or capabilities
- plugins, themes or WordPress core
- WordPress/WooCommerce administrative settings
- payment, shipping or tax configuration
- API keys, tokens, application passwords or other secrets
- orders or customer records under this automation contract

There is no user-facing delete command in this contract. Test cleanup may only remove an automation-created temporary object after verifying its exact identity.

## Public repository privacy rule

Never place credentials, private drafts, customer data, admin data, unpublished sensitive content, backups, database dumps, local bridge configuration or full private operation results in this public repository. Use the private WPVibe/Abilities route for private or unpublished content.

## Natural-language examples

The user can say in chat:

- `محصول 135383 را بخوان و فقط محتوا و سئو و موجودی را گزارش کن، قیمت را نیاور.`
- `توضیحات کامل محصول 135383 را با متن زیر به‌روزرسانی کن؛ قیمت و تخفیف را دست نزن.`
- `موجودی محصول 135383 را 12 کن.`
- `یک محصول جدید با نام ... به صورت Draft بساز و قیمت وارد نکن.`
- `برای محصول 135383 دسته‌ها و تگ‌های مناسب را اصلاح کن، چیزی را حدسی حذف نکن.`
- `ALT و عنوان تصویر 1234 را اصلاح کن.`
- `این مقاله را ویرایش کن و Yoast SEO آن را هم به‌روزرسانی کن.`
- `یک برگه Draft جدید برای ... بساز.`
- `لینک‌های داخلی مقالات را Audit کن؛ فعلا چیزی را تغییر نده.`
- `کش سایت را بعد از این تغییرات پاک کن.`

ChatGPT should choose the safest available path automatically and report what was actually changed.
