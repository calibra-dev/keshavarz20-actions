"""GET-only readback of the frozen 2026-09-16 direct-content conversion scope."""
import base64
import hashlib
import html
import io
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageOps

ROOT = pathlib.Path('media-reconciliation/20260916-content-webp75')
manifest = json.loads((ROOT / 'manifest.json').read_text())
assert manifest['read_only'] is True
assert len(manifest['items']) == 75
assert len({r['old_attachment_id'] for r in manifest['items']}) == 75
assert len(manifest['objects']) == 13
base = os.environ['WP_BASE_URL'].rstrip('/')
assert urllib.parse.urlsplit(base).hostname == 'keshavarz20.com'
auth = base64.b64encode((os.environ['WP_USERNAME'] + ':' + os.environ['WP_APP_PASSWORD']).encode()).decode()


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def get(url, authenticated=False):
    parsed = urllib.parse.urlsplit(url)
    assert parsed.scheme == 'https' and parsed.hostname == 'keshavarz20.com'
    if authenticated:
        assert parsed.path.startswith('/wp-json/wp/v2/')
    url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, urllib.parse.quote(urllib.parse.unquote(parsed.path), safe='/%'), parsed.query, ''))
    headers = {'User-Agent': 'K20-WebP75-Readback/1.0', 'Cache-Control': 'no-cache'}
    if authenticated:
        headers.update({'Authorization': 'Basic ' + auth, 'Accept': 'application/json'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method='GET'), timeout=45) as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            status = error.code
            if status < 500 and status != 429:
                return status, b'', {}
        except Exception:
            status = 0
        if attempt == 0:
            time.sleep(1)
    return status, b'', {}


def json_get(path):
    code, raw, _ = get(base + path, authenticated=True)
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    return code, data


def canonical(url):
    path = urllib.parse.unquote(urllib.parse.urlsplit(html.unescape(url)).path)
    return re.sub(r'-(?:\d{2,5}x\d{2,5}|scaled)(?=\.[^.]+$)', '', path)


def refs(text, aid, source):
    text = html.unescape(str(text or '')).replace('\\/', '/')
    urls = re.findall(r'(?:https?:)?//[^\s\"\'<>)]*/wp-content/uploads/[^\s\"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s\"\'<>)]*\.(?:jpe?g|png|webp)', text, re.I)
    matching = sorted({u for u in urls if canonical(u) == canonical(source)})
    classes = len(re.findall(rf'wp-image-{aid}(?!\d)', text))
    ids = len(re.findall(rf'[\"\'](?:id|image_id|attachment_id|thumbnail_id)[\"\']\s*[:=]\s*[\"\']?{aid}(?!\d)', text))
    return {'present': bool(matching or classes or ids), 'url_variants': matching, 'class_hits': classes, 'id_hits': ids}


started = now()
all_items = manifest['items'] + [{'old_attachment_id': r['attachment_id'], 'source_url': r['url'], 'new_attachment_id': None} for r in manifest['protected']]
object_results = []
for target in manifest['objects']:
    typ = target['object_type']
    assert typ in ('page', 'post')
    code, obj = json_get(f'/wp-json/wp/v2/{typ}s/{target["object_id"]}?context=edit&_fields=id,status,content,meta')
    content = obj.get('content') or {}
    meta = obj.get('meta') or {}
    elem = meta.get('_elementor_data') or ''
    try:
        elem_obj = json.loads(elem) if isinstance(elem, str) and elem else elem
        elem_valid = isinstance(elem_obj, (dict, list))
    except Exception:
        elem_valid = False
    public_code, public_raw, _ = get(target['url'])
    separator = '&' if '?' in target['url'] else '?'
    fresh_code, fresh_raw, _ = get(target['url'] + separator + 'k20_webp75_readback=' + str(int(time.time())))
    texts = {'content_raw': str(content.get('raw') or ''), 'elementor_data': elem,
             'content_rendered': str(content.get('rendered') or ''),
             'public_html': public_raw.decode('utf-8', 'replace'),
             'cache_busted_html': fresh_raw.decode('utf-8', 'replace')}
    pairs = []
    for item in all_items:
        old = {name: refs(text, item['old_attachment_id'], item['source_url']) for name, text in texts.items()}
        new = {name: refs(text, item['new_attachment_id'], item['new_url']) for name, text in texts.items()} if item.get('new_attachment_id') else {}
        if any(v['present'] for v in old.values()) or any(v['present'] for v in new.values()):
            pairs.append({'old_attachment_id': item['old_attachment_id'], 'new_attachment_id': item.get('new_attachment_id'), 'old': old, 'new': new})
    object_results.append({'key': target['key'], 'url': target['url'], 'rest_http': code, 'status': obj.get('status'),
                           'elementor_json_valid': elem_valid, 'public_http': public_code, 'cache_busted_http': fresh_code,
                           'content_raw_sha256': hashlib.sha256(texts['content_raw'].encode()).hexdigest(),
                           'elementor_sha256': hashlib.sha256(str(elem).encode()).hexdigest(), 'references': pairs})

media_results = []
media_ids = sorted({r['new_attachment_id'] for r in manifest['items'] if r.get('new_attachment_id')} | set(manifest['diagnostic_original_ids']) | {142597})
for aid in media_ids:
    code, obj = json_get(f'/wp-json/wp/v2/media/{aid}?context=edit&_fields=id,source_url,mime_type,media_details,alt_text')
    details = obj.get('media_details') or {}
    media_results.append({'attachment_id': aid, 'http': code, 'returned_id': obj.get('id'), 'mime_type': obj.get('mime_type'),
                          'source_url': obj.get('source_url'), 'width': details.get('width'), 'height': details.get('height'),
                          'original_image': details.get('original_image'), 'alt_text': obj.get('alt_text')})

source_images = []
for item in manifest['items']:
    if item['old_attachment_id'] not in manifest['diagnostic_original_ids']:
        continue
    code, raw, headers = get(item['source_url'])
    row = {'attachment_id': item['old_attachment_id'], 'url': item['source_url'], 'http': code,
           'content_type': headers.get('Content-Type'), 'bytes': len(raw)}
    if code == 200:
        try:
            im = Image.open(io.BytesIO(raw)); im.load()
            oriented = ImageOps.exif_transpose(im)
            row.update({'decoded_format': im.format, 'stored_size': list(im.size), 'oriented_size': list(oriented.size),
                        'mode': im.mode, 'exif_orientation': im.getexif().get(274), 'sha256': hashlib.sha256(raw).hexdigest()})
        except Exception as error:
            row['decode_error'] = type(error).__name__
    source_images.append(row)

result = {'action': 'content_media.webp75_readback', 'read_only': True, 'writes_performed': 0,
          'started_at_utc': started, 'executed_at_utc': now(), 'source_commit': os.environ.get('GITHUB_SHA'),
          'manifest_sha256': hashlib.sha256((ROOT / 'manifest.json').read_bytes()).hexdigest(),
          'objects': object_results, 'media': media_results, 'original_diagnostics': source_images}
(ROOT / 'live-readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'objects': len(object_results), 'media': len(media_results), 'writes_performed': 0}))
