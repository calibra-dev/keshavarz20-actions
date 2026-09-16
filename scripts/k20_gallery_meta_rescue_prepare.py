import base64
import io
import json
import math
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageChops, ImageOps

ROOT = pathlib.Path('.')
DIAGNOSTIC = ROOT / 'media-rest-rescue' / 'skipped-diagnostic.json'
OUT = ROOT / 'gallery-meta-rescue' / 'prepared.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(
    f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()
).decode()

MIN_PSNR = 40.0
MIN_LOSSY_SAVING = 15.0
MIN_LOSSLESS_SAVING = 5.0


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%'), p.query, p.fragment))


def api(method, url, body=None, raw=None, headers=None, timeout=180):
    h = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Gallery-Meta-Rescue-Prepare/1.0',
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
            payload = r.read().decode('utf-8', 'replace')
            try:
                obj = json.loads(payload) if payload else {}
            except Exception:
                obj = {'raw': payload[:500]}
            return int(r.status), obj
    except urllib.error.HTTPError as e:
        payload = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(payload)
        except Exception:
            obj = {'raw': payload[:500]}
        return int(e.code), obj


def get_bytes(url):
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Gallery-Meta-Rescue-Prepare/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def head(url):
    try:
        req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Gallery-Meta-Rescue-Prepare/1.0'})
        with urllib.request.urlopen(req, timeout=90) as r:
            return {
                'status': int(r.status),
                'bytes': int(r.headers.get('Content-Length') or 0),
                'content_type': str(r.headers.get('Content-Type') or ''),
            }
    except Exception:
        return {'status': 0, 'bytes': 0, 'content_type': ''}


def flatten(image):
    if 'A' in image.getbands():
        rgba = image.convert('RGBA')
        bg = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        return bg.convert('RGB')
    return image.convert('RGB')


def psnr(a, b):
    aa = flatten(a)
    bb = flatten(b)
    hist = ImageChops.difference(aa, bb).histogram()
    square_error = sum(count * ((i % 256) ** 2) for i, count in enumerate(hist))
    mse = square_error / float(aa.size[0] * aa.size[1] * 3)
    return 99.0 if mse <= 0 else 20 * math.log10(255 / math.sqrt(mse))


def encode_webp(raw, mime):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    src.load()
    width, height = src.size

    def lossless():
        buf = io.BytesIO()
        src.save(buf, format='WEBP', lossless=True, method=6)
        data = buf.getvalue()
        decoded = Image.open(io.BytesIO(data))
        decoded.load()
        exact = ImageChops.difference(src.convert('RGBA'), decoded.convert('RGBA')).getbbox() is None
        saving = round((1 - len(data) / float(len(raw))) * 100, 2)
        return data, exact, saving

    if mime == 'image/png':
        data, exact, saving = lossless()
        if exact and saving >= MIN_LOSSLESS_SAVING:
            return data, width, height, 99.0, 'lossless', True, saving
        raise RuntimeError('no acceptable lossless WebP candidate')

    for quality in (88, 92, 95):
        buf = io.BytesIO()
        src.save(buf, format='WEBP', quality=quality, method=6)
        data = buf.getvalue()
        decoded = Image.open(io.BytesIO(data))
        decoded.load()
        score = round(psnr(src, decoded), 2)
        saving = round((1 - len(data) / float(len(raw))) * 100, 2)
        if score >= MIN_PSNR and saving >= MIN_LOSSY_SAVING:
            return data, width, height, score, f'lossy-q{quality}', False, saving

    data, exact, saving = lossless()
    if exact and saving >= MIN_LOSSLESS_SAVING:
        return data, width, height, 99.0, 'lossless-fallback', True, saving
    raise RuntimeError('no WebP candidate met quality and saving guards')


def upload(filename, data):
    code, obj = api(
        'POST',
        base + '/wp-json/wp/v2/media',
        raw=data,
        headers={
            'Content-Type': 'image/webp',
            'Content-Disposition': f'attachment; filename="{filename}"',
        },
    )
    if not (200 <= code < 300):
        raise RuntimeError(f'media upload failed http={code}')
    return int(obj.get('id') or 0), str(obj.get('source_url') or '')


def delete_media(attachment_id):
    code, _ = api('DELETE', f'{base}/wp-json/wp/v2/media/{attachment_id}?force=true', timeout=120)
    return 200 <= code < 300


def cleanup_uploaded(uploaded_ids):
    failures = []
    for attachment_id in reversed(uploaded_ids):
        if not delete_media(attachment_id):
            failures.append(attachment_id)
    return failures


def read_media(attachment_id):
    return api(
        'GET',
        f'{base}/wp-json/wp/v2/media/{attachment_id}?context=edit&_fields=id,parent,source_url,mime_type,alt_text,media_details',
    )


