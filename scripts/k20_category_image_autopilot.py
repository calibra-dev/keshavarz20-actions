import base64
import io
import json
import math
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageChops, ImageOps

ROOT = pathlib.Path('.')
CONFIG_PATH = ROOT / 'category-image-autopilot' / 'config.json'
STATE_PATH = ROOT / 'category-image-autopilot' / 'state.json'
RESULTS_DIR = ROOT / 'category-image-autopilot-results'


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

config = load_json(CONFIG_PATH, {})
if config.get('enabled') is not True:
    print('Category image autopilot disabled.')
    raise SystemExit(0)

batch_size = max(1, min(10, int(config.get('batch_size', 2))))
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

state = load_json(STATE_PATH, {
    'version': 1,
    'started_at_utc': now_iso(),
    'updated_at_utc': now_iso(),
    'status': 'running',
    'cycles': 0,
    'successful_migrations': 0,
    'lossy_success': 0,
    'lossless_success': 0,
    'processed_source_ids': [],
    'migrations': {},
    'retry_counts': {},
    'terminal_skips': {},
    'critical_events': [],
})
for key, default in (
    ('processed_source_ids', []), ('migrations', {}), ('retry_counts', {}),
    ('terminal_skips', {}), ('critical_events', []),
):
    state.setdefault(key, default)
for key in ('cycles', 'successful_migrations', 'lossy_success', 'lossless_success'):
    state.setdefault(key, 0)
if state.get('status') == 'halted':
    print('Category image autopilot halted; manual review required.')
    raise SystemExit(2)


def api(method, url, body=None, timeout=180):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Category-Image-Autopilot/1.0',
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
            obj = {'raw': raw[:1200]}
        return int(e.code), obj, dict(e.headers)


def upload_media(data, filename, alt_text=''):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Category-Image-Autopilot/1.0',
        'Content-Type': 'image/webp',
        'Content-Disposition': f'attachment; filename="{filename}"',
    }
    req = urllib.request.Request(qurl(base + '/wp-json/wp/v2/media'), data=data, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            obj = json.loads(r.read().decode('utf-8', 'replace'))
            code = int(r.status)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:1200]}
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
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Category-Image-Autopilot/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def head_url(url):
    req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Category-Image-Autopilot/1.0'})
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
    dec = Image.open(io.BytesIO(data)); dec.load()
    exact = ImageChops.difference(src.convert('RGBA'), dec.convert('RGBA')).getbbox() is None
    return data, bool(exact)


def encode_candidate(raw, mime):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); src.load()
    width, height = src.size
    if mime == 'image/png':
        data, exact = encode_lossless(src)
        saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
        if exact and saving >= min_saving_lossless:
            return data, width, height, 'lossless', 99.0, True, saving
        raise RuntimeError(f'TERMINAL: PNG lossless guard failed exact={exact} saving={saving}')
    for q in dict.fromkeys([quality, min(92, quality + 4), min(95, quality + 7)]):
        out = io.BytesIO()
        kwargs = {'format': 'WEBP', 'method': 6, 'quality': int(q)}
        if src.info.get('icc_profile'):
            kwargs['icc_profile'] = src.info['icc_profile']
        if src.info.get('exif'):
            kwargs['exif'] = src.info['exif']
        src.save(out, **kwargs)
        data = out.getvalue()
        dec = Image.open(io.BytesIO(data)); dec.load()
        score = round(psnr(src, dec), 2)
        saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
        if score >= min_psnr and saving >= min_saving_lossy:
            return data, width, height, f'lossy-q{q}', score, False, saving
    data, exact = encode_lossless(src)
    saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
    if exact and saving >= min_saving_lossless:
        return data, width, height, 'lossless-fallback', 99.0, True, saving
    raise RuntimeError('TERMINAL: no WebP candidate met quality and saving guards')


def fetch_categories():
    rows_all = []
    for page in range(1, 31):
        code, rows, _ = api('GET', f'{base}/wp-json/wc/v3/products/categories?per_page=100&page={page}&orderby=id&order=asc', timeout=180)
        if code == 400 and isinstance(rows, dict) and rows.get('code') == 'woocommerce_rest_invalid_page_number':
            break
        if not (200 <= code < 300 and isinstance(rows, list)):
            raise RuntimeError(f'category inventory failed http={code}')
        rows_all.extend(rows)
        if len(rows) < 100:
            break
    return rows_all


def read_category(cid):
    return api('GET', f'{base}/wp-json/wc/v3/products/categories/{cid}?_fields=id,name,slug,image', timeout=120)


