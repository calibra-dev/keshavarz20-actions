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
import xmlrpc.client
from datetime import datetime, timezone

from PIL import Image, ImageChops, ImageOps

ROOT = pathlib.Path('.')
CONFIG_PATH = ROOT / 'media-autopilot' / 'config.json'
STATE_PATH = ROOT / 'media-autopilot' / 'state.json'
RESULTS_DIR = ROOT / 'media-autopilot-results'


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
    raise SystemExit('Autopilot is not enabled in media-autopilot/config.json')

batch_size = max(1, min(30, int(config.get('batch_size', 20))))
max_attempts = max(1, min(5, int(config.get('max_attempts', 3))))
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

state = load_json(STATE_PATH, {
    'version': 1,
    'started_at_utc': now_iso(),
    'updated_at_utc': now_iso(),
    'status': 'running',
    'cycles': 0,
    'successful_migrations': 0,
    'lossy_success': 0,
    'lossless_success': 0,
    'retry_counts': {},
    'terminal_skips': {},
    'critical_events': [],
})

state.setdefault('retry_counts', {})
state.setdefault('terminal_skips', {})
state.setdefault('critical_events', [])
state.setdefault('successful_migrations', 0)
state.setdefault('lossy_success', 0)
state.setdefault('lossless_success', 0)
state.setdefault('cycles', 0)

if state.get('status') == 'completed':
    print('Autopilot already completed.')
    raise SystemExit(0)
if state.get('status') == 'halted':
    print('Autopilot is halted; manual inspection required.')
    raise SystemExit(0)
if state['cycles'] >= max_cycles:
    state['status'] = 'halted'
    state['halt_reason'] = f'max_cycles reached ({max_cycles})'
    state['updated_at_utc'] = now_iso()
    save_json(STATE_PATH, state)
    raise SystemExit(0)


def qurl(url):
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def api(method, url, body=None, timeout=180):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Media-Autopilot/1.0',
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(qurl(url), data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            return int(r.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:1000]}
        return int(e.code), obj


