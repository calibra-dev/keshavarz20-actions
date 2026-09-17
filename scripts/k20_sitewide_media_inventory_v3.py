import base64
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OUT = ROOT / 'sitewide-media-results' / 'inventory.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(
    f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()
).decode()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%'), p.query, p.fragment))


def api_get(path, params=None, timeout=90):
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(qurl(url), headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Sitewide-Media-Inventory/3.1',
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
    except Exception as e:
        return 0, {'error': type(e).__name__}, {}


def request_bytes(url, timeout=25):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Sitewide-Media-Inventory/3.1'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read(), dict(r.headers)
    except Exception:
        return 0, b'', {}


def norm_id(value):
    if isinstance(value, dict):
        value = value.get('attachment_id') or value.get('id') or 0
    try:
        return int(value or 0)
    except Exception:
        return 0


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


# 1) Media library.
media = {}
by_key = {}
by_canonical = {}
media_pages = 0
for page in range(1, 101):
    code, rows, headers = api_get('/wp-json/wp/v2/media', {
        'per_page': 100,
        'page': page,
        'media_type': 'image',
        '_fields': 'id,post,source_url,mime_type,alt_text',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        raise SystemExit(f'media inventory failed page={page} http={code}')
    if not rows:
        break
    media_pages += 1
    for row in rows:
        aid = norm_id(row.get('id'))
        url = str(row.get('source_url') or '')
        fmt = image_format(url)
        if aid <= 0 or fmt not in ('jpeg', 'png', 'webp'):
            continue
        key = upload_key(url)
        media[aid] = {
            'attachment_id': aid,
            'parent': norm_id(row.get('post')),
            'url': url,
            'upload_key': key,
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
    aid = norm_id(aid)
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


def scan_text(text, kind, object_id, object_type, field, locator='', scan_numeric_ids=True):
    if not isinstance(text, str) or not text:
        return
    for match in re.finditer(r'wp-image-(\d+)', text, flags=re.I):
        add_ref(match.group(1), kind, object_id, object_type, field, locator)
    pattern = r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)'
    for match in re.finditer(pattern, text, flags=re.I):
        aid = resolve_url(match.group(0))
        if aid:
            add_ref(aid, kind, object_id, object_type, field, locator)
    if scan_numeric_ids:
        id_pattern = r'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?(\d{3,})'
        for match in re.finditer(id_pattern, text):
            add_ref(match.group(1), kind, object_id, object_type, field, locator)


def scan_json_resource(value, kind, object_type, locator=''):
    if value is None:
        return
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        text = str(value)
    # Nested resource objects use generic IDs for their own records. Only URL/class
    # image evidence is authoritative here; do not reinterpret arbitrary record IDs
    # as media attachment IDs.
    scan_text(text, kind, 0, object_type, 'json', locator, scan_numeric_ids=False)


def scan_post(row, type_name):
    pid = norm_id(row.get('id'))
    link = str(row.get('link') or '')
    add_ref(row.get('featured_media'), 'featured_image', pid, type_name, 'featured_media', link)
    content = row.get('content') or {}
    if isinstance(content, dict):
        scan_text(str(content.get('raw') or ''), 'post_content_raw', pid, type_name, 'content', link)
        scan_text(str(content.get('rendered') or ''), 'post_content_rendered', pid, type_name, 'content', link)
    meta = row.get('meta') or {}
    if isinstance(meta, dict):
        for key, value in meta.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            scan_text(str(value or ''), 'rest_meta', pid, type_name, str(key), link)


def enumerate_ids(route, context):
    ids = []
    for page in range(1, 101):
        params = {'per_page': 100, 'page': page, 'context': context, '_fields': 'id'}
        if context == 'edit':
            params['status'] = 'any'
        code, rows, headers = api_get(route, params)
        if code == 400 and page > 1:
            break
        if not (200 <= code < 300) or not isinstance(rows, list):
            return [], f'index_http={code}'
        ids.extend(norm_id(x.get('id')) for x in rows if norm_id(x.get('id')) > 0)
        total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
        if (total_pages and page >= total_pages) or len(rows) < 100:
            break
    return ids, None


def scan_post_type(type_name, route):
    seen = 0
    context = 'edit'
    bulk_error = None
    for page in range(1, 101):
        params = {
            'per_page': 100,
            'page': page,
            'context': context,
            'status': 'any',
            '_fields': 'id,type,status,featured_media,content,meta,link',
        }
        code, rows, headers = api_get(route, params)
        if code in (401, 403, 404) and page == 1:
            context = 'view'
            params['context'] = 'view'
            params.pop('status', None)
            code, rows, headers = api_get(route, params)
        if code == 400 and page > 1:
            break
        if not (200 <= code < 300) or not isinstance(rows, list):
            bulk_error = f'bulk_http={code}'
            break
        for row in rows:
            scan_post(row, type_name)
            seen += 1
        total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
        if (total_pages and page >= total_pages) or len(rows) < 100:
            return {'posts_read': seen, 'error': None, 'context': context, 'route': route, 'fallback': False}

    ids, index_error = enumerate_ids(route, context)
    if index_error:
        return {'posts_read': seen, 'error': bulk_error + ';' + index_error, 'context': context, 'route': route, 'fallback': True}
    seen = 0
    failures = []
    for pid in ids:
        params = {'context': context, '_fields': 'id,type,status,featured_media,content,meta,link'}
        code, row, _ = api_get(f'{route}/{pid}', params)
        if not (200 <= code < 300) or not isinstance(row, dict):
            failures.append({'id': pid, 'http': code})
            continue
        scan_post(row, type_name)
        seen += 1
    error = None if not failures and seen == len(ids) else f'individual_failures={len(failures)} expected={len(ids)} read={seen}'
    return {
        'posts_read': seen,
        'expected_posts': len(ids),
        'error': error,
        'context': context,
        'route': route,
        'fallback': True,
        'failure_sample': failures[:10],
    }


def scan_font_faces():
    context = 'edit'
    code, families, _ = api_get('/wp-json/wp/v2/font-families', {
        'per_page': 100,
        'context': context,
        '_fields': 'id',
    })
    if code in (401, 403):
        context = 'view'
        code, families, _ = api_get('/wp-json/wp/v2/font-families', {
            'per_page': 100,
            'context': context,
            '_fields': 'id',
        })
    if not (200 <= code < 300) or not isinstance(families, list):
        return {
            'posts_read': 0,
            'error': f'font_family_index_http={code}',
            'context': context,
            'route': '/wp-json/wp/v2/font-families/{id}/font-faces',
            'fallback': False,
        }
    seen = 0
    failures = []
    for family in families:
        family_id = norm_id(family.get('id'))
        if family_id <= 0:
            continue
        route = f'/wp-json/wp/v2/font-families/{family_id}/font-faces'
        code, faces, _ = api_get(route, {'per_page': 100, 'context': context})
        if not (200 <= code < 300) or not isinstance(faces, list):
            failures.append({'family_id': family_id, 'http': code})
            continue
        for face in faces:
            seen += 1
            scan_json_resource(face, 'wp_font_face_resource', 'wp_font_face', route)
    return {
        'posts_read': seen,
        'font_families_read': len(families),
        'error': None if not failures else f'font_face_failures={len(failures)}',
        'context': context,
        'route': '/wp-json/wp/v2/font-families/{id}/font-faces',
        'fallback': False,
        'failure_sample': failures[:10],
    }


def scan_global_styles():
    context = 'edit'
    code, themes, _ = api_get('/wp-json/wp/v2/themes', {
        'status': 'active',
        'context': context,
        '_fields': 'stylesheet',
    })
    if code in (401, 403):
        context = 'view'
        code, themes, _ = api_get('/wp-json/wp/v2/themes', {
            'status': 'active',
            'context': context,
            '_fields': 'stylesheet',
        })
    if not (200 <= code < 300) or not isinstance(themes, list):
        return {
            'posts_read': 0,
            'error': f'active_theme_index_http={code}',
            'context': context,
            'route': '/wp-json/wp/v2/global-styles/themes/{stylesheet}',
            'fallback': False,
        }
    seen = 0
    failures = []
    for theme in themes:
        stylesheet = str(theme.get('stylesheet') or '').strip()
        if not stylesheet:
            continue
        encoded = urllib.parse.quote(stylesheet, safe='/')
        route = f'/wp-json/wp/v2/global-styles/themes/{encoded}'
        code, style, _ = api_get(route, {'context': context})
        if not (200 <= code < 300) or not isinstance(style, dict):
            failures.append({'stylesheet': stylesheet, 'surface': 'theme', 'http': code})
            continue
        seen += 1
        scan_json_resource(style, 'wp_global_styles_theme', 'wp_global_styles', route)
        style_id = norm_id(style.get('id'))
        if style_id > 0:
            item_route = f'/wp-json/wp/v2/global-styles/{style_id}'
            item_code, item, _ = api_get(item_route, {'context': context})
            if 200 <= item_code < 300 and isinstance(item, dict):
                scan_json_resource(item, 'wp_global_styles_item', 'wp_global_styles', item_route)
            else:
                failures.append({'stylesheet': stylesheet, 'surface': 'item', 'id': style_id, 'http': item_code})
        variations_route = f'/wp-json/wp/v2/global-styles/themes/{encoded}/variations'
        variations_code, variations, _ = api_get(variations_route, {'context': context})
        if 200 <= variations_code < 300 and isinstance(variations, list):
            scan_json_resource(variations, 'wp_global_styles_variations', 'wp_global_styles', variations_route)
        else:
            failures.append({'stylesheet': stylesheet, 'surface': 'variations', 'http': variations_code})
    return {
        'posts_read': seen,
        'active_themes_read': len(themes),
        'error': None if not failures else f'global_styles_failures={len(failures)}',
        'context': context,
        'route': '/wp-json/wp/v2/global-styles/themes/{stylesheet}',
        'fallback': False,
        'failure_sample': failures[:10],
    }


# 2) All REST-visible post types. Parameterized/nested WordPress resources are
# scanned through their real routes discovered from the live REST index.
post_type_stats = {}
code, types, _ = api_get('/wp-json/wp/v2/types', {'context': 'view'})
if not (200 <= code < 300) or not isinstance(types, dict):
    raise SystemExit(f'post type discovery failed http={code}')
for type_name, info in sorted(types.items()):
    if type_name in {'attachment', 'nav_menu_item', 'wp_block', 'wp_template', 'wp_template_part', 'wp_font_face', 'wp_global_styles'}:
        continue
    if not isinstance(info, dict):
        continue
    rest_base = str(info.get('rest_base') or '').strip('/')
    namespace = str(info.get('rest_namespace') or 'wp/v2').strip('/')
    if not rest_base:
        continue
    post_type_stats[type_name] = scan_post_type(type_name, f'/wp-json/{namespace}/{rest_base}')
post_type_stats['wp_font_face'] = scan_font_faces()
post_type_stats['wp_global_styles'] = scan_global_styles()

# 3) WooCommerce authoritative product image arrays.
product_count = 0
product_error = None
for page in range(1, 51):
    code, rows, headers = api_get('/wp-json/wc/v3/products', {
        'per_page': 100,
        'page': page,
        'status': 'any',
        'orderby': 'id',
        'order': 'asc',
        '_fields': 'id,status,images,permalink',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        product_error = f'http={code}'
        break
    if not rows:
        break
    product_count += len(rows)
    for product in rows:
        pid = norm_id(product.get('id'))
        for pos, image in enumerate(product.get('images') or []):
            add_ref(image.get('id'), 'woo_product_image', pid, 'product', f'images[{pos}]', str(product.get('permalink') or ''))
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(rows) < 100:
        break

# 4) WooCommerce category images.
category_count = 0
category_error = None
for page in range(1, 21):
    code, rows, headers = api_get('/wp-json/wc/v3/products/categories', {
        'per_page': 100,
        'page': page,
        'orderby': 'id',
        'order': 'asc',
        '_fields': 'id,image',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(rows, list):
        category_error = f'http={code}'
        break
    if not rows:
        break
    category_count += len(rows)
    for term in rows:
        add_ref((term.get('image') or {}).get('id'), 'woo_category_image', term.get('id'), 'product_cat', 'image')
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(rows) < 100:
        break

# 5) Public rendered crawl from both WordPress and SEO sitemap roots.
def parse_sitemap(url):
    status, raw, _ = request_bytes(url, timeout=25)
    if not (200 <= status < 300) or not raw:
        return False, [], []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return False, [], []

    def local_name(node):
        return str(node.tag).rsplit('}', 1)[-1].lower()

    root_kind = local_name(root)
    if root_kind == 'sitemapindex':
        locs = []
        for sitemap in root:
            if local_name(sitemap) != 'sitemap':
                continue
            for node in sitemap:
                if local_name(node) == 'loc' and (node.text or '').strip():
                    locs.append((node.text or '').strip())
                    break
        return True, locs, []
    if root_kind == 'urlset':
        locs = []
        for entry in root:
            if local_name(entry) != 'url':
                continue
            for node in entry:
                if local_name(node) == 'loc' and (node.text or '').strip():
                    locs.append((node.text or '').strip())
                    break
        return True, [], locs
    return False, [], []

sitemap_queue = [base + '/wp-sitemap.xml', base + '/sitemap_index.xml']
sitemap_seen = set()
sitemap_failed = []
page_urls = set()
while sitemap_queue and len(sitemap_seen) < 100:
    sm = sitemap_queue.pop(0)
    if sm in sitemap_seen:
        continue
    sitemap_seen.add(sm)
    ok, nested, urls = parse_sitemap(sm)
    if not ok:
        sitemap_failed.append(sm)
        continue
    for child in nested:
        if child.startswith(base) and child not in sitemap_seen and len(sitemap_queue) < 100:
            sitemap_queue.append(child)
    for url in urls:
        if url.startswith(base) and len(page_urls) < 4000:
            page_urls.add(url)


def crawl_one(url):
    status, raw, headers = request_bytes(url, timeout=25)
    ctype = str(headers.get('Content-Type') or headers.get('content-type') or '').lower()
    if not (200 <= status < 300) or 'text/html' not in ctype or not raw:
        return url, status, ''
    return url, status, raw.decode('utf-8', 'replace')

rendered_pages_read = 0
rendered_failures = []
with ThreadPoolExecutor(max_workers=12) as pool:
    futures = {pool.submit(crawl_one, url): url for url in sorted(page_urls)}
    for future in as_completed(futures):
        url, status, html = future.result()
        if not html:
            rendered_failures.append({'url': url, 'http': status})
            continue
        rendered_pages_read += 1
        scan_text(html, 'rendered_page', 0, 'public_url', 'html', url)

items = []
for aid in sorted(media):
    row = media[aid]
    rr = sorted(refs.get(aid, []), key=lambda x: (x['kind'], x['object_type'], x['object_id'], x['field'], x['locator']))
    items.append({**row, 'reference_count': len(rr), 'references': rr})

post_type_errors = {name: info.get('error') for name, info in post_type_stats.items() if info.get('error')}
summary = {
    'executed_at_utc': now_iso(),
    'version': 3,
    'media_pages_read': media_pages,
    'image_attachments': len(items),
    'jpeg': sum(1 for x in items if x['format'] == 'jpeg'),
    'png': sum(1 for x in items if x['format'] == 'png'),
    'webp': sum(1 for x in items if x['format'] == 'webp'),
    'referenced_images': sum(1 for x in items if x['reference_count'] > 0),
    'zero_refs_in_scanned_surfaces': sum(1 for x in items if x['reference_count'] == 0),
    'jpeg_png_referenced': sum(1 for x in items if x['format'] in ('jpeg', 'png') and x['reference_count'] > 0),
    'jpeg_png_zero_refs_in_scanned_surfaces': sum(1 for x in items if x['format'] in ('jpeg', 'png') and x['reference_count'] == 0),
    'products_read': product_count,
    'product_error': product_error,
    'product_categories_read': category_count,
    'category_error': category_error,
    'post_types': post_type_stats,
    'post_type_errors': post_type_errors,
    'sitemaps_read': len(sitemap_seen) - len(sitemap_failed),
    'sitemap_failures': len(sitemap_failed),
    'sitemap_failure_sample': sitemap_failed[:10],
    'public_urls_discovered': len(page_urls),
    'rendered_pages_read': rendered_pages_read,
    'rendered_pages_failed': len(rendered_failures),
    'rendered_failure_sample': rendered_failures[:10],
    'crawl_complete': bool(page_urls) and rendered_pages_read == len(page_urls) and not rendered_failures,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'summary': summary, 'items': items}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
