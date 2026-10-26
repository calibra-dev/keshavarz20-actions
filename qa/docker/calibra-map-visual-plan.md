# Calibra 1.8.17 map visual acceptance

Target: byte-verified live Calibra 1.8.17 installed in disposable WordPress with WooCommerce. Test Legacy and HPOS.

Required evidence: authenticated Calibra dashboard screenshots at desktop 1366x900, mobile 390x844, tablet 768x1024 and wide desktop 1920x1080; 2D and 3D map visible and interactive; no JS console errors, clipped labels or horizontal overflow; city map geometry strictly matches city IDs; zero-sales and nonzero-sales orders; city absent from map affects statistics only, not other geometry; province and country sums correct; no production write.

PASS only with actual Playwright screenshots, per-test assertions, artifact links, run IDs and reviewed diffs. Current reusable browser smoke covers WordPress homepage only and is insufficient to certify Calibra map visuals.
