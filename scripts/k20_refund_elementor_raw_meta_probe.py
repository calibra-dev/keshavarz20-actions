import hashlib
import json
import os
import pathlib
import xmlrpc.client
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
user = os.environ['WP_USERNAME']
pw = os.environ['WP_APP_PASSWORD']
server = xmlrpc.client.ServerProxy(base + '/xmlrpc.php', allow_none=True, use_builtin_types=True)


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def count_literal(text, needle):
    return text.count(needle) if text and needle else 0

requests = sorted(REQ_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
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

post = server.wp.getPost(0, user, pw, page_id, ['post_id', 'post_type', 'post_status', 'post_modified_gmt', 'custom_fields'])
if not isinstance(post, dict):
    raise SystemExit('Unexpected XML-RPC response shape.')
if str(post.get('post_type') or '') != 'page':
    raise SystemExit('Target is not a page.')

custom = post.get('custom_fields') or []
entries = []
for field in custom:
    if not isinstance(field, dict) or str(field.get('key') or '') != '_elementor_data':
        continue
    raw = str(field.get('value') or '')
    row = {
        'meta_id': str(field.get('id') or ''),
        'length': len(raw),
        'sha256': sha256(raw),
        'phrase_count': count_literal(raw, phrase),
        'old_h1_count': count_literal(raw, f'<h1>{phrase}</h1>'),
        'new_h2_count': count_literal(raw, f'<h2>{phrase}</h2>'),
        'css_h1_count': count_literal(raw, '.k20-hero h1'),
        'css_h2_count': count_literal(raw, '.k20-hero h2'),
    }
    try:
        parsed = json.loads(raw)
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
        row['root_type'] = None
        row['root_count'] = None
        row['first_item_type'] = None
        row['first_item_keys'] = []
    entries.append(row)

safe_meta = {}
for field in custom:
    if not isinstance(field, dict):
        continue
    key = str(field.get('key') or '')
    if key in ('_elementor_edit_mode', '_elementor_template_type', '_elementor_version'):
        safe_meta[key] = str(field.get('value') or '')[:120]

result = {
    'ok': True,
    'action': 'refund.elementor_raw_meta_probe',
    'read_only': True,
    'page_id': page_id,
    'post_type': str(post.get('post_type') or ''),
    'post_status': str(post.get('post_status') or ''),
    'post_modified_gmt': str(post.get('post_modified_gmt') or ''),
    'elementor_data_entries': len(entries),
    'entries': entries,
    'safe_elementor_meta': safe_meta,
    'raw_elementor_content_persisted': False,
    'executed_at_utc': now(),
}

OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / f'refund-elementor-raw-{req_path.stem}.json'
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'page_id': page_id,
    'entries': len(entries),
    'json_valid_entries': sum(1 for x in entries if x.get('json_valid')),
    'target_h1': sum(int(x.get('old_h1_count') or 0) for x in entries),
    'target_h2': sum(int(x.get('new_h2_count') or 0) for x in entries),
}, ensure_ascii=False))
