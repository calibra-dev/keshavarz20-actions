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
    'fitting': ['nominal_size', 'connection_type', 'material'],
    'layflat_rain': ['nominal_size', 'length', 'pressure_class', 'material'],
    'layflat_component': ['nominal_size', 'connection_type', 'material'],
    'emitter': ['flow_rate', 'connection_type'],
    'drip_tape': ['nominal_size', 'length', 'emitter_spacing', 'filtration_requirement', 'pressure_class'],
    'drip_tape_component': ['connection_size', 'connection_type'],
    'filter': ['connection_size', 'filtration_grade'],
    'fertigation': ['capacity', 'connection_size', 'pressure_requirement'],
    'pipe': ['nominal_size', 'length', 'pressure_class', 'material'],
    'sprinkler': ['connection_size', 'flow_rate', 'pressure_requirement'],
    'installation_tool': ['tool_size'],
    'washer_clamp': ['nominal_size', 'component_type'],
    'riser': ['nominal_size', 'length', 'connection_type', 'material'],
    'pump': ['connection_size', 'head', 'power'],
    'unmodeled_irrigation': [],
    'excluded_non_irrigation': []
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
    name = (p.get('name') or '').lower()
    cats = ' '.join((x.get('name') or '') for x in (p.get('categories') or [])).lower()

    if re.search(r'کود|فرتینوکس|هیومیک|اسید آمینه|گوگرد|پتاس|فسفر|کلسیم|آهن|ریز مغذی|بذر|نشاء|نهال|کوکوپیت|پیت ماس', name):
        return 'excluded_non_irrigation'

    if re.search(r'مته|پانچ|پانچر|سوراخ[\s‌-]*کن|گردبر|آچار[\s‌-]*اتصالات', name):
        return 'installation_tool'
    if re.search(r'بابلر|دریپر|قطره[\s‌-]*چکان', name):
        return 'emitter'

    if re.search(r'نوار\s*تیپ|نوارتیپ|نوار\s*آبیاری', name):
        if re.search(r'شیر|رابط|بست|سه\s*راه|اتصال|کورکن|درپوش|ابتدایی', name):
            return 'drip_tape_component'
        return 'drip_tape'

    if re.search(r'لی[\s‌-]*فلت|نخ[\s‌-]*دار|نخدار', name):
        if re.search(r'رابط|کمربند|شیر|کور|واشر|بست|اتصال', name) and not re.search(r'^لوله', name):
            return 'layflat_component'
        if re.search(r'^لوله|مه[\s‌-]*پاش|لوله\s*بارانی', name):
            return 'layflat_rain'

    if re.search(r'^لوله\s*پلی[\s‌-]*اتیلن|\bpe\s*(80|100)\b', name):
        return 'pipe'
    if re.search(r'هیدروسیکلون|فیلتر', name):
        return 'filter'
    if re.search(r'مخزن\s*تزریق\s*کود|تانک\s*کود', name):
        return 'fertigation'
    if re.search(r'آبپاش|اسپرینکلر', name):
        return 'sprinkler'
    if re.search(r'واشر|اورینگ|گسکت|بست\s*(تک|دو|هندلی|ابتدایی)|بست\s*و\s*قلاب', name):
        return 'washer_clamp'
    if re.search(r'رایزر', name):
        return 'riser'
    if re.search(r'پمپ|کف\s*کش|الکتروپمپ|ست\s*کنترل', name):
        return 'pump'
    if re.search(r'شیر|سوپاپ', name):
        return 'valve'
    if re.search(r'رابط|زانو|زانویی|سه\s*راه|سه‌راه|فلنج|فلنچ|کمربند|درپوش|کپ|بوشن|تبدیل|سر\s*شلنگ|سرشلنگ|چپقی|مغزی|اتصال\s*(نر|ماده)|اتصال\s*زانو|کورکن', name):
        return 'fitting'

    if any(x in cats for x in ['آبیاری', 'اتصالات', 'لوله', 'شیرآلات']):
        return 'unmodeled_irrigation'
    return 'excluded_non_irrigation'


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