def image_id(obj):
    if not isinstance(obj, dict):
        return 0
    image = obj.get('image') or {}
    return int(image.get('id') or 0) if isinstance(image, dict) else 0


def poll_category(cid, expected_id, delays=(0, 2, 3, 5)):
    history = []
    for delay in delays:
        if delay:
            time.sleep(delay)
        code, obj, _ = read_category(cid)
        current = image_id(obj)
        history.append({'http': code, 'image_id': current})
        if 200 <= code < 300 and current == expected_id:
            return True, history
    return False, history


def live_groups():
    groups = {}
    for cat in fetch_categories():
        image = cat.get('image') or {}
        if not isinstance(image, dict):
            continue
        mid = int(image.get('id') or 0)
        src = str(image.get('src') or '')
        path = urllib.parse.urlsplit(src).path.lower()
        if mid <= 0 or not path.endswith(('.jpg', '.jpeg', '.png')):
            continue
        g = groups.setdefault(mid, {'source_attachment_id': mid, 'source_url_hint': src, 'categories': []})
        g['categories'].append({'id': int(cat.get('id') or 0), 'name': str(cat.get('name') or ''), 'slug': str(cat.get('slug') or '')})
    return groups


def rollback_categories(applied, old_id):
    ok = True
    details = []
    for cat in reversed(applied):
        cid = int(cat['id'])
        code, _, _ = api('PUT', f'{base}/wp-json/wc/v3/products/categories/{cid}', {'image': {'id': old_id}}, timeout=180)
        verified, history = poll_category(cid, old_id, (0, 2, 3))
        one_ok = 200 <= code < 300 and verified
        ok = ok and one_ok
        details.append({'category_id': cid, 'http': code, 'verified': verified, 'readback': history})
    return ok, details


def migrate_group(group):
    old_id = int(group['source_attachment_id'])
    cats = group['categories']
    row = {'old_attachment_id': old_id, 'categories': cats, 'success': False}
    new_id = None
    applied = []
    try:
        for cat in cats:
            code, obj, _ = read_category(int(cat['id']))
            current = image_id(obj)
            if not (200 <= code < 300 and current == old_id):
                raise RuntimeError(f'TERMINAL: category {cat["id"]} image changed from live group; found {current}')

        mc, media, _ = api('GET', f'{base}/wp-json/wp/v2/media/{old_id}?context=edit&_fields=id,source_url,mime_type,media_details,alt_text', timeout=120)
        if not (200 <= mc < 300):
            raise RuntimeError(f'TERMINAL: source media read failed http={mc}')
        source_url = str(media.get('source_url') or group.get('source_url_hint') or '')
        mime = str(media.get('mime_type') or '').lower()
        if mime not in ('image/jpeg', 'image/png'):
            raise RuntimeError(f'TERMINAL: unsupported source mime {mime}')
        raw = get_bytes(source_url)
        data, width, height, mode, score, exact, saving = encode_candidate(raw, mime)
        alt_before = str(media.get('alt_text') or '')
        row.update({
            'source_url': source_url, 'source_mime': mime, 'original_bytes': len(raw),
            'webp_bytes_local': len(data), 'saving_pct': saving, 'encoder_mode': mode,
            'psnr_db': score, 'pixel_exact': exact, 'width': width, 'height': height,
            'alt_before': alt_before,
        })

        uc, uploaded = upload_media(data, f'k20-category-a{old_id}.webp', alt_before)
        if not (200 <= uc < 300):
            raise RuntimeError(f'RETRY: REST media upload failed http={uc}')
        new_id = int(uploaded.get('id') or 0)
        new_url = str(uploaded.get('source_url') or uploaded.get('guid', {}).get('rendered') or '')
        if new_id <= 0 or not new_url:
            raise RuntimeError('RETRY: REST media upload returned invalid object')
        row.update({'new_attachment_id': new_id, 'new_url': new_url, 'upload_http': uc})

        vc, fresh_media, _ = api('GET', f'{base}/wp-json/wp/v2/media/{new_id}?context=edit&_fields=id,source_url,mime_type,media_details,alt_text', timeout=120)
        if not (200 <= vc < 300 and str(fresh_media.get('mime_type') or '').lower() == 'image/webp'):
            raise RuntimeError('new media REST readback failed')
        details = fresh_media.get('media_details') or {}
        if int(details.get('width') or 0) != width or int(details.get('height') or 0) != height:
            raise RuntimeError('new WebP dimensions differ from original')
        alt_after = str(fresh_media.get('alt_text') or '')
        row['alt_after'] = alt_after
        if alt_after != alt_before:
            raise RuntimeError('new WebP ALT readback mismatch')
        hd = head_url(new_url)
        row['new_head'] = hd
        if not (200 <= hd['status'] < 400 and 'image/webp' in hd['content_type'].lower()):
            raise RuntimeError('new public WebP verification failed')

        updates = []
        for cat in cats:
            cid = int(cat['id'])
            code, update_obj, _ = api('PUT', f'{base}/wp-json/wc/v3/products/categories/{cid}', {'image': {'id': new_id}}, timeout=180)
            if not (200 <= code < 300):
                raise RuntimeError(f'category {cid} update failed http={code}')
            applied.append(cat)
            verified, history = poll_category(cid, new_id)
            updates.append({'category_id': cid, 'update_http': code, 'response_image_id': image_id(update_obj), 'readback': history, 'verified': verified})
            if not verified:
                row['updates'] = updates
                raise RuntimeError(f'category {cid} readback did not confirm new media id')
        row['updates'] = updates
        row.update({'success': True, 'stage': 'verified', 'kept_original_attachment': True})
        return row, False
    except Exception as exc:
        msg = str(exc)
        row.update({'stage': 'error', 'error': msg})
        rollback_ok = True
        rollback_details = []
        if applied:
            rollback_ok, rollback_details = rollback_categories(applied, old_id)
        row['rollback_ok'] = rollback_ok
        if rollback_details:
            row['rollback_details'] = rollback_details
        cleanup_ok = True
        if new_id:
            cleanup_ok = delete_media(new_id)
        row['cleanup_uploaded_webp'] = cleanup_ok
        critical = (not rollback_ok) or (new_id is not None and not cleanup_ok)
        return row, critical


