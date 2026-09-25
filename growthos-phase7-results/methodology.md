# Keshavarz20 Growth OS — Phase 7 Original Evidence & Data Assets

Generated: 2026-09-26

## Scope
این فاز دارایی‌های داده‌ای قابل بازتولید برای Decision Hubها می‌سازد. تصویر/ویدئو در این فاز وارد نشده است.

## Method
1. تقاضا از رجیستری مرکزی Intent فاز ۵ خوانده می‌شود.
2. پوشش محصول و گپ‌های داده از Compatibility Summary فاز ۴ خوانده می‌شود.
3. دسته‌های Hub از Taxonomy موجود WooCommerce انتخاب می‌شوند؛ URL تجاری جدید خودکار ساخته نمی‌شود.
4. هیچ رابطه `fits/worksWith` از روی هم‌سایز بودن، دسته مشترک، لینک داخلی یا شباهت ظاهری ساخته نمی‌شود.
5. مقادیر فنی بدون منبع دقیق SKU/مدل به‌صورت Unknown باقی می‌مانند.

## Limitations
- Snapshot تقاضا مربوط به ۲۸ روز منتهی به 2026-09-24 است.
- نبود Topic مستقل در Phase 5 به معنی نبود تقاضا نیست.
- Family-level readiness به معنی سازگاری فنی محصول‌به‌محصول نیست.
- Bing در Phase 5 متصل بود اما هنگام دریافت Query با ThrottleIP مواجه شد؛ بنابراین به‌عنوان Measurement Gap ثبت شده است.

## Update trigger
با Snapshot جدید Search Console، تغییر Owner Map، دریافت دیتاشیت/برچسب دقیق، یا تغییر Product Truth این Datasetها باید بازسازی شوند.


## Completed original-evidence asset classes — 2026-09-26

- **Size/conversion:** `layflat-size-mapping.csv` preserves the project-provided nominal inch→mm mapping as a catalog mapping, explicitly not a universal mathematical conversion. The live 8-inch product is recorded with millimeter mapping left unknown.
- **Live catalog size index:** `layflat-live-catalog-size-index.csv` parses only the size label visible in exact live product titles; it does not infer physical diameter, pressure class or compatibility.
- **Calculation results:** `calculation-results.csv` records formula, inputs, result, source and assumption/limitation for every derived percentage.
- **Compatibility:** `compatibility-evidence-table.csv` separates verified technical edges (0) from candidate same-size edges (23); candidates are not publishable as `fits/worksWith`.
- **Selection standards:** `selection-standards.csv` defines required inputs and fail-closed triggers for all five Decision Hubs.
- **Real catalog dataset:** `hub-category-dataset.csv` records the five exact live category IDs, direct product counts, audit-match counts, timestamps and limitations.
- **Error patterns:** `error-patterns.csv` uses visible existing category/Q&A guidance and Phase 4 evidence gaps. It does not pretend to be a support-ticket frequency report.
- **Case notes:** deliberately not invented. `case-notes-status.json` records the missing evidence required before a real case note may be created.

## Provenance rule

Every asset must carry date/source/method/limitation either row-by-row or through its companion manifest/methodology. A missing exact SKU/model source keeps the technical value or compatibility relation unknown.