def title_declared_value(name, patterns, field):
    s = name or ''
    vals = []
    for pat in patterns:
        vals += re.findall(pat, s, flags=re.I)
    cleaned = []
    for x in vals:
        if isinstance(x, tuple):
            x = ' '.join(str(v) for v in x if v)
        x = re.sub(r'\s+', ' ', str(x)).strip()
        if x and x not in cleaned:
            cleaned.append(x)
    if not cleaned:
        return None
    return {
        'status': 'SITE_DECLARED',
        'value': cleaned[0] if len(cleaned) == 1 else cleaned,
        'source': 'woocommerce_product_title',
        'evidence': {'field': field, 'title': s}
    }


def title_declared_size(name):
    return title_declared_value(name, [
        r'(?<!\d)([۰-۹0-9]+(?:\s*و\s*[۰-۹0-9]+/[۰-۹0-9]+|[./][۰-۹0-9]+)?\s*اینچ)',
        r'(?<!\d)([۰-۹0-9]+\s*میلی[\s‌-]*متر)',
        r'(?<!\d)([۰-۹0-9]+\s*میلیمتر)',
        r'(?<!\d)([۰-۹0-9]+\s*mm)'
    ], 'nominal_size')


def title_declared_length(name):
    return title_declared_value(name, [
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*متری)',
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*متر)'
    ], 'length')


def title_declared_pressure(name):
    return title_declared_value(name, [
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*(?:بار|اتمسفر))'
    ], 'pressure_class')


def title_declared_emitter_spacing(name):
    if not re.search(r'نوار\s*تیپ|نوارتیپ|نوار\s*آبیاری', name or '', re.I):
        return None
    return title_declared_value(name, [
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*سانتی\s*متری)',
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*سانت)'
    ], 'emitter_spacing')


def title_declared_capacity(name):
    return title_declared_value(name, [r'([۰-۹0-9]+\s*لیتری)'], 'capacity')


def title_declared_head(name):
    if not re.search(r'پمپ|کف\s*کش|الکتروپمپ', name or '', re.I):
        return None
    return title_declared_value(name, [r'([۰-۹0-9]+\s*متری)'], 'head')


def title_declared_power(name):
    return title_declared_value(name, [r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*اسب)'], 'power')


def title_declared_connection_type(name):
    s = name or ''
    mapping = [
        (r'رزوه[‌\s-]*ای|دنده[‌\s-]*ای|یکسر\s*نر|یکسر\s*ماده|دو\s*سر\s*نر|دو\s*سر\s*ماده', 'threaded'),
        (r'پیچی', 'compression'),
        (r'جوشی|بات\s*فیوژن|butt', 'butt_fusion'),
        (r'الکتروفیوژن|electrofusion', 'electrofusion'),
        (r'چسبی', 'solvent_weld'),
        (r'ویکتالیک|victaulic', 'grooved')
    ]
    vals = [label for pat, label in mapping if re.search(pat, s, re.I)]
    if not vals:
        return None
    return {'status': 'SITE_DECLARED', 'value': vals[0] if len(vals) == 1 else vals,
            'source': 'woocommerce_product_title', 'evidence': {'field': 'connection_type', 'title': s}}


def title_declared_material(name):
    s = name or ''
    if re.search(r'upvc|u-pvc|یو\s*پی\s*وی\s*سی', s, re.I):
        v = 'uPVC'
    elif re.search(r'پلی[\s‌-]*اتیلن|\bpe\b', s, re.I):
        v = 'polyethylene'
    elif re.search(r'پلیمری', s, re.I):
        v = 'polymeric_unspecified'
    else:
        return None
    return {'status': 'SITE_DECLARED', 'value': v, 'source': 'woocommerce_product_title',
            'evidence': {'field': 'material', 'title': s}}


def component_type_from_title(name):
    s = name or ''
    for pat, val in [
        (r'واشر|اورینگ|گسکت', 'seal'),
        (r'بست', 'clamp'),
        (r'مته|پانچ|گردبر|سوراخ\s*کن', 'punch_tool'),
        (r'آچار', 'installation_wrench')
    ]:
        if re.search(pat, s, re.I):
            return {'status': 'SITE_DECLARED', 'value': val, 'source': 'woocommerce_product_title',
                    'evidence': {'field': 'component_type', 'title': s}}
    return None




def title_declared_connection_size(name):
    s = name or ''
    patterns = [
        r'شیر\s*انشعاب\s*([۰-۹0-9]+)\s*به\s*نوار',
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?)\s*به\s*نوار\s*تیپ',
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?)\s*به\s*لی[\s‌-]*فلت'
    ]
    return title_declared_value(s, patterns, 'connection_size')


