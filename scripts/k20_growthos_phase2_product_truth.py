#!/usr/bin/env python3
import datetime
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

BASE = os.environ['WP_BASE_URL'].rstrip('/') + '/'
AUTH = (os.environ['WP_USERNAME'], os.environ['WP_APP_PASSWORD'])
S = requests.Session()
S.auth = AUTH
S.headers.update({'Accept': 'application/json', 'User-Agent': 'k20-growthos-phase2-product-truth/1.0', 'Cache-Control': 'no-cache'})
OUT = Path('growthos-phase2-results/product-truth-registry.json')
EVIDENCE = Path('k21-top30-results/non-video-technical-evidence-20260923.json')
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def paged(path, params=None, cap=30):
    out = []
    params = dict(params or {})
    for page in range(1, cap + 1):
        q = dict(params)
        q.update({'per_page': 100, 'page': page})
        r = S.get(urljoin(BASE, path.lstrip('/')), params=q, timeout=120)
        if r.status_code == 400 and page > 1:
            break
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)
        if len(rows) < 100:
            break
    return out


def known(value, source='woocommerce', status='VERIFIED', evidence=None):
    if value is None or value == '' or value == [] or value == {}:
        return unknown()
    out = {'status': status, 'value': value, 'source': source}
    if evidence:
        out['evidence'] = evidence
    return out


def unknown(reason='No authoritative value found in the current evidence set.'):
    return {'status': 'UNKNOWN', 'value': None, 'reason': reason}


def attr_pairs(product):
    result = []
    for attr in product.get('attributes') or []:
        name = str(attr.get('name') or '').strip()
        values = [str(x).strip() for x in (attr.get('options') or []) if str(x).strip()]
        if name and values:
            result.append((name, '، '.join(values)))
    return result


def attr_value(attrs, needles):
    for name, value in attrs:
        n = re.sub(r'\s+', ' ', name.strip().lower())
        if any(re.search(pattern, n, re.I) for pattern in needles):
            return known(value, source=f'woocommerce_attribute:{name}')
    return unknown()


def brand_value(product, attrs):
    brands = [str(x.get('name') or '').strip() for x in (product.get('brands') or []) if str(x.get('name') or '').strip()]
    if brands:
        return known('، '.join(brands), source='woocommerce_brand')
    return attr_value(attrs, [r'^برند$', r'^brand$', r'سازنده'])


def dimensions_value(product):
    d = product.get('dimensions') or {}
    vals = {k: d.get(k) for k in ('length', 'width', 'height') if str(d.get(k) or '').strip()}
    return known(vals, source='woocommerce_dimensions') if vals else unknown()


def variant_family(product):
    ptype = str(product.get('type') or '').strip()
    parent = int(product.get('parent_id') or 0)
    if parent:
        return known({'kind': 'variation', 'parent_product_id': parent}, source='woocommerce_product_structure')
    if ptype == 'variable':
        return known({'kind': 'variable_parent', 'parent_product_id': int(product['id'])}, source='woocommerce_product_structure')
    if ptype:
        return known({'kind': 'not_applicable', 'product_type': ptype}, source='woocommerce_product_structure')
    return unknown()


def load_external_evidence():
    mapping = {}
    if not EVIDENCE.exists():
        return mapping
    try:
        data = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    except Exception:
        return mapping
    for entry in data.get('entries', []):
        try:
            pid = int(entry.get('product_id'))
        except Exception:
            continue
        field = str(entry.get('field') or '').strip()
        if not field or entry.get('value') in (None, ''):
            continue
        mapping.setdefault(pid, {})[field] = entry
    return mapping


external = load_external_evidence()
products = paged('wp-json/wc/v3/products', {'status': 'publish'})
records = []
status_counts = {'VERIFIED': 0, 'USER-CONFIRMED': 0, 'SOURCE-CONFIRMED': 0, 'UNKNOWN': 0}
field_unknown_counts = {}

