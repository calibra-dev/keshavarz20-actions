# SEO God 2026 — Phase 20 & 21 execution state

Date: 2026-09-19
Repository: calibra-dev/keshavarz20-actions
Mode: GitHub-first, evidence-first.

## Phase 20 — UX/CRO/Accessibility/Agent Usability

Status: **PARTIAL — verified theme-level accessibility blockers remain**

Persisted live evidence:
- `phase20-results/ux-a11y-live-latest.json`
- `phase20-results/a11y-diagnostics-latest.json`
- `phase20-results/fast-semantic-diagnostics-latest.json`
- `phase20-results/site-context-latest.json`

Verified good:
- all 5 target pages return HTTP 200
- Persian language and RTL are present
- mobile content-width gate passes
- server-rendered meaningful content is present
- product price / buy CTA / stock / SKU are visible
- product and decision-tool pages have one H1 and one main landmark

Verified blockers:
1. Shared header link `a.login-register` has no accessible name.
2. Shared/homepage logo links render without accessible text in server HTML.
3. Owl Carousel dot buttons (`button.owl-dot`) have no accessible names on homepage/product carousels.
4. Homepage has two H1 elements:
   - `h1.site-title` = کشاورز بیست
   - Elementor content H1 = کشاورز بیست؛ مرجع خرید مطمئن تجهیزات و نهاده‌های کشاورزی
5. Homepage heading order skips into `h3.widget-title` for «دسته‌های ویژه».
6. Several homepage promotional/category links (`a.ads-item` and image-only links) have no discernible accessible name.

WordPress context:
- front page ID: 644
- active theme: IranKala / ایران‌کالا
- stylesheet/template: `irankala`

Safety:
- site mutations performed by Phase 20 diagnostics: 0
- commerce mutations: 0
- price/payment/user/credential changes: 0

### Required remediation layer

The remaining blockers are theme/JS/template-level. They cannot be truthfully closed by editing product/page copy alone. A surgical IranKala accessibility patch is required for:
- aria-label/text for login/register and logo links
- accessible names for Owl Carousel dots
- homepage site-title heading level
- homepage heading hierarchy
- image-only promotional/category links

No arbitrary theme/plugin code was applied because the current Keshavarz20 Git Ops policy does not allow arbitrary code changes without an explicit policy change.

## Phase 21 — Digital PR & Original Citation Assets

Status: **READY / BLOCKED ONLY BY PHASE 20 PASS DEPENDENCY**

Prepared and persisted:
- `phase21/citation-campaign-assets.json`
- manufacturer-source registry
- original methodology/data brief assets
- manufacturer fact-check asset
- expert/installer outreach templates
- anti-PBN / anti-fake-review / anti-fake-dealership guards

No fake review, customer, field result, dealership/distributor claim, paid fake mention, or PBN was created.

External messages sent: 0
Paid placements: 0
Site mutations: 0

Phase 21 must not be marked PASS until Phase 20 is actually remediated and re-audited.
