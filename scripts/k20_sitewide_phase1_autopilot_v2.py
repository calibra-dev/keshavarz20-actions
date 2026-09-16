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
from datetime import datetime, timezone

from PIL import Image, ImageChops, ImageOps

ROOT = pathlib.Path('.')
CONFIG_PATH = ROOT / 'sitewide-media-autopilot' / 'config.json'
STATE_PATH = ROOT / 'sitewide-media-autopilot' / 'state.json'
INVENTORY_PATH = ROOT / 'sitewide-media-results' / 'inventory-phase1.json'
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
    print('Sitewide phase1 autopilot disabled.')
    raise SystemExit(0)
if not INVENTORY_PATH.exists():
    raise SystemExit('Missing sitewide-media-results/inventory-phase1.json')

batch_size = max(1, min(20, int(config.get('batch_size', 1))))
max_attempts = max(1, min(4, int(config.get('max_attempts', 2))))
quality = max(80, min(95, int(config.get('quality', 88))))
min_psnr = max(36.0, min(50.0, float(config.get('min_psnr', 40.0))))
min_saving_lossy = max(0.0, min(90.0, float(config.get('min_saving_lossy_pct', 15.0))))
min_saving_lossless = max(0.0, min(90.0, float(config.get('min_saving_lossless_pct', 5.0))))

base = os.environ['WP_BASE_URL'].rstrip('/')
username = os.environ['WP_USERNAME']
password = os.environ['WP_APP_PASSWORD']
auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
run_id = str(os.environ.get('GITHUB_RUN_ID') or int(time.time()))

inventory = load_json(INVENTORY_PATH, {'summary': {}, 'items': []})
state = load_json(STATE_PATH, {
    'version': 2,
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
    ('processed_attachment_ids', []), ('retry_counts', {}),
    ('terminal_skips', {}), ('critical_events', []),
):
    state.setdefault(key, default)
for key in ('cycles', 'successful_migrations', 'lossy_success', 'lossless_success'):
    state.setdefault(key, 0)

if state.get('status') == 'halted':
    print('Sitewide phase1 autopilot halted; manual review required.')
    raise SystemExit(2)


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def api(method, url, body=None, timeout=180):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Sitewide-Phase1-Autopilot/2.0',
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


def upload_media(data, filename, alt_text=''):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Sitewide-Phase1-Autopilot/2.0',
        'Content-Type': 'image/webp',
        'Content-Disposition': f'attachment; filename="{filename}"',
    }
    req = urllib.request.Request(
        qurl(base + '/wp-json/wp/v2/media'), data=data, method='POST', headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            obj = json.loads(r.read().decode('utf-8', 'replace'))
            code = int(r.status)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:800]}
        return int(e.code), obj
    if 200 <= code < 300 and alt_text:
        mid = int(obj.get('id') or 0)
        if mid:
            ac, _, _ = api('POST', f'{base}/wp-json/wp/v2/media/{mid}', {'alt_text': alt_text}, timeout=120)
            if not (200 <= ac < 300):
                return ac, {'error': 'alt_update_failed', 'uploaded': obj}
    return code, obj


def delete_media(mid):
    code, _, _ = api('DELETE', f'{base}/wp-json/wp/v2/media/{int(mid)}?force=true', timeout=120)
    return 200 <= code < 300


def get_bytes(url):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Sitewide-Phase1-Autopilot/2.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def head_url(url):
    req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Sitewide-Phase1-Autopilot/2.0'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return {'status': int(r.status), 'bytes': int(r.headers.get('Content-Length') or 0), 'content_type': str(r.headers.get('Content-Type') or '')}
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
    aa = flatten_rgb(a); bb = flatten_rgb(b)
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


def encode_candidate(raw, fmt):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); src.load()
    width, height = src.size
    if fmt == 'png':
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


def type_routes():
    code, data, _ = api('GET', base + '/wp-json/wp/v2/types?context=view')
    routes = {}
    if 200 <= code < 300 and isinstance(data, dict):
        for name, info in data.items():
            if isinstance(info, dict):
                rb = str(info.get('rest_base') or '').strip('/')
                ns = str(info.get('rest_namespace') or 'wp/v2').strip('/')
                if rb:
                    routes[str(name)] = f'{base}/wp-json/{ns}/{rb}'
    return routes


