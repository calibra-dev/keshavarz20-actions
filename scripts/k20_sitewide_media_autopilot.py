import base64
import io
import json
import math
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xmlrpc.client
from datetime import datetime, timezone

from PIL import Image, ImageChops, ImageOps

ROOT = pathlib.Path('.')
CONFIG_PATH = ROOT / 'sitewide-media-autopilot' / 'config.json'
STATE_PATH = ROOT / 'sitewide-media-autopilot' / 'state.json'
INVENTORY_PATH = ROOT / 'sitewide-media-results' / 'inventory.json'
RESULTS_DIR = ROOT / 'sitewide-media-autopilot-results'


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

config = load_json(CONFIG_PATH, {})
if config.get('enabled') is not True:
    print('Sitewide autopilot disabled.')
    raise SystemExit(0)
if not INVENTORY_PATH.exists():
    raise SystemExit('Missing sitewide-media-results/inventory.json')

batch_size = max(1, min(20, int(config.get('batch_size', 8))))
max_attempts = max(1, min(4, int(config.get('max_attempts', 2))))
max_cycles = max(1, min(200, int(config.get('max_cycles', 100))))
quality = max(80, min(95, int(config.get('quality', 88))))
min_psnr = max(36.0, min(50.0, float(config.get('min_psnr', 40.0))))
min_saving_lossy = max(0.0, min(90.0, float(config.get('min_saving_lossy_pct', 15.0))))
min_saving_lossless = max(0.0, min(90.0, float(config.get('min_saving_lossless_pct', 5.0))))

base = os.environ['WP_BASE_URL'].rstrip('/')
username = os.environ['WP_USERNAME']
password = os.environ['WP_APP_PASSWORD']
auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
bridge_url = base + '/wp-json/keshavarz20-ops/v2/execute'
server = xmlrpc.client.ServerProxy(base + '/xmlrpc.php', allow_none=True, use_builtin_types=True)
run_id = str(os.environ.get('GITHUB_RUN_ID') or int(time.time()))

inventory = load_json(INVENTORY_PATH, {'summary': {}, 'items': []})
state = load_json(STATE_PATH, {
    'version': 1,
    'started_at_utc': now_iso(),
    'updated_at_utc': now_iso(),
    'status': 'running',
    'cycles': 0,
    'successful_migrations': 0,
    'lossy_success': 0,
    'lossless_success': 0,
    'processed_attachment_ids': [],
    'retry_counts': {},
    'terminal_skips': {},
    'critical_events': [],
})
for key, default in (
    ('processed_attachment_ids', []),
    ('retry_counts', {}),
    ('terminal_skips', {}),
    ('critical_events', []),
):
    state.setdefault(key, default)
for key in ('cycles', 'successful_migrations', 'lossy_success', 'lossless_success'):
    state.setdefault(key, 0)

if state.get('status') in ('completed', 'halted'):
    print(f"Sitewide autopilot status={state.get('status')}")
    raise SystemExit(0)
if state['cycles'] >= max_cycles:
    state['status'] = 'halted'
    state['halt_reason'] = f'max_cycles reached ({max_cycles})'
    state['updated_at_utc'] = now_iso()
    save_json(STATE_PATH, state)
    raise SystemExit(0)

processed = {int(x) for x in state.get('processed_attachment_ids', [])}


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def api(method, url, body=None, timeout=180):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Sitewide-Media-Autopilot/1.0',
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(qurl(url), data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            return int(r.status), json.loads(raw) if raw else {}, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:800]}
        return int(e.code), obj, dict(e.headers)


def inspect_attachment(aid):
    payload = json.dumps({'mode': 'inspect', 'resource': 'attachment', 'id': int(aid), 'changes': {}}, separators=(',', ':')).encode()
    req = urllib.request.Request(
        bridge_url,
        data=payload,
        method='POST',
        headers={
            'Authorization': 'Basic ' + auth,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            'User-Agent': 'K20-Sitewide-Media-Autopilot/1.0',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return int(r.status), json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:800]}
        return int(e.code), obj


def get_bytes(url):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Sitewide-Media-Autopilot/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def head_url(url):
    req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Sitewide-Media-Autopilot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return {
                'status': int(r.status),
                'bytes': int(r.headers.get('Content-Length') or 0),
                'content_type': str(r.headers.get('Content-Type') or ''),
            }
    except urllib.error.HTTPError as e:
        return {'status': int(e.code), 'bytes': 0, 'content_type': str(e.headers.get('Content-Type') or '')}
    except Exception:
        return {'status': 0, 'bytes': 0, 'content_type': ''}


