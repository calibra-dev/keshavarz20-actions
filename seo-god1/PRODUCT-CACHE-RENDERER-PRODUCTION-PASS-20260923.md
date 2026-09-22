# Product singular cache renderer — production acceptance PASS

Date: 2026-09-23
Target: K60 product ID 140856

## Change
Published the prepared IranKala draft-theme remediation:
- replaced the ionCube-protected IranKala WooCommerce review template override with the current WooCommerce core single-product-reviews template
- WPVibe created theme backup: `irankala-wpvibe-backup`
- LiteSpeed and Elementor caches were purged automatically during publish

## Production validation
GitHub Actions run:
- workflow: Keshavarz20 Cache Root-Cause Matrix
- run id: 35786120945
- request commit: 886be6bc8fc1d6b86d7266bbaa9c67db5c9e415c

K60 anonymous sequence:
1. x-litespeed-cache: miss
2. x-litespeed-cache: hit
3. x-litespeed-cache: hit

K60 TTFB / total:
1. 9.981182 / 10.322381 s
2. 6.322952 / 6.669207 s
3. 5.735675 / 6.079559 s

Private WooCommerce surfaces:
- Cart: no LiteSpeed HIT; cache-control private/no-cache
- Checkout: no LiteSpeed HIT; cache-control private/no-cache
- My Account: no LiteSpeed HIT; cache-control private/no-cache/no-store

Review renderer live readback:
- review tab rendered
- rating select rendered
- textarea rendered
- name/email fields rendered
- K20 review nonce rendered
- K20 custom real-experience fields rendered
- comment_post_ID 140856

SEO readback:
- canonical preserved: https://keshavarz20.com/product/کا-۶۰-ایکس-گرین/
- Yoast schema graph still present
- SEO title/description still present

## Decision
`PRODUCT_SINGULAR_CACHE_RENDERER` acceptance criterion PASS for K60.

Important nuance:
`x-litespeed-cache-control: no-cache,esi=on` is still emitted on the product response, but the server-level cache header now proves the effective anonymous sequence is MISS -> HIT -> HIT. Therefore do not interpret the control header alone as a failed acceptance while effective x-litespeed-cache is HIT.

## Next action
Do not repeat K60 root-cause experiments.
Run a controlled small PDP cohort to verify the fix generalizes beyond K60 before declaring the whole product catalog gate closed. Measure warm TTFB/total separately because cacheability is fixed, but K60 warm latency remains around 6 seconds and still needs a separate renderer/LCP/performance investigation.
