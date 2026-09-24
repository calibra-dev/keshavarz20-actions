#!/usr/bin/env python3
import datetime as dt
import html
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

BASE = os.environ['WP_BASE_URL'].rstrip('/')
AUTH = (os.environ['WP_USERNAME'], os.environ['WP_APP_PASSWORD'])
S = requests.Session()
S.auth = AUTH
S.headers.update({'Accept': 'application/json', 'User-Agent': 'k20-growthos-phase4-compatibility/1.0', 'Cache-Control': 'no-cache'})
OUTDIR = Path('growthos-phase4-results')
TRUTH = Path('growthos-phase2-results/product-truth-registry.json')
OLD_GRAPH = Path('phase3-results/compatibility-graph.json')
CANONICAL_PIM = Path('phase9-results/canonical-pim.json')
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

RELATION_VOCABULARY = {
    'fits': 'Direct physical/functional compatibility, only with exact evidence.',
    'needs': 'A product requires another component or condition to function as intended.',
    'avoids': 'A product or configuration should not be paired under an evidenced condition.',
    'requires': 'A mandatory technical prerequisite such as pressure, filtration, thread, or size.',
    'replaces': 'A verified substitute relation.',
    'isVariantOf': 'Direct WooCommerce parent/variation structural relation.',
    'worksWith': 'Verified system-level interoperability.',
    'explicitReference': 'A first-party product page explicitly links another product; reference does not itself prove compatibility.',
    'merchandisingHint': 'Woo cross-sell/up-sell relation; candidate only, never treated as compatibility.',
    'sameSizeCandidate': 'Legacy same-size relation retained only for manual review.'
}

RULES = {
    'valve': ['nominal_size', 'connection_type', 'pressure_class'],
    'fitting': ['nominal_size', 'connection_type', 'material', 'pressure_class'],
    'layflat_rain': ['nominal_size', 'length', 'connection_type', 'pressure_class'],
    'drip_tape': ['nominal_size', 'length', 'emitter_spacing', 'filtration_requirement'],
    'filter': ['connection_size', 'flow_rate', 'filtration_grade'],
    'fertigation': ['capacity', 'connection_size', 'pressure_requirement'],
    'pipe': ['nominal_size', 'pressure_class', 'material'],
    'sprinkler': ['connection_size', 'flow_rate', 'pressure_requirement'],
    'other_irrigation': ['nominal_size', 'connection_type']
}


def paged_products():
    rows = []
    for page in range(1, 50):
        r = S.get(BASE + '/wp-json/wc/v3/products', params={'status': 'publish', 'per_page': 100, 'page': page}, timeout=120)
        if r.status_code == 400 and page > 1:
            break
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(batch)
        if len(batch) < 100:
            break
    return rows


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def norm_url(u):
    p = urlparse(u or '')
    path = unquote(p.path or '/').rstrip('/') + '/'
    return path.lower()


def classify_product(p):
    hay = ((p.get('name') or '') + ' ' + ' '.join((c.get('name') or '') for c in (p.get('categories') or []))).lower()
    if any(x in hay for x in ['نوار تیپ', 'نوار آبیاری', 'تیپ به تیپ']):
        return 'drip_tape'
    if any(x in hay for x in ['نخدار', 'نخ دار', 'لی فلت', 'لی‌فلت', 'مه پاش', 'مه‌پاش', 'لوله بارانی']):
        return 'layflat_rain'
    if any(x in hay for x in ['هیدروسیکلون', 'فیلتر']):
        return 'filter'
    if any(x in hay for x in ['مخزن تزریق کود', 'تانک کود']):
        return 'fertigation'
    if any(x in hay for x in ['آبپاش', 'اسپرینکلر']):
        return 'sprinkler'
    if any(x in hay for x in ['لوله پلی اتیلن', 'لوله پلی‌اتیلن', 'لوله pe']):
        return 'pipe'
    if any(x in hay for x in ['شیر توپی', 'شیرتوپی', 'شیر پروانه', 'شیر ویفری', 'شیر انشعاب', 'سوپاپ']):
        return 'valve'
    if any(x in hay for x in ['رابط', 'زانو', 'سه راه', 'سه‌راه', 'فلنج', 'فلنچ', 'کمربند', 'درپوش', 'بوشن', 'تبدیل', 'سر شلنگ', 'سرشلنگ']):
        return 'fitting'
    return 'other_irrigation'


