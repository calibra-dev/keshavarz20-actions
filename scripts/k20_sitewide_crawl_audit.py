import json
import os
import pathlib
import re
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser

ROOT = pathlib.Path('.')
OUT = ROOT / 'sitewide-media-results' / 'crawl-audit.json'
base = os.environ.get('WP_BASE_URL', '').rstrip('/')
if not base:
    raise SystemExit('Missing required repository secret: WP_BASE_URL')

TOP30_PATH = ROOT / 'phase3-results' / 'top30-pim.json'
MONEY_PATHS = {
    '/',
    '/shop/',
    '/irrigation-filter-selector/',
    '/polyethylene-pipe-size-flow-pressure-guide/',
    '/irrigation-fittings-compatibility-selector/',
    '/drip-tape-buying-guide/',
    '/drip-tape-length-fittings-calculator/',
    '/layflat-hose-size-inch-mm-guide/',
    '/layflat-length-fittings-calculator/',
    '/complete-drip-irrigation-system-guide/',
    '/irrigation-valves-buying-guide/',
    '/polyethylene-compression-fittings-guide/',
}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def norm(url):
    p = urllib.parse.urlsplit(str(url or ''))
    path = urllib.parse.unquote(p.path or '/').rstrip('/') or '/'
    if path != '/':
        path += '/'
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ''))


def request(url, timeout=30, user_agent='K20-Sitewide-Crawl-Audit/2.0'):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': user_agent, 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.geturl(), r.read(), dict(r.headers)
    except Exception as exc:
        code = getattr(exc, 'code', 0) or 0
        final = getattr(exc, 'url', url) or url
        try:
            raw = exc.read() if hasattr(exc, 'read') else b''
        except Exception:
            raw = b''
        headers = dict(getattr(exc, 'headers', {}) or {})
        return int(code), str(final), raw, headers


def local(tag):
    return str(tag).split('}', 1)[-1].lower()


def direct_text(parent, name):
    for child in list(parent):
        if local(child.tag) == name and (child.text or '').strip():
            return (child.text or '').strip()
    return ''


def parse_sitemap(url):
    status, _, raw, _ = request(url, timeout=30)
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
            loc = direct_text(child, 'loc')
            if loc:
                nested.append(loc)
        return True, nested, []
    if root_name == 'urlset':
        urls = []
        for child in list(root):
            if local(child.tag) != 'url':
                continue
            loc = direct_text(child, 'loc')
            if loc:
                urls.append({'url': loc, 'lastmod': direct_text(child, 'lastmod') or None})
        return True, [], urls
    return False, [], []


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.robots = []
        self.links = []
        self.title_on = False
        self.title = []
        self.h1_on = False
        self.h1 = []

    def handle_starttag(self, tag, attrs):
        a = {str(k).lower(): (v or '') for k, v in attrs}
        t = tag.lower()
        if t == 'link' and 'canonical' in a.get('rel', '').lower().split():
            self.canonical = a.get('href') or self.canonical
        elif t == 'meta' and a.get('name', '').lower() in {'robots', 'googlebot', 'bingbot'}:
            self.robots.append({'agent': a.get('name', '').lower(), 'content': a.get('content', '').lower()})
        elif t == 'a' and a.get('href'):
            self.links.append(a['href'])
        elif t == 'title':
            self.title_on = True
        elif t == 'h1':
            self.h1_on = True

    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self.title_on = False
        elif tag.lower() == 'h1':
            self.h1_on = False

    def handle_data(self, data):
        if self.title_on:
            self.title.append(data)
        if self.h1_on:
            self.h1.append(data)


def is_soft404(title, h1, body_text):
    hay = (' '.join([title, h1, body_text[:5000]])).lower()
    needles = [
        'page not found', 'not found', '404 error',
        'صفحه پیدا نشد', 'صفحه یافت نشد', 'مطلب پیدا نشد', 'محصول یافت نشد',
    ]
    return any(x in hay for x in needles)


queue = [base + '/wp-sitemap.xml', base + '/sitemap_index.xml']
seen = set()
failed_sitemaps = []
page_meta = {}
while queue and len(seen) < 200:
    sitemap = queue.pop(0)
    if sitemap in seen:
        continue
    seen.add(sitemap)
    ok, nested, rows = parse_sitemap(sitemap)
    if not ok:
        failed_sitemaps.append(sitemap)
        continue
    for child in nested:
        if child.startswith(base) and child not in seen and child not in queue and len(queue) < 200:
            queue.append(child)
    for row in rows:
        url = row['url']
        if url.startswith(base) and len(page_meta) < 6000:
            n = norm(url)
            existing = page_meta.get(n) or {'url': url, 'lastmod': row.get('lastmod'), 'sitemaps': []}
            if sitemap not in existing['sitemaps']:
                existing['sitemaps'].append(sitemap)
            if not existing.get('lastmod') and row.get('lastmod'):
                existing['lastmod'] = row.get('lastmod')
            page_meta[n] = existing