routes = type_routes()
SAFE = {'featured_image', 'woo_category_image'}
OBS = {'rendered_page', 'post_content_rendered'}
processed = {int(x) for x in state.get('processed_attachment_ids', [])}


def classify(item):
    refs = item.get('references') or []
    kinds = {str(r.get('kind') or '') for r in refs}
    if 'woo_product_image' in kinds:
        return False, 'owned_by_product_autopilot'
    writable = kinds - OBS
    if not writable:
        return False, 'no_writable_reference'
    if not writable.issubset(SAFE):
        return False, 'deferred_non_phase1_reference:' + ','.join(sorted(writable - SAFE))
    return True, ''


def rollback(applied):
    ok = True
    errors = []
    for a in reversed(applied):
        try:
            if a['kind'] == 'featured_image':
                code, _, _ = api('POST', a['url'], {'featured_media': a['old_id']})
            else:
                code, _, _ = api('PUT', a['url'], {'image': {'id': a['old_id']}})
            if not (200 <= code < 300):
                ok = False; errors.append(f"{a['kind']} rollback http={code}")
        except Exception as e:
            ok = False; errors.append(str(e))
    return ok, errors


def migrate_one(item):
    old = int(item['attachment_id'])
    fmt = str(item.get('format') or '').lower()
    refs = [r for r in item.get('references') or [] if str(r.get('kind') or '') in SAFE]
    row = {'old_attachment_id': old, 'success': False, 'references_to_update': len(refs)}
    new_id = None
    applied = []
    try:
        mc, media, _ = api('GET', f'{base}/wp-json/wp/v2/media/{old}?context=edit&_fields=id,source_url,media_type,mime_type,media_details,alt_text')
        if not (200 <= mc < 300):
            raise RuntimeError(f'TERMINAL: source media read failed http={mc}')
        old_url = str(media.get('source_url') or item.get('url') or '')
        mime = str(media.get('mime_type') or '').lower()
        if mime not in ('image/jpeg', 'image/png'):
            raise RuntimeError(f'TERMINAL: unsupported source mime {mime}')
        raw = get_bytes(old_url)
        data, width, height, mode, score, exact, saving = encode_candidate(raw, fmt)
        row.update({'source_url': old_url, 'original_bytes': len(raw), 'webp_bytes_local': len(data), 'saving_pct': saving, 'encoder_mode': mode, 'psnr_db': score, 'pixel_exact': exact, 'width': width, 'height': height})
        alt = str(media.get('alt_text') or item.get('alt_text') or '')
        uc, uploaded = upload_media(data, f'k20-sitewide-a{old}.webp', alt)
        if not (200 <= uc < 300):
            raise RuntimeError(f'RETRY: REST media upload failed http={uc}')
        new_id = int(uploaded.get('id') or 0)
        new_url = str(uploaded.get('source_url') or uploaded.get('guid', {}).get('rendered') or '')
        if new_id <= 0 or not new_url:
            raise RuntimeError('RETRY: REST media upload returned invalid object')
        row.update({'new_attachment_id': new_id, 'new_url': new_url})
        details = uploaded.get('media_details') or {}
        if int(details.get('width') or 0) != width or int(details.get('height') or 0) != height:
            raise RuntimeError('new WebP dimensions differ from original')
        hd = head_url(new_url); row['new_head'] = hd
        if not (200 <= hd['status'] < 400 and 'image/webp' in hd['content_type'].lower()):
            raise RuntimeError('new public WebP verification failed')

        seen = set()
        for ref in refs:
            kind = str(ref.get('kind') or '')
            oid = int(ref.get('object_id') or 0)
            otype = str(ref.get('object_type') or '')
            key = (kind, oid, otype)
            if key in seen:
                continue
            seen.add(key)
            if kind == 'featured_image':
                route = routes.get(otype)
                if not route:
                    raise RuntimeError(f'TERMINAL: no REST route for post type {otype}')
                obj_url = f'{route}/{oid}'
                rc, obj, _ = api('GET', obj_url + '?context=edit&_fields=id,featured_media')
                if not (200 <= rc < 300 and int(obj.get('featured_media') or 0) == old):
                    raise RuntimeError('TERMINAL: featured image changed from inventory source')
                wc, _, _ = api('POST', obj_url, {'featured_media': new_id})
                if not (200 <= wc < 300):
                    raise RuntimeError(f'featured update failed http={wc}')
                applied.append({'kind': 'featured_image', 'url': obj_url, 'old_id': old})
                vc, verify, _ = api('GET', obj_url + '?context=edit&_fields=id,featured_media')
                if not (200 <= vc < 300 and int(verify.get('featured_media') or 0) == new_id):
                    raise RuntimeError('featured readback failed')
            elif kind == 'woo_category_image':
                obj_url = f'{base}/wp-json/wc/v3/products/categories/{oid}'
                rc, obj, _ = api('GET', obj_url + '?_fields=id,image')
                current = obj.get('image') or {} if isinstance(obj, dict) else {}
                if not (200 <= rc < 300 and int(current.get('id') or 0) == old):
                    raise RuntimeError('TERMINAL: category image changed from inventory source')
                wc, _, _ = api('PUT', obj_url, {'image': {'id': new_id}})
                if not (200 <= wc < 300):
                    raise RuntimeError(f'category update failed http={wc}')
                applied.append({'kind': 'woo_category_image', 'url': obj_url, 'old_id': old})
                vc, verify, _ = api('GET', obj_url + '?_fields=id,image')
                vi = verify.get('image') or {} if isinstance(verify, dict) else {}
                if not (200 <= vc < 300 and int(vi.get('id') or 0) == new_id):
                    raise RuntimeError('category readback failed')

        row.update({'success': True, 'stage': 'verified', 'updated_reference_groups': len(applied)})
        return row, False
    except Exception as e:
        msg = str(e)
        row.update({'stage': 'error', 'error': msg})
        rb_ok, rb_errors = rollback(applied)
        row['rollback_ok'] = rb_ok
        if rb_errors:
            row['rollback_errors'] = rb_errors
        cleanup_ok = True
        if new_id:
            cleanup_ok = delete_media(new_id)
        row['cleanup_uploaded_webp'] = cleanup_ok
        critical = (not rb_ok) or (new_id is not None and not cleanup_ok)
        return row, critical


