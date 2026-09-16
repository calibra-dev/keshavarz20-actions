import json
import pathlib
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
INVENTORY = ROOT / 'content-media-results' / 'inventory.json'
OUT = ROOT / 'content-media-results' / 'direct-scope.json'

DIRECT_KINDS = {'post_content_raw', 'rest_meta', 'woo_product_description', 'woo_product_short_description', 'woo_category_description'}
RENDER_KINDS = {'rendered_page', 'post_content_rendered'}


def load(path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding='utf-8'))


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def add_mapping(mappings, old_id, new_id, source, confidence='verified_success'):
    try:
        old_id = int(old_id or 0)
        new_id = int(new_id or 0)
    except Exception:
        return
    if old_id <= 0 or new_id <= 0 or old_id == new_id:
        return
    row = mappings.setdefault(old_id, {'new_ids': set(), 'sources': set(), 'confidence': confidence})
    row['new_ids'].add(new_id)
    row['sources'].add(source)
    if row['confidence'] != confidence:
        row['confidence'] = 'mixed'


def walk_success_rows(obj, source, mappings):
    if isinstance(obj, dict):
        old_id = obj.get('old_attachment_id')
        new_id = obj.get('new_attachment_id')
        success = obj.get('success')
        if old_id and new_id and success is True:
            add_mapping(mappings, old_id, new_id, source)
        for value in obj.values():
            walk_success_rows(value, source, mappings)
    elif isinstance(obj, list):
        for value in obj:
            walk_success_rows(value, source, mappings)


inventory = load(INVENTORY)
items = inventory.get('items') or []
source_summary = inventory.get('summary') or {}
coverage = source_summary.get('coverage') or {}

mappings = {}

# Product REST rescue records successful old->new mappings in state.processed.
rest = load(ROOT / 'media-rest-rescue' / 'state.json')
for key, row in (rest.get('processed') or {}).items():
    try:
        _, old_id = [int(x) for x in str(key).split(':', 1)]
    except Exception:
        continue
    add_mapping(mappings, old_id, (row or {}).get('new_attachment_id'), 'product_rest_rescue')

# Category state has authoritative successful migration mappings.
category = load(ROOT / 'category-image-autopilot' / 'state.json')
for old_id, row in (category.get('migrations') or {}).items():
    add_mapping(mappings, old_id, (row or {}).get('new_attachment_id'), 'category_image_autopilot')

# Main product and sitewide autopilots keep per-run success rows with new IDs.
for directory, label in (
    (ROOT / 'media-autopilot-results', 'product_media_autopilot'),
    (ROOT / 'sitewide-media-autopilot-results', 'sitewide_media_autopilot'),
):
    if not directory.exists():
        continue
    for path in sorted(directory.glob('*.json')):
        try:
            walk_success_rows(load(path), label, mappings)
        except Exception:
            continue

# Known direct-content migration evidence may also contain verified old->new rows.
for directory, label in (
    (ROOT / 'gutenberg-direct-media-results', 'gutenberg_direct_media'),
    (ROOT / 'elementor-content-migrate-results', 'elementor_content_media'),
    (ROOT / 'content-direct-convert-results', 'content_direct_convert'),
):
    if not directory.exists():
        continue
    for path in sorted(directory.glob('*.json')):
        try:
            walk_success_rows(load(path), label, mappings)
        except Exception:
            continue

# Terminal source IDs are useful to keep quality-guard skips visible.
terminal = defaultdict(set)
for state_path, label in (
    (ROOT / 'media-autopilot' / 'state.json', 'product_media_autopilot'),
    (ROOT / 'sitewide-media-autopilot' / 'state.json', 'sitewide_media_autopilot'),
    (ROOT / 'category-image-autopilot' / 'state.json', 'category_image_autopilot'),
):
    state = load(state_path)
    for key in (state.get('terminal_skips') or {}):
        raw = str(key)
        try:
            source_id = int(raw.split(':')[-1])
        except Exception:
            continue
        terminal[source_id].add(label)

rows = []
objects = defaultdict(lambda: {
    'attachment_ids': set(),
    'rendered_attachment_ids': set(),
    'known_replacement_ids': set(),
    'unmapped_attachment_ids': set(),
    'terminal_attachment_ids': set(),
    'fields': set(),
})
kind_counts = Counter()

