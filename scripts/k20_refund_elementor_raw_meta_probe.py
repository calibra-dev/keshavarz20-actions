import base64
import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
REQ_DIR = ROOT / 'diagnostics' / 'refund-elementor-raw'
OUT_DIR = ROOT / 'results'
EXPECTED_ID = 13
EXPECTED_PHRASE = 'شرایط مرجوعی، مغایرت کالا و پیگیری بار در کشاورز بیست'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(
    f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode('utf-8')
).decode('ascii')
bridge = base + '/wp-json/keshavarz20-ops/v2/execute'


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def fingerprint(path, value, phrase, parse_json=False):
    text = str(value or '')
    row = {
        'path': path,
        'type': type(value).__name__,
        'length': len(text),
        'sha256': sha256(text),
        'phrase_count': text.count(phrase),
        'old_h1_count': text.count(f'<h1>{phrase}</h1>'),
        'new_h2_count': text.count(f'<h2>{phrase}</h2>'),
        'css_h1_count': text.count('.k20-hero h1'),
        'css_h2_count': text.count('.k20-hero h2'),
    }
    if parse_json:
        try:
            parsed = json.loads(text)
            row['json_valid'] = True
            row['root_type'] = type(parsed).__name__
            row['root_count'] = len(parsed) if isinstance(parsed, (list, dict)) else None
            if isinstance(parsed, list) and parsed:
                row['first_item_type'] = type(parsed[0]).__name__
                row['first_item_keys'] = sorted(str(k) for k in parsed[0].keys()) if isinstance(parsed[0], dict) else []
            else:
                row['first_item_type'] = None
                row['first_item_keys'] = []
        except Exception as exc:
            row['json_valid'] = False
            row['json_error'] = f'{type(exc).__name__}: {exc}'[:300]
    return row


def request_json(method, url, body=None, user_agent='K20-Refund-Elementor-Raw-Meta-Probe/3.0'):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': user_agent,
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode('utf-8', 'replace')
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', 'replace')
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {'error_body_length': len(raw)}
        return int(exc.code), parsed


def safe_error(obj):
    if not isinstance(obj, dict):
        return {}
    return {
        k: obj.get(k)
        for k in ('code', 'data')
        if k in obj and isinstance(obj.get(k), (str, int, float, bool, dict, list, type(None)))
    }


requests = sorted(REQ_DIR.glob('*.json'), key=lambda p: p.name, reverse=True)
if not requests:
    raise SystemExit('No refund Elementor raw-meta diagnostic request found.')
req_path = requests[0]
req = json.loads(req_path.read_text(encoding='utf-8'))
page_id = int(req.get('id') or 0)
phrase = str(req.get('phrase') or '')
if page_id != EXPECTED_ID:
    raise SystemExit('Diagnostic is hard-limited to page ID 13.')
if phrase != EXPECTED_PHRASE:
    raise SystemExit('Unexpected target phrase.')

rest_url = (
    f'{base}/wp-json/wp/v2/pages/{page_id}?context=edit&'
    + urllib.parse.urlencode({'_fields': 'id,slug,status,modified_gmt,meta'})
)
rest_code, rest_obj = request_json('GET', rest_url)
rest_meta = rest_obj.get('meta') if isinstance(rest_obj, dict) and isinstance(rest_obj.get('meta'), dict) else {}
rest_elementor = None
if '_elementor_data' in rest_meta:
    rest_elementor = fingerprint('rest.meta._elementor_data', rest_meta.get('_elementor_data'), phrase, parse_json=True)

bridge_code, bridge_obj = request_json(
    'POST',
    bridge,
    {'mode': 'inspect', 'resource': 'page', 'id': page_id, 'changes': {}},
)
bridge_before = bridge_obj.get('before') if isinstance(bridge_obj, dict) and isinstance(bridge_obj.get('before'), dict) else {}

result = {
    'ok': True,
    'action': 'refund.elementor_raw_meta_probe',
    'read_only': True,
    'page_id': page_id,
    'rest_narrow': {
        'http': rest_code,
        'ok': 200 <= rest_code < 300,
        'error': safe_error(rest_obj) if not (200 <= rest_code < 300) else {},
        'meta_keys': sorted(str(k) for k in rest_meta.keys()),
        'elementor_data': rest_elementor,
    },
    'bridge': {
        'http': bridge_code,
        'ok': isinstance(bridge_obj, dict) and bridge_obj.get('ok') is True,
        'response_keys': sorted(str(k) for k in bridge_obj.keys()) if isinstance(bridge_obj, dict) else [],
        'before_keys': sorted(str(k) for k in bridge_before.keys()),
        'before_safe_scalar': {
            k: bridge_before.get(k)
            for k in ('id', 'post_type', 'slug', 'status', 'modified_gmt')
            if k in bridge_before and isinstance(bridge_before.get(k), (str, int, float, bool, type(None)))
        },
    },
    'raw_elementor_content_persisted': False,
    'executed_at_utc': now(),
}

OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / f'refund-elementor-raw-{req_path.stem}.json'
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'page_id': page_id,
    'rest_http': rest_code,
    'rest_meta_keys': len(result['rest_narrow']['meta_keys']),
    'rest_elementor_present': rest_elementor is not None,
    'bridge_http': bridge_code,
    'bridge_ok': result['bridge']['ok'],
}, ensure_ascii=False))
