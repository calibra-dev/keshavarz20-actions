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
SCOPE = ROOT / 'content-media-results' / 'direct-scope.json'
OUT = ROOT / 'content-media-results' / 'ambiguous-probe.json'
TARGET_PAGE_ID = 644

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
        'User-Agent': 'K20-Content-Ambiguous-Probe/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode('utf-8', 'replace')
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode('utf-8', 'replace')
        try:
            body = json.loads(raw)
        except Exception:
            body = {'raw': raw[:500]}
        return int(error.code), body


def compact(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def snippets(text, old_id, old_url, radius=320):
    if not isinstance(text, str) or not text:
        return []
    patterns = []
    if old_url:
        patterns.append(('exact_url', re.compile(re.escape(old_url), re.I)))
    patterns.append(('wp_image_class', re.compile(rf'wp-image-{old_id}(?!\d)', re.I)))
    patterns.append(('exact_id', re.compile(rf'(?<!\d){old_id}(?!\d)')))
    rows = []
    seen = set()
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            if match.start() in seen:
                continue
            seen.add(match.start())
            lo = max(0, match.start() - radius)
            hi = min(len(text), match.end() + radius)
            snippet = compact(text[lo:hi])[:900]
            links = re.findall(r'https?://[^\s"\'<>]+|href=["\']([^"\']+)', snippet, flags=re.I)
            rows.append({
                'kind': kind,
                'offset': match.start(),
                'snippet': snippet,
                'product_id_hints': sorted({int(x) for x in re.findall(r'(?i)(?:product|post|p)[-_=/](\d{4,})', snippet)}),
            })
            if len(rows) >= 8:
                return rows
    return rows


scope = json.loads(SCOPE.read_text(encoding='utf-8'))
ambiguous = [
    item for item in (scope.get('items') or [])
    if str(item.get('mapping_status') or '') == 'ambiguous'
    and any(str(ref.get('object_type') or '') == 'page' and int(ref.get('object_id') or 0) == TARGET_PAGE_ID for ref in (item.get('direct_references') or []))
]

page_code, page = api_get(f'/wp-json/wp/v2/pages/{TARGET_PAGE_ID}', {
    'context': 'edit',
    '_fields': 'id,status,link,content,meta',
})
if not (200 <= page_code < 300 and isinstance(page, dict)):
    raise SystemExit(f'page read failed http={page_code}')
raw_content = (page.get('content') or {}).get('raw') if isinstance(page.get('content'), dict) else ''
meta = page.get('meta') or {}
elementor = meta.get('_elementor_data') if isinstance(meta, dict) and isinstance(meta.get('_elementor_data'), str) else ''

rows = []
for item in ambiguous:
    old_id = int(item.get('attachment_id') or 0)
    old_code, old_media = api_get(f'/wp-json/wp/v2/media/{old_id}', {
        'context': 'edit',
        '_fields': 'id,parent,source_url,mime_type,alt_text,title',
    })
    old_url = str((old_media or {}).get('source_url') or '')
    candidates = []
    for candidate_id in item.get('mapping_candidate_ids') or []:
        candidate_id = int(candidate_id)
        code, media = api_get(f'/wp-json/wp/v2/media/{candidate_id}', {
            'context': 'edit',
            '_fields': 'id,parent,source_url,mime_type,alt_text,title',
        })
        candidates.append({
            'attachment_id': candidate_id,
            'http': code,
            'parent': int((media or {}).get('parent') or 0),
            'source_url': str((media or {}).get('source_url') or ''),
            'mime_type': str((media or {}).get('mime_type') or ''),
            'title': ((media or {}).get('title') or {}).get('raw') if isinstance((media or {}).get('title'), dict) else str((media or {}).get('title') or ''),
        })
    rows.append({
        'old_attachment_id': old_id,
        'old_http': old_code,
        'old_url': old_url,
        'old_parent': int((old_media or {}).get('parent') or 0),
        'alt_text': str(item.get('alt_text') or ''),
        'mapping_candidate_ids': [int(x) for x in (item.get('mapping_candidate_ids') or [])],
        'mapping_sources': item.get('mapping_sources') or [],
        'raw_snippets': snippets(raw_content, old_id, old_url),
        'elementor_snippets': snippets(elementor, old_id, old_url),
        'candidates': candidates,
    })

result = {
    'executed_at_utc': now_iso(),
    'action': 'content_media.ambiguous_probe',
    'read_only': True,
    'page_id': TARGET_PAGE_ID,
    'page_link': str(page.get('link') or ''),
    'ambiguous_count': len(rows),
    'items': rows,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'ambiguous_count': len(rows), 'candidate_count': sum(len(x['candidates']) for x in rows)}, ensure_ascii=False))