processed = {int(x) for x in state.get('processed_source_ids', [])}
groups = live_groups()
candidates = []
for old_id, group in groups.items():
    if old_id in processed or str(old_id) in state.get('terminal_skips', {}):
        continue
    candidates.append(group)
candidates.sort(key=lambda g: (-len(g['categories']), int(g['source_attachment_id'])))
selected = candidates[:batch_size]
result = {'action': 'category_image.autopilot_cycle', 'run_id': run_id, 'executed_at_utc': now_iso(), 'selected': len(selected), 'items': []}
critical_halt = False

for group in selected:
    old_id = int(group['source_attachment_id'])
    row, critical = migrate_group(group)
    result['items'].append(row)
    if row.get('success'):
        processed.add(old_id)
        state['successful_migrations'] += 1
        if row.get('pixel_exact'):
            state['lossless_success'] += 1
        else:
            state['lossy_success'] += 1
        state['migrations'][str(old_id)] = {
            'new_attachment_id': int(row.get('new_attachment_id') or 0),
            'category_ids': [int(x['id']) for x in row.get('categories') or []],
            'at_utc': now_iso(),
        }
        state['retry_counts'].pop(str(old_id), None)
    else:
        msg = str(row.get('error') or '')
        if msg.startswith('TERMINAL:'):
            state['terminal_skips'][str(old_id)] = {'reason': msg, 'at_utc': now_iso()}
        else:
            attempts = int(state['retry_counts'].get(str(old_id), 0)) + 1
            state['retry_counts'][str(old_id)] = attempts
            if attempts >= max_attempts:
                state['terminal_skips'][str(old_id)] = {'reason': f'max_attempts_exhausted:{attempts}', 'last_error': msg, 'at_utc': now_iso()}
        if critical:
            state['critical_events'].append({'source_attachment_id': old_id, 'reason': msg, 'at_utc': now_iso()})
            state['status'] = 'halted'
            state['halt_reason'] = 'rollback_or_cleanup_guard_failed'
            critical_halt = True
            break
    time.sleep(0.2)

state['processed_source_ids'] = sorted(processed)
state['cycles'] += 1
state['updated_at_utc'] = now_iso()
result['success_count'] = sum(1 for x in result['items'] if x.get('success'))
result['critical_halt'] = critical_halt
remaining = 0
for old_id in groups:
    if old_id not in processed and str(old_id) not in state.get('terminal_skips', {}):
        remaining += 1
state['last_cycle'] = {'run_id': run_id, 'selected': len(selected), 'success': result['success_count'], 'remaining_live_groups': remaining, 'at_utc': now_iso()}
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
