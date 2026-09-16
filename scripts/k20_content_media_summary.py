import json
import pathlib
from collections import Counter, defaultdict
from datetime import datetime, timezone

src = pathlib.Path('content-media-results/inventory.json')
out = pathlib.Path('content-media-results/summary.json')
obj = json.loads(src.read_text(encoding='utf-8'))
items = obj.get('items') or []
write_kinds = {'post_content_raw', 'rest_meta', 'woo_product_description', 'woo_product_short_description', 'woo_category_description'}
rows = []
by_kind = Counter()
write_ids = set()
rendered_ids = set()
for item in items:
    aid = int(item.get('attachment_id') or 0)
    fmt = str(item.get('format') or '').lower()
    if fmt not in ('jpeg', 'png'):
        continue
    refs = item.get('references') or []
    direct = [r for r in refs if str(r.get('kind') or '') in write_kinds]
    rendered = [r for r in refs if str(r.get('kind') or '') == 'rendered_page']
    if rendered:
        rendered_ids.add(aid)
    if direct:
        write_ids.add(aid)
        for r in direct:
            by_kind[str(r.get('kind') or '')] += 1
        rows.append({
            'attachment_id': aid,
            'format': fmt,
            'url': str(item.get('url') or ''),
            'alt_text': str(item.get('alt_text') or ''),
            'direct_references': direct,
            'also_seen_rendered': bool(rendered),
            'rendered_locator_sample': [str(r.get('locator') or '') for r in rendered[:5]],
        })
summary = {
    'executed_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
    'source_executed_at_utc': (obj.get('summary') or {}).get('executed_at_utc'),
    'coverage': (obj.get('summary') or {}).get('coverage') or {},
    'direct_writable_jpeg_png_attachments': len(write_ids),
    'direct_reference_tokens_by_kind': dict(sorted(by_kind.items())),
    'rendered_jpeg_png_attachments': len(rendered_ids),
    'rendered_only_jpeg_png_attachments': len(rendered_ids - write_ids),
    'direct_items': rows,
    'note': 'Read-only compact summary. rendered_only entries are evidence of frontend presence, not proof of a writable content source.'
}
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k != 'direct_items'}, ensure_ascii=False))
