import json
import os
import pathlib
import urllib.parse
import urllib.request
import base64
import xmlrpc.client
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
STATE = ROOT / 'media-rest-rescue' / 'state.json'
OUT = ROOT / 'media-rest-rescue' / 'gallery-xmlrpc-probe.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
user = os.environ['WP_USERNAME']
pw = os.environ['WP_APP_PASSWORD']
auth = base64.b64encode(f'{user}:{pw}'.encode()).decode()
server = xmlrpc.client.ServerProxy(base + '/xmlrpc.php', allow_none=True, use_builtin_types=True)
state = json.loads(STATE.read_text(encoding='utf-8'))


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def woo_get(pid):
    url = f'{base}/wp-json/wc/v3/products/{pid}?_fields=id,status,images'
    req = urllib.request.Request(url, headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Gallery-XMLRPC-Probe/1.0',
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.status), json.loads(r.read().decode('utf-8', 'replace'))

rows = []
for key, meta in sorted((state.get('skipped') or {}).items()):
    if str((meta or {}).get('reason') or '') != 'product readback did not confirm REST rescue':
        continue
    try:
        pid, old = [int(x) for x in key.split(':', 1)]
    except Exception:
        continue
    row = {'key': key, 'product_id': pid, 'old_attachment_id': old, 'read_only': True}
    try:
        code, product = woo_get(pid)
        images = [int(x.get('id') or 0) for x in (product.get('images') or [])] if code == 200 else []
        row['woo_http'] = code
        row['woo_status'] = str(product.get('status') or '') if isinstance(product, dict) else ''
        row['woo_image_ids'] = images
        row['woo_old_positions'] = [i for i, aid in enumerate(images) if aid == old]

        post = getattr(server, 'wp.getPost')(0, user, pw, pid, ['post_id', 'post_type', 'post_status', 'custom_fields'])
        custom = post.get('custom_fields') or [] if isinstance(post, dict) else []
        gallery_fields = []
        thumb_fields = []
        for field in custom:
            if not isinstance(field, dict):
                continue
            k = str(field.get('key') or '')
            slim = {'id': str(field.get('id') or ''), 'key': k, 'value': str(field.get('value') or '')}
            if k == '_product_image_gallery':
                gallery_fields.append(slim)
            elif k == '_thumbnail_id':
                thumb_fields.append(slim)
        row['xmlrpc_post_type'] = str(post.get('post_type') or '') if isinstance(post, dict) else ''
        row['xmlrpc_post_status'] = str(post.get('post_status') or '') if isinstance(post, dict) else ''
        row['gallery_fields'] = gallery_fields
        row['thumbnail_fields'] = thumb_fields
        gallery_ids = []
        for field in gallery_fields:
            for token in str(field.get('value') or '').split(','):
                token = token.strip()
                if token.isdigit():
                    gallery_ids.append(int(token))
        row['xmlrpc_gallery_ids'] = gallery_ids
        row['xmlrpc_old_occurrences'] = gallery_ids.count(old)
        row['woo_gallery_ids'] = images[1:] if images else []
        row['gallery_matches_woo'] = gallery_ids == (images[1:] if images else [])
        row['probe_success'] = True
    except Exception as e:
        row['probe_success'] = False
        row['error'] = f'{type(e).__name__}: {e}'[:500]
    rows.append(row)

result = {
    'executed_at_utc': now(),
    'action': 'media.gallery_xmlrpc_meta_probe',
    'read_only': True,
    'items': rows,
    'all_probe_success': bool(rows) and all(x.get('probe_success') for x in rows),
    'all_gallery_matches_woo': bool(rows) and all(x.get('gallery_matches_woo') for x in rows if x.get('probe_success')),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'items': len(rows), 'all_probe_success': result['all_probe_success'], 'all_gallery_matches_woo': result['all_gallery_matches_woo']}, ensure_ascii=False))
