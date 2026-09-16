import base64
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OPS = ROOT / 'content-direct-reuse-ops'
SCOPE = ROOT / 'content-media-results' / 'direct-scope.json'
OUTDIR = ROOT / 'content-direct-reuse-results'
PROTECTED_IDS = {142597}

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
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def api(method, url, body=None, timeout=180):
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Content-Direct-Reuse/1.0',
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(qurl(url), data=data, method=method, headers=headers)
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


def public_get(url, timeout=120):
    req = urllib.request.Request(qurl(url), headers={
        'User-Agent': 'K20-Content-Direct-Reuse/1.0',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read().decode('utf-8', 'replace')
    except Exception:
        return 0, ''


def head(url):
    try:
        req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Content-Direct-Reuse/1.0'})
        with urllib.request.urlopen(req, timeout=90) as r:
            return int(r.status), str(r.headers.get('Content-Type') or ''), int(r.headers.get('Content-Length') or 0)
    except Exception:
        return 0, '', 0


def clear_elementor_cache():
    return api('DELETE', base + '/wp-json/elementor/v1/cache', timeout=180)


def upload_key(url):
    try:
        path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path)
    except Exception:
        return ''
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    return path[pos + len(marker):].lstrip('/') if pos >= 0 else ''


def canonical_key(url_or_key):
    value = str(url_or_key or '')
    key = upload_key(value) if '/wp-content/uploads/' in value else urllib.parse.unquote(value).lstrip('/')
    head, sep, name = key.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot:
        return key
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return head + '/' + clean if sep else clean


UPLOAD_RE = re.compile(
    r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)',
    re.I,
)


def replace_upload_urls(text, old_url, new_url):
    old_canon = canonical_key(old_url)
    if not old_canon:
        return text, 0
    count = 0
    def repl(match):
        nonlocal count
        if canonical_key(match.group(0)) == old_canon:
            count += 1
            return new_url
        return match.group(0)
    return UPLOAD_RE.sub(repl, text), count


