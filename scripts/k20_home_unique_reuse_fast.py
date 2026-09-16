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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OPS = ROOT / 'home-unique-reuse-ops'
SCOPE = ROOT / 'content-media-results' / 'direct-scope.json'
OUTDIR = ROOT / 'home-unique-reuse-results'
PAGE_ID = 644
PROTECTED_IDS = {142597}

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')
base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def api(method, path_or_url, body=None, timeout=120):
    url = path_or_url if str(path_or_url).startswith('http') else base + path_or_url
    headers = {'Authorization': 'Basic ' + auth, 'Accept': 'application/json', 'User-Agent': 'K20-Home-Unique-Reuse/1.0'}
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
    req = urllib.request.Request(qurl(url), headers={'User-Agent': 'K20-Home-Unique-Reuse/1.0', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read().decode('utf-8', 'replace')
    except Exception:
        return 0, ''


def head(url, timeout=35):
    try:
        req = urllib.request.Request(qurl(url), method='HEAD', headers={'User-Agent': 'K20-Home-Unique-Reuse/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {'status': int(r.status), 'content_type': str(r.headers.get('Content-Type') or ''), 'bytes': int(r.headers.get('Content-Length') or 0)}
    except Exception:
        return {'status': 0, 'content_type': '', 'bytes': 0}


def clear_elementor_cache():
    return api('DELETE', '/wp-json/elementor/v1/cache', timeout=120)


def upload_key(url):
    try:
        path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path)
    except Exception:
        return ''
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    return path[pos + len(marker):].lstrip('/') if pos >= 0 else ''


def canonical_key(url):
    key = upload_key(url)
    head_part, sep, name = key.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot:
        return key
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return head_part + '/' + clean if sep else clean


UPLOAD_RE = re.compile(r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)', re.I)


def has_old_ref(text, old_id, old_url):
    if not isinstance(text, str) or not text:
        return False
    if f'wp-image-{old_id}' in text:
        return True
    if re.search(rf'(?i)(?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?{old_id}\b', text):
        return True
    old = canonical_key(old_url)
    return bool(old and any(canonical_key(m.group(0)) == old for m in UPLOAD_RE.finditer(text)))


def count_old_urls(text, old_url):
    if not isinstance(text, str) or not text:
        return 0
    old = canonical_key(old_url)
    return sum(1 for m in UPLOAD_RE.finditer(text) if old and canonical_key(m.group(0)) == old)


def replace_refs(text, old_id, old_url, new_id, new_url):
    if not isinstance(text, str) or not text:
        return text, {'url': 0, 'class': 0, 'id': 0}
    counts = {'url': 0, 'class': 0, 'id': 0}
    old = canonical_key(old_url)
    img_re = re.compile(r'<img\b[^>]*>', re.I)
    def img_repl(match):
        tag = match.group(0)
        hit = f'wp-image-{old_id}' in tag or any(old and canonical_key(m.group(0)) == old for m in UPLOAD_RE.finditer(tag))
        if hit:
            tag = re.sub(r'\s+srcset=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
            tag = re.sub(r'\s+sizes=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
        return tag
    text = img_re.sub(img_repl, text)
    n = text.count(f'wp-image-{old_id}')
    if n:
        text = text.replace(f'wp-image-{old_id}', f'wp-image-{new_id}')
        counts['class'] += n
    def url_repl(match):
        if old and canonical_key(match.group(0)) == old:
            counts['url'] += 1
            return new_url
        return match.group(0)
    text = UPLOAD_RE.sub(url_repl, text)
    pattern = re.compile(rf'((?:"|\b)(?:id|image_id|attachment_id|thumbnail_id)(?:"|\b)\s*[:=]\s*["\']?){old_id}(["\']?)', re.I)
    text, n = pattern.subn(rf'\g<1>{new_id}\2', text)
    counts['id'] += n
    return text, counts


def changed_request():
    for cmd in (
        ['git','diff-tree','--no-commit-id','--name-only','-r','HEAD','--','home-unique-reuse-ops'],
        ['git','show','--pretty=','--name-only','HEAD','--','home-unique-reuse-ops'],
    ):
        try:
            paths = [x.strip() for x in subprocess.check_output(cmd, text=True).splitlines() if x.strip().startswith('home-unique-reuse-ops/') and x.strip().endswith('.json')]
        except Exception:
            paths = []
        if paths:
            if len(paths) != 1:
                raise SystemExit(f'Expected one request, found {len(paths)}')
            return pathlib.Path(paths[0])
    raise SystemExit('No home unique reuse request found')


scope = json.loads(SCOPE.read_text(encoding='utf-8'))
items = {int(x.get('attachment_id') or 0): x for x in (scope.get('items') or [])}
request_path = changed_request()
request = json.loads(request_path.read_text(encoding='utf-8'))
if request.get('action') != 'content_media.home_unique_reuse' or int(request.get('page_id') or 0) != PAGE_ID:
    raise SystemExit('Unsupported request')
ids = []
for raw in request.get('attachment_ids') or []:
    aid = int(raw)
    if aid > 0 and aid not in ids:
        ids.append(aid)
if not (1 <= len(ids) <= 40):
    raise SystemExit('attachment_ids must contain 1..40 unique IDs')
if any(aid in PROTECTED_IDS for aid in ids):
    raise SystemExit('protected attachment requested')

pairs = []
requested_fields = set()
for old_id in ids:
    item = items.get(old_id)
    if not item or str(item.get('mapping_status') or '') != 'unique':
        raise SystemExit(f'attachment {old_id} is not unique-mapped in retained scope')
    refs = [r for r in (item.get('direct_references') or []) if str(r.get('object_type') or '') == 'page' and int(r.get('object_id') or 0) == PAGE_ID]
    if not refs:
        raise SystemExit(f'attachment {old_id} does not reference home page')
    requested_fields.update(str(r.get('field') or '') for r in refs)
    new_id = int(item.get('known_replacement_id') or 0)
    if new_id <= 0:
        raise SystemExit(f'invalid replacement for {old_id}')
    pairs.append((old_id, new_id))
unsupported_fields = requested_fields - {'content', '_elementor_data'}
if unsupported_fields:
    raise SystemExit('unsupported writable fields: ' + ','.join(sorted(unsupported_fields)))

# Bulk-fetch all old/new media in one REST collection request.
all_media_ids = []
for old_id, new_id in pairs:
    if old_id not in all_media_ids: all_media_ids.append(old_id)
    if new_id not in all_media_ids: all_media_ids.append(new_id)
query = urllib.parse.urlencode({
    'include': ','.join(str(x) for x in all_media_ids),
    'per_page': min(100, len(all_media_ids)),
    'context': 'edit',
    '_fields': 'id,source_url,mime_type',
})
mc, media_rows = api('GET', f'/wp-json/wp/v2/media?{query}')
if not (200 <= mc < 300 and isinstance(media_rows, list)):
    raise SystemExit(f'bulk media read failed http={mc}')
media = {int(x.get('id') or 0): x for x in media_rows}
if any(mid not in media for mid in all_media_ids):
    missing = [mid for mid in all_media_ids if mid not in media]
    raise SystemExit('bulk media missing ids: ' + ','.join(map(str, missing[:20])))

mappings = []
for old_id, new_id in pairs:
    old = media[old_id]; new = media[new_id]
    old_url = str(old.get('source_url') or ''); new_url = str(new.get('source_url') or '')
    if not old_url or not new_url or str(new.get('mime_type') or '').lower() != 'image/webp':
        raise SystemExit(f'invalid media mapping {old_id}->{new_id}')
    mappings.append({'old_attachment_id': old_id, 'new_attachment_id': new_id, 'old_url': old_url, 'new_url': new_url})

# Parallel public HEAD verification of replacement WebPs before any write.
head_results = {}
with ThreadPoolExecutor(max_workers=12) as pool:
    futures = {pool.submit(head, m['new_url']): m['new_attachment_id'] for m in mappings}
    for future in as_completed(futures):
        head_results[futures[future]] = future.result()
for mapping in mappings:
    check = head_results.get(mapping['new_attachment_id']) or {}
    if not (200 <= int(check.get('status') or 0) < 400 and 'image/webp' in str(check.get('content_type') or '').lower()):
        raise SystemExit(f'public WebP HEAD failed {mapping["new_attachment_id"]}')

pc, page = api('GET', f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,status,link,content,meta')
if not (200 <= pc < 300 and isinstance(page, dict) and str(page.get('status') or '') == 'publish'):
    raise SystemExit(f'home page precondition failed http={pc}')
link = str(page.get('link') or base + '/')
original_raw = (page.get('content') or {}).get('raw') if isinstance(page.get('content'), dict) else ''
meta = page.get('meta') or {}
if not isinstance(original_raw, str) or not isinstance(meta, dict):
    raise SystemExit('home page content/meta unavailable')
original_elem = meta.get('_elementor_data') if isinstance(meta.get('_elementor_data'), str) else ''
if '_elementor_data' in requested_fields and not original_elem:
    raise SystemExit('Elementor data required but unavailable')
new_raw = original_raw
new_elem = original_elem

for mapping in mappings:
    old_id = mapping['old_attachment_id']; new_id = mapping['new_attachment_id']
    if not (has_old_ref(new_raw, old_id, mapping['old_url']) or has_old_ref(new_elem, old_id, mapping['old_url'])):
        raise SystemExit(f'current home no longer contains old reference {old_id}')
    new_raw, rc = replace_refs(new_raw, old_id, mapping['old_url'], new_id, mapping['new_url'])
    new_elem, ec = replace_refs(new_elem, old_id, mapping['old_url'], new_id, mapping['new_url']) if new_elem else (new_elem, {'url':0,'class':0,'id':0})
    mapping['raw_mutations'] = rc
    mapping['meta_mutations'] = ec
    if sum(rc.values()) + sum(ec.values()) <= 0:
        raise SystemExit(f'no deterministic mutation {old_id}')
if new_elem:
    json.loads(new_elem)

# Live public pre-read determines actual frontend obligations.
pre_http, pre_html = public_get(link + ('&' if '?' in link else '?') + f'k20_home_unique_pre={int(time.time())}')
if pre_http != 200:
    raise SystemExit(f'public pre-read failed http={pre_http}')
for mapping in mappings:
    old_id = mapping['old_attachment_id']
    class_hits = pre_html.count(f'wp-image-{old_id}')
    url_hits = count_old_urls(pre_html, mapping['old_url'])
    mapping['public_old_class_hits_before'] = class_hits
    mapping['public_old_url_hits_before'] = url_hits
    mapping['public_old_present_before'] = bool(class_hits or url_hits)

result = {
    'executed_at_utc': now_iso(),
    'action': request.get('action'),
    'request_file': request_path.name,
    'page_id': PAGE_ID,
    'success': False,
    'stage': 'start',
    'requested_attachment_ids': ids,
    'mappings': mappings,
}
wrote = False
cache_cleared = False
try:
    body = {'content': new_raw}
    if '_elementor_data' in requested_fields:
        body['meta'] = {'_elementor_data': new_elem}
    uc, _ = api('POST', f'/wp-json/wp/v2/pages/{PAGE_ID}', body)
    result['update_http'] = uc
    if not 200 <= uc < 300:
        raise RuntimeError(f'home update failed http={uc}')
    wrote = True

    rc, rb = api('GET', f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content,meta')
    rr = (rb.get('content') or {}).get('raw') if isinstance(rb, dict) and isinstance(rb.get('content'), dict) else ''
    rm_obj = rb.get('meta') or {} if isinstance(rb, dict) else {}
    rm = rm_obj.get('_elementor_data') if isinstance(rm_obj, dict) and isinstance(rm_obj.get('_elementor_data'), str) else ''
    if not (200 <= rc < 300 and isinstance(rr, str)):
        raise RuntimeError('home readback failed')
    if '_elementor_data' in requested_fields:
        if not rm:
            raise RuntimeError('Elementor readback missing')
        json.loads(rm)
    for mapping in mappings:
        if has_old_ref(rr, mapping['old_attachment_id'], mapping['old_url']) or has_old_ref(rm, mapping['old_attachment_id'], mapping['old_url']):
            raise RuntimeError(f'old reference remained {mapping["old_attachment_id"]}')
        if mapping['new_url'] not in rr and mapping['new_url'] not in rm and f"wp-image-{mapping['new_attachment_id']}" not in rr and f"wp-image-{mapping['new_attachment_id']}" not in rm:
            raise RuntimeError(f'new reference missing {mapping["new_attachment_id"]}')

    if '_elementor_data' in requested_fields:
        cc, _ = clear_elementor_cache(); result['elementor_cache_delete_http'] = cc
        if not 200 <= cc < 300:
            raise RuntimeError(f'Elementor cache purge failed http={cc}')
        cache_cleared = True

    required = [m for m in mappings if m['public_old_present_before']]
    if required:
        public_ok = False; last = {}
        for attempt in range(1, 4):
            hc, html = public_get(link + ('&' if '?' in link else '?') + f'k20_home_unique_verify={int(time.time())}-{attempt}')
            stale = 0; confirmed = 0
            if hc == 200:
                for mapping in mappings:
                    stale += html.count(f"wp-image-{mapping['old_attachment_id']}")
                    stale += count_old_urls(html, mapping['old_url'])
                for mapping in required:
                    if mapping['new_url'] in html or f"wp-image-{mapping['new_attachment_id']}" in html:
                        confirmed += 1
            last = {'attempt': attempt, 'http': hc, 'stale_hits': stale, 'required_new_mappings': len(required), 'confirmed_new_mappings': confirmed}
            if hc == 200 and stale == 0 and confirmed == len(required):
                public_ok = True; break
            time.sleep(2)
        result['public_readback'] = last
        if not public_ok:
            raise RuntimeError('public home readback failed')

    result['success'] = True
    result['stage'] = 'verified'
    result['total_mutations'] = sum(sum(m['raw_mutations'].values()) + sum(m['meta_mutations'].values()) for m in mappings)
except Exception as error:
    result['stage'] = 'error'; result['error'] = str(error)
    rollback_ok = True
    if wrote:
        rb_body = {'content': original_raw}
        if '_elementor_data' in requested_fields:
            rb_body['meta'] = {'_elementor_data': original_elem}
        bc, _ = api('POST', f'/wp-json/wp/v2/pages/{PAGE_ID}', rb_body)
        rollback_ok = 200 <= bc < 300
        result['rollback_http'] = bc
        if rollback_ok and cache_cleared:
            c2, _ = clear_elementor_cache(); rollback_ok = 200 <= c2 < 300
        if rollback_ok:
            vc, vb = api('GET', f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content,meta')
            vr = (vb.get('content') or {}).get('raw') if isinstance(vb, dict) and isinstance(vb.get('content'), dict) else None
            vm_obj = vb.get('meta') or {} if isinstance(vb, dict) else {}
            vm = vm_obj.get('_elementor_data') if isinstance(vm_obj, dict) else None
            rollback_ok = 200 <= vc < 300 and vr == original_raw
            if '_elementor_data' in requested_fields:
                rollback_ok = rollback_ok and vm == original_elem
    result['rollback_ok'] = rollback_ok

OUTDIR.mkdir(parents=True, exist_ok=True)
out = OUTDIR / (request_path.stem + '.json')
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'success': result.get('success'), 'stage': result.get('stage'), 'requested': len(ids), 'error': result.get('error')}, ensure_ascii=False))
if not result.get('success'):
    raise SystemExit(2)
