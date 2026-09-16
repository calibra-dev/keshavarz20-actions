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
OPS_DIR = ROOT / 'category-image-pilot-ops'
RESULTS_DIR = ROOT / 'category-image-pilot-results'


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
username = os.environ['WP_USERNAME']
password = os.environ['WP_APP_PASSWORD']
auth = base64.b64encode(f'{username}:{password}'.encode()).decode()


def api(method, url, body=None, timeout=180):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Category-Image-Pilot/1.0',
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
        'User-Agent': 'K20-Category-Image-Pilot/1.0',
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
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Category-Image-Pilot/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def head_url(url):
    req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Category-Image-Pilot/1.0'})
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
    dec = Image.open(io.BytesIO(data)); dec.load()
    exact = ImageChops.difference(src.convert('RGBA'), dec.convert('RGBA')).getbbox() is None
    return data, bool(exact)


def encode_candidate(raw, mime, quality, min_psnr, min_saving_lossy, min_saving_lossless):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); src.load()
    width, height = src.size
    if mime == 'image/png':
        data, exact = encode_lossless(src)
        saving = round((1.0 - len(data) / float(len(raw))) * 100.0, 2)
        if exact and saving >= min_saving_lossless:
            return data, width, height, 'lossless', 99.0, True, saving
        raise RuntimeError(f'NO_WRITE: PNG lossless guard failed exact={exact} saving={saving}')
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
    raise RuntimeError('NO_WRITE: no WebP candidate met quality and saving guards')


def discover_category_by_image(old_id):
    matches = []
    for page in range(1, 31):
        url = f'{base}/wp-json/wc/v3/products/categories?per_page=100&page={page}&orderby=id&order=asc'
        code, rows, headers = api('GET', url, timeout=180)
        if code == 400 and isinstance(rows, dict) and rows.get('code') == 'woocommerce_rest_invalid_page_number':
            break
        if not (200 <= code < 300 and isinstance(rows, list)):
            raise RuntimeError(f'category discovery failed http={code}')
        for row in rows:
            image = row.get('image') or {}
            if int(image.get('id') or 0) == old_id:
                matches.append({'id': int(row.get('id') or 0), 'name': str(row.get('name') or ''), 'slug': str(row.get('slug') or '')})
        if len(rows) < 100:
            break
    return matches


def read_category(cid):
    return api('GET', f'{base}/wp-json/wc/v3/products/categories/{cid}?_fields=id,name,slug,image', timeout=120)


def image_id(obj):
    if not isinstance(obj, dict):
        return 0
    image = obj.get('image') or {}
    return int(image.get('id') or 0) if isinstance(image, dict) else 0


def poll_category(cid, expected_id, delays):
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


def next_request():
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []
    for path in OPS_DIR.glob('*.json'):
        if not (RESULTS_DIR / path.name).exists():
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.name)
    return candidates[0]


request_path = next_request()
if request_path is None:
    print('No unprocessed category pilot request.')
    raise SystemExit(0)

request = json.loads(request_path.read_text(encoding='utf-8'))
if request.get('action') != 'category_image.webp_pilot':
    raise SystemExit('Unsupported action')

old_id = int(request.get('old_attachment_id') or 0)
if old_id <= 0:
    raise SystemExit('old_attachment_id must be positive')
quality = max(80, min(95, int(request.get('quality', 88))))
min_psnr = max(36.0, min(50.0, float(request.get('min_psnr', 40.0))))
min_saving_lossy = max(0.0, min(90.0, float(request.get('min_saving_lossy_pct', 15.0))))
min_saving_lossless = max(0.0, min(90.0, float(request.get('min_saving_lossless_pct', 5.0))))

result = {
    'action': 'category_image.webp_pilot',
    'request': request_path.name,
    'executed_at_utc': now_iso(),
    'old_attachment_id': old_id,
    'success': False,
    'critical_halt': False,
}
new_id = None
category_id = None
write_applied = False

