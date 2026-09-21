# SEO God1 — Master Closure Prompt — 2026-09-21

ماموریت:
تمام کارهای واقعاً باقی‌مانده کشاورز بیست را بدون تکرار کارهای بسته‌شده، از مسیر اصلی keshavarz20-git-ops اجرا کن و برنامه SEO God1 را تا بیشترین حد واقعی و قابل‌اثبات ببند.

مسیر اصلی اجرا:
ChatGPT -> GitHub -> calibra-dev/keshavarz20-actions -> GitHub Actions / guarded site gateway -> WordPress/WooCommerce/Keshavarz20 Bridge.
WPVibe فقط وقتی مجاز است که قابلیت موردنیاز در GitHub/REST/Bridge وجود نداشته باشد و آن عملیات همچنان در محدوده مجاز باشد.

قوانین قطعی:
1. هیچ Audit، Crawl، QA یا تغییر موفق قبلی را بی‌دلیل تکرار نکن.
2. قبل از هر Write، آخرین Ledger/Result/Run همان حوزه را بخوان.
3. هیچ قیمت، sale price، discount، coupon، payment setting، user/role/capability، secret/credential یا arbitrary executable code را تغییر نده.
4. هیچ مشخصه فنی، GTIN/MPN، سازگاری، Review، Rating، Case Study، مشتری، نتیجه پروژه، موجودی، ETA، هزینه حمل، Citation یا ویدیو را جعل نکن.
5. داده ناشناخته باید unknown/نیازمند تأیید بماند.
6. هیچ داده شخصی مشتری، Order ID، پیام خصوصی، آدرس یا export سفارش در repo عمومی ذخیره نشود.
7. هر Write باید تا حد ممکن Readback و Evidence داشته باشد.
8. PASS فقط وقتی مجاز است که Acceptance Criteria همان فاز واقعاً برآورده شده باشد.
9. وابستگی خارجی/Policy Guard را دور نزن؛ آن را با Evidence، Owner، Unlock و Validation مشخص کن.
10. اگر یک مسیر استاندارد فعلی خراب است ولی مسیر پشتیبانی‌شده دیگری در repo از قبل وجود دارد، از مسیر موجود و امن استفاده کن.
11. هیچ Paid/Trial/Billing action را بدون اقدام صریح صاحب حساب فعال نکن.
12. protected media/theme/IranKala/ionCube را force-edit نکن.

وضعیت‌های بسته‌شده که نباید دوباره‌کاری شوند:
- Phase 8 PASS_GUARDED
- Phase 9 PASS_GUARDED
- Phase 10 PASS
- Phase 14 PASS — 9/9 official regression
- Phase 16 PASS
- Phase 17 PASS
- Phase 18 PASS
- Phase 19 PASS
- Phase 21 PASS_GUARDED_IRAN_FIRST
و هر Phase دیگری که Ledger تازه امروز PASS واقعی نشان می‌دهد.

باقی‌مانده‌ها را در این ترتیب dependency اجرا کن:

P0 — Commerce path / Shipping / Checkout / Quote
- آخرین Iran shipping zone/method evidence را بخوان.
- اگر guarded path برای shipping config/test وجود دارد، فقط non-price/safe changes را اجرا و readback کن.
- اگر nationwide shipping model/ETA business rules وجود ندارد، هیچ مقدار حدسی نساز.
- صفحه/مسیر request-proforma و quote flow را verify کن.
- Quote status backend اگر مسیر مجاز موجود دارد فعال/تست شود؛ در غیر این صورت blocker دقیق ثبت شود.
- Payment redundancy فقط read/diagnose شود؛ payment settings mutation ممنوع است.

P0 — Measurement integrity
- GA4/GSC/Bing وضعیت زنده را بخوان.
- begin_checkout duplication، WhatsApp event fragmentation، request_quote، add_shipping_info، add_payment_info و purchase coverage را بررسی کن.
- اگر allow-listed tagging path موجود است، instrumentation را اصلاح کن و validate کن.
- اگر tagging mutation path مجاز نیست، exact change-set + acceptance test را ثبت کن و blocker را دقیق نگه دار.
- هیچ fake conversion event تولید نکن.

P0/P1 — Performance + Accessibility
- آخرین live Phase20 و performance evidence را بخوان.
- فقط fixهایی را اجرا کن که از page/content/settings allow-listed و قابل rollback هستند.
- IranKala/Owl/theme renderer/ionCube یا executable snippet جدید را بدون مسیر مجاز دست نزن.
- اگر هیچ supported source fix وجود ندارد، residual exact nodes + vendor/theme unlock را ثبت کن.
- PHP/runtime upgrade را فقط diagnose کن؛ host/runtime admin action را جعل نکن.