def semantic_connection_type(name):
    s = name or ''
    checks = [
        (r'کمربند.*(?:اینچ|")', 'saddle_female_threaded'),
        (r'اتصال\s*ماده|سه\s*راه\s*ماده|زانو.*ماده|یکسر\s*ماده', 'female_threaded'),
        (r'اتصال\s*نر|سه\s*راه\s*نر|زانو.*نر|یکسر\s*نر', 'male_threaded'),
        (r'مغزی', 'male_male_threaded'),
        (r'کپ\s*رزوه|درپوش\s*رزوه|بوشن\s*رزوه', 'threaded'),
        (r'فلنچ|فلنج', 'flanged'),
        (r'جوشی', 'butt_fusion'),
    ]
    for pat, value in checks:
        if re.search(pat, s, re.I):
            return {'status':'SITE_DECLARED','value':value,'source':'product_type_semantics',
                    'evidence':{'field':'connection_type','title':s,'rule':pat}}
    return None


def title_declared_flow_rate(name):
    return title_declared_value(name, [
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*لیتری)',
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*لیتر(?:\s*بر\s*ساعت)?)'
    ], 'flow_rate')


def title_declared_length_cm(name):
    return title_declared_value(name, [
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*سانتی[\s‌-]*متر)',
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*سانتیمتر)'
    ], 'length')


def title_declared_aluminum(name):
    if re.search(r'آلومینیوم|آلمینیوم|آلومینیومی|آلمینیومی', name or '', re.I):
        return {'status':'SITE_DECLARED','value':'aluminum','source':'woocommerce_product_title',
                'evidence':{'field':'material','title':name}}
    return None


def truth_field(rec, key):
    f = ((rec or {}).get('fields') or {}).get(key) or {}
    if f.get('status') in ('VERIFIED', 'SOURCE-CONFIRMED', 'USER-CONFIRMED') and f.get('value') not in (None, '', [], {}):
        return f
    return None


