import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
SITEWIDE = ROOT / 'sitewide-media-results' / 'inventory.json'
CONTENT = ROOT / 'content-media-results' / 'inventory.json'
REST_STATE = ROOT / 'media-rest-rescue' / 'state.json'
CATEGORY_STATE = ROOT / 'category-image-autopilot' / 'state.json'
SITEWIDE_STATE = ROOT / 'sitewide-media-autopilot' / 'state.json'
OPS = ROOT / 'media-cleanup-plan-ops'
OUT = ROOT / 'media-cleanup-plan' / 'plan.json'


def load(path):
    if not path.exists():
        raise SystemExit(f'Missing required file: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def parse_iso(value):
    text = str(value or '').strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def latest_request():
    rows = sorted(OPS.glob('*.json'), key=lambda p: p.stat().st_mtime)
    if not rows:
        return {}
    return json.loads(rows[-1].read_text(encoding='utf-8'))


sitewide = load(SITEWIDE)
content = load(CONTENT)
rest = load(REST_STATE)
category = load(CATEGORY_STATE)
sitewide_state = load(SITEWIDE_STATE)
request = latest_request()

site_summary = sitewide.get('summary') or {}
content_summary = content.get('summary') or {}
content_coverage = content_summary.get('coverage') or {}
post_types = site_summary.get('post_types') or {}
page_stats = post_types.get('page') or {}

coverage_errors = []
if int(site_summary.get('products_read') or 0) <= 0:
    coverage_errors.append('sitewide products_read is zero')
if site_summary.get('product_error'):
    coverage_errors.append('sitewide product REST error present')
if int(site_summary.get('product_categories_read') or 0) <= 0:
    coverage_errors.append('sitewide product_categories_read is zero')
if site_summary.get('category_error'):
    coverage_errors.append('sitewide category REST error present')
if int(site_summary.get('sitemaps_read') or 0) <= 0:
    coverage_errors.append('sitewide sitemaps_read is zero')
if int(site_summary.get('sitemap_failures') or 0) != 0:
    coverage_errors.append('sitewide sitemap failures present')
if int(site_summary.get('public_urls_discovered') or 0) <= 0:
    coverage_errors.append('sitewide public_urls_discovered is zero')
if int(site_summary.get('rendered_pages_read') or 0) <= 0:
    coverage_errors.append('sitewide rendered_pages_read is zero')
if int(site_summary.get('rendered_pages_failed') or 0) != 0:
    coverage_errors.append('sitewide rendered crawl failures present')
if site_summary.get('crawl_complete') is not True:
    coverage_errors.append('sitewide crawl is not complete')
if int(site_summary.get('rendered_pages_read') or 0) != int(site_summary.get('public_urls_discovered') or 0):
    coverage_errors.append('sitewide rendered coverage count mismatch')
if int(page_stats.get('posts_read') or 0) <= 0 or page_stats.get('error'):
    coverage_errors.append('sitewide page coverage incomplete')
for name, info in sorted(post_types.items()):
    if (info or {}).get('error'):
        coverage_errors.append(f'sitewide post type error: {name}')
if int(content_coverage.get('pages_read') or 0) <= 0:
    coverage_errors.append('content pages_read is zero')
if content_coverage.get('post_errors'):
    coverage_errors.append('content post REST errors present')
if int(content_coverage.get('products_read') or 0) <= 0:
    coverage_errors.append('content products_read is zero')
if int(content_coverage.get('categories_read') or 0) <= 0:
    coverage_errors.append('content categories_read is zero')
if int(content_coverage.get('public_urls_collected') or 0) <= 0:
    coverage_errors.append('content public_urls_collected is zero')
if int(content_coverage.get('public_pages_read') or 0) <= 0:
    coverage_errors.append('content public_pages_read is zero')

migration_times = [
    parse_iso(rest.get('updated_at_utc')),
    parse_iso(category.get('updated_at_utc')),
    parse_iso(sitewide_state.get('updated_at_utc')),
]
migration_times = [x for x in migration_times if x]
latest_migration = max(migration_times) if migration_times else None
for label, summary in (('sitewide', site_summary), ('content', content_summary)):
    inv_time = parse_iso(summary.get('executed_at_utc'))
    if not inv_time:
        coverage_errors.append(f'{label} inventory timestamp missing')
    elif latest_migration and inv_time < latest_migration:
        coverage_errors.append(f'{label} inventory predates migration state')

if coverage_errors:
    raise SystemExit('Cleanup plan blocked: ' + '; '.join(coverage_errors))

candidates = set()
sources = {}

for key in (rest.get('processed') or {}):
    try:
        _, old = [int(x) for x in str(key).split(':', 1)]
    except Exception:
        continue
    candidates.add(old)
    sources.setdefault(old, set()).add('product_rest_rescue')

for old in (category.get('migrations') or {}):
    try:
        old_id = int(old)
    except Exception:
        continue
    candidates.add(old_id)
    sources.setdefault(old_id, set()).add('category_image_autopilot')

for old in (sitewide_state.get('processed_attachment_ids') or []):
    try:
        old_id = int(old)
    except Exception:
        continue
    if old_id <= 0:
        continue
    candidates.add(old_id)
    sources.setdefault(old_id, set()).add('sitewide_media_autopilot')

for old in (request.get('extra_candidate_ids') or []):
    try:
        old_id = int(old)
    except Exception:
        continue
    if old_id <= 0:
        continue
    candidates.add(old_id)
    sources.setdefault(old_id, set()).add('explicit_verified_migration')

protected = set()
for key in (rest.get('skipped') or {}):
    try:
        _, old = [int(x) for x in str(key).split(':', 1)]
        protected.add(old)
    except Exception:
        pass
for old in (request.get('protected_ids') or []):
    try:
        protected.add(int(old))
    except Exception:
        pass

site_items = {int(x.get('attachment_id') or 0): x for x in (sitewide.get('items') or [])}
content_items = {int(x.get('attachment_id') or 0): x for x in (content.get('items') or [])}

eligible = []
blocked = []
already_absent = []
for aid in sorted(candidates):
    s = site_items.get(aid)
    c = content_items.get(aid)
    if s is None:
        already_absent.append({'attachment_id': aid, 'sources': sorted(sources.get(aid) or [])})
        continue
    site_refs = int(s.get('reference_count') or 0)
    content_refs = int((c or {}).get('reference_count') or 0)
    fmt = str(s.get('format') or '').lower()
    parent = int(s.get('parent') or 0)
    row = {
        'attachment_id': aid,
        'format': fmt,
        'parent': parent,
        'url': str(s.get('url') or ''),
        'sitewide_reference_count': site_refs,
        'content_reference_count': content_refs,
        'sources': sorted(sources.get(aid) or []),
    }
    if aid in protected:
        row['reason'] = 'protected active/skipped reference'
        blocked.append(row)
    elif fmt not in ('jpeg', 'png'):
        row['reason'] = 'not an original jpeg/png candidate'
        blocked.append(row)
    elif parent != 0:
        row['reason'] = 'attachment parent is nonzero'
        blocked.append(row)
    elif site_refs != 0 or content_refs != 0:
        row['reason'] = 'reference count is not zero'
        blocked.append(row)
    else:
        eligible.append(row)

plan = {
    'executed_at_utc': now_iso(),
    'action': 'media.cleanup_plan',
    'read_only': True,
    'latest_migration_state_utc': latest_migration.isoformat().replace('+00:00', 'Z') if latest_migration else None,
    'sitewide_inventory_executed_at_utc': site_summary.get('executed_at_utc'),
    'content_inventory_executed_at_utc': content_summary.get('executed_at_utc'),
    'candidate_count': len(candidates),
    'protected_count': len(protected),
    'eligible_zero_reference_count': len(eligible),
    'blocked_count': len(blocked),
    'already_absent_count': len(already_absent),
    'eligible': eligible,
    'blocked': blocked,
    'already_absent': already_absent,
    'note': 'Read-only plan. No WordPress media was deleted. Eligible means migrated original JPEG/PNG with parent=0, zero references in both fresh inventories, and not protected. Complete sitewide REST/sitemap/render coverage is required before this plan can be produced.'
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: plan[k] for k in ('candidate_count','protected_count','eligible_zero_reference_count','blocked_count','already_absent_count')}, ensure_ascii=False))
