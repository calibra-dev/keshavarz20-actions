import json
import pathlib

path = pathlib.Path('sitewide-media-results/inventory.json')
if not path.exists():
    raise SystemExit('Missing sitewide media inventory')
obj = json.loads(path.read_text(encoding='utf-8'))
items = []
safe = {'featured_image', 'woo_category_image'}
observational = {'rendered_page', 'post_content_rendered'}
for item in obj.get('items') or []:
    refs = item.get('references') or []
    kinds = {str(r.get('kind') or '') for r in refs}
    # Product images are owned by the separate product autopilot.
    if 'woo_product_image' in kinds:
        continue
    writable = kinds - observational
    # Phase 1 only migrates files for which every known writable reference is
    # a featured image or Woo category image. Anything also referenced from
    # raw content/meta/Elementor is deferred so the old attachment stays valid.
    if not writable or not writable.issubset(safe):
        continue
    kept = dict(item)
    kept['references'] = [r for r in refs if str(r.get('kind') or '') in safe | observational]
    kept['reference_count'] = len(kept['references'])
    items.append(kept)

runtime = {
    'summary': dict(obj.get('summary') or {}),
    'items': items,
    'phase': 'featured_and_category_only',
}
runtime['summary']['phase1_eligible_attachments'] = len(items)
path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Phase1 eligible attachments: {len(items)}')
