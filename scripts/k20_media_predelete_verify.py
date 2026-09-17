import base64
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
PLAN = ROOT / 'media-cleanup-plan' / 'plan.json'
SITEWIDE = ROOT / 'sitewide-media-results' / 'inventory.json'
CONTENT = ROOT / 'content-media-results' / 'inventory.json'
OPS = ROOT / 'media-predelete-ops'
OUT = ROOT / 'media-predelete-results' / 'manifest.json'
MAX_WORKERS = 8


def load(path):
    if not path.exists():
        raise SystemExit(f'Missing required file: {path}')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def latest_request():
    rows = sorted(OPS.glob('*.json'), key=lambda p: p.stat().st_mtime)
    if not rows:
        raise SystemExit('Missing media-predelete request.')
    return json.loads(rows[-1].read_text(encoding='utf-8-sig'))


def wp_get(base, auth_header, attachment_id):
    fields = urllib.parse.quote('id,parent,mime_type,source_url,status', safe=',')
    url = f"{base}/wp-json/wp/v2/media/{attachment_id}?context=edit&_fields={fields}"
    req = urllib.request.Request(url, headers={'Authorization': auth_header, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return int(r.status), json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode('utf-8'))
        except Exception:
            body = {'message': str(e)}
        return int(e.code), body
    except Exception as e:
        return 0, {'message': str(e)}


def encode_http_url(url):
    parts = urllib.parse.urlsplit(str(url or ''))
    path = urllib.parse.quote(parts.path, safe="/%:@-._~!$&'()*+,;=")
    query = urllib.parse.quote(parts.query, safe="=&?/%:@-._~!$'()*+,;")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def head(url):
    encoded_url = encode_http_url(url)
    req = urllib.request.Request(encoded_url, method='HEAD', headers={'Accept': 'image/*,*/*;q=0.8'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {
                'ok': 200 <= int(r.status) < 400,
                'status': int(r.status),
                'content_type': str(r.headers.get('Content-Type') or ''),
                'encoded_url': encoded_url,
            }
    except urllib.error.HTTPError as e:
        return {
            'ok': False,
            'status': int(e.code),
            'content_type': str(e.headers.get('Content-Type') or ''),
            'encoded_url': encoded_url,
        }
    except Exception as e:
        return {
            'ok': False,
            'status': 0,
            'content_type': '',
            'encoded_url': encoded_url,
            'error': str(e),
        }


plan = load(PLAN)
sitewide = load(SITEWIDE)
content = load(CONTENT)
request = latest_request()

if plan.get('action') != 'media.cleanup_plan' or plan.get('read_only') is not True:
    raise SystemExit('Pre-delete verification blocked: cleanup plan is not a read-only cleanup plan.')

site_summary = sitewide.get('summary') or {}
content_summary = content.get('summary') or {}
if site_summary.get('crawl_complete') is not True:
    raise SystemExit('Pre-delete verification blocked: sitewide crawl is not complete.')
if int(site_summary.get('rendered_pages_failed') or 0) != 0:
    raise SystemExit('Pre-delete verification blocked: sitewide crawl has failures.')
if int(site_summary.get('rendered_pages_read') or 0) != int(site_summary.get('public_urls_discovered') or 0):
    raise SystemExit('Pre-delete verification blocked: sitewide coverage mismatch.')

site_items = {int(x.get('attachment_id') or 0): x for x in (sitewide.get('items') or [])}
content_items = {int(x.get('attachment_id') or 0): x for x in (content.get('items') or [])}

protected = set()
for x in (request.get('protected_ids') or []):
    try:
        protected.add(int(x))
    except Exception:
        pass

plan_eligible = plan.get('eligible') or []
if int(plan.get('eligible_zero_reference_count') or 0) != len(plan_eligible):
    raise SystemExit('Pre-delete verification blocked: plan eligible count mismatch.')

base = str(os.environ.get('WP_BASE_URL') or '').rstrip('/')
user = str(os.environ.get('WP_USERNAME') or '')
password = str(os.environ.get('WP_APP_PASSWORD') or '')
if not base or not user or not password:
    raise SystemExit('Required WordPress secrets are missing.')
auth = base64.b64encode(f'{user}:{password}'.encode('utf-8')).decode('ascii')
auth_header = f'Basic {auth}'


def verify_row(row):
    aid = int(row.get('attachment_id') or 0)
    reasons = []
    if aid <= 0:
        reasons.append('invalid attachment id')
    if aid in protected:
        reasons.append('explicitly protected')

    s = site_items.get(aid)
    c = content_items.get(aid)
    if not s:
        reasons.append('missing from sitewide inventory')
    else:
        if int(s.get('reference_count') or 0) != 0:
            reasons.append('sitewide reference count is not zero')
        if int(s.get('parent') or 0) != 0:
            reasons.append('sitewide parent is nonzero')
        if str(s.get('format') or '').lower() not in ('jpeg', 'png'):
            reasons.append('sitewide format is not original jpeg/png')
    if c and int(c.get('reference_count') or 0) != 0:
        reasons.append('content reference count is not zero')

    status, media = wp_get(base, auth_header, aid) if aid > 0 else (0, {})
    live = {
        'http_code': status,
        'id': int(media.get('id') or 0) if isinstance(media, dict) else 0,
        'parent': int(media.get('parent') or 0) if isinstance(media, dict) else 0,
        'mime_type': str(media.get('mime_type') or '') if isinstance(media, dict) else '',
        'source_url': str(media.get('source_url') or '') if isinstance(media, dict) else '',
        'status': str(media.get('status') or '') if isinstance(media, dict) else '',
    }

    if status == 404:
        source_head = head(str(row.get('url') or '')) if row.get('url') else {'ok': False, 'status': 0, 'content_type': ''}
        return 'absent', {
            'attachment_id': aid,
            'plan_url': str(row.get('url') or ''),
            'sitewide_reference_count': int((s or {}).get('reference_count') or 0),
            'content_reference_count': int((c or {}).get('reference_count') or 0),
            'live': live,
            'source_head': source_head,
            'reason': 'WordPress media attachment is already absent (404); no attachment deletion is needed.',
        }

    if status < 200 or status >= 300:
        reasons.append(f'live media read failed ({status})')
    else:
        if live['id'] != aid:
            reasons.append('live media id mismatch')
        if live['parent'] != 0:
            reasons.append('live parent is nonzero')
        if live['mime_type'].lower() not in ('image/jpeg', 'image/png'):
            reasons.append('live mime type is not image/jpeg or image/png')
        if not live['source_url']:
            reasons.append('live source_url is empty')

    source_head = head(live['source_url']) if live['source_url'] else {'ok': False, 'status': 0, 'content_type': ''}
    if live['source_url'] and not source_head.get('ok'):
        reasons.append(f'live source HEAD failed ({source_head.get("status", 0)})')
    if source_head.get('ok') and not str(source_head.get('content_type') or '').lower().startswith('image/'):
        reasons.append('live source content-type is not image/*')

    out = {
        'attachment_id': aid,
        'plan_url': str(row.get('url') or ''),
        'sitewide_reference_count': int((s or {}).get('reference_count') or 0),
        'content_reference_count': int((c or {}).get('reference_count') or 0),
        'live': live,
        'source_head': source_head,
    }
    if reasons:
        out['reasons'] = reasons
        return 'blocked', out
    return 'ready', out


ready = []
already_absent = []
blocked = []
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
    futures = [pool.submit(verify_row, row) for row in plan_eligible]
    for future in as_completed(futures):
        state, row = future.result()
        if state == 'ready':
            ready.append(row)
        elif state == 'absent':
            already_absent.append(row)
        else:
            blocked.append(row)

for rows in (ready, already_absent, blocked):
    rows.sort(key=lambda x: x['attachment_id'])

manifest = {
    'executed_at_utc': now_iso(),
    'action': 'media.predelete_verify',
    'read_only': True,
    'deletion_authorized': False,
    'cleanup_plan_executed_at_utc': plan.get('executed_at_utc'),
    'sitewide_inventory_executed_at_utc': site_summary.get('executed_at_utc'),
    'content_inventory_executed_at_utc': content_summary.get('executed_at_utc'),
    'requested_plan_eligible_count': len(plan_eligible),
    'protected_ids': sorted(protected),
    'ready_for_delete_count': len(ready),
    'already_absent_count': len(already_absent),
    'blocked_at_predelete_count': len(blocked),
    'ready_attachment_ids': [x['attachment_id'] for x in ready],
    'already_absent_attachment_ids': [x['attachment_id'] for x in already_absent],
    'ready': ready,
    'already_absent': already_absent,
    'blocked': blocked,
    'note': 'Read-only pre-delete verification. No attachment was deleted. Unicode media URLs are percent-encoded for HEAD checks. WordPress media 404 responses are classified as already absent, not deletion candidates. Any protected or failed live item remains excluded.',
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'requested_plan_eligible_count': len(plan_eligible),
    'ready_for_delete_count': len(ready),
    'already_absent_count': len(already_absent),
    'blocked_at_predelete_count': len(blocked),
    'protected_ids': sorted(protected),
    'deletion_authorized': False,
}, ensure_ascii=False))
