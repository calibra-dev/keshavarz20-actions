import json
import pathlib
from collections import defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
PREPARED = ROOT / 'gallery-meta-rescue' / 'prepared.json'
OUT = ROOT / 'gallery-meta-rescue' / 'apply-plan.json'


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


prepared = json.loads(PREPARED.read_text(encoding='utf-8'))
if prepared.get('status') != 'prepared':
    raise SystemExit('prepared.json status is not prepared')
items = prepared.get('items') or []
if len(items) != 7:
    raise SystemExit(f'Expected 7 prepared mappings, found {len(items)}')

groups = defaultdict(list)
for item in items:
    groups[int(item.get('product_id') or 0)].append(item)
if set(groups) != {135311, 135321, 136206, 136209, 136215, 136230}:
    raise SystemExit(f'Unexpected affected product set: {sorted(groups)}')

products = []
for product_id in sorted(groups):
    rows = groups[product_id]
    original_lists = {
        tuple(int(x) for x in (row.get('original_image_ids') or []))
        for row in rows
    }
    if len(original_lists) != 1:
        raise SystemExit(f'Product {product_id} has inconsistent original image arrays')
    original = list(next(iter(original_lists)))
    if len(original) < 2:
        raise SystemExit(f'Product {product_id} has no gallery images')

    gallery_before = original[1:]
    replacements = {}
    keys = []
    for row in rows:
        key = str(row.get('key') or '')
        old_id = int(row.get('old_attachment_id') or 0)
        new_id = int(row.get('new_attachment_id') or 0)
        position = int(row.get('position') or -1)
        if not key or old_id <= 0 or new_id <= 0 or position <= 0:
            raise SystemExit(f'Invalid prepared row on product {product_id}')
        if gallery_before.count(old_id) != 1:
            raise SystemExit(f'Product {product_id} old attachment {old_id} is not unique in gallery')
        if position >= len(original) or original[position] != old_id:
            raise SystemExit(f'Product {product_id} position mismatch for {old_id}')
        if old_id in replacements:
            raise SystemExit(f'Duplicate old attachment mapping {product_id}:{old_id}')
        replacements[old_id] = new_id
        keys.append(key)

    gallery_after = [replacements.get(value, value) for value in gallery_before]
    if any(old in gallery_after for old in replacements):
        raise SystemExit(f'Product {product_id} target still contains an old attachment')
    for new_id in replacements.values():
        if gallery_after.count(new_id) != 1:
            raise SystemExit(f'Product {product_id} target new attachment is not unique: {new_id}')

    products.append({
        'product_id': product_id,
        'keys': sorted(keys),
        'featured_attachment_id': original[0],
        'expected_woo_images_before': original,
        'expected_meta_before': ','.join(str(x) for x in gallery_before),
        'target_meta': ','.join(str(x) for x in gallery_after),
        'expected_woo_images_after': [original[0]] + gallery_after,
        'replacements': [
            {'old_attachment_id': old, 'new_attachment_id': new}
            for old, new in sorted(replacements.items())
        ],
    })

result = {
    'executed_at_utc': now_iso(),
    'action': 'gallery_meta_rescue.apply_plan',
    'read_only': True,
    'product_count': len(products),
    'mapping_count': len(items),
    'products': products,
    'note': 'No gallery metadata was changed. Apply only when live _product_image_gallery exactly equals expected_meta_before for every product.'
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'product_count': len(products), 'mapping_count': len(items)}, ensure_ascii=False))
