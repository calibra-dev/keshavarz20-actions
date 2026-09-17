import base64
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
PREDELETE = ROOT / 'media-predelete-results' / 'manifest.json'
SITEWIDE = ROOT / 'sitewide-media-results' / 'inventory.json'
OPS = ROOT / 'media-reference-delta-ops'
OUT = ROOT / 'ops' / 'media' / 'unused-media-zero-ref-current25-20260917.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()


def load(path):
    if not path.exists():
        raise SystemExit(f'Missing required file: {path}')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def latest_request():
    rows = sorted(OPS.glob('*.json'), key=lambda p: p.stat().st_mtime)
    if not rows:
        raise SystemExit('Missing targeted reference-delta request.')
    return json.loads(rows[-1].read_text(encoding='utf-8-sig'))


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%:@-._~!$&\'()*+,;=')
    query = urllib.parse.quote(p.query, safe='=&?/%:@-._~!$\'()*+,;')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, query, p.fragment))


def api_get(path, params=None, timeout=90):
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(qurl(url), headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Targeted-Reference-Delta/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            return int(r.status), json.loads(raw) if raw else {}, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:500]}
        return int(e.code), obj, dict(e.headers)
    except Exception as e:
        return 0, {'error': type(e).__name__, 'message': str(e)}, {}


def public_get(url, timeout=35):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Targeted-Reference-Delta/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ctype = str(r.headers.get('Content-Type') or '').lower()
            return int(r.status), raw.decode('utf-8', 'replace') if 'text/html' in ctype else '', ctype
    except urllib.error.HTTPError as e:
        return int(e.code), '', ''
    except Exception:
        return 0, '', ''


def request_bytes(url, timeout=30):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Targeted-Reference-Delta/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read(), dict(r.headers)
    except Exception:
        return 0, b'', {}


def upload_key(url):
    try:
        path = urllib.parse.unquote(urllib.parse.urlsplit(str(url or '')).path)
    except Exception:
        return ''
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    return path[pos + len(marker):].lstrip('/') if pos >= 0 else ''


def canonical_key(key):
    key = urllib.parse.unquote(str(key or '')).lstrip('/')
    head, sep, name = key.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot:
        return key
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return head + '/' + clean if sep else clean


def parse_iso(value):
    text = str(value or '').strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


pre = load(PREDELETE)
site = load(SITEWIDE)
request = latest_request()
if request.get('action') != 'media.targeted_reference_delta':
    raise SystemExit('Unsupported targeted reference-delta action.')
if pre.get('action') != 'media.predelete_verify' or pre.get('read_only') is not True:
    raise SystemExit('Pre-delete manifest identity failed.')
if int(pre.get('blocked_at_predelete_count') or 0) != 0:
    raise SystemExit('Pre-delete manifest still has blocked items.')
ready = pre.get('ready') or []
if len(ready) != int(pre.get('ready_for_delete_count') or 0):
    raise SystemExit('Pre-delete ready count mismatch.')
expected = int(request.get('expected_ready_count') or 0)
if expected and len(ready) != expected:
    raise SystemExit(f'Expected {expected} ready items, found {len(ready)}.')

protected = {int(x) for x in (request.get('protected_ids') or []) if int(x) > 0}
targets = {}
for row in ready:
    aid = int(row.get('attachment_id') or 0)
    url = str(((row.get('live') or {}).get('source_url')) or row.get('plan_url') or '')
    if aid <= 0 or not url or aid in protected:
        raise SystemExit(f'Invalid/protected ready item: {aid}')
    targets[aid] = {'id': aid, 'url': url, 'key': upload_key(url), 'canonical': canonical_key(upload_key(url))}
if set(targets) & protected:
    raise SystemExit('Protected ID leaked into delta targets.')

site_summary = site.get('summary') or {}
baseline = parse_iso(site_summary.get('executed_at_utc'))
if baseline is None or site_summary.get('crawl_complete') is not True or int(site_summary.get('rendered_pages_failed') or 0) != 0:
    raise SystemExit('Accepted sitewide baseline is missing/incomplete.')

