import base64
import hashlib
import json
import os
import pathlib
import urllib.error
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


def scalar_fingerprint(path, value, phrase):
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
    if 'elementor_data' in path.lower():
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


def collect_elementor(node, path, phrase, out):
    if isinstance(node, dict):
        for key, value in node.items():
            child = f'{path}.{key}' if path else str(key)
            if 'elementor' in str(key).lower():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    out.append(scalar_fingerprint(child, value, phrase))
                else:
                    out.append({
                        'path': child,
                        'type': type(value).__name__,
                        'count': len(value) if isinstance(value, (list, dict)) else None,
                    })
            collect_elementor(value, child, phrase, out)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            collect_elementor(value, f'{path}[{i}]', phrase, out)


def bridge_inspect(page_id):
    body = json.dumps(
        {'mode': 'inspect', 'resource': 'page', 'id': page_id, 'changes': {}},
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')
    request = urllib.request.Request(
        bridge,
        data=body,
        method='POST',
        headers={
            'Authorization': 'Basic ' + auth,
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8',
            'User-Agent': 'K20-Refund-Elementor-Raw-Meta-Probe/2.0',
        },
    )
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

http_code, response = bridge_inspect(page_id)
if http_code < 200 or http_code >= 300:
    raise SystemExit(f'Bridge inspect failed with HTTP {http_code}.')
if not isinstance(response, dict):
    raise SystemExit('Unexpected Bridge response shape.')

before = response.get('before') if isinstance(response.get('before'), dict) else {}
candidates = []
collect_elementor(before, 'before', phrase, candidates)

safe_scalar = {}
for key, value in before.items():
    if key in ('id', 'type', 'post_type', 'status', 'slug', 'modified_gmt') and (
        isinstance(value, (str, int, float, bool)) or value is None
    ):
        safe_scalar[key] = value

result = {
    'ok': True,
    'action': 'refund.elementor_raw_meta_probe',
    'source': 'keshavarz20-ops/v2/execute mode=inspect resource=page',
    'read_only': True,
    'page_id': page_id,
    'bridge_http': http_code,
    'bridge_ok': response.get('ok') is True,
    'response_keys': sorted(str(k) for k in response.keys()),
    'before_keys': sorted(str(k) for k in before.keys()),
    'before_safe_scalar': safe_scalar,
    'elementor_candidates': candidates,
    'raw_elementor_content_persisted': False,
    'executed_at_utc': now(),
}

OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / f'refund-elementor-raw-{req_path.stem}.json'
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'page_id': page_id,
    'bridge_http': http_code,
    'bridge_ok': result['bridge_ok'],
    'before_keys': len(result['before_keys']),
    'elementor_candidates': len(candidates),
}, ensure_ascii=False))