top30_urls = set()
if TOP30_PATH.exists():
    try:
        pim = json.loads(TOP30_PATH.read_text(encoding='utf-8'))
        top30_urls = {norm(x.get('permalink')) for x in pim.get('products', []) if x.get('permalink')}
    except Exception:
        top30_urls = set()
money_urls = {norm(base + p) for p in MONEY_PATHS}


def crawl(meta):
    url = meta['url']
    status, final_url, raw, headers = request(url, timeout=30)
    ctype = str(headers.get('Content-Type') or headers.get('content-type') or '').lower()
    xrobots = str(headers.get('X-Robots-Tag') or headers.get('x-robots-tag') or '').lower()
    html_ok = bool(200 <= status < 300 and raw and 'text/html' in ctype)
    parser = PageParser()
    text = ''
    if html_ok:
        text = raw.decode('utf-8', 'replace')
        try:
            parser.feed(text)
        except Exception:
            pass
    canonical = unescape(parser.canonical or '').strip() or None
    robots_contents = [x['content'] for x in parser.robots]
    noindex = 'noindex' in xrobots or any('noindex' in x for x in robots_contents)
    self_canonical = bool(canonical) and norm(canonical) == norm(final_url)
    title = re.sub(r'\s+', ' ', ' '.join(parser.title)).strip()
    h1 = re.sub(r'\s+', ' ', ' '.join(parser.h1)).strip()
    body_plain = re.sub(r'<[^>]+>', ' ', text)
    body_plain = re.sub(r'\s+', ' ', unescape(body_plain)).strip()
    soft404 = bool(status == 200 and is_soft404(title, h1, body_plain))
    internal_links = []
    for href in parser.links:
        try:
            absolute = urllib.parse.urljoin(final_url, href)
            p = urllib.parse.urlsplit(absolute)
            if p.scheme in {'http', 'https'} and p.netloc.lower() == urllib.parse.urlsplit(base).netloc.lower():
                internal_links.append(norm(absolute))
        except Exception:
            continue
    final_same = norm(final_url) == norm(url)
    query = urllib.parse.urlsplit(url).query
    is_top30 = norm(url) in top30_urls
    is_money = is_top30 or norm(url) in money_urls
    pass_core = html_ok and not noindex and self_canonical and not soft404
    return {
        'url': url,
        'http': status,
        'final_url': final_url,
        'redirected': not final_same,
        'content_type': ctype[:120],
        'html_crawlable': html_ok,
        'canonical': canonical,
        'self_canonical': self_canonical,
        'meta_robots': parser.robots,
        'x_robots_tag': xrobots or None,
        'noindex': noindex,
        'soft_404_suspected': soft404,
        'lastmod': meta.get('lastmod'),
        'sitemaps': meta.get('sitemaps') or [],
        'has_query_params': bool(query),
        'internal_links': sorted(set(internal_links)),
        'is_top30': is_top30,
        'is_money_page': is_money,
        'pass_core': pass_core,
    }


rows = []
with ThreadPoolExecutor(max_workers=12) as pool:
    futures = [pool.submit(crawl, meta) for meta in page_meta.values()]
    for future in as_completed(futures):
        rows.append(future.result())
rows.sort(key=lambda x: x['url'])

inlinks = {norm(x['url']): 0 for x in rows}
for row in rows:
    for target in row.pop('internal_links', []):
        if target in inlinks and target != norm(row['url']):
            inlinks[target] += 1

for row in rows:
    row['internal_inlinks'] = inlinks.get(norm(row['url']), 0)
    row['orphan_candidate'] = bool(row['is_money_page'] and row['internal_inlinks'] == 0 and norm(row['url']) != norm(base + '/'))
    failures = []
    if row['http'] != 200:
        failures.append('http_not_200')
    if not row['html_crawlable']:
        failures.append('html_not_crawlable')
    if row['noindex']:
        failures.append('noindex')
    if not row['canonical']:
        failures.append('canonical_missing')
    elif not row['self_canonical']:
        failures.append('canonical_not_self')
    if row['soft_404_suspected']:
        failures.append('soft_404_suspected')
    if row['orphan_candidate']:
        failures.append('money_page_no_internal_inlinks')
    row['failures'] = failures
    row['priority'] = 'P0' if row['is_money_page'] and failures else ('P1' if failures else 'PASS')

robots_url = base + '/robots.txt'
robots_status, _, robots_raw, robots_headers = request(robots_url, timeout=30)
robots_text = robots_raw.decode('utf-8', 'replace') if robots_raw else ''
robots = urllib.robotparser.RobotFileParser()
robots.set_url(robots_url)
robots.parse(robots_text.splitlines())
crawler_agents = ['Googlebot', 'Bingbot', 'OAI-SearchBot']
crawler_access = {}
representative = [base + '/']
for candidate in sorted(money_urls | top30_urls):
    if candidate and candidate != norm(base + '/'):
        representative.append(candidate)
        if len(representative) >= 5:
            break