refs = {aid: [] for aid in targets}
seen_tokens = {aid: set() for aid in targets}
recent_urls = {base + '/'}
coverage = {
    'post_types': {}, 'products_read': 0, 'categories_read': 0,
    'font_faces_read': 0, 'global_styles_read': 0,
    'sitemaps_read': 0, 'sitemap_failures': 0,
    'delta_urls_selected': 0, 'delta_pages_read': 0, 'delta_pages_failed': 0,
}


def add_ref(aid, kind, object_id=0, object_type='', field='', locator=''):
    aid = int(aid or 0)
    if aid not in targets:
        return
    token = (str(kind), int(object_id or 0), str(object_type), str(field), str(locator))
    if token in seen_tokens[aid]:
        return
    seen_tokens[aid].add(token)
    refs[aid].append({
        'kind': token[0], 'object_id': token[1], 'object_type': token[2],
        'field': token[3], 'locator': token[4],
    })


def resolve_url(value):
    key = upload_key(value)
    if not key:
        return 0
    ck = canonical_key(key)
    for aid, t in targets.items():
        if key == t['key'] or ck == t['canonical']:
            return aid
    return 0


def scan_text(text, kind, object_id=0, object_type='', field='', locator='', scan_numeric=True):
    if not isinstance(text, str) or not text:
        return
    for m in re.finditer(r'wp-image-(\d+)', text, flags=re.I):
        add_ref(int(m.group(1)), kind, object_id, object_type, field, locator)
    pattern = r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)'
    for m in re.finditer(pattern, text, flags=re.I):
        aid = resolve_url(m.group(0))
        if aid:
            add_ref(aid, kind, object_id, object_type, field, locator)
    if scan_numeric:
        idpat = r'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id|featured_media)(?:"|\b)\s*[:=]\s*["\']?(\d{3,})'
        for m in re.finditer(idpat, text):
            add_ref(int(m.group(1)), kind, object_id, object_type, field, locator)


def scan_json(value, kind, object_type, locator=''):
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        text = str(value)
    scan_text(text, kind, 0, object_type, 'json', locator, scan_numeric=False)


def is_recent(value):
    dt = parse_iso(value)
    return bool(dt and dt >= baseline)


code, types, _ = api_get('/wp-json/wp/v2/types', {'context': 'view'})
if not (200 <= code < 300) or not isinstance(types, dict):
    raise SystemExit(f'post type discovery failed http={code}')
for type_name, info in sorted(types.items()):
    if type_name in {'attachment', 'nav_menu_item', 'wp_font_face', 'wp_global_styles'} or not isinstance(info, dict):
        continue
    rest_base = str(info.get('rest_base') or '').strip('/')
    namespace = str(info.get('rest_namespace') or 'wp/v2').strip('/')
    if not rest_base:
        continue
    route = f'/wp-json/{namespace}/{rest_base}'
    seen = 0
    error = None
    for page in range(1, 101):
        params = {'per_page': 100, 'page': page, 'context': 'edit', 'status': 'any'}
        code, rows, headers = api_get(route, params)
        if code in (400, 401, 403) and page == 1:
            params = {'per_page': 100, 'page': page, 'context': 'view'}
            code, rows, headers = api_get(route, params)
        if code == 400 and page > 1:
            break
        if not (200 <= code < 300) or not isinstance(rows, list):
            error = f'http={code}'
            break
        if not rows:
            break
        for row in rows:
            seen += 1
            oid = int(row.get('id') or 0) if isinstance(row, dict) else 0
            link = str(row.get('link') or '') if isinstance(row, dict) else ''
            if isinstance(row, dict):
                add_ref(row.get('featured_media') or 0, 'featured_image_current', oid, type_name, 'featured_media', link)
                scan_json(row, 'rest_object_current', type_name, link)
                if link.startswith(base) and (is_recent(row.get('modified_gmt')) or is_recent(row.get('modified'))):
                    recent_urls.add(link)
        total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
        if (total_pages and page >= total_pages) or len(rows) < 100:
            break
    coverage['post_types'][type_name] = {'items_read': seen, 'error': error, 'route': route}
    if error:
        raise SystemExit(f'post type delta scan failed {type_name}: {error}')