P1 — PIM / Product data / Compatibility / Media
- Top30 و current published catalog را بخوان.
- هر Brand/identifier/spec/compatibility gap که از منبع معتبر یا داده داخلی قطعی قابل اثبات است اصلاح و readback شود.
- هیچ GTIN/MPN/spec/compatibility از title شباهتی یا حدس ساخته نشود.
- gallery/media فقط از real owned/source media تکمیل شود؛ تصویر ساختگی به‌عنوان evidence محصول استفاده نشود.
- Product data quality score دوباره فقط در صورت تغییر واقعی refresh شود.

P1 — Search / Filter / Discovery
- canonical synonym normalization requirement را verify کن: Persian/Latin digits، inch/mm، ZWNJ، نخدار/نخ دار، PE/پلی‌اتیلن.
- اگر allow-listed search/filter config path وجود دارد اجرا و تست شود.
- اگر نیازمند theme/plugin code است، exact implementation contract + acceptance criteria ثبت شود و blocker واقعی باقی بماند.
- technical facets فقط بعد از authoritative structured attributes فعال شوند.

P1 — Reviews / Q&A / Trust
- Woo reviews state را verify کن.
- هیچ Review/Rating/AggregateRating ساختگی نساز.
- Question Engine موجود را سالم نگه دار؛ duplicate engine نساز.
- اگر consent-aware post-delivery review request backend موجود است تست و فعال شود؛ در غیر این صورت blocker دقیق ثبت شود.
- UGC/Case Study فقط real+consented.

P1 — CRM / Retention / Messaging
- CRM/form/consent/no-contact route inventory را verify کن.
- اگر consent-safe backend موجود است، quote follow-up / post-purchase / back-in-stock / review-request rules را مرحله‌ای تست کن.
- بدون consent یا no-contact state هیچ bulk/automated message نفرست.
- WhatsApp/Telegram provider نبودن را با connector evidence ثبت کن.
- abandoned-cart فقط وقتی فعال شود که consent/no-contact enforce شود.

P1 — Phase 15 Visual / Video
- Image Search/Image Sitemap state را verify کن و completed media batches را تکرار نکن.
- 20 video scripts/transcripts را source of truth نگه دار.
- فقط real rendered public videos را register کن.
- fake MP4/video URL/thumbnail/duration/publication metadata ممنوع.
- موجودی/Provider rendering capacity را read-only بررسی کن.
- هیچ paid/trial action را خودکار فعال نکن.
- وقتی real public assets آماده شدند، Video Sitemap Gate باید PASS شود؛ تا آن زمان external asset gate باقی بماند.

P1/P2 — AI citation measurement
- GA4 AI referral evidence را بخوان.
- GSC/Bing live telemetry را تا حد اتصال موجود بخوان.
- 200-prompt bank را حفظ کن.
- Referral را Citation حساب نکن.
- Direct citation KPIs فقط با observation واقعی ChatGPT/Perplexity/Gemini/Copilot/Google AI surfaces محاسبه شوند.
- اگر connector/tool مستقیم observation وجود ندارد، null را حفظ و blocker را دقیق ثبت کن.

P2 — Google latency / indexing
- فقط داده settled جدید را بخوان؛ audit بسته‌شده را تکرار نکن.
- outcome جدید calculator و priority pages را با pre-change baseline مقایسه کن.
- WAITING_FOR_GOOGLE را شکست اجرایی محسوب نکن.
- URLهای تکنیکی indexable ولی هنوز not-indexed را فقط براساس evidence دسته‌بندی کن.

P2 — Lifecycle
- review queue را بدون fake freshness دسته‌بندی کن.
- out-of-stock را discontinued فرض نکن.
- dateModified را بدون تغییر واقعی دست نزن.
- فقط مواردی که evidence کافی برای merge/redirect/deprecation دارند mutate شوند.

Final Gate:
- تمام Phase ledgerهای تازه را جمع کن.
- وضعیت هر فاز را یکی از PASS / PASS_GUARDED / PARTIAL_EXTERNAL / POLICY_GUARD / WAITING_EXTERNAL / BLOCKED_AUTHORITATIVE_DATA قرار بده.
- هیچ 10/10 یا COMPLETE مطلق تا زمانی که blocker ذاتی باقی است اعلام نکن.
- Final Gate باید شامل:
  * completed today
  * remaining hard blockers
  * remaining external/latency blockers
  * owner/unlock
  * next single highest-leverage action
  * evidence paths / run IDs / commits
  * safety attestation
باشد.

Definition of Done:
- هر کار قابل‌اجرا با دسترسی فعلی انجام شده باشد.
- هیچ کار بسته‌شده‌ای تکرار نشده باشد.
- هیچ داده یا نتیجه‌ای جعل نشده باشد.
- هر blocker باقی‌مانده واقعاً خارج از کنترل فعلی یا نیازمند منبع معتبر باشد.
- Final Gate تازه و قابل‌ممیزی در repo ثبت شده باشد.
