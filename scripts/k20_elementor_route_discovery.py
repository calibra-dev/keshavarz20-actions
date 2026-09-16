import base64
import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
REQ_DIR = ROOT / 'diagnostics' / 'wp-routes'
OUT_DIR = ROOT / 'results'
EXPECTED_SCOPE = 'elementor'
ALLOWED_EXACT_ROUTES = {'', '/wpvibe/v1/elementor/save-page'}

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required secret: {key}')

base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(
    f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode('utf-8')
).decode('ascii')


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def get_json(url):
    req = urllib.request.Request(
        url,
        method='GET',
        headers={
            'Authorization': 'Basic ' + auth,
            'Accept': 'application/json',
            'User-Agent': 'K20-Elementor-Route-Discovery/1.1',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read().decode('utf-8', 'replace')
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', 'replace')
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {'error_body_length': len(raw)}
        return int(exc.code), payload


requests = sorted(REQ_DIR.glob('*.json'), key=lambda p: p.name, reverse=True)
if not requests:
    raise SystemExit('No route discovery request found.')
req_path = requests[0]
req = json.loads(req_path.read_text(encoding='utf-8'))
scope = str(req.get('scope') or '').strip().lower()
exact_route = str(req.get('exact_route') or '').strip()
if scope != EXPECTED_SCOPE:
    raise SystemExit('This diagnostic is hard-limited to Elementor routes.')
if exact_route not in ALLOWED_EXACT_ROUTES:
    raise SystemExit('Unexpected exact_route.')

code, root = get_json(base + '/wp-json/')
if code != 200 or not isinstance(root, dict):
    raise SystemExit(f'WP REST index failed: HTTP {code}')
routes = root.get('routes') if isinstance(root.get('routes'), dict) else {}
rows = []
for route, spec in sorted(routes.items()):
    if 'elementor' not in str(route).lower():
        continue
    if exact_route and str(route) != exact_route:
        continue
    endpoints = spec.get('endpoints') if isinstance(spec, dict) and isinstance(spec.get('endpoints'), list) else []
    safe_endpoints = []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue
        methods = endpoint.get('methods')
        if isinstance(methods, list):
            safe_methods = [str(x) for x in methods]
        elif isinstance(methods, str):
            safe_methods = [methods]
        else:
            safe_methods = []
        args = endpoint.get('args') if isinstance(endpoint.get('args'), dict) else {}
        safe_args = []
        for name, arg in sorted(args.items()):
            if not isinstance(arg, dict):
                safe_args.append({'name': str(name)})
                continue
            row = {'name': str(name)}
            for key in ('required', 'type', 'format', 'default'):
                value = arg.get(key)
                if isinstance(value, (str, int, float, bool)) or value is None:
                    row[key] = value
            enum = arg.get('enum')
            if isinstance(enum, list) and len(enum) <= 30 and all(isinstance(x, (str, int, float, bool, type(None))) for x in enum):
                row['enum'] = enum
            safe_args.append(row)
        safe_endpoints.append({'methods': safe_methods, 'args': safe_args})
    rows.append({
        'route': str(route),
        'namespace': str(spec.get('namespace') or '') if isinstance(spec, dict) else '',
        'methods': sorted(str(x) for x in (spec.get('methods') or [])) if isinstance(spec, dict) and isinstance(spec.get('methods'), list) else [],
        'endpoints': safe_endpoints,
    })

if exact_route and len(rows) != 1:
    raise SystemExit(f'Expected exactly one matching route, found {len(rows)}.')
result = {
    'ok': True,
    'read_only': True,
    'scope': scope,
    'exact_route': exact_route or None,
    'http': code,
    'route_count': len(rows),
    'routes': rows,
    'request_file': req_path.name,
    'executed_at_utc': now(),
}
OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / f'wp-routes-{req_path.stem}.json'
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'http': code, 'elementor_routes': len(rows), 'exact_route': exact_route or None}, ensure_ascii=False))
