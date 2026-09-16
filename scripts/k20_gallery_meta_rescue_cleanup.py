import base64
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
PREPARED = ROOT / 'gallery-meta-rescue' / 'prepared.json'
OUT = ROOT / 'gallery-meta-rescue' / 'cleanup.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(
    f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()
).decode()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%'), p.query, p.fragment))


def api(method, url, timeout=120):
    req = urllib.request.Request(qurl(url), method=method, headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Gallery-Meta-Rescue-Cleanup/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            try:
                obj = json.loads(raw) if raw else {}
            except Exception:
                obj = {'raw': raw[:500]}
            return int(r.status), obj
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:500]}
        return int(e.code), obj


prepared = json.loads(PREPARED.read_text(encoding='utf-8'))
if prepared.get('status') != 'prepared':
    raise SystemExit('prepared.json status is not prepared')
items = prepared.get('items') or []
if len(items) != 7:
    raise SystemExit(f'Expected 7 prepared items, found {len(items)}')

rows = []
for item in items:
    new_id = int(item.get('new_attachment_id') or 0)
    product_id = int(item.get('product_id') or 0)
    old_id = int(item.get('old_attachment_id') or 0)
    if new_id <= 0 or product_id <= 0 or old_id <= 0:
        raise SystemExit('invalid prepared mapping')

    code, media = api('GET', f'{base}/wp-json/wp/v2/media/{new_id}?context=edit&_fields=id,parent,source_url,mime_type')
    if code == 404:
        rows.append({'new_attachment_id': new_id, 'already_absent': True, 'deleted': True})
        continue
    if not (200 <= code < 300 and isinstance(media, dict)):
        raise SystemExit(f'prepared attachment {new_id} cannot be inspected http={code}')

    parent = int(media.get('parent') or 0)
    mime = str(media.get('mime_type') or '').lower()
    url = str(media.get('source_url') or '')
    filename = pathlib.PurePosixPath(urllib.parse.urlsplit(url).path).name
    expected = f'k20-p{product_id}-a{old_id}-gallery-meta-rescue'
    if parent != 0 or mime != 'image/webp' or not filename.startswith(expected):
        raise SystemExit(f'cleanup guard failed for attachment {new_id}')

    product_code, product = api('GET', f'{base}/wp-json/wc/v3/products/{product_id}')
    if not (200 <= product_code < 300 and isinstance(product, dict)):
        raise SystemExit(f'product {product_id} read failed before cleanup')
    live_ids = [int(x.get('id') or 0) for x in (product.get('images') or [])]
    if new_id in live_ids:
        raise SystemExit(f'cleanup blocked: attachment {new_id} is live on product {product_id}')

    delete_code, _ = api('DELETE', f'{base}/wp-json/wp/v2/media/{new_id}?force=true')
    if not (200 <= delete_code < 300):
        raise SystemExit(f'delete failed attachment={new_id} http={delete_code}')
    check_code, _ = api('GET', f'{base}/wp-json/wp/v2/media/{new_id}?context=edit&_fields=id')
    if check_code != 404:
        raise SystemExit(f'delete readback failed attachment={new_id} http={check_code}')
    rows.append({'new_attachment_id': new_id, 'already_absent': False, 'deleted': True})

result = {
    'executed_at_utc': now_iso(),
    'status': 'cleaned',
    'deleted_count': sum(1 for x in rows if x.get('deleted')),
    'items': rows,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': result['status'], 'deleted_count': result['deleted_count']}, ensure_ascii=False))
