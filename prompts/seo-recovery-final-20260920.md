# Keshavarz20 SEO Recovery Final Prompt — 2026-09-20

## Objective
Finalize the remaining actionable SEO validation work without repeating closed audits. Focus on the verified traffic loss of the drip-tape calculator, finish the fresh crawl/404 validation delta, improve exact-query relevance and CTR safely, preserve existing calculator functionality/layout, and update the SEO God evidence ledger.

## Source of truth
- Site: https://keshavarz20.com
- Repository: calibra-dev/keshavarz20-actions
- Primary control plane: GitHub + guarded gateway
- WPVibe fallback is allowed only for capabilities the guarded gateway does not safely expose, specifically:
  - partial server-side content patching without round-tripping the full 100k+ page body
  - protected Yoast postmeta writes plus re-save/cache refresh
- Search/analytics evidence: live Windsor.ai GA4 + GSC; Bing connected but provider throttled.

## Verified current facts
1. Fresh sitewide crawl run 35515578289 completed successfully.
   - sitemaps_seen: 9
   - sitemaps_read: 9
   - sitemap_failures: 0
   - public_urls_discovered: 839
   - rendered_pages_read: 839
   - rendered_pages_failed: 0
   - crawl_complete: true
2. Current 28-day GSC window 2026-08-21..2026-09-17:
   - 931 clicks
   - 15,704 impressions
   - CTR 5.93%
   - impression-weighted avg position 9.53
3. Previous 28-day window 2026-07-24..2026-08-20:
   - 971 clicks
   - 16,049 impressions
   - CTR 6.05%
   - avg position 6.49
4. Main verified loss:
   URL: https://keshavarz20.com/drip-tape-length-fittings-calculator/
   - clicks 129 -> 41
   - impressions 913 -> 543
   - position 2.93 -> 3.76
   Exact query "ماشین حساب نوار تیپ":
   - previous: 113 clicks / 780 impressions / CTR 14.49% / position 2.63
   - current: 15 clicks / 275 impressions / CTR 5.45% / position 3.23
5. WordPress post ID for calculator: 143698
6. Current post title:
   "محاسبه متراژ نوار تیپ و تعداد اتصالات؛ فرمول و محاسبه‌گر آنلاین"
7. Current Yoast title:
   "محاسبه متراژ نوار تیپ و تعداد اتصالات | کشاورز بیست"
8. Current Yoast focus keyword:
   "محاسبه متراژ نوار تیپ"
9. Current meta description ends abruptly and is not ideal for the dominant exact query.
10. Existing contextual inbound links already exist from 8 relevant pages, including exact/near-exact anchors. Do not mass-add duplicate links.

## Execution plan

### A. Fresh crawl closure
- Treat the successful 839/839 rendered crawl with zero failures as evidence that the current public sitemap crawl has no discovered hard fetch failures.
- Do not claim all historical 404s are globally impossible; record only the fresh crawl evidence.
- Close the generic "fresh crawl delta pending" item.

### B. Calculator CTR/relevance recovery
Make a minimal, reversible, relevance-preserving update to post 143698:
- New WordPress title:
  "ماشین حساب نوار تیپ؛ محاسبه متراژ، تعداد رول و اتصالات"
- New Yoast SEO title:
  "ماشین حساب نوار تیپ | محاسبه متراژ، رول و اتصالات"
- New Yoast focus keyword:
  "ماشین حساب نوار تیپ"
- New Yoast meta description:
  "با ماشین حساب نوار تیپ کشاورز بیست، متراژ نوار، تعداد رول، رابط و اتصالات و دبی تقریبی را بر اساس طول خطوط، فاصله ردیف‌ها و مشخصات زمین محاسبه کنید."
- Patch only the first introductory sentence so the exact dominant query appears naturally near the top:
  replace:
  "برای محاسبه نوار تیپ، دانستن مساحت زمین به‌تنهایی کافی نیست. دو زمین"
  with:
  "ماشین حساب نوار تیپ این صفحه برای برآورد متراژ و اتصالات طراحی شده است؛ با این حال دانستن مساحت زمین به‌تنهایی کافی نیست. دو زمین"
- Preserve slug, URL, calculator JS, forms, IDs, schema/FAQ content, CTA, and all existing functional sections.
- Do not rewrite the full page.
- Do not change price, products, inventory, commercial terms, phone/WhatsApp, or unrelated content.

### C. Internal-link policy
- Do not mass-edit the 8 existing inbound donors.
- Existing exact anchors on tools pages already cover "ماشین حساب نوار تیپ و اتصالات".
- Keep diversity on guide pages ("محاسبه متراژ...", "محاسبه متراژ... و تعداد خطوط").
- No new link is required in this pass unless readback proves the calculator has fewer than the already verified 8 donors.

### D. Verification
After writes:
- Read back WordPress title.
- Read back Yoast title, meta description, focus keyword.
- Search the post body and prove the new intro phrase exists exactly once.
- Re-save post once after Yoast meta update so Yoast indexables/live render can refresh.
- Purge cache using the site's supported cache purge command if available.
- Re-read public/REST rendered metadata if available.
- Do not claim ranking recovery immediately; GSC needs new settled data.

### E. Evidence / final gate update
Write immutable evidence to GitHub:
- validation-results/drip-tape-calculator-recovery-20260920.json
- validation-results/sitewide-crawl-delta-20260920.json
Update Phase 25 only because hard blockers materially changed:
- fresh crawl delta -> CLOSED/PASS_GUARDED
- calculator recovery action -> APPLIED_WAITING_GSC
- Phase 24 remains PARTIAL due incomplete direct multi-surface citation observations
- Phase 7 remains guarded by IranKala/LCP
- Phase 20 remains guarded by theme/Owl accessibility
- Bing remains connected but temporary provider throttle
- no false 10/10 release

## Success criteria
PASS for this execution only when:
- post 143698 title readback matches target,
- Yoast title/metadesc/focuskw readback match targets,
- intro exact-query patch exists once,
- fresh crawl evidence is recorded,
- no unrelated page/product/price changes occurred,
- final ledger states WAITING_GSC rather than claiming recovered rankings.

## Safety
- Never expose credentials or secrets.
- No destructive SQL.
- No full-body rewrite.
- No mass internal-link edits.
- No plugin/theme protected-code edits.
- No price/stock/payment/user/role changes.
- No fabricated ranking, citation, revenue, or conversion claims.
