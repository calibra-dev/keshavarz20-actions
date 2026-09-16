import base64
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import xmlrpc.client
from collections import defaultdict
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
server = xmlrpc.client.ServerProxy(base + '/xmlrpc.php', allow_none=True, use_builtin_types=True)


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def api_get(path, params=None, timeout=180):
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Sitewide-Media-Inventory/1.0',
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


def media_url(item):
    for key in ('link', 'url', 'source_url'):
        value = str(item.get(key) or '').strip()
        if value:
            return value
    meta = item.get('metadata') or {}
    if isinstance(meta, dict):
        for key in ('file', 'url'):
            value = str(meta.get(key) or '').strip()
            if value.startswith('http'):
                return value
    return ''


def upload_key(url):
    if not url:
        return ''
    try:
        p = urllib.parse.urlsplit(url)
        path = urllib.parse.unquote(p.path)
    except Exception:
        path = str(url)
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    if pos < 0:
        return ''
    return path[pos + len(marker):].lstrip('/')


def image_ext(url):
    path = urllib.parse.urlsplit(url).path.lower()
    if path.endswith('.jpg') or path.endswith('.jpeg'):
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

# 1) Media library inventory.
media = {}
media_by_upload_key = {}
offset = 0
while True:
    try:
        batch = server.wp.getMediaLibrary(0, username, password, {'number': 100, 'offset': offset})
    except xmlrpc.client.Fault as e:
        raise SystemExit(f'wp.getMediaLibrary failed at offset={offset}: {e.faultString}')
    if not batch:
        break
    for item in batch:
        aid = norm_id(item.get('attachment_id'))
        url = media_url(item)
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
        }
        media[aid] = row
        if key:
            media_by_upload_key[key] = aid
    offset += len(batch)
    if len(batch) < 100:
        break

image_ids = set(media)
refs = defaultdict(list)


def add_ref(aid, kind, object_id=0, object_type='', field=''):
    aid = norm_id(aid)
    if aid not in image_ids:
        return
    token = {
        'kind': str(kind),
        'object_id': int(object_id or 0),
        'object_type': str(object_type or ''),
        'field': str(field or ''),
    }
    if token not in refs[aid]:
        refs[aid].append(token)


def scan_text(text, kind, object_id, object_type, field):
    if not isinstance(text, str) or not text:
        return
    for match in re.finditer(r'wp-image-(\d+)', text, flags=re.I):
        add_ref(int(match.group(1)), kind, object_id, object_type, field)
    for match in re.finditer(r'/(?:wp-content/)?uploads/([^\s"\'<>?]+\.(?:jpe?g|png|webp))', text, flags=re.I):
        key = urllib.parse.unquote(match.group(1)).lstrip('/')
        aid = media_by_upload_key.get(key)
        if aid:
            add_ref(aid, kind, object_id, object_type, field)
    # JSON/serialized builders commonly store attachment ids next to id/image/attachment keys.
    for match in re.finditer(r'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?(\d{3,})', text):
        add_ref(int(match.group(1)), kind, object_id, object_type, field)

# 2) WordPress post types: featured images, content, and custom fields (Elementor included when exposed by XML-RPC).
post_type_stats = {}
try:
    types = server.wp.getPostTypes(0, username, password, {})
except xmlrpc.client.Fault as e:
    raise SystemExit(f'wp.getPostTypes failed: {e.faultString}')

skip_types = {'attachment', 'revision', 'nav_menu_item'}
for post_type in sorted(types):
    if post_type in skip_types:
        continue
    offset = 0
    seen = 0
    failed = None
    while True:
        flt = {'post_type': post_type, 'post_status': 'any', 'number': 100, 'offset': offset}
        fields = ['post_id', 'post_type', 'post_status', 'post_content', 'post_thumbnail', 'custom_fields']
        try:
            posts = server.wp.getPosts(0, username, password, flt, fields)
        except xmlrpc.client.Fault as e:
            failed = e.faultString
            break
        if not posts:
            break
        for post in posts:
            pid = norm_id(post.get('post_id'))
            seen += 1
            add_ref(post.get('post_thumbnail'), 'featured_image', pid, post_type, 'post_thumbnail')
            scan_text(str(post.get('post_content') or ''), 'post_content', pid, post_type, 'post_content')
            for cf in post.get('custom_fields') or []:
                if not isinstance(cf, dict):
                    continue
                key = str(cf.get('key') or '')
                value = cf.get('value')
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                scan_text(str(value or ''), 'custom_field', pid, post_type, key)
        offset += len(posts)
        if len(posts) < 100:
            break
    post_type_stats[post_type] = {'posts_read': seen, 'error': failed}

# 3) WooCommerce product image arrays: authoritative product/gallery references.
product_count = 0
for page in range(1, 51):
    code, data, headers = api_get('/wp-json/wc/v3/products', {
        'per_page': 100,
        'page': page,
        'status': 'any',
        'orderby': 'id',
        'order': 'asc',
        '_fields': 'id,status,images',
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
            add_ref(img.get('id'), 'woo_product_image', pid, 'product', f'images[{pos}]')
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

items = []
for aid in sorted(media):
    m = media[aid]
    r = sorted(refs.get(aid, []), key=lambda x: (x['kind'], x['object_type'], x['object_id'], x['field']))
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
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'summary': summary, 'items': items}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
