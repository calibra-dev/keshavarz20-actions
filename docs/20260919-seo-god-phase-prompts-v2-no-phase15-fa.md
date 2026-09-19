# SEO God 2026 — Phase Prompt Pack v2 (فاز ۱۵ خارج از اجرا)

مبنای اجرا: 2026-09-19  
دامنه: keshavarz20.com  
قاعده اصلی: Evidence > Action > Readback > Public Verify > Regression Check

## قواعد مشترک تمام فازها
- وضعیت زنده و جدیدتر بر handoff قدیمی مقدم است.
- کار PASS‌شده بدون شواهد regression تکرار نشود.
- داده نامعلوم، نامعلوم بماند.
- هیچ قیمت، تخفیف، کاربر، نقش، credential یا secret تغییر نکند.
- کد دلخواه قالب/افزونه بدون مجوز صریح تغییر نکند.
- هر blocker با یکی از این چهار نوع ثبت شود: HARD، SOFT_EXTERNAL، WAITING_FOR_GOOGLE، POLICY_GUARD.
- «commit شد» یا «workflow موفق شد» به‌تنهایی PASS نیست.
- Phase 15 = SKIPPED_BY_USER و در این اجرا هیچ write/audit جدیدی برای آن انجام نشود.

## Phase 1 — Source of Truth / No Repeat
پرامپت: جدیدترین evidenceهای GitHub، WordPress، GSC و handoff را merge کن؛ برای هر موضوع یک owner و یک status ثبت کن؛ duplicate audit و اقدام منسوخ را قفل کن. خروجی: ledger یکتا با timestamps و evidence pointers.

## Phase 2 — Crawl / Index Matrix
پرامپت: URLها را به technical indexable، Google indexed، discovered-not-indexed، unknown-to-Google، intentional noindex و error تفکیک کن. نتیجه Google را با indexability فنی یکی نگیر. اولویت را بر صفحات تجاری/تصمیمی قرار بده.

## Phase 3 — Root Cause
پرامپت: به‌جای patch کور، علت را تا لایه renderer/cache/plugin/template ردیابی کن. هر فرض را با A/B یا evidence رد/تأیید کن؛ تست ردشده را تکرار نکن.

## Phase 4 — AI/GEO Baseline
پرامپت: prompt bank، query families، entity/brand baseline و citation fields را بساز. مشاهده‌نشده را NULL نگه دار؛ ranking را citation فرض نکن.

## Phase 5 — PIM Baseline
پرامپت: SKU، brand، GTIN، attributes، media، availability و descriptions را audit کن. مقدار مفقود را fabricate نکن. Gapها را با impact و evidence priority مرتب کن.

## Phase 6 — Indexability Remediation
پرامپت: برای URL هدف 200 + self-canonical + index/follow + sitemap + robots allow را اثبات کن. پس از PASS فنی، نتیجه Google را WAITING_FOR_GOOGLE نگه دار تا URL Inspection خلاف آن را نشان دهد.

## Phase 7 — Performance / CWV
پرامپت: فقط root causeهای باقی‌مانده را هدف بگیر. اگر ionCube/protected theme یا سرویس پولی شرط اصلاح است، POLICY_GUARD ثبت کن. cache bypass و checkout/account/cart safety را حفظ کن. تست‌های A/B بسته‌شده تکرار نشوند.

## Phase 8 — Entity / Trust
پرامپت: Organization/entity/about/contact/policies را با واقعیت سایت همسو کن؛ ادعای نمایندگی یا تأیید سازنده جعل نشود. consistency نام، تماس، آدرس و entity links را بسنج.

## Phase 9 — Canonical PIM
پرامپت: روی sample/priority set، page/schema/feed parity را اثبات کن. unknown GTIN/specs همان unknown بماند. تفاوت source fields را صفر کن.

## Phase 10 — Measurement
پرامپت: GSC، GA4، Bing، CrUX و AI surfaces را هرکدام مستقل ثبت کن. نبود connector فقط همان metric را PARTIAL_EXTERNAL می‌کند و نباید فازهای محتوایی مستقل را قفل کند. baseline تاریخ‌دار و reproducible بساز.