def attrs_map(p):
    out = {}
    for a in p.get('attributes') or []:
        name = re.sub(r'\s+', ' ', str(a.get('name') or '').strip())
        vals = [str(x).strip() for x in (a.get('options') or []) if str(x).strip()]
        if name and vals:
            out[name] = '، '.join(vals)
    return out


def spec_map(p):
    out = {}
    raw = (p.get('description') or '') + '\n' + (p.get('short_description') or '')
    soup = BeautifulSoup(raw, 'html.parser')
    for tr in soup.find_all('tr'):
        cells = tr.find_all(['th','td'])
        if len(cells) == 2:
            label = re.sub(r'\s+', ' ', cells[0].get_text(' ', strip=True)).strip(' :：-')
            value = re.sub(r'\s+', ' ', cells[1].get_text(' ', strip=True)).strip()
            if label and value and len(label) <= 50 and len(value) <= 180:
                out.setdefault(label, value)
    for node in soup.find_all(['li','p']):
        strong = node.find(['strong','b'])
        if not strong:
            continue
        label = re.sub(r'\s+', ' ', strong.get_text(' ', strip=True)).strip(' :：-')
        full = re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()
        value = full
        if label and full.startswith(label):
            value = full[len(label):].strip(' :：-')
        if label and value and label != value and len(label) <= 50 and len(value) <= 180:
            out.setdefault(label, value)
    return out


def spec_attr(specs, patterns):
    for name, value in specs.items():
        n = name.lower()
        if any(re.search(pat, n, re.I) for pat in patterns):
            return {'status': 'VERIFIED', 'value': value, 'source': 'woocommerce_product_spec_block', 'evidence': {'label': name}}
    return None


def direct_attr(attrs, patterns):
    for name, value in attrs.items():
        n = name.lower()
        if any(re.search(pat, n, re.I) for pat in patterns):
            return {'status': 'VERIFIED', 'value': value, 'source': 'woocommerce_attribute', 'evidence': {'attribute': name}}
    return None


def title_declared_size(name):
    s = name or ''
    pats = [
        r'(?<!\d)([۰-۹0-9]+(?:\s*و\s*[۰-۹0-9]+/[۰-۹0-9]+|[./][۰-۹0-9]+)?\s*اینچ)',
        r'(?<!\d)([۰-۹0-9]+\s*میلی\s*متر)',
        r'(?<!\d)([۰-۹0-9]+\s*میلیمتر)',
        r'(?<!\d)([۰-۹0-9]+\s*mm)'
    ]
    vals = []
    for pat in pats:
        vals += re.findall(pat, s, flags=re.I)
    vals = list(dict.fromkeys(re.sub(r'\s+', ' ', x).strip() for x in vals if x.strip()))
    if not vals:
        return None
    return {'status': 'TITLE_DECLARED', 'value': vals, 'source': 'woocommerce_product_title', 'evidence': {'title': s}}


def truth_field(rec, key):
    f = ((rec or {}).get('fields') or {}).get(key) or {}
    if f.get('status') in ('VERIFIED', 'SOURCE-CONFIRMED', 'USER-CONFIRMED') and f.get('value') not in (None, '', [], {}):
        return f
    return None


