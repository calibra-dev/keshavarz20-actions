import base64
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OUT = ROOT / 'content-media-results' / 'inventory.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def api_get(path, params=None, timeout=180):
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(qurl(url), headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Content-Media-Inventory/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            try:
                obj = json.loads(raw) if raw else {}
            except Exception:
                obj = {'_non_json_response': True, 'raw': raw[:500]}
            return int(r.status), obj, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:500]}
        return int(e.code), obj, dict(e.headers)


def public_get(url, timeout=60):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Content-Media-Inventory/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ctype = str(r.headers.get('Content-Type') or '').lower()
            return int(r.status), raw.decode('utf-8', 'replace') if 'text/html' in ctype else '', ctype
    except Exception:
        return 0, '', ''


def image_format(url):
    path = urllib.parse.urlsplit(str(url)).path.lower()
    if path.endswith(('.jpg', '.jpeg')):
        return 'jpeg'
    if path.endswith('.png'):
        return 'png'
    if path.endswith('.webp'):
        return 'webp'
    return ''


def upload_key(url):
    try:
        path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path)
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


media = {}
by_key = {}
by_canonical = {}
media_pages = 0
for page in range(1, 101):
    code, rows, headers = api_get('/wp-json/wp/v2/media', {
        'per_page': 100,
        'page': page,
        'media_type': 'image',
        '_fields': 'id,parent,source_url,mime_type,alt_text',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        raise SystemExit(f'media inventory failed page={page} http={code}')
    if not rows:
        break
    media_pages += 1
    for row in rows:
        aid = int(row.get('id') or 0)
        url = str(row.get('source_url') or '')
        fmt = image_format(url)
        if aid <= 0 or fmt not in ('jpeg', 'png', 'webp'):
            continue
        key = upload_key(url)
        media[aid] = {
            'attachment_id': aid,
            'parent': int(row.get('parent') or 0),
            'url': url,
            'format': fmt,
            'alt_text': str(row.get('alt_text') or ''),
        }
        if key:
            by_key[key] = aid
            by_canonical.setdefault(canonical_key(key), aid)
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(rows) < 100:
        break

image_ids = set(media)
refs = defaultdict(list)


def add_ref(aid, kind, object_id=0, object_type='', field='', locator=''):
    try:
        aid = int(aid or 0)
    except Exception:
        return
    if aid not in image_ids:
        return
    token = {
        'kind': str(kind),
        'object_id': int(object_id or 0),
        'object_type': str(object_type or ''),
        'field': str(field or ''),
        'locator': str(locator or ''),
    }
    if token not in refs[aid]:
        refs[aid].append(token)


def resolve_url(value):
    key = upload_key(value)
    if not key:
        return 0
    return int(by_key.get(key) or by_canonical.get(canonical_key(key)) or 0)


def scan_text(text, kind, object_id, object_type, field, locator=''):
    if not isinstance(text, str) or not text:
        return
    for m in re.finditer(r'wp-image-(\d+)', text, flags=re.I):
        add_ref(m.group(1), kind, object_id, object_type, field, locator)
    for m in re.finditer(r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)', text, flags=re.I):
        aid = resolve_url(m.group(0))
        if aid:
            add_ref(aid, kind, object_id, object_type, field, locator)
    for m in re.finditer(r'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?(\d{3,})', text):
        add_ref(m.group(1), kind, object_id, object_type, field, locator)


coverage = {
    'media_pages_read': media_pages,
    'posts_read': 0,
    'pages_read': 0,
    'products_read': 0,
    'categories_read': 0,
    'post_errors': {},
    'public_urls_collected': 0,
    'public_pages_read': 0,
}
public_urls = set()

# Posts and pages: raw/rendered content + REST-exposed meta.
for typ, route in (('post', '/wp-json/wp/v2/posts'), ('page', '/wp-json/wp/v2/pages')):
    seen = 0
    error = None
    for page in range(1, 101):
        params = {
            'per_page': 100, 'page': page, 'context': 'edit', 'status': 'any',
            '_fields': 'id,type,status,featured_media,content,meta,link',
        }
        code, rows, headers = api_get(route, params)
        if code in (401, 403) and page == 1:
            params['context'] = 'view'; params.pop('status', None)
            code, rows, headers = api_get(route, params)
        if code == 400 and page > 1:
            break
        if not (200 <= code < 300) or not isinstance(rows, list):
            error = f'http={code}'
            break
        if not rows:
            break
        for row in rows:
            oid = int(row.get('id') or 0)
            link = str(row.get('link') or '')
            if link.startswith(base):
                public_urls.add(link)
            content = row.get('content') or {}
            if isinstance(content, dict):
                scan_text(str(content.get('raw') or ''), 'post_content_raw', oid, typ, 'content', link)
                scan_text(str(content.get('rendered') or ''), 'post_content_rendered', oid, typ, 'content', link)
            meta = row.get('meta') or {}
            if isinstance(meta, dict):
                for key, value in meta.items():
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                    scan_text(str(value or ''), 'rest_meta', oid, typ, str(key), link)
            seen += 1
        total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
        if (total_pages and page >= total_pages) or len(rows) < 100:
            break
    coverage[f'{typ}s_read'] = seen
    if error:
        coverage['post_errors'][typ] = error

# Woo product descriptions/short descriptions and permalinks.
for page in range(1, 51):
    code, rows, headers = api_get('/wp-json/wc/v3/products', {
        'per_page': 100, 'page': page, 'status': 'any', 'orderby': 'id', 'order': 'asc',
        '_fields': 'id,status,description,short_description,permalink,images',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        coverage['product_error'] = f'http={code}'
        break
    if not rows:
        break
    for row in rows:
        oid = int(row.get('id') or 0)
        link = str(row.get('permalink') or '')
        if link.startswith(base):
            public_urls.add(link)
        scan_text(str(row.get('description') or ''), 'woo_product_description', oid, 'product', 'description', link)
        scan_text(str(row.get('short_description') or ''), 'woo_product_short_description', oid, 'product', 'short_description', link)
    coverage['products_read'] += len(rows)
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(rows) < 100:
        break

# Woo category descriptions. Category URL is not assumed; only direct text scan here.
for page in range(1, 21):
    code, rows, headers = api_get('/wp-json/wc/v3/products/categories', {
        'per_page': 100, 'page': page, 'orderby': 'id', 'order': 'asc',
        '_fields': 'id,name,slug,description,image',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        coverage['category_error'] = f'http={code}'
        break
    if not rows:
        break
    for row in rows:
        oid = int(row.get('id') or 0)
        scan_text(str(row.get('description') or ''), 'woo_category_description', oid, 'product_cat', 'description', str(row.get('slug') or ''))
    coverage['categories_read'] += len(rows)
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(rows) < 100:
        break

# Public render crawl of known post/page/product permalinks; catches Elementor/theme output.
coverage['public_urls_collected'] = len(public_urls)

def crawl(url):
    code, html, _ = public_get(url)
    return url, code, html

with ThreadPoolExecutor(max_workers=6) as pool:
    futures = [pool.submit(crawl, url) for url in sorted(public_urls)]
    for future in as_completed(futures):
        url, code, html = future.result()
        if 200 <= code < 300 and html:
            coverage['public_pages_read'] += 1
            scan_text(html, 'rendered_page', 0, 'public_url', 'html', url)

items = []
for aid, row in sorted(media.items()):
    rr = sorted(refs.get(aid, []), key=lambda x: (x['kind'], x['object_type'], x['object_id'], x['field'], x['locator']))
    if not rr:
        continue
    items.append({**row, 'reference_count': len(rr), 'references': rr})

kind_counts = defaultdict(lambda: {'reference_tokens': 0, 'attachments': set(), 'jpeg_png_attachments': set()})
for item in items:
    aid = int(item['attachment_id']); fmt = item['format']
    for ref in item['references']:
        kind = ref['kind']; k = kind_counts[kind]
        k['reference_tokens'] += 1; k['attachments'].add(aid)
        if fmt in ('jpeg', 'png'):
            k['jpeg_png_attachments'].add(aid)
summary_kinds = {
    kind: {
        'reference_tokens': data['reference_tokens'],
        'distinct_attachments': len(data['attachments']),
        'distinct_jpeg_png_attachments': len(data['jpeg_png_attachments']),
    }
    for kind, data in sorted(kind_counts.items())
}
summary = {
    'executed_at_utc': now_iso(),
    'coverage': coverage,
    'referenced_attachments': len(items),
    'reference_kinds': summary_kinds,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'summary': summary, 'items': items}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