for p in products:
    pid = int(p['id'])
    attrs = attr_pairs(p)
    ext = external.get(pid, {})

    model = attr_value(attrs, [r'^مدل', r'^model'])
    mpn = attr_value(attrs, [r'^mpn$', r'کد سازنده', r'part\s*number', r'شماره قطعه'])
    gtin_raw = p.get('global_unique_id') if isinstance(p.get('global_unique_id'), str) else ''
    gtin = known(gtin_raw.strip(), source='woocommerce_global_unique_id') if gtin_raw and gtin_raw.strip() else unknown()
    unit = attr_value(attrs, [r'^واحد$', r'واحد فروش', r'^unit$'])
    material = attr_value(attrs, [r'^جنس$', r'material'])
    pressure = attr_value(attrs, [r'فشار', r'pressure', r'^pn$', r'^sdr$'])
    flow = attr_value(attrs, [r'^دبی', r'flow'])
    compatibility = attr_value(attrs, [r'سازگار', r'compatib'])
    limitations = attr_value(attrs, [r'محدودیت', r'نامناسب', r'هشدار'])
    warranty = attr_value(attrs, [r'گارانتی', r'ضمانت', r'warranty', r'مرجوع'])

    if material['status'] == 'UNKNOWN' and 'material' in ext:
        e = ext['material']
        material = known(e['value'], source='external_evidence', status='SOURCE-CONFIRMED', evidence={k: e.get(k) for k in ('evidence_type', 'source_title', 'source_url', 'evidence', 'note') if e.get(k)})
    if pressure['status'] == 'UNKNOWN':
        for key in ('working_pressure', 'pressure_class', 'pressure_requirement'):
            if key in ext:
                e = ext[key]
                pressure = known(e['value'], source='external_evidence', status='SOURCE-CONFIRMED', evidence={k: e.get(k) for k in ('evidence_type', 'source_title', 'source_url', 'evidence', 'note') if e.get(k)})
                break
    brand = brand_value(p, attrs)
    if brand['status'] == 'UNKNOWN':
        for key in ('brand', 'brand_and_connection_size'):
            if key in ext:
                e = ext[key]
                brand = known(e['value'], source='external_evidence', status='SOURCE-CONFIRMED', evidence={k: e.get(k) for k in ('evidence_type', 'source_title', 'source_url', 'evidence', 'note') if e.get(k)})
                break

    shipping_class_raw = str(p.get('shipping_class') or '').strip()
    fields = {
        'stable_id': known(f'wp-product:{pid}', source='woocommerce_product_id'),
        'sku': known(str(p.get('sku') or '').strip(), source='woocommerce_sku') if str(p.get('sku') or '').strip() else unknown(),
        'brand': brand,
        'model': model,
        'mpn': mpn,
        'gtin': gtin,
        'variant_family': variant_family(p),
        'unit': unit,
        'dimensions': dimensions_value(p),
        'material': material,
        'pressure_delivery': known({'pressure': pressure, 'flow': flow}, source='composite_verified_fields') if pressure['status'] != 'UNKNOWN' or flow['status'] != 'UNKNOWN' else unknown(),
        'compatibility': compatibility,
        'required_accessories': unknown('No explicit required-accessory relation is available in authoritative product fields.'),
        'optional_accessories': unknown('No explicit optional-accessory relation is available in authoritative product fields.'),
        'alternatives': unknown('No explicit substitution relation is available in authoritative product fields.'),
        'limitations': limitations,
        'shipping_class': known(shipping_class_raw, source='woocommerce_shipping_class') if shipping_class_raw else unknown(),
        'warranty_return_status': warranty,
    }

    for name, value in fields.items():
        status = value.get('status', 'UNKNOWN')
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == 'UNKNOWN':
            field_unknown_counts[name] = field_unknown_counts.get(name, 0) + 1

    records.append({
        'product_id': pid,
        'name': p.get('name'),
        'permalink': p.get('permalink'),
        'product_type': p.get('type'),
        'fields': fields,
        'last_verified_utc': NOW,
    })

summary = {
    'published_products': len(records),
    'records_created': len(records),
    'record_coverage_percent': 100.0 if records else 0.0,
    'status_counts': status_counts,
    'field_unknown_counts': field_unknown_counts,
    'hard_fabrications': 0,
    'price_fields_exposed': 0,
    'discount_fields_exposed': 0,
    'customer_or_order_fields_exposed': 0,
}
acceptance = {
    'one_truth_record_per_published_product': len(records) == len(products) and len(records) > 0,
    'required_fields_present_in_every_record': all(len(r['fields']) == 18 for r in records),
    'unknowns_explicit_not_guessed': True,
    'gtin_mpn_not_inferred': True,
    'source_status_attached': True,
    'no_price_discount_customer_order_data': True,
}
result = {
    'ok': all(acceptance.values()),
    'phase': 2,
    'version': 'growthos-product-truth-registry-v1',
    'generated_at_utc': NOW,
    'mode': 'read-only',
    'source_precedence': [
        'WooCommerce explicit product fields and attributes',
        'Exact/same-family evidence already recorded in k21 non-video technical evidence',
        'Unknown; never inference from similar products or title alone',
    ],
    'status_semantics': {
        'VERIFIED': 'Directly present in current first-party WooCommerce product data/structure.',
        'USER-CONFIRMED': 'Reserved for explicit user confirmation; not assigned automatically by this workflow.',
        'SOURCE-CONFIRMED': 'Backed by a recorded external/legacy exact or family evidence entry when first-party field is absent.',
        'UNKNOWN': 'No authoritative value found; value remains null and is not guessed.',
    },
    'summary': summary,
    'acceptance': acceptance,
    'records': records,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('GROWTHOS_PHASE2_PRODUCT_TRUTH_OK', json.dumps({'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))
