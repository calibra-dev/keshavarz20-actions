import base64
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
REQ_DIR = ROOT / 'elementor-wpvibe-repair-ops'
OUT_DIR = ROOT / 'results'
EXPECTED_ACTION = 'refund.elementor_root_wrap_wpvibe'
EXPECTED_ID = 13
EXPECTED_PHRASE = 'شرایط مرجوعی، مغایرت کالا و پیگیری بار در کشاورز بیست'
EXPECTED_BROKEN_SHA256 = '411d1c0bb3ac6038a4effd4758984f99836c72b3864588cd539880d8ff1fb344'
EXPECTED_ROOT_KEYS = {'elType', 'elements', 'id', 'isInner', 'settings'}
SAVE_ROUTE = '/wp-json/wpvibe/v1/elementor/save-page'
REFUND_PATH = '/refund_returns/'
PRODUCT_PATH = '/product/%d8%b4%db%8c%d8%b1-%d9%be%d8%b1%d9%88%d8%a7%d9%86%d9%87-%d8%a7%db%8c-%d9%be%d9%84%db%8c%d9%85%d8%b1%db%8c-%d8%a8%d8%a7-%d8%af%d8%b3%d8%aa%d9%87-%d9%81%d9%84%d8%b2%db%8c-%d9%88%db%8c%d8%b3%d9%be-3/'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(
    f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode('utf-8')
).decode('ascii')


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def semantic_sha(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def api(method, url, body=None, accept='application/json'):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': accept,
        'User-Agent': 'K20-Refund-Elementor-WPVibe-Repair/1.0',
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read().decode('utf-8', 'replace')
            ctype = str(response.headers.get('Content-Type') or '')
            if 'json' in ctype.lower() and raw:
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {}
            else:
                payload = raw
            return int(response.status), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', 'replace')
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {'error_body_length': len(raw)}
        return int(exc.code), payload


def public_get(path):
    url = base + path + ('&' if '?' in path else '?') + 'k20verify=' + str(int(time.time() * 1000))
    req = urllib.request.Request(
        url,
        method='GET',
        headers={
            'Accept': 'text/html,application/xhtml+xml',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'User-Agent': 'K20-Refund-Elementor-WPVibe-Repair-Verify/1.0',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return int(response.status), response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode('utf-8', 'replace')


def narrow_page():
    fields = urllib.parse.urlencode({'_fields': 'id,slug,status,modified_gmt,meta'})
    code, obj = api('GET', f'{base}/wp-json/wp/v2/pages/{EXPECTED_ID}?context=edit&{fields}')
    meta = obj.get('meta') if isinstance(obj, dict) and isinstance(obj.get('meta'), dict) else {}
    raw = meta.get('_elementor_data')
    return code, obj, raw if isinstance(raw, str) else None


def counts(raw):
    return {
        'target_h1': raw.count(f'<h1>{EXPECTED_PHRASE}</h1>'),
        'target_h2': raw.count(f'<h2>{EXPECTED_PHRASE}</h2>'),
        'css_h1': raw.count('.k20-hero h1'),
        'css_h2': raw.count('.k20-hero h2'),
    }


def markup_counts(text):
    return {
        'total_h1': len(re.findall(r'(?is)<h1\b[^>]*>', text)),
        'target_h1': len(re.findall(r'(?is)<h1\b[^>]*>\s*' + re.escape(EXPECTED_PHRASE) + r'\s*</h1>', text)),
        'target_h2': len(re.findall(r'(?is)<h2\b[^>]*>\s*' + re.escape(EXPECTED_PHRASE) + r'\s*</h2>', text)),
    }


def safe_response_summary(payload):
    if not isinstance(payload, dict):
        return {'type': type(payload).__name__}
    out = {'keys': sorted(str(k) for k in payload.keys())}
    for key in ('ok', 'success', 'id', 'post_id', 'status'):
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            if key in payload:
                out[key] = value
    message = payload.get('message')
    if isinstance(message, str):
        out['message'] = message[:300]
    return out


requests = sorted(REQ_DIR.glob('*.json'), key=lambda p: p.name, reverse=True)
if not requests:
    raise SystemExit('No WPVibe Elementor repair request found.')
req_path = requests[0]
req = json.loads(req_path.read_text(encoding='utf-8'))
if str(req.get('action') or '') != EXPECTED_ACTION:
    raise SystemExit('Unexpected repair action.')
if int(req.get('id') or 0) != EXPECTED_ID:
    raise SystemExit('Repair is hard-limited to Page 13.')
if str(req.get('phrase') or '') != EXPECTED_PHRASE:
    raise SystemExit('Unexpected target phrase.')
if str(req.get('expected_sha256') or '') != EXPECTED_BROKEN_SHA256:
    raise SystemExit('Unexpected SHA guard in request.')

result = {
    'ok': False,
    'action': EXPECTED_ACTION,
    'page_id': EXPECTED_ID,
    'save_route': SAVE_ROUTE,
    'request_file': req_path.name,
    'started_at_utc': now(),
    'raw_elementor_content_persisted': False,
}
error_text = None

try:
    code, page, raw = narrow_page()
    if code != 200 or raw is None:
        raise RuntimeError(f'Narrow Page 13 read failed: HTTP {code}')
    before_hash = sha256(raw)
    if before_hash != EXPECTED_BROKEN_SHA256:
        raise RuntimeError(f'Current Elementor SHA changed: {before_hash}')
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError(f'Expected current dict root, found {type(parsed).__name__}')
    if set(parsed.keys()) != EXPECTED_ROOT_KEYS:
        raise RuntimeError(f'Unexpected current root keys: {sorted(parsed.keys())}')
    before_counts = counts(raw)
    if before_counts['target_h1'] != 0 or before_counts['target_h2'] != 1:
        raise RuntimeError(f'Current heading guard failed: {before_counts}')
    if before_counts['css_h1'] != 0 or before_counts['css_h2'] < 1:
        raise RuntimeError(f'Current CSS guard failed: {before_counts}')
    before_semantic = semantic_sha(parsed)

    payload = {'id': EXPECTED_ID, 'data': [parsed]}
    save_code, save_obj = api('POST', base + SAVE_ROUTE, payload)
    result['save_http'] = save_code
    result['save_response'] = safe_response_summary(save_obj)
    if save_code < 200 or save_code >= 300:
        raise RuntimeError(f'WPVibe save-page failed: HTTP {save_code}')

    read_code, read_page, stored = narrow_page()
    if read_code != 200 or stored is None:
        raise RuntimeError(f'Narrow readback failed: HTTP {read_code}')
    stored_parsed = json.loads(stored)
    if not (isinstance(stored_parsed, list) and len(stored_parsed) == 1 and isinstance(stored_parsed[0], dict)):
        raise RuntimeError(f'Readback root is not a one-item list: {type(stored_parsed).__name__}')
    if set(stored_parsed[0].keys()) != EXPECTED_ROOT_KEYS:
        raise RuntimeError('Readback root keys changed unexpectedly.')
    after_semantic = semantic_sha(stored_parsed[0])
    if after_semantic != before_semantic:
        raise RuntimeError('Readback semantic content differs from guarded source object.')
    after_counts = counts(stored)
    if after_counts['target_h1'] != 0 or after_counts['target_h2'] != 1:
        raise RuntimeError(f'Readback heading guard failed: {after_counts}')
    if after_counts['css_h1'] != 0 or after_counts['css_h2'] < 1:
        raise RuntimeError(f'Readback CSS guard failed: {after_counts}')

    cache_code, _ = api('DELETE', base + '/wp-json/elementor/v1/cache')
    result['elementor_cache_http'] = cache_code
    if cache_code < 200 or cache_code >= 300:
        raise RuntimeError(f'Elementor cache clear failed: HTTP {cache_code}')

    time.sleep(3)
    refund_code, refund_html = public_get(REFUND_PATH)
    refund = markup_counts(refund_html)
    product_code, product_html = public_get(PRODUCT_PATH)
    product = markup_counts(product_html)

    result.update({
        'before': {
            'sha256': before_hash,
            'root_type': 'dict',
            'root_keys': sorted(parsed.keys()),
            'semantic_sha256': before_semantic,
            **before_counts,
        },
        'after': {
            'sha256': sha256(stored),
            'root_type': 'list',
            'root_count': len(stored_parsed),
            'root_keys': sorted(stored_parsed[0].keys()),
            'semantic_sha256': after_semantic,
            **after_counts,
        },
        'refund_live': {'http': refund_code, **refund},
        'product_live': {'http': product_code, **product},
    })

    if refund_code != 200 or refund != {'total_h1': 1, 'target_h1': 0, 'target_h2': 1}:
        raise RuntimeError(f'Refund live verification failed: http={refund_code} counts={refund}')
    if product_code != 200 or product['total_h1'] != 1 or product['target_h1'] != 0 or product['target_h2'] < 1:
        raise RuntimeError(f'Product sentinel verification failed: http={product_code} counts={product}')

    result['ok'] = True
except Exception as exc:
    error_text = f'{type(exc).__name__}: {exc}'
    result['error'] = error_text[:1000]
finally:
    result['finished_at_utc'] = now()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f'elementor-wpvibe-repair-{req_path.stem}.json'
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'ok': result.get('ok'),
        'save_http': result.get('save_http'),
        'refund_http': (result.get('refund_live') or {}).get('http'),
        'refund_h1': (result.get('refund_live') or {}).get('total_h1'),
        'refund_target_h2': (result.get('refund_live') or {}).get('target_h2'),
        'product_http': (result.get('product_live') or {}).get('http'),
    }, ensure_ascii=False))

if error_text:
    raise SystemExit(error_text)