def flatten_rgb(img):
    if 'A' in img.getbands():
        rgba = img.convert('RGBA')
        bg = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        return bg.convert('RGB')
    return img.convert('RGB')


def psnr(a, b):
    aa = flatten_rgb(a)
    bb = flatten_rgb(b)
    hist = ImageChops.difference(aa, bb).histogram()
    sq = 0.0
    for i, count in enumerate(hist):
        v = i % 256
        sq += count * (v * v)
    mse = sq / float(aa.size[0] * aa.size[1] * 3)
    return 99.0 if mse <= 0 else 20.0 * math.log10(255.0 / math.sqrt(mse))


def encode_lossless(src):
    out = io.BytesIO()
    kwargs = {'format': 'WEBP', 'lossless': True, 'method': 6}
    if src.info.get('icc_profile'):
        kwargs['icc_profile'] = src.info['icc_profile']
    if src.info.get('exif'):
        kwargs['exif'] = src.info['exif']
    src.save(out, **kwargs)
    data = out.getvalue()
    decoded = Image.open(io.BytesIO(data)); decoded.load()
    exact = ImageChops.difference(src.convert('RGBA'), decoded.convert('RGBA')).getbbox() is None
    return data, bool(exact)


def encode_candidate(raw, mime):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); src.load()
    width, height = src.size
    if mime == 'image/png':
        data, exact = encode_lossless(src)
        saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
        if not exact:
            raise RuntimeError('TERMINAL: lossless pixel equality check failed')
        if saving < min_saving_lossless:
            raise RuntimeError(f'TERMINAL: lossless saving {saving}% below minimum {min_saving_lossless}%')
        return data, width, height, 'lossless', 99.0, True, saving
    for q in dict.fromkeys([quality, min(92, quality + 4), min(95, quality + 7)]):
        out = io.BytesIO()
        kwargs = {'format': 'WEBP', 'method': 6, 'quality': int(q)}
        if src.info.get('icc_profile'):
            kwargs['icc_profile'] = src.info['icc_profile']
        if src.info.get('exif'):
            kwargs['exif'] = src.info['exif']
        src.save(out, **kwargs)
        data = out.getvalue()
        decoded = Image.open(io.BytesIO(data)); decoded.load()
        score = round(psnr(src, decoded), 2)
        saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
        if score >= min_psnr and saving >= min_saving_lossy:
            return data, width, height, f'lossy-q{q}', score, False, saving
    data, exact = encode_lossless(src)
    saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
    if exact and saving >= min_saving_lossless:
        return data, width, height, 'lossless-fallback', 99.0, True, saving
    raise RuntimeError('TERMINAL: no WebP candidate met quality and saving guards')


def upload_key(url):
    path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path)
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    return path[pos + len(marker):].lstrip('/') if pos >= 0 else ''


def canonical_key(url_or_key):
    key = upload_key(url_or_key) if '/wp-content/uploads/' in str(url_or_key) else str(url_or_key).lstrip('/')
    head, sep, name = key.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot:
        return key
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return (head + '/' + clean) if sep else clean


def replace_upload_urls(text, old_key, new_url):
    if not text:
        return text
    old_canon = canonical_key(old_key)
    url_re = re.compile(r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png)', re.I)
    def repl(m):
        return new_url if canonical_key(m.group(0)) == old_canon else m.group(0)
    return url_re.sub(repl, text)


