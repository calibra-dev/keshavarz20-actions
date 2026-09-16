import json
import os
import pathlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OUT = ROOT / 'sitewide-media-results' / 'crawl-audit.json'
base = os.environ.get('WP_BASE_URL', '').rstrip('/')
if not base:
    raise SystemExit('Missing required repository secret: WP_BASE_URL')


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def request(url, timeout=25):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Sitewide-Crawl-Audit/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read(), dict(r.headers)
    except Exception:
        return 0, b'', {}


def local(tag):
    return str(tag).split('}', 1)[-1].lower()


def direct_loc(parent):
    for child in list(parent):
        if local(child.tag) == 'loc' and (child.text or '').strip():
            return (child.text or '').strip()
    return ''


def parse_sitemap(url):
    status, raw, _ = request(url, timeout=25)
    if not (200 <= status < 300) or not raw:
        return False, [], []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return False, [], []
    root_name = local(root.tag)
    if root_name == 'sitemapindex':
        nested = []
        for child in list(root):
            if local(child.tag) != 'sitemap':
                continue
            loc = direct_loc(child)
            if loc:
                nested.append(loc)
        return True, nested, []
    if root_name == 'urlset':
        urls = []
        for child in list(root):
            if local(child.tag) != 'url':
                continue
            loc = direct_loc(child)
            if loc:
                urls.append(loc)
        return True, [], urls
    return False, [], []


queue = [base + '/wp-sitemap.xml', base + '/sitemap_index.xml']
seen = set()
failed_sitemaps = []
page_urls = set()
while queue and len(seen) < 150:
    sitemap = queue.pop(0)
    if sitemap in seen:
        continue
    seen.add(sitemap)
    ok, nested, urls = parse_sitemap(sitemap)
    if not ok:
        failed_sitemaps.append(sitemap)
        continue
    for child in nested:
        if child.startswith(base) and child not in seen and child not in queue and len(queue) < 150:
            queue.append(child)
    for url in urls:
        if url.startswith(base) and len(page_urls) < 5000:
            page_urls.add(url)


def crawl(url):
    status, raw, headers = request(url, timeout=25)
    ctype = str(headers.get('Content-Type') or headers.get('content-type') or '').lower()
    ok = bool(200 <= status < 300 and raw and 'text/html' in ctype)
    return {'url': url, 'http': status, 'content_type': ctype[:100], 'ok': ok}

success = 0
failures = []
with ThreadPoolExecutor(max_workers=12) as pool:
    futures = [pool.submit(crawl, url) for url in sorted(page_urls)]
    for future in as_completed(futures):
        row = future.result()
        if row['ok']:
            success += 1
        else:
            failures.append(row)

result = {
    'executed_at_utc': now_iso(),
    'action': 'sitewide_media.crawl_audit',
    'read_only': True,
    'sitemaps_seen': len(seen),
    'sitemaps_read': len(seen) - len(failed_sitemaps),
    'sitemap_failures': len(failed_sitemaps),
    'sitemap_failure_sample': failed_sitemaps[:20],
    'public_urls_discovered': len(page_urls),
    'rendered_pages_read': success,
    'rendered_pages_failed': len(failures),
    'rendered_failure_sample': failures[:30],
    'crawl_complete': bool(page_urls) and not failed_sitemaps and not failures and success == len(page_urls),
    'note': 'Only direct <url><loc> page URLs are crawled. image:loc and other nested media loc elements are intentionally excluded.',
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
