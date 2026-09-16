import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
SCOPE = ROOT / 'content-media-results' / 'direct-scope.json'
OUT = ROOT / 'content-media-results' / 'direct-plan.json'
PROTECTED_IDS = {142597}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


scope = json.loads(SCOPE.read_text(encoding='utf-8'))
items = scope.get('items') or []
objects = scope.get('objects') or []
by_id = {int(x.get('attachment_id') or 0): x for x in items}

rows = []
for obj in objects:
    ids = [int(x) for x in (obj.get('attachment_ids') or [])]
    unique = []
    ambiguous = []
    needs_conversion = []
    protected = []
    terminal_unmapped = []
    for aid in ids:
        item = by_id.get(aid) or {}
        if aid in PROTECTED_IDS:
            protected.append(aid)
            continue
        status = str(item.get('mapping_status') or 'none')
        if status == 'unique':
            unique.append(aid)
        elif status == 'ambiguous':
            ambiguous.append(aid)
        else:
            needs_conversion.append(aid)
            if item.get('terminal_sources'):
                terminal_unmapped.append(aid)
    rows.append({
        'key': obj.get('key'),
        'object_type': obj.get('object_type'),
        'object_id': int(obj.get('object_id') or 0),
        'locator': obj.get('locator') or '',
        'fields': obj.get('fields') or [],
        'direct_attachment_count': len(ids),
        'rendered_attachment_count': int(obj.get('rendered_attachment_count') or 0),
        'reuse_ready_count': len(unique),
        'ambiguous_count': len(ambiguous),
        'needs_conversion_count': len(needs_conversion),
        'terminal_unmapped_count': len(terminal_unmapped),
        'protected_count': len(protected),
        'reuse_ready_ids': unique,
        'ambiguous_ids': ambiguous,
        'needs_conversion_ids': needs_conversion,
        'terminal_unmapped_ids': terminal_unmapped,
        'protected_ids': protected,
    })

rows.sort(key=lambda x: (x['reuse_ready_count'] == 0, x['reuse_ready_count'], x['direct_attachment_count'], x['object_id']))
summary = {
    'executed_at_utc': now_iso(),
    'source_scope_executed_at_utc': (scope.get('summary') or {}).get('executed_at_utc'),
    'object_count': len(rows),
    'reuse_ready_attachments': sum(x['reuse_ready_count'] for x in rows),
    'ambiguous_attachments': sum(x['ambiguous_count'] for x in rows),
    'needs_conversion_attachments': sum(x['needs_conversion_count'] for x in rows),
    'terminal_unmapped_attachments': len({aid for x in rows for aid in x['terminal_unmapped_ids']}),
    'protected_attachment_ids': sorted(PROTECTED_IDS & set(by_id)),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'summary': summary, 'objects': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
