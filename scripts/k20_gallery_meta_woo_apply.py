import base64
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
PLAN = ROOT / 'gallery-meta-rescue' / 'apply-plan.json'
PREPARED = ROOT / 'gallery-meta-rescue' / 'prepared.json'
OPS = ROOT / 'gallery-meta-woo-ops'
OUT = ROOT / 'gallery-meta-rescue' / 'woo-apply.json'
ALLOWED_PRODUCTS = {135311, 135321, 136206, 136209, 136215, 136230}
ALLOWED_KEY = '_product_image_gallery'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')
base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%'), p.query, p.fragment))


def api(method, url, body=None, timeout=180):
    headers = {'Authorization': 'Basic ' + auth, 'Accept': 'application/json', 'User-Agent': 'K20-Gallery-Meta-Woo-Apply/1.0'}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
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
            obj = {'raw': raw[:500]}
        return int(e.code), obj


def changed_request():
    for cmd in (
        ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD', '--', 'gallery-meta-woo-ops'],
        ['git', 'show', '--pretty=', '--name-only', 'HEAD', '--', 'gallery-meta-woo-ops'],
    ):
        try:
            paths = [x.strip() for x in subprocess.check_output(cmd, text=True).splitlines() if x.strip().startswith('gallery-meta-woo-ops/') and x.strip().endswith('.json')]
        except Exception:
            paths = []
        if paths:
            if len(paths) != 1:
                raise SystemExit(f'Expected one request, found {len(paths)}')
            return pathlib.Path(paths[0])
    raise SystemExit('No changed gallery meta Woo request found')


def product_images(pid):
    code, obj = api('GET', f'{base}/wp-json/wc/v3/products/{pid}?_fields=id,status,images')
    ids = [int(x.get('id') or 0) for x in (obj.get('images') or [])] if isinstance(obj, dict) else []
    return code, obj, ids


request_path = changed_request()
request = json.loads(request_path.read_text(encoding='utf-8'))
if request.get('action') != 'gallery_meta_rescue.woo_apply':
    raise SystemExit('Unsupported action')
mode = str(request.get('mode') or '')
if mode not in ('smoke', 'all'):
    raise SystemExit('mode must be smoke or all')
smoke_pid = int(request.get('product_id') or 136206)

plan = json.loads(PLAN.read_text(encoding='utf-8'))
prepared = json.loads(PREPARED.read_text(encoding='utf-8'))
if plan.get('action') != 'gallery_meta_rescue.apply_plan' or plan.get('read_only') is not True:
    raise SystemExit('apply plan is invalid')
if prepared.get('status') != 'prepared' or int(prepared.get('prepared_count') or 0) != 7:
    raise SystemExit('prepared replacements are incomplete')
products = plan.get('products') or []
if {int(x.get('product_id') or 0) for x in products} != ALLOWED_PRODUCTS:
    raise SystemExit('apply plan product set is not allow-listed')
if mode == 'smoke':
    products = [x for x in products if int(x.get('product_id') or 0) == smoke_pid]
    if len(products) != 1 or smoke_pid not in ALLOWED_PRODUCTS:
        raise SystemExit('invalid smoke product')

result = {'executed_at_utc': now_iso(), 'action': request.get('action'), 'mode': mode, 'request_file': request_path.name, 'items': []}
critical = False

for row in products:
    pid = int(row['product_id'])
    before = [int(x) for x in row['expected_woo_images_before']]
    after = [int(x) for x in row['expected_woo_images_after']]
    old_meta = str(row['expected_meta_before'])
    target_meta = str(row['target_meta'])
    item = {'product_id': pid, 'success': False, 'expected_before': before, 'expected_after': after, 'target_meta': target_meta}
    wrote = False
    try:
        code, obj, live_before = product_images(pid)
        item['pre_http'] = code
        item['live_before'] = live_before
        if not (200 <= code < 300 and isinstance(obj, dict) and str(obj.get('status') or '') == 'publish'):
            raise RuntimeError(f'product pre-read failed http={code}')
        if live_before != before:
            raise RuntimeError(f'precondition mismatch live={live_before} expected={before}')

        payload = {'meta_data': [{'key': ALLOWED_KEY, 'value': target_meta}]}
        uc, _ = api('PUT', f'{base}/wp-json/wc/v3/products/{pid}', payload)
        item['update_http'] = uc
        if not 200 <= uc < 300:
            raise RuntimeError(f'gallery meta update failed http={uc}')
        wrote = True

        verified = False
        last_ids = []
        for attempt in range(1, 5):
            if attempt > 1:
                time.sleep(2)
            rc, _, ids = product_images(pid)
            last_ids = ids
            item['readback_http'] = rc
            item['readback_attempts'] = attempt
            if 200 <= rc < 300 and ids == after:
                verified = True
                break
        item['live_after'] = last_ids
        if not verified:
            raise RuntimeError(f'readback did not confirm target gallery: {last_ids}')
        if any(old in last_ids for old in [int(x['old_attachment_id']) for x in row.get('replacements') or []]):
            raise RuntimeError('old gallery attachment remained after verified write')
        item['success'] = True
        item['stage'] = 'verified'
    except Exception as error:
        item['stage'] = 'error'
        item['error'] = str(error)
        rollback_ok = True
        if wrote:
            bc, _ = api('PUT', f'{base}/wp-json/wc/v3/products/{pid}', {'meta_data': [{'key': ALLOWED_KEY, 'value': old_meta}]})
            item['rollback_http'] = bc
            rollback_ok = 200 <= bc < 300
            if rollback_ok:
                for attempt in range(1, 4):
                    if attempt > 1:
                        time.sleep(2)
                    _, _, ids = product_images(pid)
                    if ids == before:
                        break
                else:
                    rollback_ok = False
        item['rollback_ok'] = rollback_ok
        if not rollback_ok:
            critical = True
        result['items'].append(item)
        break
    result['items'].append(item)

result['success_count'] = sum(1 for x in result['items'] if x.get('success'))
result['failed_count'] = sum(1 for x in result['items'] if not x.get('success'))
result['critical_failure'] = critical
result['completed'] = result['failed_count'] == 0 and result['success_count'] == len(products)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'mode': mode, 'success': result['success_count'], 'failed': result['failed_count'], 'critical': critical}, ensure_ascii=False))
if result['failed_count'] or critical:
    raise SystemExit(2)
