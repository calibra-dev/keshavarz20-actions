import json
import pathlib
import re
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OPS = ROOT / 'diagnostics' / 'schema-organization'
OUT = ROOT / 'results' / 'schema-organization-live.json'


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'K20-Schema-Organization-Probe/1.0', 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.status), r.read().decode('utf-8', 'replace')


def org_nodes(value, path='$'):
    out = []
    if isinstance(value, dict):
        types = value.get('@type')
        type_list = types if isinstance(types, list) else [types]
        if 'Organization' in type_list:
            logo = value.get('logo')
            if isinstance(logo, dict):
                logo = {k: logo.get(k) for k in ('@id', 'url', 'contentUrl', 'width', 'height') if k in logo}
            out.append({
                'path': path,
                '@id': value.get('@id'),
                'name': value.get('name'),
                'url': value.get('url'),
                'logo': logo,
                'sameAs': value.get('sameAs'),
            })
        for key, child in value.items():
            out.extend(org_nodes(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            out.extend(org_nodes(child, f'{path}[{idx}]'))
    return out


def analyze(url):
    status, html = fetch(url)
    scripts = []
    pat = re.compile(r'(?is)<script\b([^>]*)type=["\']application/ld\+json["\']([^>]*)>(.*?)</script>')
    for idx, match in enumerate(pat.finditer(html)):
        attrs = re.sub(r'\s+', ' ', (match.group(1) + ' ' + match.group(2)).strip())[:500]
        raw = match.group(3).strip()
        try:
            data = json.loads(raw)
            err = None
            nodes = org_nodes(data)
        except Exception as exc:
            data = None
            err = f'{type(exc).__name__}: {exc}'[:300]
            nodes = []
        scripts.append({
            'index': idx,
            'attrs': attrs,
            'json_valid': data is not None,
            'parse_error': err,
            'organization_nodes': nodes,
        })
    orgs = []
    for script in scripts:
        for node in script['organization_nodes']:
            orgs.append({'script_index': script['index'], 'script_attrs': script['attrs'], **node})
    return {'url': url, 'http': status, 'ld_json_scripts': len(scripts), 'organization_count': len(orgs), 'organizations': orgs}


requests = sorted(OPS.glob('*.json'), key=lambda p: p.name, reverse=True)
if not requests:
    raise SystemExit('No schema organization diagnostic request found')
req = json.loads(requests[0].read_text(encoding='utf-8'))
if req.get('action') != 'schema.organization_probe':
    raise SystemExit('Unsupported diagnostic action')
urls = [str(x) for x in (req.get('urls') or []) if str(x).startswith('https://keshavarz20.com/')]
if not (1 <= len(urls) <= 3):
    raise SystemExit('Expected 1..3 keshavarz20.com URLs')
result = {'executed_at_utc': now(), 'action': req['action'], 'read_only': True, 'pages': [analyze(url) for url in urls]}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'pages': len(result['pages']), 'organization_counts': [p['organization_count'] for p in result['pages']]}, ensure_ascii=False))