def read_product(product_id):
    return api('GET', f'{base}/wp-json/wc/v3/products/{product_id}')


diagnostic = json.loads(DIAGNOSTIC.read_text(encoding='utf-8'))
items = diagnostic.get('items') or []
if len(items) != 7:
    raise SystemExit(f'Expected exactly 7 skipped gallery items, found {len(items)}')

prepared = []
uploaded = []
try:
    for item in items:
        product_id = int(item.get('product_id') or 0)
        old_id = int(item.get('old_attachment_id') or 0)
        if product_id <= 0 or old_id <= 0:
            raise RuntimeError('invalid product or attachment id')

        product_code, product = read_product(product_id)
        if not (200 <= product_code < 300 and isinstance(product, dict)):
            raise RuntimeError(f'product {product_id} read failed http={product_code}')
        if str(product.get('status') or '') != 'publish':
            raise RuntimeError(f'product {product_id} is not publish')
        images = list(product.get('images') or [])
        positions = [i for i, image in enumerate(images) if int(image.get('id') or 0) == old_id]
        if len(positions) != 1:
            raise RuntimeError(f'{product_id}:{old_id} occurrence={len(positions)}')
        position = positions[0]
        if position == 0:
            raise RuntimeError(f'{product_id}:{old_id} is primary, expected gallery')

        media_code, old_media = read_media(old_id)
        if not (200 <= media_code < 300 and isinstance(old_media, dict)):
            raise RuntimeError(f'media {old_id} read failed http={media_code}')
        mime = str(old_media.get('mime_type') or '').lower()
        source_url = str(old_media.get('source_url') or '')
        if mime not in ('image/jpeg', 'image/png') or not source_url:
            raise RuntimeError(f'{product_id}:{old_id} source mime/url invalid')

        raw = get_bytes(source_url)
        data, width, height, score, mode, exact, saving = encode_webp(raw, mime)
        filename = f'k20-p{product_id}-a{old_id}-gallery-meta-rescue.webp'
        new_id, new_url = upload(filename, data)
        if new_id <= 0 or not new_url:
            raise RuntimeError(f'{product_id}:{old_id} invalid upload result')
        uploaded.append(new_id)

        new_code, new_media = read_media(new_id)
        details = (new_media or {}).get('media_details') or {}
        if not (200 <= new_code < 300 and str((new_media or {}).get('mime_type') or '').lower() == 'image/webp'):
            raise RuntimeError(f'{product_id}:{old_id} new media verification failed')
        if int(details.get('width') or 0) != width or int(details.get('height') or 0) != height:
            raise RuntimeError(f'{product_id}:{old_id} new media dimension mismatch')

        public = head(new_url)
        if not (200 <= public['status'] < 400 and 'image/webp' in public['content_type'].lower()):
            raise RuntimeError(f'{product_id}:{old_id} public WebP verification failed')

        alt = str((old_media or {}).get('alt_text') or images[position].get('alt') or product.get('name') or '')
        if alt:
            alt_code, _ = api('POST', f'{base}/wp-json/wp/v2/media/{new_id}', body={'alt_text': alt})
            if not (200 <= alt_code < 300):
                raise RuntimeError(f'{product_id}:{old_id} ALT update failed http={alt_code}')

        prepared.append({
            'key': f'{product_id}:{old_id}',
            'product_id': product_id,
            'old_attachment_id': old_id,
            'new_attachment_id': new_id,
            'position': position,
            'original_image_ids': [int(image.get('id') or 0) for image in images],
            'source_url': source_url,
            'new_url': new_url,
            'mime_before': mime,
            'original_bytes': len(raw),
            'webp_bytes': len(data),
            'saving_pct': saving,
            'psnr_db': score,
            'pixel_exact': exact,
            'encoder_mode': mode,
            'width': width,
            'height': height,
            'alt_text': alt,
            'public_head': public,
        })
except Exception as error:
    cleanup_failures = cleanup_uploaded(uploaded)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'executed_at_utc': now_iso(),
        'status': 'failed_rolled_back' if not cleanup_failures else 'failed_cleanup_incomplete',
        'error': str(error),
        'uploaded_ids': uploaded,
        'cleanup_failures': cleanup_failures,
        'items_prepared_before_failure': len(prepared),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    raise

result = {
    'executed_at_utc': now_iso(),
    'status': 'prepared',
    'read_only_gallery': True,
    'site_effect': 'uploads verified WebP replacement attachments only; product gallery metadata is unchanged',
    'prepared_count': len(prepared),
    'items': prepared,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': result['status'], 'prepared_count': len(prepared)}, ensure_ascii=False))
