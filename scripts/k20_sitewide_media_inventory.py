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
username = os.environ['WP_USERNAME']
password = os.environ['WP_APP_PASSWORD']
auth = base64.b64encode(f'{username}:{password}'.encode()).decode()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def request_bytes(url, timeout=90, auth_header=False):
    headers = {'User-Agent': 'K20-Sitewide-Media-Inventory/2.0'}
    if auth_header:
        headers['Authorization'] = 'Basic ' + auth
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return int(r.status), r.read(), dict(r.headers)


def api_get(path, params=None, timeout=180):
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Sitewide-Media-Inventory/2.0',
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


def upload_key(url):
    if not url:
        return ''
    try:
        path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path)
    except Exception:
        path = str(url)
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    if pos < 0:
        return ''
    return path[pos + len(marker):].lstrip('/')


def canonical_upload_key(key):
    if not key:
        return ''
    path = urllib.parse.unquote(key).lstrip('/')
    head, sep, name = path.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot:
        return path
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return (head + '/' + clean) if sep else clean


def image_ext(url):
    path = urllib.parse.urlsplit(str(url)).path.lower()
    if path.endswith(('.jpg', '.jpeg')):
        return 'jpeg'
    if path.endswith('.png'):
        return 'png'
    if path.endswith('.webp'):
        return 'webp'
    return ''


def norm_id(value):
    if isinstance(value, dict):
        value = value.get('attachment_id') or value.get('id') or 0
    try:
        return int(value or 0)
    except Exception:
        return 0

