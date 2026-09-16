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
OPS = ROOT / 'home-contextual-reuse-ops'
OUTDIR = ROOT / 'home-contextual-reuse-results'
PAGE_ID = 644
PLAN = [
    {'old_id': 139388, 'product_id': 140545, 'new_id': 144642},
    {'old_id': 140408, 'product_id': 140406, 'new_id': 144585},
    {'old_id': 140408, 'product_id': 140407, 'new_id': 144586},
    {'old_id': 140629, 'product_id': 140628, 'new_id': 144678},
    {'old_id': 140629, 'product_id': 140630, 'new_id': 144679},
    {'old_id': 140629, 'product_id': 140631, 'new_id': 144680},
    {'old_id': 142972, 'product_id': 142971, 'new_id': 145073},
]

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
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Home-Contextual-Reuse/1.0',
    }
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


def public_get(url, timeout=120):
    req = urllib.request.Request(qurl(url), headers={
        'User-Agent': 'K20-Home-Contextual-Reuse/1.0',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read().decode('utf-8', 'replace')
    except Exception:
        return 0, ''


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
    head, sep, name = key.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot:
        return key
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return head + '/' + clean if sep else clean


UPLOAD_RE = re.compile(r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)', re.I)


def img_has_old(tag, old_url):
    old = canonical_key(old_url)
    return bool(old and any(canonical_key(m.group(0)) == old for m in UPLOAD_RE.finditer(tag)))


def rewrite_img(tag, old_url, new_url):
    if not img_has_old(tag, old_url):
        raise RuntimeError('target product card image does not contain expected old source')
    tag = re.sub(r'\s+srcset=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
    tag = re.sub(r'\s+sizes=("[^"]*"|\'[^\']*\')', '', tag, flags=re.I)
    tag, count = re.subn(r'\bsrc=("[^"]*"|\'[^\']*\')', lambda m: f'src="{new_url}"', tag, count=1, flags=re.I)
    if count != 1:
        raise RuntimeError('target product card img src replacement count != 1')
    return tag


def changed_request():
    for cmd in (
        ['git','diff-tree','--no-commit-id','--name-only','-r','HEAD','--','home-contextual-reuse-ops'],
        ['git','show','--pretty=','--name-only','HEAD','--','home-contextual-reuse-ops'],
    ):
        try:
            paths = [x.strip() for x in subprocess.check_output(cmd, text=True).splitlines() if x.strip().startswith('home-contextual-reuse-ops/') and x.strip().endswith('.json')]
        except Exception:
            paths = []
        if paths:
            if len(paths) != 1:
                raise SystemExit(f'Expected one request, found {len(paths)}')
            return pathlib.Path(paths[0])
    raise SystemExit('No contextual reuse request found')


request_path = changed_request()
request = json.loads(request_path.read_text(encoding='utf-8'))
if request.get('action') != 'content_media.home_contextual_reuse' or int(request.get('page_id') or 0) != PAGE_ID:
    raise SystemExit('Unsupported request')

result = {
    'executed_at_utc': now_iso(),
    'action': request.get('action'),
    'request_file': request_path.name,
    'page_id': PAGE_ID,
    'success': False,
    'stage': 'start',
    'items': [],
}

page_code, page = api('GET', f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,status,link,content')
if not (200 <= page_code < 300 and isinstance(page, dict) and str(page.get('status') or '') == 'publish'):
    raise SystemExit(f'page precondition failed http={page_code}')
original_raw = (page.get('content') or {}).get('raw') if isinstance(page.get('content'), dict) else ''
if not isinstance(original_raw, str) or not original_raw:
    raise SystemExit('home raw content unavailable')
link = str(page.get('link') or base + '/')
new_raw = original_raw

# Build and verify the complete contextual plan before any write.
for row in PLAN:
    old_id = int(row['old_id']); product_id = int(row['product_id']); new_id = int(row['new_id'])
    oc, old_media = api('GET', f'/wp-json/wp/v2/media/{old_id}?context=edit&_fields=id,source_url,mime_type')
    nc, new_media = api('GET', f'/wp-json/wp/v2/media/{new_id}?context=edit&_fields=id,source_url,mime_type')
    pc, product = api('GET', f'/wp-json/wc/v3/products/{product_id}?_fields=id,name,status,permalink,images')
    if not (200 <= oc < 300 and isinstance(old_media, dict)):
        raise SystemExit(f'old media read failed {old_id}')
    if not (200 <= nc < 300 and isinstance(new_media, dict) and str(new_media.get('mime_type') or '').lower() == 'image/webp'):
        raise SystemExit(f'new media invalid {new_id}')
    if not (200 <= pc < 300 and isinstance(product, dict) and str(product.get('status') or '') == 'publish'):
        raise SystemExit(f'product read failed {product_id}')
    images = [int(x.get('id') or 0) for x in (product.get('images') or [])]
    if not images or images[0] != new_id:
        raise SystemExit(f'product {product_id} primary image is not expected WebP {new_id}')
    old_url = str(old_media.get('source_url') or '')
    new_url = str(new_media.get('source_url') or '')
    permalink = str(product.get('permalink') or '')
    if not old_url or not new_url or not permalink:
        raise SystemExit(f'invalid contextual mapping {old_id}->{new_id}')

    # Match exactly one product card anchor and rewrite only its first image tag.
    card_pattern = re.compile(
        r'(<a\b[^>]*href=["\']' + re.escape(permalink) + r'["\'][^>]*>)(.*?)(</a>)',
        flags=re.I | re.S,
    )
    matches = list(card_pattern.finditer(new_raw))
    if len(matches) != 1:
        raise SystemExit(f'product card count for {product_id} is {len(matches)}')
    match = matches[0]
    inside = match.group(2)
    img_match = re.search(r'<img\b[^>]*>', inside, flags=re.I | re.S)
    if not img_match:
        raise SystemExit(f'product card image missing {product_id}')
    old_tag = img_match.group(0)
    if not img_has_old(old_tag, old_url):
        raise SystemExit(f'product card {product_id} no longer uses expected old media {old_id}')
    new_tag = rewrite_img(old_tag, old_url, new_url)
    inside_new = inside[:img_match.start()] + new_tag + inside[img_match.end():]
    replacement = match.group(1) + inside_new + match.group(3)
    new_raw = new_raw[:match.start()] + replacement + new_raw[match.end():]
    result['items'].append({
        'old_attachment_id': old_id,
        'product_id': product_id,
        'new_attachment_id': new_id,
        'product_name': str(product.get('name') or ''),
        'permalink': permalink,
        'old_url': old_url,
        'new_url': new_url,
    })

# Live public pre-read: every planned product card currently exposes the old source family.
pre_http, pre_html = public_get(link + ('&' if '?' in link else '?') + f'k20_context_pre={int(time.time())}')
if pre_http != 200:
    raise SystemExit(f'public pre-read failed http={pre_http}')
for item in result['items']:
    if item['permalink'] not in pre_html:
        raise SystemExit(f'public product card absent before write {item["product_id"]}')

wrote = False
try:
    uc, _ = api('POST', f'/wp-json/wp/v2/pages/{PAGE_ID}', {'content': new_raw})
    result['update_http'] = uc
    if not 200 <= uc < 300:
        raise RuntimeError(f'page update failed http={uc}')
    wrote = True

    rc, rb = api('GET', f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content')
    rr = (rb.get('content') or {}).get('raw') if isinstance(rb, dict) and isinstance(rb.get('content'), dict) else ''
    if not (200 <= rc < 300 and isinstance(rr, str)):
        raise RuntimeError('raw readback failed')
    for item in result['items']:
        product_pattern = re.compile(r'<a\b[^>]*href=["\']' + re.escape(item['permalink']) + r'["\'][^>]*>(.*?)</a>', re.I | re.S)
        matches = list(product_pattern.finditer(rr))
        if len(matches) != 1:
            raise RuntimeError(f'product card readback count mismatch {item["product_id"]}')
        card = matches[0].group(1)
        if item['new_url'] not in card:
            raise RuntimeError(f'new WebP missing in product card readback {item["product_id"]}')
        if canonical_key(item['old_url']) and any(canonical_key(m.group(0)) == canonical_key(item['old_url']) for m in UPLOAD_RE.finditer(card)):
            raise RuntimeError(f'old image remained in product card readback {item["product_id"]}')

    public_ok = False
    last = {}
    for attempt in range(1, 4):
        hc, html = public_get(link + ('&' if '?' in link else '?') + f'k20_context_verify={int(time.time())}-{attempt}')
        confirmed = 0
        stale = 0
        if hc == 200:
            for item in result['items']:
                pattern = re.compile(r'<a\b[^>]*href=["\']' + re.escape(item['permalink']) + r'["\'][^>]*>(.*?)</a>', re.I | re.S)
                matches = list(pattern.finditer(html))
                if len(matches) != 1:
                    stale += 1
                    continue
                card = matches[0].group(1)
                if item['new_url'] in card:
                    confirmed += 1
                if canonical_key(item['old_url']) and any(canonical_key(m.group(0)) == canonical_key(item['old_url']) for m in UPLOAD_RE.finditer(card)):
                    stale += 1
        last = {'attempt': attempt, 'http': hc, 'confirmed_cards': confirmed, 'stale_cards': stale}
        if hc == 200 and confirmed == len(result['items']) and stale == 0:
            public_ok = True
            break
        time.sleep(2)
    result['public_readback'] = last
    if not public_ok:
        raise RuntimeError('public contextual readback failed')

    result['success'] = True
    result['stage'] = 'verified'
except Exception as error:
    result['stage'] = 'error'
    result['error'] = str(error)
    rollback_ok = True
    if wrote:
        bc, _ = api('POST', f'/wp-json/wp/v2/pages/{PAGE_ID}', {'content': original_raw})
        rollback_ok = 200 <= bc < 300
        result['rollback_http'] = bc
        if rollback_ok:
            vc, vb = api('GET', f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content')
            vr = (vb.get('content') or {}).get('raw') if isinstance(vb, dict) and isinstance(vb.get('content'), dict) else None
            rollback_ok = 200 <= vc < 300 and vr == original_raw
    result['rollback_ok'] = rollback_ok

OUTDIR.mkdir(parents=True, exist_ok=True)
out = OUTDIR / (request_path.stem + '.json')
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'success': result.get('success'), 'stage': result.get('stage'), 'items': len(result['items']), 'error': result.get('error')}, ensure_ascii=False))
if not result.get('success'):
    raise SystemExit(2)