## Phase 11 — Product Decision Pages
پرامپت: فقط محصولات اولویت‌دار با evidence تقاضا را ارتقا بده. مناسب/نامناسب، ورودی لازم قبل خرید، محدودیت، compatibility، source confidence و decision links را اضافه کن. قیمت/stock را تغییر نده مگر سیاست جداگانه صریحاً اجازه دهد.

## Phase 12 — Category Decision Pages
پرامپت: قبل از write، current taxonomy را بخوان. فقط gap تصمیم‌گیری را اصلاح کن: معیار انتخاب، grouping، suitable/not-suitable، comparison، uncertainty، source/method/update. یک category در هر mutation، سپس readback عمومی.

## Phase 13 — Guides / Hubs
پرامپت: برای هر intent یک owner داشته باش. query-variant thin page نساز. فقط وقتی live diff شکاف واقعی را ثابت کرد owner موجود را تقویت کن. dosage/compatibility بدون منبع ممنوع. اگر content readback نداریم، write متوقف شود.

## Phase 14 — Calculators / Selectors
پرامپت: formula، unit، input validation، edge cases، disclaimers و worked examples را تست کن. ابزار راهنمای تصمیم است نه certified hydraulic/agronomic design.

## Phase 15 — Visual / Video
SKIPPED_BY_USER. در این اجرا هیچ اقدام جدیدی انجام نشود.

## Phase 16 — Internal Link Graph
پرامپت: orphan و weakly-connected priority pages را با links واقعی و context مناسب رفع کن. link stuffing ممنوع. graph بعد از mutation دوباره اندازه‌گیری شود.

## Phase 17 — Evidence / Expert Layer
پرامپت: evidence card، method note، author/reviewer و limitations را فقط با مدرک واقعی پر کن. case study و testimonial بدون evidence ممنوع.

## Phase 18 — Automation Governance
پرامپت: تولید خودکار باید draft/hold و human review داشته باشد؛ fake freshness، auto-publish ادعای فنی و content flooding ممنوع. logs و fail-safe لازم است.

## Phase 19 — Feed / API / Agent
پرامپت: page/schema/feed parity، brand، currency normalization، descriptions، identifiers و canonical URL را validate کن. external submission را بدون endpoint/authorization انجام‌شده تلقی نکن.

## Phase 20 — UX / Accessibility
پرامپت: WCAG 2.2 AA، mobile RTL، semantic H1/headings، accessible names، form labels، contrast، target size و no-JS decision content را live تست کن. content fixes مجازند؛ template/JS/CSS قالب فقط با مجوز کد. intrinsic theme defects = POLICY_GUARD.

## Phase 21 — Digital PR
پرامپت: citation assets، methodology notes، fact sheets و outreach targets را evidence-backed آماده کن. آماده‌سازی asset مستقل از Phase20 است. پیام ارسال‌شده را فقط با delivery evidence بشمار. PBN/fake mention/fake endorsement ممنوع.

## Phase 22 — Farmer Decision Personalization
پرامپت: مدل توضیح‌پذیر باشد؛ ورودی ناقص توصیه خاص را متوقف یا نرم کند؛ hydraulic/agronomic certainty ادعا نشود؛ escalation مشخص باشد. functional model PASS را از site accessibility جدا گزارش کن.

## Phase 23 — Freshness / Lifecycle
پرامپت: stale review با fake dateModified فرق دارد. out-of-stock = discontinued نیست. merge/redirect/deprecation نیازمند evidence و plan است. صف review را تولید کن، bulk rewrite نکن.

## Phase 24 — AI Citation Measurement
پرامپت: 200 prompt bank را روی surface نام‌برده واقعاً مشاهده کن. citation/brand mention/rank/referral/conversion بدون observation NULL بماند. GSC جایگزین AI surface نیست.

## Phase 25 — Final Gate
پرامپت: دو scorecard بساز:
1) Original SEO God: Phase15 = SKIPPED_BY_USER/UNASSESSED، پس 10/10 اصلی اعلام نشود.
2) Run Completion excluding Phase15: تمام 24 فاز دیگر را PASS / PASS_GUARDED / PARTIAL_EXTERNAL / WAITING_FOR_GOOGLE / POLICY_GUARD / FAIL نشان بده.
Scale فقط وقتی مجاز است که intrinsic blockers صفر باشند و evidence قابل بازتولید باشد.