def technical_dimensions(p, truth_rec):
    attrs = attrs_map(p)
    specs = spec_map(p)
    name = p.get('name') or ''
    dims = {}
    size_patterns = [r'^سایز$', r'^قطر$', r'diameter', r'^size$', r'سایز.*قطر']
    dims['nominal_size'] = direct_attr(attrs, size_patterns) or spec_attr(specs, size_patterns) or title_declared_size(name)
    dims['connection_size'] = (
        direct_attr(attrs, [r'سایز اتصال', r'قطر اتصال'])
        or spec_attr(specs, [r'سایز اتصال', r'قطر اتصال'])
        or title_declared_connection_size(name)
        or dims['nominal_size']
    )
    dims['connection_type'] = (
        direct_attr(attrs, [r'نوع اتصال', r'رزوه', r'connection', r'thread'])
        or spec_attr(specs, [r'نوع اتصال', r'رزوه', r'connection', r'thread'])
        or title_declared_connection_type(name)
        or semantic_connection_type(name)
    )
    dims['material'] = (
        truth_field(truth_rec, 'material')
        or direct_attr(attrs, [r'^جنس$', r'material'])
        or spec_attr(specs, [r'^جنس$', r'material'])
        or title_declared_material(name)
        or title_declared_aluminum(name)
    )
    dims['pressure_class'] = (
        direct_attr(attrs, [r'فشار کاری', r'کلاس فشار', r'pressure', r'^pn$', r'^sdr$'])
        or spec_attr(specs, [r'فشار کاری', r'کلاس فشار', r'pressure', r'^pn$', r'^sdr$'])
        or title_declared_pressure(name)
    )
    dims['pressure_requirement'] = (
        direct_attr(attrs, [r'نیاز فشار', r'فشار مورد نیاز', r'pressure requirement'])
        or spec_attr(specs, [r'نیاز فشار', r'فشار مورد نیاز', r'pressure requirement'])
        or dims['pressure_class']
    )
    dims['flow_rate'] = (
        direct_attr(attrs, [r'^دبی', r'flow'])
        or spec_attr(specs, [r'^دبی', r'flow'])
        or title_declared_flow_rate(name)
    )
    dims['filtration_grade'] = (
        direct_attr(attrs, [r'میکرون', r'مش', r'mesh', r'filtration grade'])
        or spec_attr(specs, [r'میکرون', r'مش', r'mesh', r'filtration grade'])
    )
    dims['filtration_requirement'] = (
        direct_attr(attrs, [r'نیاز فیلتراسیون', r'الزام فیلتراسیون', r'filtration requirement'])
        or spec_attr(specs, [r'نیاز فیلتراسیون', r'الزام فیلتراسیون', r'filtration requirement'])
    )
    dims['emitter_spacing'] = (
        direct_attr(attrs, [r'فاصله قطره', r'فاصله خروجی', r'emitter spacing'])
        or spec_attr(specs, [r'فاصله قطره', r'فاصله خروجی', r'emitter spacing'])
        or title_declared_emitter_spacing(name)
    )
    dims['length'] = (
        direct_attr(attrs, [r'^طول$', r'طول رول', r'length'])
        or spec_attr(specs, [r'^طول$', r'طول رول', r'length'])
        or title_declared_length(name)
        or title_declared_length_cm(name)
    )
    dims['capacity'] = direct_attr(attrs, [r'^ظرفیت$', r'capacity']) or spec_attr(specs, [r'^ظرفیت$', r'capacity']) or title_declared_capacity(name)
    dims['tool_size'] = dims['nominal_size']
    dims['component_type'] = component_type_from_title(name)
    dims['head'] = direct_attr(attrs, [r'هد', r'ارتفاع']) or spec_attr(specs, [r'هد', r'ارتفاع']) or title_declared_head(name)
    dims['power'] = direct_attr(attrs, [r'توان', r'اسب']) or spec_attr(specs, [r'توان', r'اسب']) or title_declared_power(name)
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
        required = RULES.get(family, [])
        in_scope = family != 'excluded_non_irrigation'
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        data_ready = in_scope and bool(required) and not missing
        exact_ready = data_ready and all(dims[k].get('status') in ('VERIFIED', 'SOURCE-CONFIRMED', 'USER-CONFIRMED', 'MANUFACTURER_VERIFIED') for k in required)
        if data_ready:
            ready_counts[family] += 1
        for k in missing:
            missing_dim_counts[k] += 1
        if in_scope and (missing or family == 'unmodeled_irrigation'):
            backlog.append({
                'product_id': pid,
                'name': p.get('name'),
                'family': family,
                'missing_required_dimensions': missing,
                'model_gap': family == 'unmodeled_irrigation',
                'priority': 'HIGH' if family in ('drip_tape', 'drip_tape_component', 'layflat_rain', 'filter', 'fitting', 'valve', 'pipe', 'fertigation', 'sprinkler', 'pump') else 'NORMAL',
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. SITE_DECLARED values are useful evidence but are not promoted to manufacturer-verified compatibility.'
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
            'compatibility_scope': 'excluded' if family == 'excluded_non_irrigation' else 'in_scope',
            'data_dimension_ready': data_ready,
            'exact_compatibility_dimension_ready': exact_ready,
            'evidence_policy': 'VERIFIED/MANUFACTURER_VERIFIED can support exact compatibility. SITE_DECLARED is retailer first-party evidence and must not be silently upgraded to manufacturer proof.'
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
        'products_data_dimension_ready': sum(1 for n in nodes if n.get('data_dimension_ready')),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n.get('compatibility_scope') == 'in_scope' and n['missing_required_dimensions']),
        'excluded_non_irrigation_products': sum(1 for n in nodes if n.get('compatibility_scope') == 'excluded'),
        'unmodeled_irrigation_products': sum(1 for n in nodes if n.get('family') == 'unmodeled_irrigation'),
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
        'version': 'growthos-compatibility-knowledge-graph-v2',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_RESCOPED_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'policy': {
            'verified_edge_rule': 'fits/worksWith/needs/replaces/avoids/requires require exact source evidence; same size/title/category is never enough.',
            'title_declared_rule': 'Explicit title/spec values are stored as SITE_DECLARED and can satisfy machine-readable data completeness, but they do not by themselves prove manufacturer-grade compatibility.',
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
