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
PROBE = ROOT / 'content-media-results' / 'ambiguous-probe.json'
OUT = ROOT / 'content-media-results' / 'ambiguous-product-resolver.json'
PAGE_ID = 644

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


def api_get(path, params=None, timeout=90):
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(qurl(url), headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Ambiguous-Product-Resolver/1.0',
    })
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


def product_from_webp(url):
    m = re.search(r'k20-p(\d+)-a\d+', str(url or ''), flags=re.I)
    return int(m.group(1)) if m else 0


def compact(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


probe = json.loads(PROBE.read_text(encoding='utf-8'))
page_code, page = api_get(f'/wp-json/wp/v2/pages/{PAGE_ID}', {
    'context': 'edit',
    '_fields': 'id,status,link,content,meta',
})
if not (200 <= page_code < 300 and isinstance(page, dict)):
    raise SystemExit(f'page read failed http={page_code}')
raw = (page.get('content') or {}).get('raw') if isinstance(page.get('content'), dict) else ''
if not isinstance(raw, str):
    raw = ''

rows = []
product_cache = {}
for item in probe.get('items') or []:
    old_id = int(item.get('old_attachment_id') or 0)
    candidates = []
    product_ids = []
    for media in item.get('candidates') or []:
        pid = product_from_webp(media.get('source_url'))
        if pid > 0 and pid not in product_ids:
            product_ids.append(pid)
    for pid in product_ids:
        if pid not in product_cache:
            code, product = api_get(f'/wp-json/wc/v3/products/{pid}', {
                '_fields': 'id,name,slug,status,permalink,images',
            })
            product_cache[pid] = {'http': code, 'product': product if isinstance(product, dict) else {}}
        entry = product_cache[pid]
        product = entry['product']
        permalink = str(product.get('permalink') or '')
        name = str(product.get('name') or '')
        link_positions = [m.start() for m in re.finditer(re.escape(permalink), raw, flags=re.I)] if permalink else []
        contexts = []
        for pos in link_positions[:5]:
            snippet = compact(raw[max(0, pos - 900):min(len(raw), pos + 1500)])
            contexts.append(snippet[:2200])
        candidates.append({
            'product_id': pid,
            'http': entry['http'],
            'name': name,
            'slug': str(product.get('slug') or ''),
            'status': str(product.get('status') or ''),
            'permalink': permalink,
            'image_ids': [int(x.get('id') or 0) for x in (product.get('images') or [])],
            'home_link_occurrences': len(link_positions),
            'home_contexts': contexts,
        })
    rows.append({
        'old_attachment_id': old_id,
        'old_url': str(item.get('old_url') or ''),
        'alt_text': str(item.get('alt_text') or ''),
        'mapping_candidate_ids': [int(x) for x in (item.get('mapping_candidate_ids') or [])],
        'candidate_products': candidates,
    })

result = {
    'executed_at_utc': now_iso(),
    'action': 'content_media.ambiguous_product_resolver',
    'read_only': True,
    'page_id': PAGE_ID,
    'items': rows,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'items': len(rows), 'products': len(product_cache)}, ensure_ascii=False))