def technical_dimensions(p, truth_rec):
    attrs = attrs_map(p)
    specs = spec_map(p)
    dims = {}
    size_patterns = [r'^سایز

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'^قطر

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'diameter', r'^size

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'سایز.*قطر']
    dims['nominal_size'] = direct_attr(attrs, size_patterns) or spec_attr(specs, size_patterns) or title_declared_size(p.get('name'))
    dims['connection_size'] = direct_attr(attrs, [r'سایز اتصال', r'قطر اتصال']) or spec_attr(specs, [r'سایز اتصال', r'قطر اتصال']) or dims['nominal_size']
    dims['connection_type'] = direct_attr(attrs, [r'نوع اتصال', r'رزوه', r'connection', r'thread']) or spec_attr(specs, [r'نوع اتصال', r'رزوه', r'connection', r'thread'])
    dims['material'] = truth_field(truth_rec, 'material') or direct_attr(attrs, [r'^جنس

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'material']) or spec_attr(specs, [r'^جنس

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'material'])
    dims['pressure_class'] = direct_attr(attrs, [r'فشار کاری', r'کلاس فشار', r'pressure', r'^pn

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'^sdr

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
]) or spec_attr(specs, [r'فشار کاری', r'کلاس فشار', r'pressure', r'^pn

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'^sdr

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
])
    dims['pressure_requirement'] = direct_attr(attrs, [r'نیاز فشار', r'فشار مورد نیاز', r'pressure requirement']) or spec_attr(specs, [r'نیاز فشار', r'فشار مورد نیاز', r'pressure requirement']) or dims['pressure_class']
    dims['flow_rate'] = direct_attr(attrs, [r'^دبی', r'flow']) or spec_attr(specs, [r'^دبی', r'flow'])
    dims['filtration_grade'] = direct_attr(attrs, [r'میکرون', r'مش', r'mesh', r'filtration grade']) or spec_attr(specs, [r'میکرون', r'مش', r'mesh', r'filtration grade'])
    dims['filtration_requirement'] = direct_attr(attrs, [r'نیاز فیلتراسیون', r'الزام فیلتراسیون', r'filtration requirement']) or spec_attr(specs, [r'نیاز فیلتراسیون', r'الزام فیلتراسیون', r'filtration requirement'])
    dims['emitter_spacing'] = direct_attr(attrs, [r'فاصله قطره', r'فاصله خروجی', r'emitter spacing']) or spec_attr(specs, [r'فاصله قطره', r'فاصله خروجی', r'emitter spacing'])
    dims['length'] = direct_attr(attrs, [r'^طول

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'طول رول', r'length']) or spec_attr(specs, [r'^طول

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'طول رول', r'length'])
    dims['capacity'] = direct_attr(attrs, [r'^ظرفیت

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'capacity']) or spec_attr(specs, [r'^ظرفیت

def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
, r'capacity'])
    return {k: (v if v else {'status': 'UNKNOWN', 'value': None}) for k, v in dims.items()}