try:
    matches = discover_category_by_image(old_id)
    result['category_matches'] = matches
    if len(matches) != 1:
        raise RuntimeError(f'NO_WRITE: expected exactly one category using old image; found {len(matches)}')
    category_id = int(matches[0]['id'])
    result['category'] = matches[0]

    rc, current_obj, _ = read_category(category_id)
    current_id = image_id(current_obj)
    result['pre_readback'] = {'http': rc, 'image_id': current_id}
    if not (200 <= rc < 300 and current_id == old_id):
        raise RuntimeError(f'NO_WRITE: live category image changed; expected {old_id}, found {current_id}')

    mc, media, _ = api('GET', f'{base}/wp-json/wp/v2/media/{old_id}?context=edit&_fields=id,source_url,mime_type,media_details,alt_text', timeout=120)
    if not (200 <= mc < 300):
        raise RuntimeError(f'NO_WRITE: source media read failed http={mc}')
    source_url = str(media.get('source_url') or '')
    mime = str(media.get('mime_type') or '').lower()
    if mime not in ('image/jpeg', 'image/png'):
        raise RuntimeError(f'NO_WRITE: unsupported source mime {mime}')
    raw = get_bytes(source_url)
    data, width, height, mode, score, exact, saving = encode_candidate(
        raw, mime, quality, min_psnr, min_saving_lossy, min_saving_lossless
    )
    result.update({
        'source_url': source_url,
        'source_mime': mime,
        'original_bytes': len(raw),
        'webp_bytes_local': len(data),
        'saving_pct': saving,
        'encoder_mode': mode,
        'psnr_db': score,
        'pixel_exact': exact,
        'width': width,
        'height': height,
        'alt_before': str(media.get('alt_text') or ''),
    })

    uc, uploaded = upload_media(data, f'k20-category-pilot-a{old_id}.webp', str(media.get('alt_text') or ''))
    result['upload_http'] = uc
    if not (200 <= uc < 300):
        raise RuntimeError(f'RETRY: REST media upload failed http={uc}')
    new_id = int(uploaded.get('id') or 0)
    new_url = str(uploaded.get('source_url') or uploaded.get('guid', {}).get('rendered') or '')
    if new_id <= 0 or not new_url:
        raise RuntimeError('RETRY: upload returned invalid media object')
    result['new_attachment_id'] = new_id
    result['new_url'] = new_url
    result['alt_after'] = str(uploaded.get('alt_text') or '')

    details = uploaded.get('media_details') or {}
    result['uploaded_dimensions'] = {'width': int(details.get('width') or 0), 'height': int(details.get('height') or 0)}
    if int(details.get('width') or 0) != width or int(details.get('height') or 0) != height:
        raise RuntimeError('uploaded WebP dimensions differ from original')
    hd = head_url(new_url)
    result['new_head'] = hd
    if not (200 <= hd['status'] < 400 and 'image/webp' in hd['content_type'].lower()):
        raise RuntimeError('public WebP verification failed')

    update_url = f'{base}/wp-json/wc/v3/products/categories/{category_id}'
    wc, update_obj, _ = api('PUT', update_url, {'image': {'id': new_id}}, timeout=180)
    result['update_http'] = wc
    result['update_response_image_id'] = image_id(update_obj)
    if not (200 <= wc < 300):
        raise RuntimeError(f'category update failed http={wc}')
    write_applied = True

    verified, history = poll_category(category_id, new_id, [0, 2, 3, 5])
    result['readback_attempts'] = history
    if not verified:
        raise RuntimeError('category readback did not confirm new media id after retries')

    result['success'] = True
    result['stage'] = 'verified'
    result['kept_original_attachment'] = True
except Exception as exc:
    msg = str(exc)
    result['stage'] = 'error'
    result['error'] = msg
    rollback_ok = True
    cleanup_ok = True
    if write_applied and category_id:
        rc, rollback_obj, _ = api('PUT', f'{base}/wp-json/wc/v3/products/categories/{category_id}', {'image': {'id': old_id}}, timeout=180)
        result['rollback_http'] = rc
        rb_verified, rb_history = poll_category(category_id, old_id, [0, 2, 3])
        result['rollback_readback_attempts'] = rb_history
        rollback_ok = 200 <= rc < 300 and rb_verified
        result['rollback_ok'] = rollback_ok
    else:
        result['rollback_ok'] = True
    if new_id:
        cleanup_ok = delete_media(new_id)
        result['cleanup_uploaded_webp'] = cleanup_ok
    else:
        result['cleanup_uploaded_webp'] = True
    if not rollback_ok or not cleanup_ok:
        result['critical_halt'] = True

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
out_path = RESULTS_DIR / request_path.name
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'request': request_path.name, 'success': result['success'], 'critical_halt': result['critical_halt'], 'category_id': category_id, 'new_attachment_id': new_id}, ensure_ascii=False))
if result['critical_halt']:
    raise SystemExit(2)
