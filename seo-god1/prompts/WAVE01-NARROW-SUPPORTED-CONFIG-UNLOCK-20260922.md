# WAVE 1 — NARROW SUPPORTED CONFIG UNLOCK / EXECUTION PROMPT

## نقش
به‌عنوان اپراتور ارشد فنی Keshavarz20، فقط از مسیرهای تأییدشده و evidence-first کار کن. هیچ PASS ساختگی، هیچ audit تکراری، هیچ تغییر گسترده و هیچ دورزدن policy مجاز نیست.

## Control plane
مسیر اصلی:
ChatGPT -> GitHub -> calibra-dev/keshavarz20-actions -> GitHub Actions / guarded gateway -> WordPress

WPVibe فقط در صورتی fallback است که capability لازم در GitHub/Bridge/REST وجود نداشته باشد و policy آن را مجاز بداند.

## وضعیت قطعی فعلی
- IranKala 10.10.0 فعال است.
- کش singular ماشین‌حساب قبلاً رفع شده؛ دوباره A/B نکن.
- تصویر featured ماشین‌حساب قبلاً بهینه شده؛ دوباره compression نکن.
- دو تصویر سنگین promotion صفحه اصلی قبلاً با WebP جایگزین و روی live readback تأیید شده‌اند:
  - term 722 -> attachment 145324
  - term 793 -> attachment 145323
- کار promotion-image را دوباره trace یا اجرا نکن.
- Homepage LCP residual: polyetilenetesal.keshavarz20-768x225.jpg، هنوز lazy و بدون fetchpriority=high.
- Calculator LCP residual: featured WebP هنوز lazy.
- Phase20 residuals: Owl dot button names، login/register link name، image-link names.
- PHP runtime: 8.1.34.
- Product singular no-cache هنوز residual است و reviews باید حفظ شوند.
- config/site-access-policy.json صریحاً admin_settings/themes/plugins/core را Block می‌کند.

## هدف
بستن بیشترین بخش ممکن از Wave 1 بدون شکستن گارد، و تبدیل residualها به یکی از این سه حالت:
1. RESOLVED_VERIFIED
2. POLICY_GUARD_EXACT_UNLOCK_REQUIRED
3. EXTERNAL_HOSTING_OR_VENDOR_REQUIRED

## قوانین عدم تکرار
- IranKala update verification را تکرار نکن.
- calculator cache root-cause A/B را تکرار نکن.
- calculator image compression را تکرار نکن.
- homepage promotion-image tracing/WebP conversion را تکرار نکن.
- product cache probe را فقط در صورت mutation مرتبط با product cache تکرار کن.
- Phase20 exact audit فقط چون بعد از آخرین baseline یک renderer/media mutation واقعی اعمال شده، یک‌بار re-run شود.

## اجرای مرحله‌ای

### Step 1 — Post-mutation exact verification
فقط تست‌های لازم بعد از تغییر واقعی promotion images:
- Phase20 exact A11y diagnostics روی Home / PDP / guides
- Phase20 live UX/A11y gate
- Homepage LCP-chain diagnostic
- از تکرار calculator performance و product cache خودداری کن مگر mutation مرتبط رخ داده باشد.

### Step 2 — Compare against prior evidence
مقایسه کن:
- accessibility scores
- button-name counts
- link-name counts
- heading-order
- homepage LCP / CLS / TBT
- LCP element
- lazy-loading state
- fetchpriority state

هر improvement فقط با شواهد run جدید ثبت شود.

### Step 3 — Supported-path resolution search
برای هر residual:
- اول existing GitHub/Bridge/REST path را بررسی کن.
- اگر مسیر مجاز content/taxonomy/media/cache.purge وجود دارد، فقط narrow mutation با precondition + readback + rollback اجرا کن.
- theme protected code، arbitrary PHP/JS/snippet injection ممنوع.
- admin_settings/options mutation تحت policy فعلی ممنوع.
- broad lazy-load disable ممنوع.
- wp-post-image class-wide exclusion ممنوع.
- تغییر قیمت/پرداخت/کاربر/role/credential ممنوع.

### Step 4 — LiteSpeed LCP config candidate
فقط validate/document کن، اجرا نکن مگر policy صریحاً unlock شده باشد:
- current litespeed.conf.media-lazy_exc:
  - polyetilenetesal.keshavarz20.jpg
- proposed narrow additions:
  - polyetilenetesal.keshavarz20-768x225.jpg
  - k20-calculator-featured-optimized-1200-768x432.webp
- rollback:
  - restore exact prior array
- broad media-lazy off ممنوع.
- اگر policy هنوز admin_settings را Block می‌کند، status = POLICY_GUARD_EXACT_UNLOCK_REQUIRED.

### Step 5 — Accessibility residual routing
برای Owl dots / login-register / image-only links:
- اگر source/content/taxonomy/media metadata مجاز می‌تواند accessible name ایجاد کند، narrow fix با readback اجرا کن.
- اگر خروجی از ionCube-protected IranKala renderer می‌آید و هیچ hook/config مجاز موجود نیست، status = VENDOR_OR_POLICY_GUARD؛ کد محافظت‌شده را دستکاری نکن.

### Step 6 — Runtime
PHP 8.1.34 را فقط classify کن:
- اگر hosting/staging control در current tool path نیست، EXTERNAL_HOSTING_OR_STAGING_REQUIRED.
- روی production runtime بدون staging/compatibility proof تغییر نده.

### Step 7 — Evidence + master plan
در پایان:
- یک execution ledger تازه در seo-god1/ بساز.
- WAVE01-CURRENT-STATE-20260922.json را فقط با evidence تازه update کن.
- SEO-GOD1-REMAINING-MASTER-PLAN-20260921.json را بدون تغییر وضعیت فازهای بسته update کن.
- remaining gate را دوباره اجرا کن.
- تعداد blockerها و next action را از gate بخوان، حدس نزن.

## Success criteria
Wave 1 فقط وقتی PASS شود که:
- homepage/calculator LCP path به‌طور قابل‌تأیید اصلاح شده باشد،
- targeted Phase20 accessible-name failures بسته شده باشند،
- runtime path resolved/staged باشد یا صریحاً خارج از scope release gate تعریف شده باشد،
- هیچ policy bypass رخ نداده باشد.

در غیر این صورت Wave 1 را PARTIAL/POLICY_GUARD نگه دار و دقیقاً کوچک‌ترین unlock موردنیاز را ثبت کن.

## Safety attestation
در گزارش نهایی صریحاً ذکر شود:
- price/payment/user/role/credential mutations = 0
- protected theme edits = 0
- arbitrary snippet injection = 0
- broad plugin/theme administration = 0
- repeated closed work = 0