def replace_content_refs(content, old_id, old_url, new_id, new_url):
    old_key = upload_key(old_url)
    img_re = re.compile(r'<img\b[^>]*>', re.I)
    def img_repl(m):
        tag = m.group(0)
        if f'wp-image-{old_id}' not in tag and canonical_key(old_key) not in canonical_key(tag):
            if canonical_key(old_key) not in canonical_key(upload_key(tag)):
                return tag
        tag = re.sub(r'\s+srcset=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
        tag = re.sub(r'\s+sizes=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
        tag = tag.replace(f'wp-image-{old_id}', f'wp-image-{new_id}')
        tag = replace_upload_urls(tag, old_key, new_url)
        return tag
    updated = img_re.sub(img_repl, content)
    updated = re.sub(rf'("id"\s*:\s*){old_id}(\b)', rf'\g<1>{new_id}\2', updated)
    updated = re.sub(rf'("attachment_id"\s*:\s*["\']?){old_id}(["\']?)', rf'\g<1>{new_id}\2', updated)
    updated = replace_upload_urls(updated, old_key, new_url)
    return updated


def content_still_has_old(content, old_id, old_url):
    if f'wp-image-{old_id}' in content:
        return True
    if re.search(rf'("id"\s*:\s*){old_id}\b', content):
        return True
    old_canon = canonical_key(upload_key(old_url))
    for match in re.finditer(r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png)', content, flags=re.I):
        if canonical_key(match.group(0)) == old_canon:
            return True
    return False


def type_routes():
    code, data, _ = api('GET', base + '/wp-json/wp/v2/types?context=view')
    routes = {}
    if 200 <= code < 300 and isinstance(data, dict):
        for name, info in data.items():
            if not isinstance(info, dict):
                continue
            rb = str(info.get('rest_base') or '').strip('/')
            ns = str(info.get('rest_namespace') or 'wp/v2').strip('/')
            if rb:
                routes[str(name)] = f'{base}/wp-json/{ns}/{rb}'
    return routes

routes = type_routes()

SUPPORTED = {'featured_image', 'post_content_raw', 'woo_category_image'}
OBSERVATIONAL = {'rendered_page', 'post_content_rendered'}


def classify(item):
    refs = item.get('references') or []
    kinds = {str(r.get('kind') or '') for r in refs}
    if 'woo_product_image' in kinds:
        return False, 'owned_by_product_autopilot'
    unsupported = kinds - SUPPORTED - OBSERVATIONAL
    if unsupported:
        return False, 'unsupported_reference_kinds:' + ','.join(sorted(unsupported))
    supported_refs = [r for r in refs if str(r.get('kind') or '') in SUPPORTED]
    if not supported_refs:
        return False, 'rendered_only_or_no_writable_reference'
    rendered_raw_pairs = {(r.get('object_type'), int(r.get('object_id') or 0)) for r in refs if r.get('kind') == 'post_content_raw'}
    for r in refs:
        if r.get('kind') == 'post_content_rendered':
            key = (r.get('object_type'), int(r.get('object_id') or 0))
            if key not in rendered_raw_pairs:
                return False, 'rendered_content_without_raw_reference'
    return True, ''


def rollback_actions(actions):
    ok = True
    errors = []
    for action in reversed(actions):
        try:
            kind = action['kind']
            if kind == 'post_featured':
                code, _, _ = api('POST', action['url'], {'featured_media': action['old_id']})
                ok = ok and (200 <= code < 300)
            elif kind == 'post_content':
                code, _, _ = api('POST', action['url'], {'content': action['old_content']})
                ok = ok and (200 <= code < 300)
            elif kind == 'woo_category':
                code, _, _ = api('PUT', action['url'], {'image': {'id': action['old_id']}})
                ok = ok and (200 <= code < 300)
        except Exception as e:
            ok = False
            errors.append(str(e))
    return ok, errors


def migrate_one(item):
    old = int(item['attachment_id'])
    refs = [r for r in item.get('references') or [] if r.get('kind') in SUPPORTED]
    row = {'old_attachment_id': old, 'success': False, 'references_to_update': len(refs)}
    new_id = None
    applied = []
    try:
        ic, inspected = inspect_attachment(old)
        before = inspected.get('before') if isinstance(inspected, dict) else None
        if not (200 <= ic < 300 and inspected.get('ok') is True and isinstance(before, dict)):
            raise RuntimeError(f'attachment inspect failed http={ic}')
        mime = str(before.get('mime_type') or '').lower()
        if mime not in ('image/jpeg', 'image/png'):
            raise RuntimeError(f'TERMINAL: unsupported source mime {mime}')
        old_url = str(before.get('url') or item.get('url') or '')
        raw = get_bytes(old_url)
        data, width, height, mode, score, exact, saving = encode_candidate(raw, mime)
        row.update({
            'source_url': old_url,
            'original_bytes': len(raw),
            'webp_bytes_local': len(data),
            'saving_pct': saving,
            'encoder_mode': mode,
            'psnr_db': score,
            'pixel_exact': exact,
            'width': width,
            'height': height,
        })
        upload = server.wp.uploadFile(0, username, password, {
            'name': f'k20-sitewide-a{old}.webp',
            'type': 'image/webp',
            'bits': xmlrpc.client.Binary(data),
            'overwrite': False,
            'post_id': 0,
        })
        new_id = int(upload.get('id') or 0)
        new_url = str(upload.get('url') or '')
        if new_id <= 0 or not new_url:
            raise RuntimeError('WebP upload did not return valid attachment')
        row.update({'new_attachment_id': new_id, 'new_url': new_url})
        nc, ninspect = inspect_attachment(new_id)
        nb = ninspect.get('before') if isinstance(ninspect, dict) else None
        if not (200 <= nc < 300 and ninspect.get('ok') is True and isinstance(nb, dict)):
            raise RuntimeError('new attachment inspect failed')
        if str(nb.get('mime_type') or '').lower() != 'image/webp':
            raise RuntimeError('new attachment is not image/webp')
        if int(nb.get('width') or 0) != width or int(nb.get('height') or 0) != height:
            raise RuntimeError('new WebP dimensions differ')
        hd = head_url(new_url); row['new_head'] = hd
        if not (200 <= hd['status'] < 400 and 'image/webp' in hd['content_type'].lower()):
            raise RuntimeError('new public WebP verification failed')
        alt = str(item.get('alt_text') or '')
        if alt:
            ac, _, _ = api('POST', f'{base}/wp-json/wp/v2/media/{new_id}', {'alt_text': alt}, timeout=120)
            if not (200 <= ac < 300):
                raise RuntimeError(f'new attachment alt update failed http={ac}')

        seen_ref_keys = set()
        for ref in refs:
            kind = str(ref.get('kind') or '')
            oid = int(ref.get('object_id') or 0)
            otype = str(ref.get('object_type') or '')
            key = (kind, oid, otype)
            if key in seen_ref_keys:
                continue
            seen_ref_keys.add(key)
            if kind in ('featured_image', 'post_content_raw'):
                route = routes.get(otype)
                if not route:
                    raise RuntimeError(f'TERMINAL: no REST route for post type {otype}')
                obj_url = f'{route}/{oid}'
                rc, obj, _ = api('GET', obj_url + '?context=edit&_fields=id,featured_media,content')
                if not (200 <= rc < 300):
                    raise RuntimeError(f'post read failed type={otype} id={oid} http={rc}')
                if kind == 'featured_image':
                    current = int(obj.get('featured_media') or 0)
                    if current != old:
                        raise RuntimeError(f'TERMINAL: featured image changed from {old} to {current}')
                    uc, _, _ = api('POST', obj_url, {'featured_media': new_id})
                    if not (200 <= uc < 300):
                        raise RuntimeError(f'featured update failed http={uc}')
                    applied.append({'kind': 'post_featured', 'url': obj_url, 'old_id': old})
                    vc, verify, _ = api('GET', obj_url + '?context=edit&_fields=id,featured_media')
                    if not (200 <= vc < 300 and int(verify.get('featured_media') or 0) == new_id):
                        raise RuntimeError('featured readback failed')
                else:
                    content = obj.get('content') or {}
                    raw_content = str(content.get('raw') or '') if isinstance(content, dict) else ''
                    if not raw_content or not content_still_has_old(raw_content, old, old_url):
                        raise RuntimeError('TERMINAL: raw content no longer contains expected old image')
                    new_content = replace_content_refs(raw_content, old, old_url, new_id, new_url)
                    if new_content == raw_content:
                        raise RuntimeError('TERMINAL: content replacement produced no change')
                    uc, _, _ = api('POST', obj_url, {'content': new_content})
                    if not (200 <= uc < 300):
                        raise RuntimeError(f'content update failed http={uc}')
                    applied.append({'kind': 'post_content', 'url': obj_url, 'old_content': raw_content})
                    vc, verify, _ = api('GET', obj_url + '?context=edit&_fields=id,content')
                    vcontent = verify.get('content') or {} if isinstance(verify, dict) else {}
                    vraw = str(vcontent.get('raw') or '') if isinstance(vcontent, dict) else ''
                    if not (200 <= vc < 300 and vraw and not content_still_has_old(vraw, old, old_url) and new_url in vraw):
                        raise RuntimeError('content readback failed')
            elif kind == 'woo_category_image':
                url = f'{base}/wp-json/wc/v3/products/categories/{oid}'
                rc, obj, _ = api('GET', url + '?_fields=id,image')
                image = obj.get('image') or {} if isinstance(obj, dict) else {}
                if not (200 <= rc < 300 and int(image.get('id') or 0) == old):
                    raise RuntimeError('TERMINAL: category image changed from expected source')
                uc, _, _ = api('PUT', url, {'image': {'id': new_id}})
                if not (200 <= uc < 300):
                    raise RuntimeError(f'category image update failed http={uc}')
                applied.append({'kind': 'woo_category', 'url': url, 'old_id': old})
                vc, verify, _ = api('GET', url + '?_fields=id,image')
                vi = verify.get('image') or {} if isinstance(verify, dict) else {}
                if not (200 <= vc < 300 and int(vi.get('id') or 0) == new_id):
                    raise RuntimeError('category image readback failed')

        row.update({'success': True, 'stage': 'verified', 'updated_reference_groups': len(applied)})
        return row, False
    except Exception as e:
        msg = str(e)
        row.update({'stage': 'error', 'error': msg})
        rollback_ok, rollback_errors = rollback_actions(applied)
        row['rollback_ok'] = rollback_ok
        if rollback_errors:
            row['rollback_errors'] = rollback_errors
        cleanup_ok = True
        if new_id:
            try:
                cleanup_ok = bool(server.wp.deleteFile(0, username, password, new_id))
            except Exception:
                cleanup_ok = False
        row['cleanup_uploaded_webp'] = cleanup_ok
        critical = (not rollback_ok) or (new_id is not None and not cleanup_ok)
        return row, critical

# Classify the current inventory snapshot.
eligible = []
for item in inventory.get('items') or []:
    aid = int(item.get('attachment_id') or 0)
    if aid <= 0 or item.get('format') not in ('jpeg', 'png') or aid in processed:
        continue
    if str(aid) in state.get('terminal_skips', {}):
        continue
    ok, reason = classify(item)
    if ok:
        eligible.append(item)
    else:
        # Only record true unsupported live references. Product-owned images are left to the product autopilot.
        if reason != 'owned_by_product_autopilot' and int(item.get('reference_count') or 0) > 0:
            state['terminal_skips'].setdefault(str(aid), {'reason': reason, 'at_utc': now_iso()})

eligible.sort(key=lambda x: (x.get('format') != 'jpeg', -int(x.get('reference_count') or 0), int(x.get('attachment_id') or 0)))
selected = eligible[:batch_size]

result = {
    'action': 'sitewide_media.autopilot_cycle',
    'run_id': run_id,
    'executed_at_utc': now_iso(),
    'selected': len(selected),
    'items': [],
}
critical_halt = False
for item in selected:
    aid = int(item['attachment_id'])
    row, critical = migrate_one(item)
    result['items'].append(row)
    if row.get('success'):
        processed.add(aid)
        state['successful_migrations'] += 1
        if row.get('pixel_exact'):
            state['lossless_success'] += 1
        else:
            state['lossy_success'] += 1
        state['retry_counts'].pop(str(aid), None)
    else:
        msg = str(row.get('error') or '')
        if msg.startswith('TERMINAL:'):
            state['terminal_skips'][str(aid)] = {'reason': msg, 'at_utc': now_iso()}
        else:
            attempts = int(state['retry_counts'].get(str(aid), 0)) + 1
            state['retry_counts'][str(aid)] = attempts
            if attempts >= max_attempts:
                state['terminal_skips'][str(aid)] = {'reason': f'max_attempts_exhausted:{attempts}', 'last_error': msg, 'at_utc': now_iso()}
        if critical:
            event = {'attachment_id': aid, 'reason': row.get('error'), 'at_utc': now_iso()}
            state['critical_events'].append(event)
            state['status'] = 'halted'
            state['halt_reason'] = 'rollback_or_cleanup_guard_failed'
            critical_halt = True
            break

state['processed_attachment_ids'] = sorted(processed)
state['cycles'] += 1
state['updated_at_utc'] = now_iso()
result['success_count'] = sum(1 for x in result['items'] if x.get('success'))
result['critical_halt'] = critical_halt

# Recompute whether another cycle has actionable candidates from this same inventory snapshot.
remaining_actionable = 0
for item in inventory.get('items') or []:
    aid = int(item.get('attachment_id') or 0)
    if aid <= 0 or item.get('format') not in ('jpeg', 'png') or aid in processed:
        continue
    if str(aid) in state.get('terminal_skips', {}):
        continue
    ok, _ = classify(item)
    if ok:
        remaining_actionable += 1

state['last_cycle'] = {
    'run_id': run_id,
    'selected': len(selected),
    'success': result['success_count'],
    'remaining_actionable_from_snapshot': remaining_actionable,
    'at_utc': now_iso(),
}
if not critical_halt and remaining_actionable == 0:
    state['status'] = 'completed'
    state['completed_at_utc'] = now_iso()

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
save_json(RESULTS_DIR / f'{run_id}.json', result)
save_json(STATE_PATH, state)
print(json.dumps({'state': state['status'], 'selected': len(selected), 'success': result['success_count'], 'remaining': remaining_actionable}, ensure_ascii=False))

if critical_halt:
    raise SystemExit(2)
