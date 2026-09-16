import base64
import io
import json
import math
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageChops, ImageOps

ROOT = pathlib.Path('.')
OPS = ROOT / 'content-direct-convert-ops'
SCOPE = ROOT / 'content-media-results' / 'direct-scope.json'
OUTDIR = ROOT / 'content-direct-convert-results'
PROTECTED_IDS = {142597}
MIN_PSNR = 40.0
MIN_LOSSY_SAVING = 15.0
MIN_LOSSLESS_SAVING = 5.0

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


def api(method, url, body=None, raw=None, headers=None, timeout=180):
    h = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Content-Direct-Convert/1.0',
    }
    if headers:
        h.update(headers)
    data = raw
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
        h['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(qurl(url), data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode('utf-8', 'replace')
            try:
                obj = json.loads(text) if text else {}
            except Exception:
                obj = {'raw': text[:500]}
            return int(r.status), obj
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(text)
        except Exception:
            obj = {'raw': text[:500]}
        return int(e.code), obj


def get_bytes(url):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Content-Direct-Convert/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def public_get(url, timeout=120):
    req = urllib.request.Request(qurl(url), headers={
        'User-Agent': 'K20-Content-Direct-Convert/1.0',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read().decode('utf-8', 'replace')
    except Exception:
        return 0, ''


def head(url):
    try:
        req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Content-Direct-Convert/1.0'})
        with urllib.request.urlopen(req, timeout=90) as r:
            return int(r.status), str(r.headers.get('Content-Type') or ''), int(r.headers.get('Content-Length') or 0)
    except Exception:
        return 0, '', 0


def clear_elementor_cache():
    return api('DELETE', base + '/wp-json/elementor/v1/cache', timeout=180)


def flat(image):
    if 'A' in image.getbands():
        rgba = image.convert('RGBA')
        bg = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        return bg.convert('RGB')
    return image.convert('RGB')


def psnr(a, b):
    aa = flat(a)
    bb = flat(b)
    hist = ImageChops.difference(aa, bb).histogram()
    square_error = sum(count * ((i % 256) ** 2) for i, count in enumerate(hist))
    mse = square_error / float(aa.size[0] * aa.size[1] * 3)
    return 99.0 if mse <= 0 else 20 * math.log10(255 / math.sqrt(mse))


def encode(raw, mime):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    src.load()
    width, height = src.size

    def lossless():
        buf = io.BytesIO()
        kwargs = {'format': 'WEBP', 'lossless': True, 'method': 6}
        if src.info.get('icc_profile'):
            kwargs['icc_profile'] = src.info['icc_profile']
        if src.info.get('exif'):
            kwargs['exif'] = src.info['exif']
        src.save(buf, **kwargs)
        data = buf.getvalue()
        decoded = Image.open(io.BytesIO(data)); decoded.load()
        exact = ImageChops.difference(src.convert('RGBA'), decoded.convert('RGBA')).getbbox() is None
        saving = round((1 - len(data) / float(len(raw))) * 100, 2)
        return data, exact, saving

    if mime == 'image/png':
        data, exact, saving = lossless()
        if exact and saving >= MIN_LOSSLESS_SAVING:
            return data, width, height, 99.0, 'lossless', True, saving
        raise RuntimeError(f'QUALITY_GUARD: PNG exact={exact} saving={saving}')

    for quality in (88, 92, 95):
        buf = io.BytesIO()
        kwargs = {'format': 'WEBP', 'quality': quality, 'method': 6}
        if src.info.get('icc_profile'):
            kwargs['icc_profile'] = src.info['icc_profile']
        if src.info.get('exif'):
            kwargs['exif'] = src.info['exif']
        src.save(buf, **kwargs)
        data = buf.getvalue()
        decoded = Image.open(io.BytesIO(data)); decoded.load()
        score = round(psnr(src, decoded), 2)
        saving = round((1 - len(data) / float(len(raw))) * 100, 2)
        if score >= MIN_PSNR and saving >= MIN_LOSSY_SAVING:
            return data, width, height, score, f'lossy-q{quality}', False, saving

    data, exact, saving = lossless()
    if exact and saving >= MIN_LOSSLESS_SAVING:
        return data, width, height, 99.0, 'lossless-fallback', True, saving
    raise RuntimeError(f'QUALITY_GUARD: no acceptable WebP saving={saving}')


def upload_webp(old_id, data, alt):
    filename = f'k20-direct-a{old_id}.webp'
    code, obj = api(
        'POST', base + '/wp-json/wp/v2/media', raw=data,
        headers={
            'Content-Type': 'image/webp',
            'Content-Disposition': f'attachment; filename="{filename}"',
        },
    )
    if not (200 <= code < 300 and isinstance(obj, dict) and int(obj.get('id') or 0) > 0):
        raise RuntimeError(f'media upload failed http={code}')
    new_id = int(obj['id'])
    new_url = str(obj.get('source_url') or '')
    if alt:
        ac, _ = api('POST', f'{base}/wp-json/wp/v2/media/{new_id}', body={'alt_text': alt})
        if not 200 <= ac < 300:
            api('DELETE', f'{base}/wp-json/wp/v2/media/{new_id}?force=true')
            raise RuntimeError(f'alt update failed http={ac}')
    return new_id, new_url


def delete_media(aid):
    code, _ = api('DELETE', f'{base}/wp-json/wp/v2/media/{aid}?force=true', timeout=120)
    return 200 <= code < 300


def upload_key(url):
    try:
        path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path)
    except Exception:
        return ''
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    return path[pos + len(marker):].lstrip('/') if pos >= 0 else ''


def canonical_key(url_or_key):
    value = str(url_or_key or '')
    key = upload_key(value) if '/wp-content/uploads/' in value else urllib.parse.unquote(value).lstrip('/')
    head, sep, name = key.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot:
        return key
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return head + '/' + clean if sep else clean


UPLOAD_RE = re.compile(
    r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)',
    re.I,
)


def replace_upload_urls(text, old_url, new_url):
    old_canon = canonical_key(old_url)
    count = 0
    def repl(match):
        nonlocal count
        if old_canon and canonical_key(match.group(0)) == old_canon:
            count += 1
            return new_url
        return match.group(0)
    return UPLOAD_RE.sub(repl, text), count


def replace_refs(text, old_id, old_url, new_id, new_url):
    if not isinstance(text, str) or not text:
        return text, 0
    mutations = 0
    old_canon = canonical_key(old_url)
    img_re = re.compile(r'<img\b[^>]*>', re.I)
    def img_repl(match):
        tag = match.group(0)
        hit = f'wp-image-{old_id}' in tag
        if not hit:
            for found in UPLOAD_RE.finditer(tag):
                if canonical_key(found.group(0)) == old_canon:
                    hit = True
                    break
        if hit:
            tag = re.sub(r'\s+srcset=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
            tag = re.sub(r'\s+sizes=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
        return tag
    text = img_re.sub(img_repl, text)

    n = text.count(f'wp-image-{old_id}')
    if n:
        text = text.replace(f'wp-image-{old_id}', f'wp-image-{new_id}')
        mutations += n
    text, n = replace_upload_urls(text, old_url, new_url)
    mutations += n
    pattern = re.compile(rf'((?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?){old_id}(["\']?)', re.I)
    text, n = pattern.subn(rf'\g<1>{new_id}\2', text)
    mutations += n
    return text, mutations


def has_old_ref(text, old_id, old_url):
    if not isinstance(text, str) or not text:
        return False
    if f'wp-image-{old_id}' in text:
        return True
    if re.search(rf'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?{old_id}\b', text):
        return True
    old_canon = canonical_key(old_url)
    for match in UPLOAD_RE.finditer(text):
        if old_canon and canonical_key(match.group(0)) == old_canon:
            return True
    return False


def get_media(aid):
    return api('GET', f'{base}/wp-json/wp/v2/media/{aid}?context=edit&_fields=id,parent,source_url,mime_type,media_details,alt_text')


def discover_routes():
    code, types = api('GET', base + '/wp-json/wp/v2/types?context=view')
    if not (200 <= code < 300 and isinstance(types, dict)):
        raise RuntimeError(f'post type discovery failed http={code}')
    routes = {}
    for name, info in types.items():
        if not isinstance(info, dict):
            continue
        rb = str(info.get('rest_base') or '').strip('/')
        ns = str(info.get('rest_namespace') or 'wp/v2').strip('/')
        if rb:
            routes[str(name)] = f'{base}/wp-json/{ns}/{rb}'
    return routes


def changed_request():
    for cmd in (
        ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD', '--', 'content-direct-convert-ops'],
        ['git', 'show', '--pretty=', '--name-only', 'HEAD', '--', 'content-direct-convert-ops'],
    ):
        try:
            paths = [x.strip() for x in subprocess.check_output(cmd, text=True).splitlines() if x.strip().startswith('content-direct-convert-ops/') and x.strip().endswith('.json')]
        except Exception:
            paths = []
        if paths:
            if len(paths) != 1:
                raise SystemExit(f'Expected exactly one request, found {len(paths)}')
            return pathlib.Path(paths[0])
    raise SystemExit('No changed direct conversion request found')


scope = json.loads(SCOPE.read_text(encoding='utf-8'))
items = {int(x.get('attachment_id') or 0): x for x in (scope.get('items') or [])}
object_rows = {str(x.get('key') or ''): x for x in (scope.get('objects') or [])}
routes = discover_routes()
request_path = changed_request()
request = json.loads(request_path.read_text(encoding='utf-8'))
if request.get('action') != 'content_media.direct_convert':
    raise SystemExit('Unsupported action')
ids = []
for raw in (request.get('attachment_ids') or []):
    aid = int(raw)
    if aid > 0 and aid not in ids:
        ids.append(aid)
if not (1 <= len(ids) <= 10):
    raise SystemExit('attachment_ids must contain 1..10 unique positive IDs')
if any(aid in PROTECTED_IDS for aid in ids):
    raise SystemExit('request includes protected attachment')

batch_result = {
    'executed_at_utc': now_iso(),
    'action': request.get('action'),
    'request_file': request_path.name,
    'requested_ids': ids,
    'items': [],
}
critical_failure = False

for old_id in ids:
    item_result = {
        'old_attachment_id': old_id,
        'success': False,
        'stage': 'start',
        'objects': [],
    }
    item = items.get(old_id)
    uploaded_id = 0
    backups = []
    wrote_any = False
    cache_cleared = False
    try:
        if not item:
            raise RuntimeError('attachment absent from direct scope')
        if str(item.get('mapping_status') or '') not in ('none', 'ambiguous'):
            raise RuntimeError('attachment already has a unique replacement; use reuse workflow')
        refs = item.get('direct_references') or []
        groups = {}
        for ref in refs:
            otype = str(ref.get('object_type') or '')
            oid = int(ref.get('object_id') or 0)
            if otype not in ('page', 'post') or oid <= 0:
                raise RuntimeError(f'unsupported direct object {otype}:{oid}')
            key = f'{otype}:{oid}'
            group = groups.setdefault(key, {'object_type': otype, 'object_id': oid, 'fields': set(), 'locator': str(ref.get('locator') or '')})
            group['fields'].add(str(ref.get('field') or ''))
        if not groups:
            raise RuntimeError('no supported direct reference groups')
        for group in groups.values():
            unsupported = group['fields'] - {'content', '_elementor_data'}
            if unsupported:
                raise RuntimeError('unsupported writable fields: ' + ','.join(sorted(unsupported)))

        old_code, old_media = get_media(old_id)
        if not (200 <= old_code < 300 and isinstance(old_media, dict)):
            raise RuntimeError(f'old media read failed http={old_code}')
        old_url = str(old_media.get('source_url') or '')
        mime = str(old_media.get('mime_type') or '').lower()
        alt = str(old_media.get('alt_text') or '')
        if mime not in ('image/jpeg', 'image/png') or not old_url:
            raise RuntimeError(f'unsupported source mime/url {mime}')
        raw = get_bytes(old_url)
        try:
            webp, width, height, score, mode, exact, saving = encode(raw, mime)
        except RuntimeError as quality_error:
            if str(quality_error).startswith('QUALITY_GUARD:'):
                item_result.update({'stage': 'quality_guard', 'terminal': True, 'error': str(quality_error)})
                batch_result['items'].append(item_result)
                continue
            raise

        new_id, new_url = upload_webp(old_id, webp, alt)
        uploaded_id = new_id
        new_code, new_media = get_media(new_id)
        details = (new_media or {}).get('media_details') or {}
        if not (
            200 <= new_code < 300
            and str((new_media or {}).get('mime_type') or '').lower() == 'image/webp'
            and int(details.get('width') or 0) == width
            and int(details.get('height') or 0) == height
        ):
            raise RuntimeError('new media verification failed')
        hs, hct, hbytes = head(new_url)
        if not (200 <= hs < 400 and 'image/webp' in hct.lower()):
            raise RuntimeError('new media public HEAD failed')

        # Pre-read all referenced objects before any write.
        prepared = []
        for key, group in sorted(groups.items()):
            route = routes.get(group['object_type'])
            if not route:
                raise RuntimeError(f'no REST route for {group["object_type"]}')
            code, obj = api('GET', f'{route}/{group["object_id"]}?context=edit&_fields=id,status,link,content,meta')
            if not (200 <= code < 300 and isinstance(obj, dict) and str(obj.get('status') or '') == 'publish'):
                raise RuntimeError(f'object precondition failed {key} http={code}')
            raw_content = (obj.get('content') or {}).get('raw') if isinstance(obj.get('content'), dict) else ''
            meta = obj.get('meta') or {}
            if not isinstance(raw_content, str) or not isinstance(meta, dict):
                raise RuntimeError(f'object fields invalid {key}')
            elem = meta.get('_elementor_data') if isinstance(meta.get('_elementor_data'), str) else ''
            if '_elementor_data' in group['fields'] and not elem:
                raise RuntimeError(f'Elementor data missing {key}')
            if not (has_old_ref(raw_content, old_id, old_url) or has_old_ref(elem, old_id, old_url)):
                raise RuntimeError(f'live object no longer contains old reference {key}')
            new_raw, raw_mut = replace_refs(raw_content, old_id, old_url, new_id, new_url)
            new_elem, meta_mut = replace_refs(elem, old_id, old_url, new_id, new_url) if elem else (elem, 0)
            if raw_mut + meta_mut <= 0:
                raise RuntimeError(f'no deterministic mutation for {key}')
            if '_elementor_data' in group['fields']:
                json.loads(new_elem)
            rendered_ids = set(int(x) for x in ((object_rows.get(key) or {}).get('rendered_attachment_ids') or []))
            prepared.append({
                'key': key,
                'route': route,
                'object_type': group['object_type'],
                'object_id': group['object_id'],
                'link': str(obj.get('link') or group.get('locator') or ''),
                'fields': sorted(group['fields']),
                'rendered_expected': old_id in rendered_ids,
                'old_raw': raw_content,
                'old_elem': elem,
                'new_raw': new_raw,
                'new_elem': new_elem,
                'raw_mutations': raw_mut,
                'meta_mutations': meta_mut,
            })

        for prepared_obj in prepared:
            body = {'content': prepared_obj['new_raw']}
            if '_elementor_data' in prepared_obj['fields']:
                body['meta'] = {'_elementor_data': prepared_obj['new_elem']}
            uc, _ = api('POST', f"{prepared_obj['route']}/{prepared_obj['object_id']}", body)
            if not 200 <= uc < 300:
                raise RuntimeError(f"object update failed {prepared_obj['key']} http={uc}")
            wrote_any = True
            backups.append(prepared_obj)

            rc, rb = api('GET', f"{prepared_obj['route']}/{prepared_obj['object_id']}?context=edit&_fields=id,content,meta")
            rr = (rb.get('content') or {}).get('raw') if isinstance(rb, dict) and isinstance(rb.get('content'), dict) else ''
            rm_obj = rb.get('meta') or {} if isinstance(rb, dict) else {}
            rm = rm_obj.get('_elementor_data') if isinstance(rm_obj, dict) and isinstance(rm_obj.get('_elementor_data'), str) else ''
            if not (200 <= rc < 300 and isinstance(rr, str)):
                raise RuntimeError(f"object readback failed {prepared_obj['key']}")
            if '_elementor_data' in prepared_obj['fields']:
                if not rm:
                    raise RuntimeError(f"Elementor readback missing {prepared_obj['key']}")
                json.loads(rm)
            if has_old_ref(rr, old_id, old_url) or has_old_ref(rm, old_id, old_url):
                raise RuntimeError(f"old reference remained {prepared_obj['key']}")
            if new_url not in rr and new_url not in rm and f'wp-image-{new_id}' not in rr and f'wp-image-{new_id}' not in rm:
                raise RuntimeError(f"new reference missing {prepared_obj['key']}")
            item_result['objects'].append({
                'key': prepared_obj['key'],
                'update_http': uc,
                'raw_mutations': prepared_obj['raw_mutations'],
                'meta_mutations': prepared_obj['meta_mutations'],
                'rendered_expected': prepared_obj['rendered_expected'],
            })

        if any('_elementor_data' in p['fields'] for p in prepared):
            cc, _ = clear_elementor_cache()
            item_result['elementor_cache_delete_http'] = cc
            if not 200 <= cc < 300:
                raise RuntimeError(f'Elementor cache purge failed http={cc}')
            cache_cleared = True

        # Public readback for objects where this attachment was observed rendered.
        for prepared_obj in prepared:
            if not prepared_obj['rendered_expected'] or not prepared_obj['link']:
                continue
            ok = False
            last = {}
            for attempt in range(1, 4):
                verify_url = prepared_obj['link'] + ('&' if '?' in prepared_obj['link'] else '?') + f'k20_direct_convert={int(time.time())}-{attempt}'
                hc, html = public_get(verify_url)
                old_class = html.count(f'wp-image-{old_id}') if hc == 200 else -1
                new_seen = bool(hc == 200 and (new_url in html or f'wp-image-{new_id}' in html))
                last = {'attempt': attempt, 'http': hc, 'old_class_hits': old_class, 'new_seen': new_seen}
                if hc == 200 and old_class == 0 and new_seen:
                    ok = True
                    break
                time.sleep(2)
            if not ok:
                raise RuntimeError(f"public readback failed {prepared_obj['key']}: {last}")

        item_result.update({
            'success': True,
            'stage': 'verified',
            'new_attachment_id': new_id,
            'new_url': new_url,
            'source_url': old_url,
            'source_mime': mime,
            'original_bytes': len(raw),
            'webp_bytes': len(webp),
            'saving_pct': saving,
            'psnr_db': score,
            'encoder_mode': mode,
            'pixel_exact': exact,
            'width': width,
            'height': height,
            'affected_objects': len(prepared),
        })
    except Exception as error:
        item_result['stage'] = 'error'
        item_result['error'] = str(error)
        rollback_ok = True
        if wrote_any:
            for prepared_obj in reversed(backups):
                try:
                    body = {'content': prepared_obj['old_raw']}
                    if '_elementor_data' in prepared_obj['fields']:
                        body['meta'] = {'_elementor_data': prepared_obj['old_elem']}
                    bc, _ = api('POST', f"{prepared_obj['route']}/{prepared_obj['object_id']}", body)
                    if not 200 <= bc < 300:
                        rollback_ok = False
                except Exception:
                    rollback_ok = False
            if rollback_ok and cache_cleared:
                rcc, _ = clear_elementor_cache()
                rollback_ok = 200 <= rcc < 300
        cleanup_ok = True
        if uploaded_id and rollback_ok:
            cleanup_ok = delete_media(uploaded_id)
        item_result['rollback_ok'] = rollback_ok
        item_result['cleanup_uploaded_webp_ok'] = cleanup_ok if uploaded_id else True
        if not rollback_ok or (uploaded_id and rollback_ok and not cleanup_ok):
            critical_failure = True
    batch_result['items'].append(item_result)

batch_result['success_count'] = sum(1 for x in batch_result['items'] if x.get('success'))
batch_result['terminal_quality_count'] = sum(1 for x in batch_result['items'] if x.get('stage') == 'quality_guard')
batch_result['failed_count'] = sum(1 for x in batch_result['items'] if x.get('stage') == 'error')
batch_result['critical_failure'] = critical_failure

OUTDIR.mkdir(parents=True, exist_ok=True)
out_path = OUTDIR / (request_path.stem + '.json')
out_path.write_text(json.dumps(batch_result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'success': batch_result['success_count'],
    'terminal_quality': batch_result['terminal_quality_count'],
    'failed': batch_result['failed_count'],
    'critical_failure': critical_failure,
}, ensure_ascii=False))
if critical_failure or batch_result['failed_count']:
    raise SystemExit(2)
