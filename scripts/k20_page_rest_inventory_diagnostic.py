import base64
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OUT = ROOT / 'content-media-results' / 'page-rest-diagnostic.json'

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


def api_get(path, params=None, timeout=120):
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(qurl(url), headers={
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'User-Agent': 'K20-Page-REST-Diagnostic/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            try:
                obj = json.loads(raw) if raw else {}
            except Exception:
                obj = {'raw': raw[:1000]}
            return int(r.status), obj, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {'raw': raw[:1000]}
        return int(e.code), obj, dict(e.headers)


def compact_error(obj):
    if isinstance(obj, dict):
        return {
            'code': obj.get('code'),
            'message': obj.get('message'),
            'data': obj.get('data'),
        }
    return {'type': type(obj).__name__}


result = {'executed_at_utc': now_iso(), 'checks': {}, 'sample_pages': []}

checks = [
    ('bulk_edit_any', '/wp-json/wp/v2/pages', {'per_page': 5, 'page': 1, 'context': 'edit', 'status': 'any', '_fields': 'id,status,link'}),
    ('bulk_edit_publish', '/wp-json/wp/v2/pages', {'per_page': 5, 'page': 1, 'context': 'edit', 'status': 'publish', '_fields': 'id,status,link'}),
    ('bulk_view', '/wp-json/wp/v2/pages', {'per_page': 5, 'page': 1, 'context': 'view', '_fields': 'id,status,link'}),
    ('search_pages', '/wp-json/wp/v2/search', {'per_page': 100, 'page': 1, 'subtype': 'page', '_fields': 'id,title,url,subtype'}),
]

search_ids = []
for name, path, params in checks:
    code, obj, headers = api_get(path, params)
    rows = obj if isinstance(obj, list) else []
    result['checks'][name] = {
        'http': code,
        'row_count': len(rows),
        'total': int(headers.get('X-WP-Total') or headers.get('x-wp-total') or 0),
        'total_pages': int(headers.get('X-WP-TotalPages') or headers.get('x-wp-totalpages') or 0),
        'error': None if 200 <= code < 300 else compact_error(obj),
    }
    if name == 'search_pages' and 200 <= code < 300:
        search_ids = [int(row.get('id') or 0) for row in rows if int(row.get('id') or 0) > 0]

for pid in search_ids[:10]:
    edit_code, edit_obj, _ = api_get(f'/wp-json/wp/v2/pages/{pid}', {'context': 'edit', '_fields': 'id,status,link,content,meta'})
    view_code, view_obj, _ = api_get(f'/wp-json/wp/v2/pages/{pid}', {'context': 'view', '_fields': 'id,status,link,content'})
    result['sample_pages'].append({
        'id': pid,
        'edit_http': edit_code,
        'view_http': view_code,
        'edit_has_content': isinstance(edit_obj, dict) and isinstance(edit_obj.get('content'), dict),
        'edit_has_meta': isinstance(edit_obj, dict) and isinstance(edit_obj.get('meta'), dict),
        'view_has_content': isinstance(view_obj, dict) and isinstance(view_obj.get('content'), dict),
        'edit_error': None if 200 <= edit_code < 300 else compact_error(edit_obj),
        'view_error': None if 200 <= view_code < 300 else compact_error(view_obj),
    })

result['summary'] = {
    'search_ids_found': len(search_ids),
    'sample_individual_edit_ok': sum(1 for row in result['sample_pages'] if 200 <= row['edit_http'] < 300),
    'sample_individual_view_ok': sum(1 for row in result['sample_pages'] if 200 <= row['view_http'] < 300),
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result['summary'], ensure_ascii=False))
