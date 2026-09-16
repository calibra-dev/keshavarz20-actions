import json
import pathlib

config_path = pathlib.Path('sitewide-media-autopilot/config.json')
inventory_path = pathlib.Path('sitewide-media-results/inventory-phase1.json')

if not inventory_path.exists():
    raise SystemExit('Missing sitewide-media-results/inventory-phase1.json')
config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
mode = str(config.get('reference_mode') or 'all_phase1').strip().lower()
obj = json.loads(inventory_path.read_text(encoding='utf-8'))
obs = {'rendered_page', 'post_content_rendered'}

if mode == 'featured_only':
    allowed = {'featured_image'}
elif mode == 'category_only':
    allowed = {'woo_category_image'}
else:
    allowed = {'featured_image', 'woo_category_image'}

items = []
for item in obj.get('items') or []:
    refs = item.get('references') or []
    kinds = {str(r.get('kind') or '') for r in refs}
    if 'woo_product_image' in kinds:
        continue
    writable = kinds - obs
    if not writable or not writable.issubset(allowed):
        continue
    kept = dict(item)
    kept['references'] = refs
    kept['reference_count'] = len(refs)
    items.append(kept)

runtime = {'summary': dict(obj.get('summary') or {}), 'items': items, 'runtime_reference_mode': mode}
runtime['summary']['runtime_eligible_attachments'] = len(items)
# This rewrites only the ephemeral checkout copy. The workflow never stages this source inventory.
inventory_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'reference_mode': mode, 'runtime_eligible_attachments': len(items)}, ensure_ascii=False))
