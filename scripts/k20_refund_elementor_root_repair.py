import base64
import hashlib
import html
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
REQ_DIR = ROOT / 'elementor-root-repair-ops'
OUT_DIR = ROOT / 'results'
EXPECTED_ID = 13
EXPECTED_ACTION = 'refund.elementor_root_wrap'
EXPECTED_PHRASE = 'شرایط مرجوعی، مغایرت کالا و پیگیری بار در کشاورز بیست'
EXPECTED_BROKEN_SHA256 = '411d1c0bb3ac6038a4effd4758984f99836c72b3864588cd539880d8ff1fb344'
EXPECTED_ROOT_KEYS = {'elType', 'elements', 'id', 'isInner', 'settings'}
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


def request(method, url, body=None, accept='application/json'):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': accept,
        'User-Agent': 'K20-Refund-Elementor-Root-Repair/1.0',
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
            payload = raw
        return int(exc.code), payload


def public_get(path):
    sep = '&' if '?' in path else '?'
    url = base + path + sep + 'k20verify=' + str(int(time.time() * 1000))
    req = urllib.request.Request(
        url,
        method='GET',
        headers={
            'Accept': 'text/html,application/xhtml+xml',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'User-Agent': 'K20-Refund-Elementor-Root-Repair-Verify/1.0',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return int(response.status), response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode('utf-8', 'replace')


def markup_counts(text, phrase):
    h1_total = len(re.findall(r'(?is)<h1\b[^>]*>', text))
    h1_target = len(re.findall(r'(?is)<h1\b[^>]*>\s*' + re.escape(phrase) + r'\s*</h1>', text))
    h2_target = len(re.findall(r'(?is)<h2\b[^>]*>\s*' + re.escape(phrase) + r'\s*</h2>', text))
    return {'total_h1': h1_total, 'target_h1': h1_target, 'target_h2': h2_target}


def narrow_page():
    fields = urllib.parse.urlencode({'_fields': 'id,slug,status,modified_gmt,meta'})
    code, obj = request('GET', f'{base}/wp-json/wp/v2/pages/{EXPECTED_ID}?context=edit&{fields}')
    meta = obj.get('meta') if isinstance(obj, dict) and isinstance(obj.get('meta'), dict) else {}
    raw = meta.get('_elementor_data')
    return code, obj, raw if isinstance(raw, str) else None


requests = sorted(REQ_DIR.glob('*.json'), key=lambda p: p.name, reverse=True)
if not requests:
    raise SystemExit('No Elementor root repair request found.')
req_path = requests[0]
req = json.loads(req_path.read_text(encoding='utf-8'))
if str(req.get('action') or '') != EXPECTED_ACTION:
    raise SystemExit('Unexpected repair action.')
if int(req.get('id') or 0) != EXPECTED_ID:
    raise SystemExit('Repair is hard-limited to page ID 13.')
if str(req.get('phrase') or '') != EXPECTED_PHRASE:
    raise SystemExit('Unexpected target phrase.')
if str(req.get('expected_sha256') or '') != EXPECTED_BROKEN_SHA256:
    raise SystemExit('Unexpected expected_sha256 guard.')

result = {
    'ok': False,
    'action': EXPECTED_ACTION,
    'page_id': EXPECTED_ID,
    'request_file': str(req_path),
    'started_at_utc': now(),
}
exit_error = None

try:
    read_code, read_obj, raw = narrow_page()
    if read_code != 200 or raw is None:
        raise RuntimeError(f'Narrow REST read failed: HTTP {read_code}')
    before_hash = sha256(raw)
    parsed = json.loads(raw)
    if before_hash != EXPECTED_BROKEN_SHA256:
        raise RuntimeError(f'Current Elementor hash changed: {before_hash}')
    if not isinstance(parsed, dict):
        raise RuntimeError(f'Expected broken dict root, found {type(parsed).__name__}')
    if set(parsed.keys()) != EXPECTED_ROOT_KEYS:
        raise RuntimeError(f'Unexpected broken root keys: {sorted(parsed.keys())}')
    if raw.count(f'<h1>{EXPECTED_PHRASE}</h1>') != 0:
        raise RuntimeError('Target phrase unexpectedly remains H1 before root repair.')
    if raw.count(f'<h2>{EXPECTED_PHRASE}</h2>') != 1:
        raise RuntimeError('Expected exactly one target H2 before root repair.')
    if raw.count('.k20-hero h1') != 0 or raw.count('.k20-hero h2') < 1:
        raise RuntimeError('Expected patched hero CSS selectors before root repair.')

    wrapped = '[' + raw + ']'
    wrapped_parsed = json.loads(wrapped)
    if not (isinstance(wrapped_parsed, list) and len(wrapped_parsed) == 1 and isinstance(wrapped_parsed[0], dict)):
        raise RuntimeError('Wrapped Elementor payload did not become a one-item root list.')
    if set(wrapped_parsed[0].keys()) != EXPECTED_ROOT_KEYS:
        raise RuntimeError('Wrapped root keys changed unexpectedly.')
    after_hash = sha256(wrapped)

    write_fields = urllib.parse.urlencode({'_fields': 'id,slug,status,modified_gmt,meta'})
    write_code, _ = request(
        'POST',
        f'{base}/wp-json/wp/v2/pages/{EXPECTED_ID}?{write_fields}',
        {'meta': {'_elementor_data': wrapped}},
    )
    if write_code < 200 or write_code >= 300:
        raise RuntimeError(f'Elementor root repair POST failed: HTTP {write_code}')

    verify_code, verify_obj, stored = narrow_page()
    if verify_code != 200 or stored is None:
        raise RuntimeError(f'Narrow REST readback failed: HTTP {verify_code}')
    stored_hash = sha256(stored)
    stored_parsed = json.loads(stored)
    if stored_hash != after_hash:
        raise RuntimeError(f'Readback hash mismatch: expected {after_hash} got {stored_hash}')
    if not (isinstance(stored_parsed, list) and len(stored_parsed) == 1 and isinstance(stored_parsed[0], dict)):
        raise RuntimeError('Readback root is not a one-item list.')
    if stored.count(f'<h1>{EXPECTED_PHRASE}</h1>') != 0 or stored.count(f'<h2>{EXPECTED_PHRASE}</h2>') != 1:
        raise RuntimeError('Readback heading guard failed.')
    if stored.count('.k20-hero h1') != 0 or stored.count('.k20-hero h2') < 1:
        raise RuntimeError('Readback CSS selector guard failed.')

    cache_code, _ = request('DELETE', base + '/wp-json/elementor/v1/cache')
    if cache_code < 200 or cache_code >= 300:
        raise RuntimeError(f'Elementor cache clear failed: HTTP {cache_code}')

    time.sleep(3)
    refund_code, refund_html = public_get(REFUND_PATH)
    refund_counts = markup_counts(refund_html, EXPECTED_PHRASE)
    product_code, product_html = public_get(PRODUCT_PATH)
    product_counts = markup_counts(product_html, EXPECTED_PHRASE)

    result.update({
        'before': {
            'sha256': before_hash,
            'length': len(raw),
            'root_type': 'dict',
            'root_keys': sorted(parsed.keys()),
            'target_h1': raw.count(f'<h1>{EXPECTED_PHRASE}</h1>'),
            'target_h2': raw.count(f'<h2>{EXPECTED_PHRASE}</h2>'),
            'css_h1': raw.count('.k20-hero h1'),
            'css_h2': raw.count('.k20-hero h2'),
        },
        'after': {
            'sha256': stored_hash,
            'length': len(stored),
            'root_type': 'list',
            'root_count': len(stored_parsed),
            'target_h1': stored.count(f'<h1>{EXPECTED_PHRASE}</h1>'),
            'target_h2': stored.count(f'<h2>{EXPECTED_PHRASE}</h2>'),
            'css_h1': stored.count('.k20-hero h1'),
            'css_h2': stored.count('.k20-hero h2'),
        },
        'write_http': write_code,
        'cache_http': cache_code,
        'refund_live': {'http': refund_code, **refund_counts},
        'product_live': {'http': product_code, **product_counts},
    })

    if refund_code != 200:
        raise RuntimeError(f'Refund live page is HTTP {refund_code}')
    if refund_counts != {'total_h1': 1, 'target_h1': 0, 'target_h2': 1}:
        raise RuntimeError(f'Refund live heading verification failed: {refund_counts}')
    if product_code != 200:
        raise RuntimeError(f'Product sentinel is HTTP {product_code}')
    if product_counts['total_h1'] != 1 or product_counts['target_h1'] != 0 or product_counts['target_h2'] < 1:
        raise RuntimeError(f'Product sentinel heading verification failed: {product_counts}')

    result['ok'] = True
except Exception as exc:
    exit_error = f'{type(exc).__name__}: {exc}'
    result['error'] = exit_error[:1000]
finally:
    result['finished_at_utc'] = now()
    result['raw_elementor_content_persisted'] = False
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f'elementor-root-repair-{req_path.stem}.json'
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'ok': result['ok'],
        'page_id': EXPECTED_ID,
        'refund_http': (result.get('refund_live') or {}).get('http'),
        'refund_h1': (result.get('refund_live') or {}).get('total_h1'),
        'refund_target_h2': (result.get('refund_live') or {}).get('target_h2'),
        'product_http': (result.get('product_live') or {}).get('http'),
    }, ensure_ascii=False))

if exit_error:
    raise SystemExit(exit_error)