for page in range(1, 51):
    code, rows, headers = api_get('/wp-json/wc/v3/products', {
        'per_page': 100, 'page': page, 'status': 'any', 'orderby': 'id', 'order': 'asc',
        '_fields': 'id,images,description,short_description,permalink,date_modified_gmt',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        raise SystemExit(f'Woo product delta scan failed http={code}')
    if not rows:
        break
    for row in rows:
        coverage['products_read'] += 1
        pid = int(row.get('id') or 0)
        link = str(row.get('permalink') or '')
        for pos, image in enumerate(row.get('images') or []):
            add_ref((image or {}).get('id') or 0, 'woo_product_image_current', pid, 'product', f'images[{pos}]', link)
            aid = resolve_url((image or {}).get('src') or '')
            if aid:
                add_ref(aid, 'woo_product_image_url_current', pid, 'product', f'images[{pos}]', link)
        scan_text(str(row.get('description') or ''), 'woo_product_description_current', pid, 'product', 'description', link)
        scan_text(str(row.get('short_description') or ''), 'woo_product_short_description_current', pid, 'product', 'short_description', link)
        if link.startswith(base) and is_recent(row.get('date_modified_gmt')):
            recent_urls.add(link)
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(rows) < 100:
        break

for page in range(1, 21):
    code, rows, headers = api_get('/wp-json/wc/v3/products/categories', {
        'per_page': 100, 'page': page, 'orderby': 'id', 'order': 'asc',
        '_fields': 'id,slug,description,image',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        raise SystemExit(f'Woo category delta scan failed http={code}')
    if not rows:
        break
    for row in rows:
        coverage['categories_read'] += 1
        tid = int(row.get('id') or 0)
        slug = str(row.get('slug') or '')
        image = row.get('image') or {}
        add_ref(image.get('id') or 0, 'woo_category_image_current', tid, 'product_cat', 'image', slug)
        aid = resolve_url(image.get('src') or '')
        if aid:
            add_ref(aid, 'woo_category_image_url_current', tid, 'product_cat', 'image', slug)
        scan_text(str(row.get('description') or ''), 'woo_category_description_current', tid, 'product_cat', 'description', slug)
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(rows) < 100:
        break

code, families, _ = api_get('/wp-json/wp/v2/font-families', {'per_page': 100, 'context': 'edit'})
if code in (401, 403):
    code, families, _ = api_get('/wp-json/wp/v2/font-families', {'per_page': 100, 'context': 'view'})
if 200 <= code < 300 and isinstance(families, list):
    for family in families:
        fid = int(family.get('id') or 0)
        fcode, faces, _ = api_get(f'/wp-json/wp/v2/font-families/{fid}/font-faces', {'per_page': 100, 'context': 'edit'})
        if fcode in (401, 403):
            fcode, faces, _ = api_get(f'/wp-json/wp/v2/font-families/{fid}/font-faces', {'per_page': 100, 'context': 'view'})
        if not (200 <= fcode < 300) or not isinstance(faces, list):
            raise SystemExit(f'font face delta scan failed family={fid} http={fcode}')
        for face in faces:
            coverage['font_faces_read'] += 1
            scan_json(face, 'wp_font_face_current', 'wp_font_face', f'family:{fid}')
elif code not in (404,):
    raise SystemExit(f'font family delta scan failed http={code}')

code, themes, _ = api_get('/wp-json/wp/v2/themes', {'status': 'active', 'context': 'edit', '_fields': 'stylesheet'})
if code in (401, 403):
    code, themes, _ = api_get('/wp-json/wp/v2/themes', {'status': 'active', 'context': 'view', '_fields': 'stylesheet'})
if 200 <= code < 300 and isinstance(themes, list):
    for theme in themes:
        stylesheet = str(theme.get('stylesheet') or '').strip()
        if not stylesheet:
            continue
        route = f"/wp-json/wp/v2/global-styles/themes/{urllib.parse.quote(stylesheet, safe='/')}"
        scode, style, _ = api_get(route, {'context': 'edit'})
        if scode in (401, 403):
            scode, style, _ = api_get(route, {'context': 'view'})
        if not (200 <= scode < 300) or not isinstance(style, dict):
            raise SystemExit(f'global styles delta scan failed theme={stylesheet} http={scode}')
        coverage['global_styles_read'] += 1
        scan_json(style, 'wp_global_styles_current', 'wp_global_styles', route)
elif code not in (404,):
    raise SystemExit(f'active theme delta scan failed http={code}')


def parse_sitemap(url):
    status, raw, _ = request_bytes(url)
    if not (200 <= status < 300) or not raw:
        return False, [], []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return False, [], []
    local = lambda tag: str(tag).rsplit('}', 1)[-1].lower()
    if local(root.tag) == 'sitemapindex':
        nested = []
        for sm in root:
            if local(sm.tag) != 'sitemap':
                continue
            loc = ''; lastmod = ''
            for node in sm:
                if local(node.tag) == 'loc': loc = (node.text or '').strip()
                elif local(node.tag) == 'lastmod': lastmod = (node.text or '').strip()
            if loc: nested.append((loc, lastmod))
        return True, nested, []
    if local(root.tag) == 'urlset':
        urls = []
        for entry in root:
            if local(entry.tag) != 'url':
                continue
            loc = ''; lastmod = ''
            for node in entry:
                if local(node.tag) == 'loc': loc = (node.text or '').strip()
                elif local(node.tag) == 'lastmod': lastmod = (node.text or '').strip()
            if loc: urls.append((loc, lastmod))
        return True, [], urls
    return False, [], []

queue = [base + '/wp-sitemap.xml', base + '/sitemap_index.xml']
seen = set(); sitemap_ok = 0; sitemap_failures = []
while queue and len(seen) < 100:
    sm = queue.pop(0)
    if sm in seen:
        continue
    seen.add(sm)
    ok, nested, urls = parse_sitemap(sm)
    if not ok:
        sitemap_failures.append(sm)
        continue
    sitemap_ok += 1
    for child, _ in nested:
        if child.startswith(base) and child not in seen:
            queue.append(child)
    for loc, lastmod in urls:
        if not loc.startswith(base):
            continue
        lm = parse_iso(lastmod)
        if lm is not None and lm >= baseline:
            recent_urls.add(loc)
coverage['sitemaps_read'] = sitemap_ok
coverage['sitemap_failures'] = len(sitemap_failures)
if sitemap_ok <= 0 or sitemap_failures:
    raise SystemExit(f'Sitemap delta coverage incomplete read={sitemap_ok} failures={len(sitemap_failures)}')

coverage['delta_urls_selected'] = len(recent_urls)

def crawl(url):
    code, html, _ = public_get(url)
    return url, code, html

with ThreadPoolExecutor(max_workers=10) as pool:
    futures = [pool.submit(crawl, url) for url in sorted(recent_urls)]
    for future in as_completed(futures):
        url, code, html = future.result()
        if not (200 <= code < 300) or not html:
            coverage['delta_pages_failed'] += 1
            raise SystemExit(f'Delta rendered page failed url={url} http={code}')
        coverage['delta_pages_read'] += 1
        scan_text(html, 'rendered_delta_current', 0, 'public_url', 'html', url)

referenced_ids = sorted(aid for aid, rr in refs.items() if rr)
zero_ref_ids = sorted(aid for aid, rr in refs.items() if not rr)
manifest = {
    'action': 'media.targeted_reference_delta',
    'generated_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'read_only': True,
    'deletion_authorized': False,
    'source_predelete_executed_at_utc': pre.get('executed_at_utc'),
    'source_sitewide_baseline_utc': site_summary.get('executed_at_utc'),
    'target_count': len(targets),
    'protected_ids': sorted(protected),
    'zero_ref_count': len(zero_ref_ids),
    'referenced_count': len(referenced_ids),
    'zero_ref_ids': zero_ref_ids,
    'referenced_ids': referenced_ids,
    'references': {str(aid): refs[aid] for aid in referenced_ids},
    'coverage': coverage,
    'note': 'Targeted fresh reference delta only. It does not rebuild the media inventory. Current REST content/product/category/global surfaces are matched only against the 25 pre-delete candidates; rendered crawling is limited to sitemap URLs changed since the accepted complete sitewide snapshot plus recently modified REST objects. No media was deleted by this step.'
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'target_count': len(targets), 'zero_ref_count': len(zero_ref_ids),
    'referenced_count': len(referenced_ids), 'delta_urls_selected': coverage['delta_urls_selected'],
    'delta_pages_read': coverage['delta_pages_read'], 'protected_ids': sorted(protected),
}, ensure_ascii=False))