for item in items:
    aid = int(item.get('attachment_id') or 0)
    fmt = str(item.get('format') or '').lower()
    if aid <= 0 or fmt not in ('jpeg', 'png'):
        continue
    refs = item.get('references') or []
    direct_refs = [r for r in refs if str(r.get('kind') or '') in DIRECT_KINDS]
    if not direct_refs:
        continue
    render_refs = [r for r in refs if str(r.get('kind') or '') in RENDER_KINDS]
    rendered = bool(render_refs)

    mapping = mappings.get(aid)
    new_ids = sorted(mapping['new_ids']) if mapping else []
    mapping_status = 'none'
    new_id = None
    if len(new_ids) == 1:
        mapping_status = 'unique'
        new_id = new_ids[0]
    elif len(new_ids) > 1:
        mapping_status = 'ambiguous'

    object_refs = []
    for ref in direct_refs:
        kind = str(ref.get('kind') or '')
        otype = str(ref.get('object_type') or '')
        oid = int(ref.get('object_id') or 0)
        field = str(ref.get('field') or '')
        locator = str(ref.get('locator') or '')
        kind_counts[kind] += 1
        key = f'{otype}:{oid}'
        bucket = objects[key]
        bucket['object_type'] = otype
        bucket['object_id'] = oid
        bucket['locator'] = locator
        bucket['attachment_ids'].add(aid)
        bucket['fields'].add(field)
        if any(
            (str(r.get('object_type') or '') == otype and int(r.get('object_id') or 0) == oid)
            or (locator and str(r.get('locator') or '') == locator)
            for r in render_refs
        ):
            bucket['rendered_attachment_ids'].add(aid)
        if mapping_status == 'unique':
            bucket['known_replacement_ids'].add(aid)
        else:
            bucket['unmapped_attachment_ids'].add(aid)
        if aid in terminal:
            bucket['terminal_attachment_ids'].add(aid)
        object_refs.append({'kind': kind, 'object_type': otype, 'object_id': oid, 'field': field, 'locator': locator})

    rows.append({
        'attachment_id': aid,
        'format': fmt,
        'url': str(item.get('url') or ''),
        'alt_text': str(item.get('alt_text') or ''),
        'rendered': rendered,
        'mapping_status': mapping_status,
        'known_replacement_id': new_id,
        'mapping_candidate_ids': new_ids,
        'mapping_sources': sorted(mapping['sources']) if mapping else [],
        'terminal_sources': sorted(terminal.get(aid) or []),
        'direct_references': object_refs,
        'rendered_locator_sample': [str(r.get('locator') or '') for r in render_refs[:5]],
    })

object_rows = []
for key, bucket in objects.items():
    attachments = sorted(bucket['attachment_ids'])
    object_rows.append({
        'key': key,
        'object_type': bucket['object_type'],
        'object_id': bucket['object_id'],
        'locator': bucket.get('locator') or '',
        'fields': sorted(bucket['fields']),
        'direct_attachment_count': len(attachments),
        'rendered_attachment_count': len(bucket['rendered_attachment_ids']),
        'rendered_attachment_ids': sorted(bucket['rendered_attachment_ids']),
        'known_replacement_count': len(bucket['known_replacement_ids']),
        'unmapped_count': len(bucket['unmapped_attachment_ids']),
        'terminal_count': len(bucket['terminal_attachment_ids']),
        'attachment_ids': attachments,
        'known_replacement_attachment_ids': sorted(bucket['known_replacement_ids']),
        'unmapped_attachment_ids': sorted(bucket['unmapped_attachment_ids']),
        'terminal_attachment_ids': sorted(bucket['terminal_attachment_ids']),
    })
object_rows.sort(key=lambda x: (-x['direct_attachment_count'], x['object_type'], x['object_id']))
rows.sort(key=lambda x: (x['mapping_status'] != 'unique', not x['rendered'], x['attachment_id']))

summary = {
    'executed_at_utc': now_iso(),
    'source_inventory_executed_at_utc': source_summary.get('executed_at_utc'),
    'source_coverage': coverage,
    'direct_jpeg_png_attachments': len(rows),
    'rendered_direct_attachments': sum(1 for x in rows if x['rendered']),
    'not_seen_rendered_direct_attachments': sum(1 for x in rows if not x['rendered']),
    'unique_known_replacement_attachments': sum(1 for x in rows if x['mapping_status'] == 'unique'),
    'ambiguous_replacement_attachments': sum(1 for x in rows if x['mapping_status'] == 'ambiguous'),
    'unmapped_attachments': sum(1 for x in rows if x['mapping_status'] == 'none'),
    'terminal_attachment_count': sum(1 for x in rows if x['terminal_sources']),
    'object_count': len(object_rows),
    'direct_reference_tokens_by_kind': dict(sorted(kind_counts.items())),
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'summary': summary, 'objects': object_rows, 'items': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
