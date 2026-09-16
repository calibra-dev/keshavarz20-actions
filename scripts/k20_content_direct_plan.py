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

# Recorded conversion outcomes are separate from the legacy unmapped count.
# A terminal or rolled-back source must not silently enter another conversion batch.
outcomes = {}
for path in sorted((ROOT / 'content-direct-convert-results').glob('*.json')):
    result = json.loads(path.read_text(encoding='utf-8'))
    timestamp = str(result.get('executed_at_utc') or '')
    for item in result.get('items') or []:
        aid = int(item.get('old_attachment_id') or 0)
        if aid and timestamp >= outcomes.get(aid, {}).get('timestamp', ''):
            outcomes[aid] = dict(item, timestamp=timestamp, evidence_file=str(path))

non_rendered_exceptions = set()
exception_path = ROOT / 'content-direct-convert-results' / '20260916-batch04-terminal-exceptions.json'
if exception_path.exists():
    exception = json.loads(exception_path.read_text(encoding='utf-8'))
    attempt = exception.get('conversion_attempt') or {}
    if exception.get('classification') == 'terminal_non_rendered_stale_reference' and attempt.get('rollback_ok') is True:
        non_rendered_exceptions = set(exception.get('attachment_ids') or [])

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
reuse_ids = {aid for x in rows for aid in x['reuse_ready_ids']}
ambiguous_ids = {aid for x in rows for aid in x['ambiguous_ids']}
conversion_ids = {aid for x in rows for aid in x['needs_conversion_ids']}
terminal_ids = {aid for x in rows for aid in x['terminal_unmapped_ids']}
protected_ids = PROTECTED_IDS & set(by_id)
execution = {'ready_for_conversion_ids': [], 'terminal_quality_ids': [],
             'terminal_non_rendered_ids': [], 'blocked_verification_ids': [],
             'blocked_existing_replacement_ids': []}
for aid in sorted(conversion_ids):
    outcome = outcomes.get(aid) or {}
    if outcome.get('success') is True:
        bucket = 'blocked_existing_replacement_ids'
    elif outcome.get('stage') == 'quality_guard' and outcome.get('terminal') is True:
        bucket = 'terminal_quality_ids'
    elif aid in non_rendered_exceptions and not (by_id.get(aid) or {}).get('rendered'):
        bucket = 'terminal_non_rendered_ids'
    elif outcome.get('stage') == 'error':
        bucket = 'blocked_verification_ids'
    else:
        bucket = 'ready_for_conversion_ids'
    execution[bucket].append(aid)
summary = {
    'executed_at_utc': now_iso(),
    'source_scope_executed_at_utc': (scope.get('summary') or {}).get('executed_at_utc'),
    'object_count': len(rows),
    'reuse_ready_attachments': len(reuse_ids),
    'ambiguous_attachments': len(ambiguous_ids),
    'needs_conversion_attachments': len(conversion_ids),
    'terminal_unmapped_attachments': len(terminal_ids),
    'protected_attachment_ids': sorted(protected_ids),
    'distinct_actionable_attachments': len(reuse_ids | ambiguous_ids | conversion_ids),
    'ready_for_conversion_attachments': len(execution['ready_for_conversion_ids']),
    'terminal_quality_attachments': len(execution['terminal_quality_ids']),
    'terminal_non_rendered_attachments': len(execution['terminal_non_rendered_ids']),
    'blocked_verification_attachments': len(execution['blocked_verification_ids']),
    'legacy_count_note': 'needs_conversion and distinct_actionable are unresolved mapping counts, not safe execution queues; consult execution_classification before any write',
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'summary': summary, 'objects': rows, 'execution_classification': execution}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