# 1) Media Library via REST. This avoids XML-RPC media-library methods blocked by the site security layer.
media = {}
media_by_upload_key = {}
media_by_canonical_key = {}
for page in range(1, 101):
    code, data, headers = api_get('/wp-json/wp/v2/media', {
        'per_page': 100,
        'page': page,
        'media_type': 'image',
        '_fields': 'id,parent,source_url,mime_type,alt_text',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(data, list):
        raise SystemExit(f'REST media inventory failed page={page} http={code}')
    if not data:
        break
    for item in data:
        aid = norm_id(item.get('id'))
        url = str(item.get('source_url') or '')
        ext = image_ext(url)
        if aid <= 0 or ext not in ('jpeg', 'png', 'webp'):
            continue
        key = upload_key(url)
        row = {
            'attachment_id': aid,
            'parent': norm_id(item.get('parent')),
            'url': url,
            'upload_key': key,
            'format': ext,
            'alt_text': str(item.get('alt_text') or ''),
        }
        media[aid] = row
        if key:
            media_by_upload_key[key] = aid
            media_by_canonical_key.setdefault(canonical_upload_key(key), aid)
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(data) < 100:
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


def resolve_upload_ref(value):
    key = upload_key(value)
    if not key:
        return 0
    return int(media_by_upload_key.get(key) or media_by_canonical_key.get(canonical_upload_key(key)) or 0)


def scan_text(text, kind, object_id, object_type, field, locator=''):
    if not isinstance(text, str) or not text:
        return
    for match in re.finditer(r'wp-image-(\d+)', text, flags=re.I):
        add_ref(int(match.group(1)), kind, object_id, object_type, field, locator)
    # Find upload URLs/paths, including responsive derivative files.
    for match in re.finditer(r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)', text, flags=re.I):
        aid = resolve_upload_ref(match.group(0))
        if aid:
            add_ref(aid, kind, object_id, object_type, field, locator)
    for match in re.finditer(r'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?(\d{3,})', text):
        add_ref(int(match.group(1)), kind, object_id, object_type, field, locator)

# 2) WordPress REST post types. Scan published/raw content and REST-exposed meta without storing the source text.
post_type_stats = {}
code, types, _ = api_get('/wp-json/wp/v2/types', {'context': 'view'})
if 200 <= code < 300 and isinstance(types, dict):
    for type_name, info in sorted(types.items()):
        if type_name in {'attachment', 'nav_menu_item', 'wp_block', 'wp_template', 'wp_template_part'}:
            continue
        if not isinstance(info, dict):
            continue
        rest_base = str(info.get('rest_base') or '').strip('/')
        namespace = str(info.get('rest_namespace') or 'wp/v2').strip('/')
        if not rest_base:
            continue
        route = f'/wp-json/{namespace}/{rest_base}'
        seen = 0
        failed = None
        context = 'edit'
        for page in range(1, 101):
            params = {
                'per_page': 100,
                'page': page,
                'context': context,
                'status': 'any',
                '_fields': 'id,type,status,featured_media,content,meta,link',
            }
            pcode, posts, headers = api_get(route, params)
            if pcode in (401, 403, 404) and page == 1:
                context = 'view'
                params['context'] = 'view'
                params.pop('status', None)
                pcode, posts, headers = api_get(route, params)
            if pcode == 400 and page > 1:
                break
            if not (200 <= pcode < 300) or not isinstance(posts, list):
                failed = f'http={pcode}'
                break
            if not posts:
                break
            for post in posts:
                pid = norm_id(post.get('id'))
                seen += 1
                add_ref(post.get('featured_media'), 'featured_image', pid, type_name, 'featured_media', str(post.get('link') or ''))
                content = post.get('content') or {}
                if isinstance(content, dict):
                    scan_text(str(content.get('raw') or ''), 'post_content_raw', pid, type_name, 'content', str(post.get('link') or ''))
                    scan_text(str(content.get('rendered') or ''), 'post_content_rendered', pid, type_name, 'content', str(post.get('link') or ''))
                meta = post.get('meta') or {}
                if isinstance(meta, dict):
                    for key, value in meta.items():
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                        scan_text(str(value or ''), 'rest_meta', pid, type_name, str(key), str(post.get('link') or ''))
            total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
            if (total_pages and page >= total_pages) or len(posts) < 100:
                break
        post_type_stats[type_name] = {'posts_read': seen, 'error': failed, 'context': context, 'route': route}

# 3) WooCommerce product arrays: authoritative product/gallery references.
product_count = 0
for page in range(1, 51):
    code, data, headers = api_get('/wp-json/wc/v3/products', {
        'per_page': 100,
        'page': page,
        'status': 'any',
        'orderby': 'id',
        'order': 'asc',
        '_fields': 'id,status,images,permalink',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(data, list):
        break
    if not data:
        break
    product_count += len(data)
    for product in data:
        pid = norm_id(product.get('id'))
        for pos, img in enumerate(product.get('images') or []):
            add_ref(img.get('id'), 'woo_product_image', pid, 'product', f'images[{pos}]', str(product.get('permalink') or ''))
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(data) < 100:
        break

# 4) WooCommerce product category images.
category_count = 0
for page in range(1, 21):
    code, data, headers = api_get('/wp-json/wc/v3/products/categories', {
        'per_page': 100,
        'page': page,
        'orderby': 'id',
        'order': 'asc',
        '_fields': 'id,image',
    })
    if code == 400 and page > 1:
        break
    if not (200 <= code < 300) or not isinstance(data, list):
        break
    if not data:
        break
    category_count += len(data)
    for term in data:
        image = term.get('image') or {}
        add_ref(image.get('id'), 'woo_category_image', term.get('id'), 'product_cat', 'image')
    total_pages = int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0)
    if (total_pages and page >= total_pages) or len(data) < 100:
        break

# 5) Public rendered-page crawl from WordPress/SEO sitemaps. This catches Elementor/theme/options references even when private meta is not REST-exposed.
def parse_sitemap(url):
    try:
        status, raw, _ = request_bytes(url, timeout=90, auth_header=False)
        if not (200 <= status < 300):
            return [], []
        root = ET.fromstring(raw)
        locs = [(node.text or '').strip() for node in root.iter() if node.tag.lower().endswith('loc') and (node.text or '').strip()]
        if root.tag.lower().endswith('sitemapindex'):
            return locs, []
        return [], locs
    except Exception:
        return [], []

sitemap_queue = [base + '/wp-sitemap.xml', base + '/sitemap_index.xml']
sitemap_seen = set()
page_urls = set()
while sitemap_queue and len(sitemap_seen) < 100:
    sm = sitemap_queue.pop(0)
    if sm in sitemap_seen:
        continue
    sitemap_seen.add(sm)
    nested, urls = parse_sitemap(sm)
    for child in nested:
        if child not in sitemap_seen and len(sitemap_queue) < 100:
            sitemap_queue.append(child)
    for url in urls:
        if url.startswith(base) and len(page_urls) < 4000:
            page_urls.add(url)


def crawl_one(url):
    try:
        status, raw, headers = request_bytes(url, timeout=60, auth_header=False)
        ctype = str(headers.get('Content-Type') or headers.get('content-type') or '').lower()
        if not (200 <= status < 300) or 'text/html' not in ctype:
            return url, ''
        return url, raw.decode('utf-8', 'replace')
    except Exception:
        return url, ''

rendered_pages_read = 0
with ThreadPoolExecutor(max_workers=6) as pool:
    futures = {pool.submit(crawl_one, url): url for url in sorted(page_urls)}
    for future in as_completed(futures):
        url, html = future.result()
        if not html:
            continue
        rendered_pages_read += 1
        scan_text(html, 'rendered_page', 0, 'public_url', 'html', url)

items = []
for aid in sorted(media):
    m = media[aid]
    r = sorted(refs.get(aid, []), key=lambda x: (x['kind'], x['object_type'], x['object_id'], x['field'], x['locator']))
    items.append({
        **m,
        'reference_count': len(r),
        'references': r,
    })

summary = {
    'executed_at_utc': now_iso(),
    'image_attachments': len(items),
    'jpeg': sum(1 for x in items if x['format'] == 'jpeg'),
    'png': sum(1 for x in items if x['format'] == 'png'),
    'webp': sum(1 for x in items if x['format'] == 'webp'),
    'referenced_images': sum(1 for x in items if x['reference_count'] > 0),
    'zero_refs_in_scanned_surfaces': sum(1 for x in items if x['reference_count'] == 0),
    'jpeg_png_referenced': sum(1 for x in items if x['format'] in ('jpeg', 'png') and x['reference_count'] > 0),
    'jpeg_png_zero_refs_in_scanned_surfaces': sum(1 for x in items if x['format'] in ('jpeg', 'png') and x['reference_count'] == 0),
    'products_read': product_count,
    'product_categories_read': category_count,
    'post_types': post_type_stats,
    'sitemaps_read': len(sitemap_seen),
    'public_urls_discovered': len(page_urls),
    'rendered_pages_read': rendered_pages_read,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'summary': summary, 'items': items}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