for agent in crawler_agents:
    probes = []
    for u in representative:
        allowed = robots.can_fetch(agent, u) if robots_status == 200 else None
        status, final, _, _ = request(u, timeout=25, user_agent=agent)
        probes.append({'url': u, 'robots_allowed': allowed, 'http': status, 'final_url': final})
    crawler_access[agent] = {
        'robots_allowed_all_representative': all(x['robots_allowed'] is not False for x in probes),
        'http_200_all_representative': all(x['http'] == 200 for x in probes),
        'probes': probes,
    }

money = [x for x in rows if x['is_money_page']]
top30 = [x for x in rows if x['is_top30']]
failed = [x for x in rows if x['failures']]
lastmod_missing = [x for x in rows if not x.get('lastmod')]
future_lastmod = []
for x in rows:
    lm = x.get('lastmod')
    if not lm:
        continue
    try:
        dt = datetime.fromisoformat(lm.replace('Z', '+00:00'))
        if dt > datetime.now(timezone.utc):
            future_lastmod.append(x['url'])
    except Exception:
        pass

summary = {
    'public_urls_discovered': len(rows),
    'http_200': sum(1 for x in rows if x['http'] == 200),
    'html_crawlable': sum(1 for x in rows if x['html_crawlable']),
    'self_canonical': sum(1 for x in rows if x['self_canonical']),
    'noindex': sum(1 for x in rows if x['noindex']),
    'soft_404_suspected': sum(1 for x in rows if x['soft_404_suspected']),
    'redirected_sitemap_urls': sum(1 for x in rows if x['redirected']),
    'query_param_sitemap_urls': sum(1 for x in rows if x['has_query_params']),
    'lastmod_missing': len(lastmod_missing),
    'future_lastmod': len(future_lastmod),
    'money_pages_in_scope': len(money),
    'money_pages_pass': sum(1 for x in money if not x['failures']),
    'top30_in_scope': len(top30),
    'top30_pass': sum(1 for x in top30 if not x['failures']),
    'p0': sum(1 for x in rows if x['priority'] == 'P0'),
    'p1': sum(1 for x in rows if x['priority'] == 'P1'),
    'pass': sum(1 for x in rows if x['priority'] == 'PASS'),
}

result = {
    'executed_at_utc': now_iso(),
    'action': 'growthos.phase1.technical_retrieval_index_control',
    'version': 'sitewide-crawl-audit-v2',
    'read_only': True,
    'sitemaps_seen': len(seen),
    'sitemaps_read': len(seen) - len(failed_sitemaps),
    'sitemap_failures': len(failed_sitemaps),
    'sitemap_failure_sample': failed_sitemaps[:20],
    'robots_txt': {
        'url': robots_url,
        'http': robots_status,
        'content_type': str(robots_headers.get('Content-Type') or robots_headers.get('content-type') or '')[:120],
    },
    'crawler_access': crawler_access,
    'summary': summary,
    'money_page_failures': [x for x in money if x['failures']],
    'top30_failures': [x for x in top30 if x['failures']],
    'failure_sample': failed[:100],
    'url_inventory': rows,
    'limitations': [
        'Server-log bot hit frequency is not inferred; only robots policy and representative live HTTP access are tested.',
        'Orphan detection is computed against links found within sitemap-discovered HTML pages and is therefore a crawl-scope signal, not a full external-link graph.',
        'Soft-404 detection is conservative text-based suspicion and should be human-reviewed before any destructive redirect/delete action.',
        'IndexNow delivery is validated by its dedicated workflow/evidence rather than inferred from this crawl.',
    ],
    'definition_of_done': {
        'top30_200_canonical_indexable_crawlable_sitemap_internal_linked': bool(len(top30) == 30 and all(not x['failures'] for x in top30)),
        'money_pages_200_canonical_indexable_crawlable_sitemap_internal_linked': bool(money and all(not x['failures'] for x in money)),
        'robots_reachable': robots_status == 200,
        'googlebot_access': crawler_access['Googlebot']['robots_allowed_all_representative'] and crawler_access['Googlebot']['http_200_all_representative'],
        'bingbot_access': crawler_access['Bingbot']['robots_allowed_all_representative'] and crawler_access['Bingbot']['http_200_all_representative'],
        'oai_searchbot_access': crawler_access['OAI-SearchBot']['robots_allowed_all_representative'] and crawler_access['OAI-SearchBot']['http_200_all_representative'],
    },
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'summary': summary, 'definition_of_done': result['definition_of_done']}, ensure_ascii=False))