def inspect_attachment(aid):
    payload = json.dumps({
        'mode': 'inspect',
        'resource': 'attachment',
        'id': int(aid),
        'changes': {},
    }, separators=(',', ':')).encode('utf-8')
    req = urllib.request.Request(
        bridge_url,
        data=payload,
        method='POST',
        headers={
            'Authorization': 'Basic ' + auth,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            'User-Agent': 'K20-Media-Autopilot/1.0',
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
            obj = {'raw': raw[:1000]}
        return int(e.code), obj


def get_bytes(url):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Media-Autopilot/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def head_url(url):
    req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Media-Autopilot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return {
                'status': int(r.status),
                'bytes': int(r.headers.get('Content-Length') or 0),
                'content_type': str(r.headers.get('Content-Type') or ''),
            }
    except urllib.error.HTTPError as e:
        return {
            'status': int(e.code),
            'bytes': 0,
            'content_type': str(e.headers.get('Content-Type') or ''),
        }
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
    decoded = Image.open(io.BytesIO(data))
    decoded.load()
    exact = ImageChops.difference(src.convert('RGBA'), decoded.convert('RGBA')).getbbox() is None
    return data, bool(exact)


def encode_candidate(raw, mime):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    src.load()
    width, height = src.size

    if mime == 'image/png':
        data, exact = encode_lossless(src)
        if not exact:
            raise RuntimeError('TERMINAL: lossless pixel equality check failed')
        saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
        if saving < min_saving_lossless:
            raise RuntimeError(f'TERMINAL: lossless saving {saving}% below minimum {min_saving_lossless}%')
        return {
            'bytes': data,
            'width': width,
            'height': height,
            'mode': 'lossless',
            'pixel_exact': True,
            'psnr': 99.0,
            'saving_pct': saving,
            'attempts': [{'mode': 'lossless', 'bytes': len(data), 'pixel_exact': True}],
        }

    attempts = []
    for q in dict.fromkeys([quality, min(92, quality + 4), min(95, quality + 7)]):
        out = io.BytesIO()
        kwargs = {'format': 'WEBP', 'method': 6, 'quality': int(q)}
        if src.info.get('icc_profile'):
            kwargs['icc_profile'] = src.info['icc_profile']
        if src.info.get('exif'):
            kwargs['exif'] = src.info['exif']
        src.save(out, **kwargs)
        data = out.getvalue()
        decoded = Image.open(io.BytesIO(data))
        decoded.load()
        score = round(psnr(src, decoded), 2)
        saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
        attempts.append({'mode': f'lossy-q{q}', 'bytes': len(data), 'psnr': score, 'saving_pct': saving})
        if score >= min_psnr and saving >= min_saving_lossy:
            return {
                'bytes': data,
                'width': width,
                'height': height,
                'mode': f'lossy-q{q}',
                'pixel_exact': False,
                'psnr': score,
                'saving_pct': saving,
                'attempts': attempts,
            }

    data, exact = encode_lossless(src)
    saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
    attempts.append({'mode': 'lossless-fallback', 'bytes': len(data), 'pixel_exact': exact, 'saving_pct': saving})
    if exact and saving >= min_saving_lossless:
        return {
            'bytes': data,
            'width': width,
            'height': height,
            'mode': 'lossless-fallback',
            'pixel_exact': True,
            'psnr': 99.0,
            'saving_pct': saving,
            'attempts': attempts,
        }
    raise RuntimeError('TERMINAL: no WebP candidate met quality and saving guards')


def product_inventory():
    rows = []
    products = 0
    pages = 0
    for page in range(1, 51):
        params = urllib.parse.urlencode({
            'per_page': 100,
            'page': page,
            'status': 'publish',
            'orderby': 'id',
            'order': 'asc',
            '_fields': 'id,name,slug,status,images',
        })
        code, data = api('GET', f'{base}/wp-json/wc/v3/products?{params}')
        if code == 400 and page > 1:
            break
        if not (200 <= code < 300):
            raise RuntimeError(f'product inventory read failed page={page} http={code}')
        if not data:
            break
        pages += 1
        products += len(data)
        for product in data:
            images = list(product.get('images') or [])
            for pos, image in enumerate(images):
                src = str(image.get('src') or '')
                path = urllib.parse.urlsplit(src).path.lower()
                if not path.endswith(('.jpg', '.jpeg', '.png')):
                    continue
                aid = int(image.get('id') or 0)
                if aid <= 0:
                    continue
                rows.append({
                    'product_id': int(product['id']),
                    'product_name': str(product.get('name') or ''),
                    'attachment_id': aid,
                    'position': pos,
                    'primary': pos == 0,
                    'src': src,
                    'alt': str(image.get('alt') or ''),
                })
        if len(data) < 100:
            break
    rows.sort(key=lambda x: (not x['primary'], x['product_id'], x['position'], x['attachment_id']))
    return {
        'products_read': products,
        'pages_read': pages,
        'refs': rows,
        'jpeg_png_refs': len(rows),
        'primary_refs': sum(1 for x in rows if x['primary']),
        'distinct_attachment_ids': len({x['attachment_id'] for x in rows}),
    }


def set_attachment_alt(new_id, alt_text):
    if not alt_text:
        return 200, {'alt_text': ''}
    return api('POST', f'{base}/wp-json/wp/v2/media/{new_id}', {'alt_text': alt_text}, timeout=120)


def cleanup_upload(new_id):
    try:
        return bool(server.wp.deleteFile(0, username, password, int(new_id)))
    except Exception:
        return False


def migrate_one(candidate):
    pid = int(candidate['product_id'])
    old = int(candidate['attachment_id'])
    expected_pos = int(candidate['position'])
    row = {
        'product_id': pid,
        'old_attachment_id': old,
        'expected_position': expected_pos,
        'primary': bool(candidate['primary']),
        'success': False,
    }
    new_id = None
    original_images = None
    replacement_attempted = False
    rollback_ok = True

    try:
        pc, product = api('GET', f'{base}/wp-json/wc/v3/products/{pid}')
        if not (200 <= pc < 300):
            raise RuntimeError(f'product read failed http={pc}')
        original_images = list(product.get('images') or [])
        if expected_pos >= len(original_images):
            raise RuntimeError('TERMINAL: expected image position no longer exists')
        current_id = int(original_images[expected_pos].get('id') or 0)
        if current_id != old:
            raise RuntimeError(f'TERMINAL: current image changed from expected {old} to {current_id}')
        occurrences = sum(1 for x in original_images if int(x.get('id') or 0) == old)
        if occurrences != 1:
            raise RuntimeError(f'TERMINAL: attachment occurs {occurrences} times in product images')

        ic, inspected = inspect_attachment(old)
        before = inspected.get('before') if isinstance(inspected, dict) else None
        if not (200 <= ic < 300 and inspected.get('ok') is True and isinstance(before, dict)):
            raise RuntimeError(f'attachment inspect failed http={ic}')
        mime = str(before.get('mime_type') or '').lower()
        if mime not in ('image/jpeg', 'image/png'):
            raise RuntimeError(f'TERMINAL: unsupported source mime {mime}')
        source_url = str(before.get('url') or '')
        if not source_url:
            raise RuntimeError('attachment source URL missing')

        raw = get_bytes(source_url)
        encoded = encode_candidate(raw, mime)
        alt_text = str(original_images[expected_pos].get('alt') or product.get('name') or '').strip()
        row.update({
            'source_url': source_url,
            'source_mime': mime,
            'original_bytes': len(raw),
            'webp_bytes_local': len(encoded['bytes']),
            'saving_pct': encoded['saving_pct'],
            'encoder_mode': encoded['mode'],
            'psnr_db': encoded['psnr'],
            'pixel_exact': encoded['pixel_exact'],
            'encoder_attempts': encoded['attempts'],
            'width': encoded['width'],
            'height': encoded['height'],
            'alt_before': alt_text,
        })

        filename = f'k20-p{pid}-a{old}-webp.webp'
        upload = server.wp.uploadFile(0, username, password, {
            'name': filename,
            'type': 'image/webp',
            'bits': xmlrpc.client.Binary(encoded['bytes']),
            'overwrite': False,
            'post_id': pid,
        })
        new_id = int(upload.get('id') or 0)
        new_url = str(upload.get('url') or '')
        if new_id <= 0 or not new_url:
            raise RuntimeError('upload did not return a valid attachment')
        row.update({'new_attachment_id': new_id, 'new_url': new_url})

        nc, nobj = inspect_attachment(new_id)
        nb = nobj.get('before') if isinstance(nobj, dict) else None
        if not (200 <= nc < 300 and nobj.get('ok') is True and isinstance(nb, dict)):
            raise RuntimeError('new attachment inspect failed')
        if str(nb.get('mime_type') or '').lower() != 'image/webp':
            raise RuntimeError('new attachment is not image/webp')
        if int(nb.get('width') or 0) != encoded['width'] or int(nb.get('height') or 0) != encoded['height']:
            raise RuntimeError('new WebP dimensions differ from original')

        hd = head_url(new_url)
        row['new_head'] = hd
        if not (200 <= hd['status'] < 400 and 'image/webp' in hd['content_type'].lower()):
            raise RuntimeError('public WebP HEAD verification failed')

        ac, _ = set_attachment_alt(new_id, alt_text)
        row['alt_update_http'] = ac
        if alt_text and not (200 <= ac < 300):
            raise RuntimeError(f'attachment alt update failed http={ac}')

        if expected_pos == 0:
            replacement_attempted = True
            edited = bool(server.wp.editPost(0, username, password, pid, {'post_thumbnail': new_id}))
            row['xmlrpc_featured_edit_return'] = edited
            if not edited:
                raise RuntimeError('wp.editPost featured image returned false')
        else:
            replacement = []
            for idx, image in enumerate(original_images):
                if idx == expected_pos:
                    replacement.append({'id': new_id, 'alt': alt_text})
                else:
                    replacement.append({'id': int(image.get('id') or 0)})
            replacement_attempted = True
            uc, _ = api('PUT', f'{base}/wp-json/wc/v3/products/{pid}', {'images': replacement})
            row['woo_gallery_update_http'] = uc
            if not (200 <= uc < 300):
                raise RuntimeError(f'gallery image update failed http={uc}')

        confirmed = False
        for attempt in range(1, 4):
            if attempt > 1:
                time.sleep(2)
            rc, rb = api('GET', f'{base}/wp-json/wc/v3/products/{pid}')
            imgs = list(rb.get('images') or []) if 200 <= rc < 300 else []
            if expected_pos < len(imgs) and int(imgs[expected_pos].get('id') or 0) == new_id:
                alt_after = str(imgs[expected_pos].get('alt') or '')
                if alt_text and alt_after != alt_text:
                    row['alt_after'] = alt_after
                    raise RuntimeError('readback alt text differs from original')
                row.update({
                    'readback_attempts': attempt,
                    'readback_http': rc,
                    'readback_image_id': new_id,
                    'readback_src': str(imgs[expected_pos].get('src') or ''),
                    'alt_after': alt_after,
                })
                confirmed = True
                break
        if not confirmed:
            raise RuntimeError('product readback did not confirm new WebP attachment')

        row.update({'success': True, 'stage': 'verified'})
        return row, False

    except Exception as exc:
        message = str(exc)
        terminal = message.startswith('TERMINAL:')
        row.update({'stage': 'error', 'error': message, 'terminal': terminal})

        if new_id and replacement_attempted:
            if expected_pos == 0:
                try:
                    rollback_ok = bool(server.wp.editPost(0, username, password, pid, {'post_thumbnail': old}))
                    row['rollback_featured_return'] = rollback_ok
                except Exception as re:
                    rollback_ok = False
                    row['rollback_error'] = str(re)
            else:
                try:
                    original_payload = [{'id': int(x.get('id') or 0)} for x in (original_images or [])]
                    rc, _ = api('PUT', f'{base}/wp-json/wc/v3/products/{pid}', {'images': original_payload})
                    rollback_ok = 200 <= rc < 300
                    row['rollback_product_http'] = rc
                except Exception as re:
                    rollback_ok = False
                    row['rollback_error'] = str(re)

        if new_id:
            row['cleanup_uploaded_webp'] = cleanup_upload(new_id)

        critical = replacement_attempted and not rollback_ok
        if critical:
            row['critical'] = True
        return row, critical


for key, attempts in list(state['retry_counts'].items()):
    if int(attempts) >= max_attempts and key not in state['terminal_skips']:
        state['terminal_skips'][key] = {
            'reason': f'max_attempts_exhausted:{attempts}',
            'at_utc': now_iso(),
        }

before = product_inventory()
refs = before['refs']
eligible = []
for ref in refs:
    key = f"{ref['product_id']}:{ref['attachment_id']}"
    if key in state['terminal_skips']:
        continue
    if int(state['retry_counts'].get(key, 0)) >= max_attempts:
        continue
    eligible.append(ref)

selected = eligible[:batch_size]
cycle_rows = []
critical_halt = False

for candidate in selected:
    key = f"{candidate['product_id']}:{candidate['attachment_id']}"
    row, critical = migrate_one(candidate)
    cycle_rows.append(row)
    if row.get('success'):
        state['successful_migrations'] += 1
        if row.get('pixel_exact'):
            state['lossless_success'] += 1
        else:
            state['lossy_success'] += 1
        state['retry_counts'].pop(key, None)
    else:
        if row.get('terminal'):
            state['terminal_skips'][key] = {
                'reason': row.get('error', 'terminal'),
                'product_id': candidate['product_id'],
                'attachment_id': candidate['attachment_id'],
                'at_utc': now_iso(),
            }
        else:
            state['retry_counts'][key] = int(state['retry_counts'].get(key, 0)) + 1
    if critical:
        critical_halt = True
        state['critical_events'].append({
            'at_utc': now_iso(),
            'product_id': candidate['product_id'],
            'attachment_id': candidate['attachment_id'],
            'error': row.get('error', 'critical rollback failure'),
        })
        break
    time.sleep(0.2)

after = product_inventory()
state['cycles'] += 1
state['updated_at_utc'] = now_iso()
state['last_inventory'] = {
    'products_read': after['products_read'],
    'jpeg_png_refs': after['jpeg_png_refs'],
    'primary_refs': after['primary_refs'],
    'distinct_attachment_ids': after['distinct_attachment_ids'],
}
state['last_cycle'] = {
    'run_id': run_id,
    'selected': len(selected),
    'success': sum(1 for x in cycle_rows if x.get('success')),
    'failed_or_skipped': sum(1 for x in cycle_rows if not x.get('success')),
    'before_refs': before['jpeg_png_refs'],
    'after_refs': after['jpeg_png_refs'],
    'at_utc': now_iso(),
}

if critical_halt:
    state['status'] = 'halted'
    state['halt_reason'] = 'critical rollback failure'
elif after['jpeg_png_refs'] == 0:
    state['status'] = 'completed'
    state['completed_at_utc'] = now_iso()
else:
    remaining_eligible = []
    for ref in after['refs']:
        key = f"{ref['product_id']}:{ref['attachment_id']}"
        if key in state['terminal_skips']:
            continue
        if int(state['retry_counts'].get(key, 0)) >= max_attempts:
            continue
        remaining_eligible.append(ref)
    if not remaining_eligible:
        state['status'] = 'completed_with_skips'
        state['completed_at_utc'] = now_iso()
    else:
        state['status'] = 'running'

result = {
    'action': 'media.autopilot.cycle',
    'run_id': run_id,
    'executed_at_utc': now_iso(),
    'config': {
        'batch_size': batch_size,
        'max_attempts': max_attempts,
        'quality': quality,
        'min_psnr': min_psnr,
        'min_saving_lossy_pct': min_saving_lossy,
        'min_saving_lossless_pct': min_saving_lossless,
    },
    'inventory_before': {k: before[k] for k in ('products_read', 'jpeg_png_refs', 'primary_refs', 'distinct_attachment_ids')},
    'items': cycle_rows,
    'inventory_after': {k: after[k] for k in ('products_read', 'jpeg_png_refs', 'primary_refs', 'distinct_attachment_ids')},
    'state_status': state['status'],
    'total_successful_migrations': state['successful_migrations'],
    'total_terminal_skips': len(state['terminal_skips']),
}

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
save_json(RESULTS_DIR / f'run-{run_id}.json', result)
save_json(STATE_PATH, state)
print(json.dumps({
    'status': state['status'],
    'cycle': state['cycles'],
    'selected': len(selected),
    'success': result['inventory_before']['jpeg_png_refs'] - result['inventory_after']['jpeg_png_refs'],
    'remaining_refs': after['jpeg_png_refs'],
    'remaining_primary': after['primary_refs'],
    'terminal_skips': len(state['terminal_skips']),
}, ensure_ascii=False))
