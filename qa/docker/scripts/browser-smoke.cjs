'use strict';

// Smoke-tests only the disposable WordPress installation on the Docker network.
const fs = require('node:fs');
const { chromium } = require('playwright');

(async () => {
  const site = process.env.QA_URL || 'http://wordpress';
  const mode = process.env.QA_STORAGE_MODE || 'legacy';
  const output = '/qa/artifacts/' + mode;
  fs.mkdirSync(output, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
    const failures = [];
    page.on('pageerror', (error) => failures.push(error.message));
    const response = await page.goto(site, { waitUntil: 'domcontentloaded', timeout: 30000 });
    if (!response || !response.ok()) {
      throw new Error('QA_BROWSER_HOME_HTTP_FAILURE');
    }
    const title = await page.title();
    if (!title.includes('K20 Disposable QA')) {
      throw new Error('QA_BROWSER_UNEXPECTED_SITE_TITLE');
    }
    await page.screenshot({ path: output + '/desktop.png', fullPage: true });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.screenshot({ path: output + '/mobile.png', fullPage: true });
    if (failures.length) {
      throw new Error('QA_BROWSER_PAGE_ERRORS count=' + failures.length + ' first=' + failures[0]);
    }
    console.log('QA_CHROMIUM_DESKTOP_MOBILE_PASS mode=' + mode);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