def replace_refs(text, old_id, old_url, new_id, new_url):
    if not isinstance(text, str) or not text:
        return text, {'url': 0, 'class': 0, 'id': 0}
    counts = {'url': 0, 'class': 0, 'id': 0}

    # Remove stale responsive variants on img tags that reference this source before URL substitution.
    old_canon = canonical_key(old_url)
    img_re = re.compile(r'<img\b[^>]*>', re.I)
    def img_repl(match):
        tag = match.group(0)
        tag_has_old = f'wp-image-{old_id}' in tag
        if not tag_has_old:
            for found in UPLOAD_RE.finditer(tag):
                if canonical_key(found.group(0)) == old_canon:
                    tag_has_old = True
                    break
        if not tag_has_old:
            return tag
        tag = re.sub(r'\s+srcset=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
        tag = re.sub(r'\s+sizes=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
        return tag
    text = img_re.sub(img_repl, text)

    before = text.count(f'wp-image-{old_id}')
    if before:
        text = text.replace(f'wp-image-{old_id}', f'wp-image-{new_id}')
        counts['class'] += before

    text, url_count = replace_upload_urls(text, old_url, new_url)
    counts['url'] += url_count

    patterns = [
        re.compile(rf'((?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?){old_id}(["\']?)', re.I),
    ]
    for pattern in patterns:
        text, n = pattern.subn(rf'\g<1>{new_id}\2', text)
        counts['id'] += n
    return text, counts


def has_old_ref(text, old_id, old_url):
    if not isinstance(text, str) or not text:
        return False
    if f'wp-image-{old_id}' in text:
        return True
    if re.search(rf'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?{old_id}\b', text):
        return True
    old_canon = canonical_key(old_url)
    if old_canon:
        for match in UPLOAD_RE.finditer(text):
            if canonical_key(match.group(0)) == old_canon:
                return True
    return False


def get_media(aid):
    return api('GET', f'{base}/wp-json/wp/v2/media/{aid}?context=edit&_fields=id,parent,source_url,mime_type,media_details,alt_text')


def discover_routes():
    code, types = api('GET', base + '/wp-json/wp/v2/types?context=view')
    if not (200 <= code < 300 and isinstance(types, dict)):
        raise RuntimeError(f'post type discovery failed http={code}')
    routes = {}
    for name, info in types.items():
        if not isinstance(info, dict):
            continue
        rest_base = str(info.get('rest_base') or '').strip('/')
        namespace = str(info.get('rest_namespace') or 'wp/v2').strip('/')
        if rest_base:
            routes[str(name)] = f'{base}/wp-json/{namespace}/{rest_base}'
    return routes


def changed_request():
    for cmd in (
        ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD', '--', 'content-direct-reuse-ops'],
        ['git', 'show', '--pretty=', '--name-only', 'HEAD', '--', 'content-direct-reuse-ops'],
    ):
        try:
            paths = [x.strip() for x in subprocess.check_output(cmd, text=True).splitlines() if x.strip().startswith('content-direct-reuse-ops/') and x.strip().endswith('.json')]
        except Exception:
            paths = []
        if paths:
            if len(paths) != 1:
                raise SystemExit(f'Expected exactly one request, found {len(paths)}')
            return pathlib.Path(paths[0])
    raise SystemExit('No changed direct reuse request found')


scope = json.loads(SCOPE.read_text(encoding='utf-8'))
scope_items = {int(x.get('attachment_id') or 0): x for x in (scope.get('items') or [])}
request_path = changed_request()
request = json.loads(request_path.read_text(encoding='utf-8'))
if request.get('action') != 'content_media.direct_reuse':
    raise SystemExit('Unsupported action')

object_type = str(request.get('object_type') or '')
object_id = int(request.get('object_id') or 0)
attachment_ids = []
for raw in (request.get('attachment_ids') or []):
    aid = int(raw)
    if aid > 0 and aid not in attachment_ids:
        attachment_ids.append(aid)
if object_id <= 0 or object_type not in ('page', 'post'):
    raise SystemExit('Only positive page/post objects are supported')
if not (1 <= len(attachment_ids) <= 30):
    raise SystemExit('attachment_ids must contain 1..30 unique IDs')
if any(aid in PROTECTED_IDS for aid in attachment_ids):
    raise SystemExit('request contains a protected attachment')

routes = discover_routes()
route = routes.get(object_type)
if not route:
    raise SystemExit(f'No REST route for {object_type}')

# Every requested mapping must be unique in the retained scope and reference this exact object.
selected = []
for aid in attachment_ids:
    item = scope_items.get(aid)
    if not item or item.get('mapping_status') != 'unique':
        raise SystemExit(f'attachment {aid} does not have a unique verified replacement')
    direct = item.get('direct_references') or []
    if not any(str(r.get('object_type') or '') == object_type and int(r.get('object_id') or 0) == object_id for r in direct):
        raise SystemExit(f'attachment {aid} does not reference requested object')
    new_id = int(item.get('known_replacement_id') or 0)
    if new_id <= 0:
        raise SystemExit(f'attachment {aid} replacement is invalid')
    selected.append((aid, new_id, bool(item.get('rendered'))))

result = {
    'executed_at_utc': now_iso(),
    'action': request.get('action'),
    'request_file': request_path.name,
    'object_type': object_type,
    'object_id': object_id,
    'requested_attachment_ids': attachment_ids,
    'success': False,
    'stage': 'start',
    'mappings': [],
}

wrote = False
cache_cleared = False
original_raw = ''
original_meta = {}
try:
    code, obj = api('GET', f'{route}/{object_id}?context=edit&_fields=id,status,link,content,meta')
    if not (200 <= code < 300 and isinstance(obj, dict) and str(obj.get('status') or '') == 'publish'):
        raise RuntimeError(f'object precondition failed http={code}')
    link = str(obj.get('link') or '')
    content = obj.get('content') or {}
    original_raw = str(content.get('raw') or '') if isinstance(content, dict) else ''
    meta = obj.get('meta') or {}
    if not isinstance(meta, dict):
        meta = {}
    original_meta = dict(meta)

    # Limit writes to content + Elementor meta. Any other direct meta field is an explicit blocker.
    requested_fields = set()
    for aid in attachment_ids:
        for ref in scope_items[aid].get('direct_references') or []:
            if str(ref.get('object_type') or '') == object_type and int(ref.get('object_id') or 0) == object_id:
                requested_fields.add(str(ref.get('field') or ''))
    unsupported_fields = requested_fields - {'content', '_elementor_data'}
    if unsupported_fields:
        raise RuntimeError('unsupported writable fields: ' + ','.join(sorted(unsupported_fields)))

    original_elem = original_meta.get('_elementor_data')
    if '_elementor_data' in requested_fields and (not isinstance(original_elem, str) or not original_elem):
        raise RuntimeError('Elementor data required but unavailable')

    new_raw = original_raw
    new_elem = original_elem if isinstance(original_elem, str) else ''
    total_mutations = 0
    for old_id, new_id, rendered in selected:
        oc, oldm = get_media(old_id)
        nc, newm = get_media(new_id)
        if not (200 <= oc < 300 and isinstance(oldm, dict)):
            raise RuntimeError(f'old media {old_id} read failed http={oc}')
        if not (200 <= nc < 300 and isinstance(newm, dict)):
            raise RuntimeError(f'new media {new_id} read failed http={nc}')
        old_url = str(oldm.get('source_url') or '')
        new_url = str(newm.get('source_url') or '')
        new_mime = str(newm.get('mime_type') or '').lower()
        if not old_url or not new_url or new_mime != 'image/webp':
            raise RuntimeError(f'media mapping invalid {old_id}->{new_id}')
        hs, hct, hbytes = head(new_url)
        if not (200 <= hs < 400 and 'image/webp' in hct.lower() and hbytes >= 0):
            raise RuntimeError(f'new media public verification failed {new_id}')

        before_present = has_old_ref(new_raw, old_id, old_url) or has_old_ref(new_elem, old_id, old_url)
        if not before_present:
            raise RuntimeError(f'current object no longer contains old reference {old_id}')
        new_raw, raw_counts = replace_refs(new_raw, old_id, old_url, new_id, new_url)
        if new_elem:
            new_elem, meta_counts = replace_refs(new_elem, old_id, old_url, new_id, new_url)
        else:
            meta_counts = {'url': 0, 'class': 0, 'id': 0}
        mutations = sum(raw_counts.values()) + sum(meta_counts.values())
        if mutations <= 0:
            raise RuntimeError(f'no deterministic mutation made for {old_id}')
        total_mutations += mutations
        result['mappings'].append({
            'old_attachment_id': old_id,
            'new_attachment_id': new_id,
            'new_url': new_url,
            'rendered_expected': rendered,
            'raw_mutations': raw_counts,
            'meta_mutations': meta_counts,
        })

    body = {'content': new_raw}
    if '_elementor_data' in requested_fields:
        # Ensure Elementor JSON stays valid before sending it.
        json.loads(new_elem)
        body['meta'] = {'_elementor_data': new_elem}
    uc, _ = api('POST', f'{route}/{object_id}', body)
    result['update_http'] = uc
    if not 200 <= uc < 300:
        raise RuntimeError(f'object update failed http={uc}')
    wrote = True

    rc, rb = api('GET', f'{route}/{object_id}?context=edit&_fields=id,status,link,content,meta')
    if not (200 <= rc < 300 and isinstance(rb, dict)):
        raise RuntimeError('object readback failed')
    rr = (rb.get('content') or {}).get('raw') if isinstance(rb.get('content'), dict) else ''
    rm_obj = rb.get('meta') or {}
    rm = rm_obj.get('_elementor_data') if isinstance(rm_obj, dict) else ''
    if not isinstance(rr, str):
        raise RuntimeError('raw readback invalid')
    if '_elementor_data' in requested_fields:
        if not isinstance(rm, str) or not rm:
            raise RuntimeError('Elementor readback invalid')
        json.loads(rm)

    for mapping in result['mappings']:
        old_id = mapping['old_attachment_id']
        new_id = mapping['new_attachment_id']
        oc, oldm = get_media(old_id)
        nc, newm = get_media(new_id)
        old_url = str((oldm or {}).get('source_url') or '')
        new_url = str((newm or {}).get('source_url') or '')
        if has_old_ref(rr, old_id, old_url) or has_old_ref(rm, old_id, old_url):
            raise RuntimeError(f'old reference remained after readback {old_id}')
        if new_url not in rr and new_url not in rm and f'wp-image-{new_id}' not in rr and f'wp-image-{new_id}' not in rm:
            raise RuntimeError(f'new reference missing after readback {new_id}')

    if '_elementor_data' in requested_fields:
        cc, _ = clear_elementor_cache()
        result['elementor_cache_delete_http'] = cc
        if not 200 <= cc < 300:
            raise RuntimeError(f'Elementor cache purge failed http={cc}')
        cache_cleared = True

    # Public verification is required only for mappings that were observed rendered.
    rendered_mappings = [m for m in result['mappings'] if m['rendered_expected']]
    if rendered_mappings and link:
        public_ok = False
        last = {}
        for attempt in range(1, 4):
            check_url = link + ('&' if '?' in link else '?') + f'k20_direct_reuse_verify={int(time.time())}-{attempt}'
            hc, html = public_get(check_url)
            old_hits = 0
            new_hits = 0
            if hc == 200:
                for mapping in rendered_mappings:
                    old_id = mapping['old_attachment_id']
                    new_id = mapping['new_attachment_id']
                    old_hits += html.count(f'wp-image-{old_id}')
                    if mapping['new_url'] in html or f'wp-image-{new_id}' in html:
                        new_hits += 1
            last = {'attempt': attempt, 'http': hc, 'old_class_hits': old_hits, 'confirmed_new_mappings': new_hits}
            if hc == 200 and old_hits == 0 and new_hits == len(rendered_mappings):
                public_ok = True
                break
            time.sleep(2)
        result['public_readback'] = last
        if not public_ok:
            raise RuntimeError('public page did not confirm all rendered replacements')

    result['success'] = True
    result['stage'] = 'verified'
    result['total_mutations'] = total_mutations
except Exception as error:
    result['stage'] = 'error'
    result['error'] = str(error)
    rollback_ok = True
    if wrote:
        try:
            rollback_body = {'content': original_raw}
            if isinstance(original_meta.get('_elementor_data'), str):
                rollback_body['meta'] = {'_elementor_data': original_meta['_elementor_data']}
            bc, _ = api('POST', f'{route}/{object_id}', rollback_body)
            rollback_ok = 200 <= bc < 300
            result['rollback_http'] = bc
            if rollback_ok and cache_cleared:
                rcc, _ = clear_elementor_cache()
                result['rollback_elementor_cache_delete_http'] = rcc
                rollback_ok = 200 <= rcc < 300
            if rollback_ok:
                vc, vb = api('GET', f'{route}/{object_id}?context=edit&_fields=id,content,meta')
                vr = (vb.get('content') or {}).get('raw') if isinstance(vb, dict) and isinstance(vb.get('content'), dict) else None
                vm_obj = vb.get('meta') or {} if isinstance(vb, dict) else {}
                vm = vm_obj.get('_elementor_data') if isinstance(vm_obj, dict) else None
                rollback_ok = 200 <= vc < 300 and vr == original_raw
                if isinstance(original_meta.get('_elementor_data'), str):
                    rollback_ok = rollback_ok and vm == original_meta.get('_elementor_data')
        except Exception as rollback_error:
            rollback_ok = False
            result['rollback_error'] = str(rollback_error)
    result['rollback_ok'] = rollback_ok

OUTDIR.mkdir(parents=True, exist_ok=True)
out_path = OUTDIR / (request_path.stem + '.json')
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'success': result.get('success'),
    'stage': result.get('stage'),
    'object': f'{object_type}:{object_id}',
    'requested': len(attachment_ids),
    'error': result.get('error'),
}, ensure_ascii=False))
if not result.get('success'):
    raise SystemExit(2)