eligible = []
for item in inventory.get('items') or []:
    aid = int(item.get('attachment_id') or 0)
    if aid <= 0 or str(item.get('format') or '').lower() not in ('jpeg', 'png') or aid in processed:
        continue
    if str(aid) in state.get('terminal_skips', {}):
        continue
    ok, reason = classify(item)
    if ok:
        eligible.append(item)
    elif reason not in ('owned_by_product_autopilot', 'no_writable_reference') and int(item.get('reference_count') or 0) > 0:
        state['terminal_skips'].setdefault(str(aid), {'reason': reason, 'at_utc': now_iso()})

eligible.sort(key=lambda x: (x.get('format') != 'jpeg', -int(x.get('reference_count') or 0), int(x.get('attachment_id') or 0)))
selected = eligible[:batch_size]
result = {'action': 'sitewide_media.phase1_cycle_v2', 'run_id': run_id, 'executed_at_utc': now_iso(), 'selected': len(selected), 'items': []}
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
            state['critical_events'].append({'attachment_id': aid, 'reason': msg, 'at_utc': now_iso()})
            state['status'] = 'halted'
            state['halt_reason'] = 'rollback_or_cleanup_guard_failed'
            critical_halt = True
            break
    time.sleep(0.2)

state['processed_attachment_ids'] = sorted(processed)
state['cycles'] += 1
state['updated_at_utc'] = now_iso()
result['success_count'] = sum(1 for x in result['items'] if x.get('success'))
result['critical_halt'] = critical_halt

remaining = 0
for item in inventory.get('items') or []:
    aid = int(item.get('attachment_id') or 0)
    if aid <= 0 or aid in processed or str(aid) in state.get('terminal_skips', {}):
        continue
    ok, _ = classify(item)
    if ok:
        remaining += 1
state['last_cycle'] = {'run_id': run_id, 'selected': len(selected), 'success': result['success_count'], 'remaining_actionable_from_snapshot': remaining, 'at_utc': now_iso()}
if not critical_halt:
    state['status'] = 'completed' if remaining == 0 else 'running'
    if remaining == 0:
        state['completed_at_utc'] = now_iso()

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
save_json(RESULTS_DIR / f'{run_id}.json', result)
save_json(STATE_PATH, state)
print(json.dumps({'state': state['status'], 'selected': len(selected), 'success': result['success_count'], 'remaining': remaining}, ensure_ascii=False))
if critical_halt:
    raise SystemExit(2)