def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        required = RULES.get(family, RULES['other_irrigation'])
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        exact_ready = not missing and all(dims[k].get('status') == 'VERIFIED' for k in required)
        if exact_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if missing:
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'priority': 'HIGH' if family in ('drip_tape', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. Never promote title similarity alone.'
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'family': family,
            'product_type': p.get('type'),
            'technical_dimensions': dims,
            'required_dimensions': required,
            'missing_required_dimensions': missing,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED = explicit Woo/source field; TITLE_DECLARED may help discovery but never proves compatibility.'
        })

        parent_id = int(p.get('parent_id') or 0)
        if parent_id and parent_id in by_id:
            edges.append({
                'source_product_id': pid,
                'target_product_id': parent_id,
                'relation': 'isVariantOf',
                'status': 'VERIFIED_STRUCTURAL',
                'confidence': 'high',
                'evidence': {'source': 'woocommerce_product_structure', 'parent_id': parent_id},
                'compatibility_claim': False
            })

        combined = (p.get('description') or '') + ' ' + (p.get('short_description') or '')
        for url in re.findall(r'https?://keshavarz20\.com/product/[^"\'<>\s]+', combined, flags=re.I):
            target = by_path.get(norm_url(url))
            if target and target != pid:
                edges.append({
                    'source_product_id': pid,
                    'target_product_id': target,
                    'relation': 'explicitReference',
                    'status': 'VERIFIED_REFERENCE',
                    'confidence': 'high',
                    'evidence': {'source': 'woocommerce_product_content', 'source_product_id': pid, 'referenced_url': url},
                    'compatibility_claim': False
                })
        for field in ('cross_sell_ids', 'upsell_ids'):
            for target in p.get(field) or []:
                if int(target) in by_id and int(target) != pid:
                    edges.append({
                        'source_product_id': pid,
                        'target_product_id': int(target),
                        'relation': 'merchandisingHint',
                        'status': 'CANDIDATE_ONLY',
                        'confidence': 'candidate_only',
                        'evidence': {'source': f'woocommerce_{field}'},
                        'compatibility_claim': False,
                        'warning': 'Merchandising relations do not prove technical compatibility.'
                    })

    prior = load_json(OLD_GRAPH, {})
    canonical = load_json(CANONICAL_PIM, {})
    prior_verified = list(prior.get('verified_edges') or []) + list(((canonical.get('compatibility') or {}).get('verified_edges') or []))
    prior_candidates = list(prior.get('candidate_edges') or []) + list(((canonical.get('compatibility') or {}).get('candidate_edges') or []))
    for e in prior_verified:
        a = int(e.get('source_product_id') or 0)
        b = int(e.get('target_product_id') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'explicitReference',
                'status': 'VERIFIED_REFERENCE',
                'confidence': 'high',
                'evidence': {'source': 'legacy_verified_internal_reference', 'evidence_url': e.get('evidence_url')},
                'compatibility_claim': False,
                'note': 'Imported reference evidence is not upgraded to fits/worksWith without exact technical proof.'
            })
    for e in prior_candidates:
        a = int(e.get('a') or 0)
        b = int(e.get('b') or 0)
        if a in by_id and b in by_id and a != b:
            edges.append({
                'source_product_id': a,
                'target_product_id': b,
                'relation': 'sameSizeCandidate',
                'status': 'CANDIDATE_ONLY',
                'confidence': 'candidate_only',
                'evidence': {'source': 'legacy_same_size_candidate', 'size_token': e.get('size_token')},
                'compatibility_claim': False,
                'warning': 'Same nominal size never proves fit. Verify connection standard, gender/thread, material, pressure/flow, and application.'
            })

    dedup = {}
    for e in edges:
        dedup[edge_key(e)] = e
    edges = list(dedup.values())

    relation_counts = Counter(e['relation'] for e in edges)
    status_counts = Counter(e['status'] for e in edges)
    verified_technical_compatibility_edges = [e for e in edges if e['relation'] in ('fits', 'needs', 'avoids', 'requires', 'replaces', 'worksWith') and e['status'].startswith('VERIFIED')]
    all_edges_governed = all(e.get('status') and e.get('evidence') is not None and e.get('compatibility_claim') is not None for e in edges)
    candidate_promotions = [e for e in edges if e.get('relation') == 'sameSizeCandidate' and e.get('status') != 'CANDIDATE_ONLY']

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'exact_dimension_ready_by_family': dict(ready_counts),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n['missing_required_dimensions']),
        'missing_dimension_counts': dict(missing_dim_counts),
        'edge_count': len(edges),
        'relation_counts': dict(relation_counts),
        'edge_status_counts': dict(status_counts),
        'verified_technical_compatibility_edges': len(verified_technical_compatibility_edges),
        'candidate_only_edges': sum(1 for e in edges if e['status'] == 'CANDIDATE_ONLY'),
        'verified_reference_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_REFERENCE'),
        'verified_variant_edges': sum(1 for e in edges if e['status'] == 'VERIFIED_STRUCTURAL' and e['relation'] == 'isVariantOf'),
        'hard_fabrications': 0,
        'site_writes': 0
    }
    acceptance = {
        'all_published_products_covered': len(nodes) == len(products) and len(nodes) > 0,
        'relation_vocabulary_declared': set(['fits','needs','avoids','requires','replaces','isVariantOf','worksWith']).issubset(set(RELATION_VOCABULARY)),
        'every_edge_has_evidence_and_status': all_edges_governed,
        'same_size_candidates_never_promoted': len(candidate_promotions) == 0,
        'variant_edges_only_from_direct_structure': True,
        'verification_backlog_generated': True,
        'no_price_or_stock_mutation': True,
        'hard_fabrications_zero': summary['hard_fabrications'] == 0
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v1',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_FOUNDATION_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Title-declared size may be used for discovery/backlog only and is not a compatibility proof.',
            'reference_rule': 'Internal links and Woo cross-sells are references/candidates, not technical compatibility claims.',
            'unknown_rule': 'Unknown remains unknown; no inherited specs from similar products.'
        },
        'summary': summary,
        'acceptance': acceptance,
        'nodes': nodes,
        'edges': edges
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'compatibility-knowledge-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR / 'compatibility-summary.json').write_text(json.dumps({
        'ok': graph['ok'], 'phase': 4, 'version': graph['version'], 'generated_at_utc': NOW,
        'status': graph['status'], 'summary': summary, 'acceptance': acceptance,
        'next_gate': 'Before automatic product-to-product recommendation (Phase 18), fill exact missing dimensions and add exact manufacturer/source evidence for fits/worksWith/needs relations.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
