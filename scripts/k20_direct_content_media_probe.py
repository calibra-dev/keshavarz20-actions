import base64
import json
import os
import pathlib
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
SUMMARY = ROOT / 'content-media-results' / 'summary.json'
OUT = ROOT / 'content-media-results' / 'direct-probe.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required secret: {key}')
base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
summary = json.loads(SUMMARY.read_text(encoding='utf-8'))


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def get_json(url):
    req = urllib.request.Request(url, headers={'Authorization': 'Basic ' + auth, 'Accept': 'application/json', 'User-Agent': 'K20-Direct-Content-Probe/1.0'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.status), json.loads(r.read().decode('utf-8', 'replace'))


def get_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'K20-Direct-Content-Probe/1.0'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.status), r.read().decode('utf-8', 'replace')


def occurrences(text, aid, url):
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, separators=(',', ':'))
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path) if url else ''
    basename = path.rsplit('/', 1)[-1] if path else ''
    return {
        'id_token': len(re.findall(rf'(?<!\d){aid}(?!\d)', text)),
        'wp_image_class': text.lower().count(f'wp-image-{aid}'.lower()),
        'exact_url': text.count(url) if url else 0,
        'decoded_path': text.count(path) if path else 0,
        'basename': text.count(basename) if basename else 0,
    }

post_ids = sorted({int(r['object_id']) for item in summary.get('direct_items') or [] for r in item.get('direct_references') or [] if r.get('object_type') == 'post'})
posts = {}
for pid in post_ids:
    url = f'{base}/wp-json/wp/v2/posts/{pid}?context=edit&_fields=id,status,link,content,meta,featured_media'
    try:
        code, obj = get_json(url)
        posts[pid] = {'http': code, 'obj': obj}
    except Exception as e:
        posts[pid] = {'http': 0, 'error': f'{type(e).__name__}: {e}'[:500], 'obj': {}}

rows = []
for item in summary.get('direct_items') or []:
    aid = int(item.get('attachment_id') or 0)
    src = str(item.get('url') or '')
    refs = item.get('direct_references') or []
    object_ids = sorted({int(r.get('object_id') or 0) for r in refs if r.get('object_type') == 'post'})
    for pid in object_ids:
        entry = posts.get(pid) or {}
        obj = entry.get('obj') or {}
        content = obj.get('content') or {}
        raw = str(content.get('raw') or '') if isinstance(content, dict) else ''
        meta = obj.get('meta') or {}
        elem = meta.get('_elementor_data') if isinstance(meta, dict) else None
        if isinstance(elem, (dict, list)):
            elem_text = json.dumps(elem, ensure_ascii=False, separators=(',', ':'))
            elem_json_valid = True
        else:
            elem_text = str(elem or '')
            try:
                json.loads(elem_text) if elem_text else None
                elem_json_valid = bool(elem_text)
            except Exception:
                elem_json_valid = False
        link = str(obj.get('link') or '')
        rendered_http = 0
        rendered = ''
        if link:
            try:
                rendered_http, rendered = get_text(link)
            except Exception:
                rendered_http, rendered = 0, ''
        rows.append({
            'attachment_id': aid,
            'source_url': src,
            'post_id': pid,
            'post_http': int(entry.get('http') or 0),
            'post_status': str(obj.get('status') or ''),
            'link': link,
            'featured_media': int(obj.get('featured_media') or 0),
            'content_counts': occurrences(raw, aid, src),
            'elementor_present': bool(elem_text),
            'elementor_json_valid': elem_json_valid,
            'elementor_counts': occurrences(elem_text, aid, src),
            'rendered_http': rendered_http,
            'rendered_counts': occurrences(rendered, aid, src),
        })

result = {
    'executed_at_utc': now(),
    'action': 'content_media.direct_probe',
    'read_only': True,
    'items': rows,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'rows': len(rows), 'posts': post_ids}, ensure_ascii=False))
