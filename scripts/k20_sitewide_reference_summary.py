import json
import pathlib
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
FRESH_SOURCE = ROOT / 'sitewide-media-results' / 'inventory.json'
LEGACY_SOURCE = ROOT / 'sitewide-media-results' / 'inventory-phase1.json'
SOURCE = FRESH_SOURCE if FRESH_SOURCE.exists() else LEGACY_SOURCE
OUT = ROOT / 'sitewide-media-results' / 'reference-summary.json'

if not SOURCE.exists():
    raise SystemExit('Missing sitewide media inventory')
obj = json.loads(SOURCE.read_text(encoding='utf-8'))
items = obj.get('items') or []
source_summary = obj.get('summary') or {}

kind_refs = Counter()
kind_attachments = defaultdict(set)
kind_jpeg_png_attachments = defaultdict(set)
object_kind_counts = Counter()
format_counts = Counter()
referenced_formats = Counter()

for item in items:
    aid = int(item.get('attachment_id') or 0)
    fmt = str(item.get('format') or '').lower()
    format_counts[fmt] += 1
    refs = item.get('references') or []
    if refs:
        referenced_formats[fmt] += 1
    for ref in refs:
        kind = str(ref.get('kind') or '')
        otype = str(ref.get('object_type') or '')
        kind_refs[kind] += 1
        if aid:
            kind_attachments[kind].add(aid)
            if fmt in ('jpeg', 'png'):
                kind_jpeg_png_attachments[kind].add(aid)
        object_kind_counts[f'{kind}|{otype}'] += 1

focus = ['woo_product_image', 'featured_image', 'woo_category_image', 'post_content_raw', 'rest_meta', 'post_content_rendered', 'rendered_page']
post_types = source_summary.get('post_types') or {}
post_types_compact = {
    str(name): {
        'posts_read': int((info or {}).get('posts_read') or 0),
        'expected_posts': int((info or {}).get('expected_posts') or 0),
        'error': (info or {}).get('error'),
        'context': (info or {}).get('context'),
        'route': (info or {}).get('route'),
        'fallback': bool((info or {}).get('fallback')),
    }
    for name, info in sorted(post_types.items())
}
summary = {
    'executed_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'source_inventory_executed_at_utc': source_summary.get('executed_at_utc'),
    'source_inventory_version': source_summary.get('version'),
    'source_image_attachments': len(items),
    'formats': dict(sorted(format_counts.items())),
    'referenced_formats': dict(sorted(referenced_formats.items())),
    'coverage': {
        'products_read': int(source_summary.get('products_read') or 0),
        'product_error': source_summary.get('product_error'),
        'product_categories_read': int(source_summary.get('product_categories_read') or 0),
        'category_error': source_summary.get('category_error'),
        'sitemaps_read': int(source_summary.get('sitemaps_read') or 0),
        'sitemap_failures': int(source_summary.get('sitemap_failures') or 0),
        'public_urls_discovered': int(source_summary.get('public_urls_discovered') or 0),
        'rendered_pages_read': int(source_summary.get('rendered_pages_read') or 0),
        'rendered_pages_failed': int(source_summary.get('rendered_pages_failed') or 0),
        'crawl_complete': source_summary.get('crawl_complete') is True,
        'post_type_errors': source_summary.get('post_type_errors') or {},
        'post_types': post_types_compact,
    },
    'reference_kinds': {
        kind: {
            'reference_tokens': int(kind_refs[kind]),
            'distinct_attachments': len(kind_attachments[kind]),
            'distinct_jpeg_png_attachments': len(kind_jpeg_png_attachments[kind]),
        }
        for kind in sorted(kind_refs)
    },
    'focus': {
        kind: {
            'reference_tokens': int(kind_refs[kind]),
            'distinct_attachments': len(kind_attachments[kind]),
            'distinct_jpeg_png_attachments': len(kind_jpeg_png_attachments[kind]),
        }
        for kind in focus
    },
    'object_type_breakdown': dict(sorted(object_kind_counts.items())),
    'note': 'Read-only summary of the retained inventory snapshot. Rerun after fresh inventory before any content/meta write phase.'
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'focus': summary['focus'], 'coverage': summary['coverage']}, ensure_ascii=False))
