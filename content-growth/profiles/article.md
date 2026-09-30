# K20 Master Prompt v3.1 — ARTICLE PROFILE

این پروفایل فقط برای موتور نوشته‌هاست و همراه Master Prompt v3 خوانده می‌شود.

- هدف: ساخت/ارتقای یک صفحه مرجع آموزشی یا تصمیم‌یار، نه خبر.
- Answer-first اجباری برای سؤال‌های عملی.
- برای موضوع فنی، FACT / ESTIMATE / ENGINEERING CALCULATION را در متن روشن نگه دار.
- مثال عددی فقط با فرض شفاف.
- FAQ فقط سؤال واقعی و غیرتکراری.
- حداقل عمق مفید فعلی را حفظ کن؛ کوتاه‌سازی صرفاً برای سبک ممنوع.
- بخش‌های «جمع‌بندی»، «نظر کارشناسی کشاورز بیست»، «منابع» و «روش تهیه و بازبینی» اگر در ورودی وجود دارند حفظ شوند.
- internal links فقط از allow-list.
- source_urls/source_names/research_summary و داده‌های intent محافظت شوند.
- slug و شناسه‌های انتشار تغییر نکنند.
- خروجی دقیقاً مطابق JSON contract موتور نوشته باشد؛ کلید اضافه نساز.


- برای صفحه موجود، READ → DIAGNOSE → NARROW PATCH → TEST → APPLY → CACHE PURGE → READBACK → LIGHTHOUSE ×3 → ACCEPT/ROLLBACK را اجرا کن؛ مراحل خارج از scope را N/A کن.
- Answer-first باید قبل از توضیح طولانی، تصمیم اصلی را روشن کند.
- Information Gain واقعی ترجیحاً با جدول تصمیم، فرمول، مثال، «چه زمانی مناسب نیست»، troubleshooting، compatibility یا ورودی‌های طراحی ایجاد شود.
- Existing Article Repair: برای مسئله Performance، SEO/content سالم را بی‌دلیل بازنویسی نکن.
- اگر Hero/LCP بررسی می‌شود، duplicate context، responsive srcset/sizes و heavy non-LCP assets را هم audit کن.
- CTA طبیعی و تصمیم‌محور باشد؛ هیچ pressure copy یا ادعای ساختگی موجودی/قیمت/برتری نساز.
- DONE فقط با readback و شواهد مربوط به scope؛ «همه چیز عالی شد» بدون داده ممنوع.
