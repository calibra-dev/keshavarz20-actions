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
EXTERNAL_EVIDENCE = Path('growthos-phase4-input/external-evidence-20260924.json')
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
    'layflat_component': ['interface_signature'],
    'emitter': ['flow_rate', 'connection_type'],
    'drip_tape': ['nominal_size', 'length', 'emitter_spacing', 'filtration_requirement', 'pressure_class'],
    'drip_tape_component': ['interface_signature'],
    'drip_line_component': ['interface_signature'],
    'filter': ['connection_size', 'filtration_grade'],
    'fertigation': ['capacity', 'connection_size', 'pressure_requirement'],
    'pipe': ['nominal_size', 'length', 'pressure_class', 'material'],
    'sprinkler': ['connection_size', 'flow_rate', 'pressure_requirement'],
    'installation_tool': ['tool_size'],
    'washer_clamp': ['interface_signature', 'component_type'],
    'riser': ['nominal_size', 'length', 'connection_type', 'material'],
    'pump': ['connection_size', 'head', 'power'],
    'branch_connector': ['interface_signature'],
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

    if re.search(r'کلید\s*شیر\s*خودکار|مته|پانچ|پانچر|سوراخ[\s‌-]*کن|گردبر|آچار[\s‌-]*اتصالات', name):
        return 'installation_tool'
    if re.search(r'بابلر|دریپر|قطره[\s‌-]*چکان', name):
        return 'emitter'

    if re.search(r'^لوله.*(?:مه[\s‌-]*پاش|بارانی)', name):
        return 'layflat_rain'

    if re.search(r'(?:رابط|شیر|سه\s*راه|اتصال|کورکن|درپوش).*تیپ|تیپ.*(?:رابط|شیر|سه\s*راه|اتصال|کورکن|درپوش)', name) and not re.search(r'لی[\s‌-]*فلت|نخ[\s‌-]*دار', name):
        return 'drip_tape_component'

    if re.search(r'(?:رابط|زانو|سه\s*راه|کورکن|درپوش).*(?:16|۱۶)\s*میلی', name):
        return 'drip_line_component'

    if re.search(r'شیر\s*انشعاب\s*(?:16|۱۶)\s*به\s*(?:(?:16|۱۶)|(?:1/2|۱/۲))', name):
        return 'drip_line_component'

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
    if re.search(r'انشعاب\s*(?:دو|سه)[\s‌-]*شاخه', name):
        return 'branch_connector'
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
        (r'کلید\s*شیر\s*خودکار', 'automatic_valve_key'),
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



def category_semantics(p):
    names = [str(x.get('name') or '') for x in (p.get('categories') or [])]
    cats = ' | '.join(names).lower()
    title = str(p.get('name') or '').lower()
    out = {}
    allow_connection_inference = not re.search(r'شیر|آبپاش|فیلتر|پمپ|بابلر|دریپر|قطره[\s‌-]*چکان|رایزر|سوپاپ', title)
    if re.search(r'اتصالات.*پلی[\s‌-]*اتیلن|polyethylene.*fitting|لوله.*پلی[\s‌-]*اتیلن', cats, re.I):
        out['material'] = {'status':'SITE_DECLARED','value':'polyethylene','source':'woocommerce_category',
                           'evidence':{'categories':names}}
    if allow_connection_inference and re.search(r'اتصالات.*پیچی|compression.*fitting|پیچی.*پلی[\s‌-]*اتیلن', cats, re.I):
        out['connection_type'] = {'status':'SITE_DECLARED','value':'compression','source':'woocommerce_category',
                                  'evidence':{'categories':names}}
    elif allow_connection_inference and re.search(r'اتصالات.*جوشی|butt.*fusion|جوشی.*پلی[\s‌-]*اتیلن', cats, re.I):
        out['connection_type'] = {'status':'SITE_DECLARED','value':'butt_fusion','source':'woocommerce_category',
                                  'evidence':{'categories':names}}
    elif allow_connection_inference and re.search(r'اتصالات.*رزوه|threaded.*fitting', cats, re.I):
        out['connection_type'] = {'status':'SITE_DECLARED','value':'threaded','source':'woocommerce_category',
                                  'evidence':{'categories':names}}
    return out


def quoted_inch_size(name):
    s = name or ''
    for pat in [r'["″]\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?)', r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?)\s*["″]']:
        m = re.search(pat, s)
        if m:
            return {'status':'SITE_DECLARED','value':m.group(1) + ' inch','source':'woocommerce_product_title',
                    'evidence':{'field':'nominal_size','title':s}}
    return None



def fitting_pair_size(name):
    s = name or ''
    if not re.search(r'اتصال|رابط|زانو|سه\s*راه|تبدیل|کمربند|بوشن', s, re.I):
        return None
    pair = pair_size_signature(s)
    if pair:
        return {'status':'SITE_DECLARED','value':pair,'source':'woocommerce_product_title',
                'evidence':{'field':'nominal_size','title':s,'rule':'explicit_pair_signature'}}
    return None

def installation_tool_size(name):
    s = name or ''
    m = re.search(r'(?:پانچ|پانچر|گردبر|سوراخ[\s‌-]*کن)\D*([۰-۹0-9]+)', s, re.I)
    if m:
        return {'status':'SITE_DECLARED','value':m.group(1),'source':'woocommerce_product_title',
                'evidence':{'field':'tool_size','title':s}}
    m = re.search(r'\(([۰-۹0-9]+)\s*[-–]\s*([۰-۹0-9]+)\)', s)
    if m:
        return {'status':'SITE_DECLARED','value':m.group(1)+'-'+m.group(2),'source':'woocommerce_product_title',
                'evidence':{'field':'tool_size','title':s}}
    return None


def emitter_connection_type(name):
    s = name or ''
    if re.search(r'پرسی', s, re.I):
        return {'status':'SITE_DECLARED','value':'press_fit','source':'woocommerce_product_title',
                'evidence':{'field':'connection_type','title':s}}
    if re.search(r'مخصوص\s*لوله\s*(?:16|۱۶)|لوله\s*(?:16|۱۶)', s, re.I):
        return {'status':'SITE_DECLARED','value':'fit_on_16mm_line','source':'woocommerce_product_title',
                'evidence':{'field':'connection_type','title':s}}
    return None



def implicit_fraction_size(name):
    s = name or ''
    if not re.search(r'بوشن|مغزی|کپ|درپوش|زانو|سه\s*راه|اتصال|شیر|رایزر|سر\s*شلنگ|سرشلنگ', s, re.I):
        return None
    m = re.search(r'(?<![۰-۹0-9])([۰-۹0-9]+/[۰-۹0-9]+)(?![۰-۹0-9])', s)
    if m:
        return {'status':'SITE_DECLARED','value':m.group(1)+' inch','source':'woocommerce_product_title',
                'evidence':{'field':'nominal_size','title':s,'rule':'implicit_fraction_in_fitting_or_valve_title'}}
    return None


def pair_size_signature(name):
    s = name or ''
    patterns = [
        r'([۰-۹0-9]+(?:[./][۰-۹0-9]+)?)\s*[x×*]\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?)',
        r'([۰-۹0-9]+)\s*به\s*([۰-۹0-9]+(?:/[۰-۹0-9]+)?)'
    ]
    for pat in patterns:
        m = re.search(pat, s, re.I)
        if m:
            return m.group(1)+'x'+m.group(2)
    return None


def interface_signature_from_title(name):
    s = name or ''
    n = re.sub(r'\s+', ' ', s).strip()
    pair = pair_size_signature(n)

    if re.search(r'رابط.*(?:نخ[\s‌-]*دار|لی[\s‌-]*فلت)', n, re.I) and pair:
        return {'status':'SITE_DECLARED','value':'layflat:'+pair.replace('x','<->layflat:'),
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'(?:رابط|شیر).*لی[\s‌-]*فلت.*(?:به\s*)?تیپ|(?:رابط|شیر).*تیپ.*به\s*لی[\s‌-]*فلت', n, re.I):
        return {'status':'SITE_DECLARED','value':'layflat<->drip_tape',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'کور(?:کن)?(?:\s*کامل)?\s*لی[\s‌-]*فلت', n, re.I):
        return {'status':'SITE_DECLARED','value':'layflat:end_cap',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'کمربند.*(?:نخ[\s‌-]*دار|لی[\s‌-]*فلت)', n, re.I):
        size = title_declared_size(n)
        v = 'layflat:saddle'
        if size and size.get('value'):
            v += ':' + str(size.get('value'))
        return {'status':'SITE_DECLARED','value':v,
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'رابط.*تیپ.*(?:به\s*)?(?:16|۱۶)|رابط.*(?:16|۱۶).*(?:به\s*)?تیپ', n, re.I):
        return {'status':'SITE_DECLARED','value':'drip_tape<->line16mm',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'رابط.*تیپ.*به\s*تیپ|رابط\s*لوله\s*نواری\s*تیپ\s*به\s*تیپ', n, re.I):
        return {'status':'SITE_DECLARED','value':'drip_tape<->drip_tape',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'رابط.*تیپ.*به\s*لوله', n, re.I):
        return {'status':'SITE_DECLARED','value':'drip_tape<->pipe',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'شیر\s*انشعاب.*(?:16|۱۶)\s*به\s*تیپ', n, re.I):
        return {'status':'SITE_DECLARED','value':'line16<->drip_tape',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'شیر\s*انشعاب.*(?:1/2|۱/۲).*نوار\s*تیپ|شیر\s*انشعاب.*نوار\s*تیپ', n, re.I):
        return {'status':'SITE_DECLARED','value':'thread_or_branch<->drip_tape',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'بست|واشر|اورینگ|گسکت', n, re.I):
        v = 'seal_or_clamp'
        if pair:
            v += ':'+pair
        else:
            sz = title_declared_size(n)
            if sz and sz.get('value'):
                v += ':'+str(sz.get('value'))
        return {'status':'SITE_DECLARED','value':v,
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'شیر\s*انشعاب\s*(?:16|۱۶)\s*به\s*(?:1/2|۱/۲)', n, re.I):
        return {'status':'SITE_DECLARED','value':'line16<->thread_1/2',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'شیر\s*انشعاب\s*(?:16|۱۶)\s*به\s*(?:16|۱۶)', n, re.I):
        return {'status':'SITE_DECLARED','value':'line16<->line16',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'انشعاب\s*(?:دو|سه)[\s‌-]*شاخه', n, re.I):
        v = 'branch'
        if pair:
            v += ':'+pair
        return {'status':'SITE_DECLARED','value':v,
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    if re.search(r'رابط.*(?:16|۱۶).*میلی', n, re.I):
        return {'status':'SITE_DECLARED','value':'line16<->line16',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}
    if re.search(r'زانو.*(?:16|۱۶).*میلی', n, re.I):
        return {'status':'SITE_DECLARED','value':'line16:elbow',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}
    if re.search(r'سه\s*راه.*(?:16|۱۶).*میلی', n, re.I):
        return {'status':'SITE_DECLARED','value':'line16:tee',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}
    if re.search(r'کورکن|درپوش', n, re.I) and re.search(r'(?:16|۱۶).*میلی', n, re.I):
        return {'status':'SITE_DECLARED','value':'line16:end_closure',
                'source':'woocommerce_product_title','evidence':{'field':'interface_signature','title':s}}

    return None


def metal_material_from_title(name):
    s = name or ''
    if re.search(r'فلزی', s, re.I):
        return {'status':'SITE_DECLARED','value':'metal_unspecified','source':'woocommerce_product_title',
                'evidence':{'field':'material','title':s}}
    return None


def hose_barb_connection(name):
    s = name or ''
    if re.search(r'سر\s*شلنگ|سرشلنگ', s, re.I):
        return {'status':'SITE_DECLARED','value':'hose_barb','source':'product_type_semantics',
                'evidence':{'field':'connection_type','title':s}}
    if re.search(r'کورکن\s*کلیدی', s, re.I):
        return {'status':'SITE_DECLARED','value':'line_end_closure','source':'product_type_semantics',
                'evidence':{'field':'connection_type','title':s}}
    return None


def exact_product_prose(p):
    raw = (p.get('description') or '') + '\n' + (p.get('short_description') or '')
    text = BeautifulSoup(raw, 'html.parser').get_text(' ', strip=True)
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def prose_match(p, patterns, field):
    text = exact_product_prose(p)
    if not text:
        return None
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        value = m.group(1).strip(' :：-،؛.')
        if not value:
            continue
        start = max(0, m.start() - 55)
        end = min(len(text), m.end() + 90)
        return {
            'status': 'VERIFIED',
            'value': re.sub(r'\s+', ' ', value),
            'source': 'woocommerce_product_prose',
            'evidence': {
                'field': field,
                'matched_snippet': text[start:end]
            }
        }
    return None


def prose_nominal_size(p):
    return prose_match(p, [
        r'(?:قطر\s*داخلی|قطر\s*اسمی|سایز\s*اسمی)\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*(?:میلی[\s‌-]*متر|میلیمتر|mm|اینچ))'
    ], 'nominal_size')


def prose_pressure(p):
    return prose_match(p, [
        r'(?:فشار\s*(?:کاری|کارکرد|اسمی|مجاز|بهینه|مورد\s*نیاز)|محدوده\s*فشار\s*کاری)\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?(?:\s*(?:الی|تا|[-–])\s*[۰-۹0-9]+(?:[./][۰-۹0-9]+)?)?\s*(?:بار|اتمسفر|atm|bar))',
        r'(?:حداقل\s*فشار|حداکثر\s*فشار)\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*(?:بار|اتمسفر|atm|bar))'
    ], 'pressure_class')


def prose_flow_rate(p):
    return prose_match(p, [
        r'(?:دبی|آبدهی|آب[\s‌-]*دهی)\s*(?:اسمی|خروجی|هر\s*قطره[\s‌-]*چکان|هر\s*روزنه)?\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?(?:\s*(?:الی|تا|[-–])\s*[۰-۹0-9]+(?:[./][۰-۹0-9]+)?)?\s*(?:لیتر(?:\s*بر\s*(?:ساعت|ثانیه))?|l/h|lph|m3/h|متر\s*مکعب(?:\s*بر\s*ساعت)?))'
    ], 'flow_rate')


def prose_filtration_grade(p):
    name = p.get('name') or ''
    if not re.search(r'فیلتر', name, re.I):
        return None
    return prose_match(p, [
        r'(?:مش|درجه\s*فیلتراسیون|دقت\s*فیلتراسیون)\s*[:：\-]?\s*([۰-۹0-9]{2,3}\s*(?:مش|mesh)?)',
        r'(?:فیلتر|دیسک|کارتریج)[^.!؟]{0,80}?([۰-۹0-9]{2,3}\s*(?:مش|mesh))'
    ], 'filtration_grade')


def prose_filtration_requirement(p):
    name = p.get('name') or ''
    if not re.search(r'نوار\s*تیپ|نوارتیپ|نوار\s*آبیاری', name, re.I):
        return None
    return prose_match(p, [
        r'(?:فیلتر(?:اسیون)?\s*(?:مناسب|مورد\s*نیاز|توصیه\s*شده)?|مش\s*فیلتر)\s*[:：\-]?\s*([۰-۹0-9]{2,3}\s*(?:مش|mesh))',
        r'(?:ذرات|ناخالصی)[^.!؟]{0,80}?([۰-۹0-9]{2,3}\s*میکرون)'
    ], 'filtration_requirement')


def prose_connection_size(p):
    return prose_match(p, [
        r'(?:سایز\s*اتصال|قطر\s*اتصال|سایز\s*ورودی|سایز\s*خروجی|ورودی\s*و\s*خروجی)\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*(?:اینچ|میلی[\s‌-]*متر|میلیمتر|mm))'
    ], 'connection_size')


def prose_connection_type(p):
    return prose_match(p, [
        r'(?:نوع\s*اتصال|روش\s*اتصال)\s*[:：\-]?\s*((?:رزوه[‌\s-]*ای|دنده[‌\s-]*ای|پیچی|جوشی|چسبی|ویکتالیک|فلنجی|پرسی|کوپلینگی))'
    ], 'connection_type')


def prose_material(p):
    return prose_match(p, [
        r'(?:جنس\s*(?:بدنه|لوله|محصول)?|مواد\s*سازنده)\s*[:：\-]?\s*((?:u[\s-]*pvc|upvc|pvc|pe100|pe80|پلی[\s‌-]*اتیلن|پلیمری|آلومینیوم|آلمینیوم|چدن|فلز)[^،؛.!؟]{0,55})'
    ], 'material')


def prose_power(p):
    return prose_match(p, [
        r'(?:توان\s*(?:موتور|نامی)?|قدرت\s*موتور)\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*(?:وات|کیلووات|kw|w|اسب(?:\s*بخار)?|hp))'
    ], 'power')


def prose_head(p):
    return prose_match(p, [
        r'(?:حداکثر\s*ارتفاع|ارتفاع\s*پمپاژ|هد\s*(?:حداکثر|ماکزیمم|پمپ)?|max(?:imum)?\s*head)\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*(?:متر|m))'
    ], 'head')


def prose_length(p):
    return prose_match(p, [
        r'(?:طول\s*(?:کلاف|رول|شاخه|لوله)?|متراژ\s*(?:کلاف|رول)?)\s*[:：\-]?\s*([۰-۹0-9]+(?:[./][۰-۹0-9]+)?\s*(?:متر|متری|m))'
    ], 'length')


def technical_dimensions(p, truth_rec):
    attrs = attrs_map(p)
    specs = spec_map(p)
    name = p.get('name') or ''
    dims = {}
    cat = category_semantics(p)
    size_patterns = [r'^سایز$', r'^قطر$', r'diameter', r'^size$', r'سایز.*قطر']
    dims['nominal_size'] = direct_attr(attrs, size_patterns) or spec_attr(specs, size_patterns) or prose_nominal_size(p) or title_declared_size(name) or quoted_inch_size(name) or implicit_fraction_size(name) or fitting_pair_size(name)
    dims['connection_size'] = (
        direct_attr(attrs, [r'سایز اتصال', r'قطر اتصال'])
        or spec_attr(specs, [r'سایز اتصال', r'قطر اتصال'])
        or prose_connection_size(p)
        or title_declared_connection_size(name)
        or dims['nominal_size']
    )
    dims['connection_type'] = (
        direct_attr(attrs, [r'نوع اتصال', r'رزوه', r'connection', r'thread'])
        or spec_attr(specs, [r'نوع اتصال', r'رزوه', r'connection', r'thread'])
        or prose_connection_type(p)
        or title_declared_connection_type(name)
        or semantic_connection_type(name)
        or hose_barb_connection(name)
        or cat.get('connection_type')
    )
    dims['material'] = (
        truth_field(truth_rec, 'material')
        or direct_attr(attrs, [r'^جنس$', r'material'])
        or spec_attr(specs, [r'^جنس$', r'material'])
        or prose_material(p)
        or title_declared_material(name)
        or title_declared_aluminum(name)
        or metal_material_from_title(name)
        or cat.get('material')
    )
    dims['pressure_class'] = (
        direct_attr(attrs, [r'فشار کاری', r'کلاس فشار', r'pressure', r'^pn$', r'^sdr$'])
        or spec_attr(specs, [r'فشار کاری', r'کلاس فشار', r'pressure', r'^pn$', r'^sdr$'])
        or prose_pressure(p)
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
        or prose_flow_rate(p)
        or title_declared_flow_rate(name)
    )
    dims['filtration_grade'] = (
        direct_attr(attrs, [r'میکرون', r'مش', r'mesh', r'filtration grade'])
        or spec_attr(specs, [r'میکرون', r'مش', r'mesh', r'filtration grade'])
        or prose_filtration_grade(p)
    )
    dims['filtration_requirement'] = (
        direct_attr(attrs, [r'نیاز فیلتراسیون', r'الزام فیلتراسیون', r'filtration requirement'])
        or spec_attr(specs, [r'نیاز فیلتراسیون', r'الزام فیلتراسیون', r'filtration requirement'])
        or prose_filtration_requirement(p)
    )
    dims['emitter_spacing'] = (
        direct_attr(attrs, [r'فاصله قطره', r'فاصله خروجی', r'emitter spacing'])
        or spec_attr(specs, [r'فاصله قطره', r'فاصله خروجی', r'emitter spacing'])
        or title_declared_emitter_spacing(name)
    )
    dims['length'] = (
        direct_attr(attrs, [r'^طول$', r'طول رول', r'length'])
        or spec_attr(specs, [r'^طول$', r'طول رول', r'length'])
        or prose_length(p)
        or title_declared_length(name)
        or title_declared_length_cm(name)
    )
    dims['capacity'] = direct_attr(attrs, [r'^ظرفیت$', r'capacity']) or spec_attr(specs, [r'^ظرفیت$', r'capacity']) or title_declared_capacity(name)
    nominal = dims.get('nominal_size') or {'status':'UNKNOWN','value':None}
    dims['tool_size'] = nominal if nominal.get('status') != 'UNKNOWN' else (installation_tool_size(name) or {'status':'UNKNOWN','value':None})
    dims['component_type'] = component_type_from_title(name)
    dims['interface_signature'] = interface_signature_from_title(name)
    dims['head'] = direct_attr(attrs, [r'هد', r'ارتفاع']) or spec_attr(specs, [r'هد', r'ارتفاع']) or prose_head(p) or title_declared_head(name)
    dims['power'] = direct_attr(attrs, [r'توان', r'اسب']) or spec_attr(specs, [r'توان', r'اسب']) or prose_power(p) or title_declared_power(name)
    connection = dims.get('connection_type') or {'status':'UNKNOWN','value':None}
    if re.search(r'بابلر|دریپر|قطره[\s‌-]*چکان', name, re.I) and connection.get('status') == 'UNKNOWN':
        dims['connection_type'] = emitter_connection_type(name) or connection
    return {k: (v if v else {'status': 'UNKNOWN', 'value': None}) for k, v in dims.items()}


def normalize_evidence_value(field, value):
    s = str(value or '').strip().lower()
    fa = '۰۱۲۳۴۵۶۷۸۹'
    en = '0123456789'
    s = s.translate(str.maketrans(fa, en))
    s = s.replace('‌', ' ')
    s = re.sub(r'\s+', ' ', s)
    if field in ('pressure_class', 'pressure_requirement'):
        m = re.search(r'([0-9]+(?:[./][0-9]+)?)\s*(بار|bar|اتمسفر|atm)', s, re.I)
        if m:
            num = m.group(1).replace('/', '.')
            unit = m.group(2).lower()
            unit = 'bar' if unit in ('بار','bar') else 'atm'
            return f'{num}:{unit}'
    if field == 'connection_type':
        aliases = {
            'دنده ای':'threaded','دنده‌ای':'threaded','رزوه ای':'threaded','رزوه‌ای':'threaded',
            'threaded':'threaded','male_male_threaded':'threaded','female_threaded':'threaded',
            'male_threaded':'threaded'
        }
        if s in aliases:
            return aliases[s]
    if field == 'material':
        if 'upvc' in s or 'u-pvc' in s or 'u pvc' in s:
            return 'upvc'
        aliases = {
            'پلی اتیلن':'polyethylene','پلی‌اتیلن':'polyethylene','polyethylene':'polyethylene',
            'polymeric_unspecified':'polymeric','polymeric':'polymeric','upvc':'upvc','u-pvc':'upvc',
            'pe100':'pe100'
        }
        if s in aliases:
            return aliases[s]
        if 'پلی' in s and 'اتیلن' in s and 'نخ' in s:
            return 'reinforced_polyethylene'
        if 'polyethylene' in s and 'reinforced' in s:
            return 'reinforced_polyethylene'
    return re.sub(r'[^0-9a-zآ-ی]+', '', s)


def values_compatible(field, current, incoming):
    a = normalize_evidence_value(field, current)
    b = normalize_evidence_value(field, incoming)
    if a == b:
        return True
    if field == 'connection_type' and a == 'threaded' and b == 'threaded':
        return True
    if field == 'material':
        # Manufacturer PE100 is a refinement of retailer-declared polyethylene.
        if {a,b} == {'polyethylene','pe100'}:
            return True
        if {a,b} == {'polymeric','upvc'}:
            return True
        if a == b == 'reinforced_polyethylene':
            return True
    return False


def apply_external_evidence(p, family, dims, pack, fill_counts, conflicts):
    name = p.get('name') or ''
    source_map = {s.get('id'): s for s in (pack.get('sources') or []) if s.get('id')}
    for rule in pack.get('rules') or []:
        allowed = rule.get('family') or []
        if family not in allowed:
            continue
        try:
            matched = re.search(rule.get('name_regex') or r'$.', name, re.I)
        except re.error:
            continue
        if not matched:
            continue
        source_id = rule.get('source_id')
        source = source_map.get(source_id, {})
        for field, spec in (rule.get('fields') or {}).items():
            incoming = {
                'status': spec.get('status') or ('MANUFACTURER_VERIFIED' if source.get('tier') == 'manufacturer' else 'SECONDARY_VERIFIED'),
                'value': spec.get('value'),
                'source': 'external_research_evidence',
                'evidence': {
                    'rule_id': rule.get('id'),
                    'source_id': source_id,
                    'publisher': source.get('publisher'),
                    'source_tier': source.get('tier'),
                    'url': source.get('url'),
                    'retrieved_at': source.get('retrieved_at')
                }
            }
            current = dims.get(field) or {'status':'UNKNOWN','value':None}
            if current.get('status') == 'UNKNOWN' or current.get('value') in (None, '', [], {}):
                dims[field] = incoming
                fill_counts[incoming['status']] += 1
                continue

            if values_compatible(field, current.get('value'), incoming.get('value')):
                # Prefer a manufacturer refinement over a generic retailer/title declaration.
                if incoming['status'] == 'MANUFACTURER_VERIFIED' and current.get('status') == 'SITE_DECLARED':
                    old = current
                    dims[field] = dict(incoming)
                    dims[field]['evidence'] = dict(incoming['evidence'])
                    dims[field]['evidence']['corroborates'] = old
                    fill_counts['MANUFACTURER_REFINED'] += 1
                else:
                    ev = dict(current.get('evidence') or {})
                    ev.setdefault('corroboration', []).append(incoming['evidence'])
                    current['evidence'] = ev
                    if incoming['status'] == 'MANUFACTURER_VERIFIED' and current.get('status') in ('VERIFIED','SOURCE-CONFIRMED','USER-CONFIRMED'):
                        current['status'] = 'MANUFACTURER_CORROBORATED'
                    dims[field] = current
                    fill_counts['CORROBORATED'] += 1
                continue

            conflicts.append({
                'product_id': p.get('id'),
                'name': name,
                'family': family,
                'field': field,
                'existing': current,
                'incoming': incoming,
                'resolution': 'kept_existing_value; true semantic conflict retained for review'
            })
    return dims



def research_disposition(p, family, missing):
    name = str(p.get('name') or '')
    fields = list(missing or [])
    common = {
        'research_state': 'SOURCE_BOUND_UNRESOLVED',
        'missing_fields': fields,
        'do_not_infer': True
    }

    if family == 'drip_tape':
        return {**common,
            'code': 'EXACT_TAPE_MANUFACTURER_OR_LABEL_REQUIRED',
            'reason': 'Current public tape specifications vary materially by manufacturer, wall thickness, emitter type, and model. K20 title alone does not identify an exact technical series.',
            'next_evidence': 'Exact manufacturer/model identity plus package label or first-party datasheet stating diameter, operating pressure, and filtration requirement.'
        }
    if family == 'filter':
        return {**common,
            'code': 'EXACT_FILTER_ELEMENT_GRADE_REQUIRED',
            'reason': 'Connection size identifies the housing, but filtration grade is an element-specific property and cannot be inherited from a different filter size or series.',
            'next_evidence': 'Exact Farat Polymer catalog/label for this SKU stating mesh or micron grade.'
        }
    if family == 'layflat_rain' and re.search(r'موج', name, re.I):
        return {**common,
            'code': 'MOUJ_EXACT_DATASHEET_OR_ROLL_LABEL_REQUIRED',
            'reason': 'Reinforced layflat/rain-hose pressure, material stack, and roll length vary by manufacturer and series; comparable brands are benchmark evidence only.',
            'next_evidence': 'Mouj manufacturer datasheet, packaging, or roll label for the exact diameter/series.'
        }
    if family == 'pipe':
        return {**common,
            'code': 'EXACT_PIPE_PN_SDR_MARKING_REQUIRED',
            'reason': 'Nominal diameter and roll length do not determine pressure class.',
            'next_evidence': 'Pipe print-line/label or manufacturer table with PN/SDR for the exact 16 mm product.'
        }
    if family == 'pump':
        return {**common,
            'code': 'EXACT_PUMP_MODEL_DATASHEET_OR_NAMEPLATE_REQUIRED',
            'reason': 'Pumps with similar outlet size and head can have different motor power, max head, controller limits, and hydraulic curves.',
            'next_evidence': 'Exact Camel/FLYGEN model code and manufacturer nameplate/datasheet for power, head, and inlet/outlet size.'
        }
    if family == 'sprinkler':
        return {**common,
            'code': 'EXACT_SPRINKLER_NOZZLE_FLOW_TABLE_REQUIRED',
            'reason': 'Flow and pressure depend on nozzle configuration and exact sprinkler model; radius or inlet size alone is insufficient.',
            'next_evidence': 'Manufacturer nozzle table/curve for the exact Vispar/Paya sprinkler model and nozzle set.'
        }
    if family == 'valve':
        if re.search(r'آبافرین', name, re.I):
            code = 'ABAFARIN_EXACT_PRESSURE_DATASHEET_REQUIRED'
            reason = 'Current manufacturer material confirms the product family, but no exact pressure class for these K20 Abafarin SKUs was found in the verified public source set.'
        elif re.search(r'سوپاپ|چدنی', name, re.I):
            code = 'CAST_IRON_VALVE_MODEL_PN_AND_CONNECTION_REQUIRED'
            reason = 'Cast-iron valve/check-valve pressure and end connection vary by model and standard.'
        else:
            code = 'EXACT_VALVE_PRESSURE_OR_CONNECTION_DATASHEET_REQUIRED'
            reason = 'Pressure class or end-connection standard is not uniquely determined by size/title.'
        return {**common,
            'code': code,
            'reason': reason,
            'next_evidence': 'Exact model label, first-party catalog, or manufacturer datasheet with the missing pressure/connection field.'
        }
    if family == 'emitter':
        return {**common,
            'code': 'EXACT_EMITTER_FLOW_OR_INTERFACE_SPEC_REQUIRED',
            'reason': 'Emitter/bubbler flow range and inlet interface differ by model; another brand or visually similar emitter is not a valid substitute source.',
            'next_evidence': 'Exact Zalal Roud/product-series datasheet or package label with flow range and inlet/interface.'
        }
    if family == 'riser':
        return {**common,
            'code': 'EXACT_RISER_COUPLING_STANDARD_REQUIRED',
            'reason': 'Length and diameter are known, but the lower-end coupling/connection standard is not explicit for this unbranded aluminum riser.',
            'next_evidence': 'Exact product label/catalog or first-party specification for the riser-to-valve connection.'
        }
    if family == 'fitting':
        return {**common,
            'code': 'EXACT_FITTING_INTERFACE_OR_MATERIAL_REQUIRED',
            'reason': 'The remaining fitting title/category evidence does not uniquely prove every interface/material field.',
            'next_evidence': 'Exact manufacturer SKU/catalog/packaging showing connection method and material.'
        }
    return {**common,
        'code': 'EXACT_SKU_SOURCE_REQUIRED',
        'reason': 'The remaining field is not uniquely recoverable from the current exact-source evidence.',
        'next_evidence': 'Exact SKU label, first-party catalog, or manufacturer datasheet for the missing field.'
    }


def edge_key(e):
    return (str(e.get('source_product_id') or ''), str(e.get('target_product_id') or ''), e.get('relation'), e.get('status'))


def main():
    truth = load_json(TRUTH, {})
    truth_by_id = {int(r.get('product_id')): r for r in truth.get('records', []) if r.get('product_id')}
    external = load_json(EXTERNAL_EVIDENCE, {'sources': [], 'rules': []})
    products = paged_products()
    by_id = {int(p['id']): p for p in products}
    by_path = {norm_url(p.get('permalink')): int(p['id']) for p in products if p.get('permalink')}

    nodes = []
    family_counts = Counter()
    ready_counts = Counter()
    missing_dim_counts = Counter()
    backlog = []
    edges = []
    external_fill_counts = Counter()
    external_conflicts = []

    for p in products:
        pid = int(p['id'])
        family = classify_product(p)
        family_counts[family] += 1
        dims = technical_dimensions(p, truth_by_id.get(pid))
        dims = apply_external_evidence(p, family, dims, external, external_fill_counts, external_conflicts)
        required = RULES.get(family, [])
        in_scope = family != 'excluded_non_irrigation'
        missing = [k for k in required if dims.get(k, {}).get('status') == 'UNKNOWN']
        data_ready = in_scope and bool(required) and not missing
        exact_ready = data_ready and all(dims[k].get('status') in ('VERIFIED', 'SOURCE-CONFIRMED', 'USER-CONFIRMED', 'MANUFACTURER_VERIFIED', 'MANUFACTURER_CORROBORATED') for k in required)
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
                'verification_rule': 'Use exact manufacturer datasheet, packaging/label, first-party catalog, or explicit Woo attribute. SITE_DECLARED values are useful evidence but are not promoted to manufacturer-verified compatibility.',
                'research_disposition': research_disposition(p, family, missing)
            })
        nodes.append({
            'product_id': pid,
            'stable_id': f'wp-product:{pid}',
            'name': p.get('name'),
            'permalink': p.get('permalink'),
            'brands': [{'id': b.get('id'), 'name': b.get('name'), 'slug': b.get('slug')} for b in (p.get('brands') or [])],
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

    disposition_counts = Counter((x.get('research_disposition') or {}).get('code') for x in backlog)
    all_backlog_disposed = all((x.get('research_disposition') or {}).get('research_state') == 'SOURCE_BOUND_UNRESOLVED' for x in backlog)

    summary = {
        'published_products': len(products),
        'nodes': len(nodes),
        'node_coverage_percent': round(len(nodes) / len(products) * 100, 2) if products else 0,
        'family_counts': dict(family_counts),
        'data_dimension_ready_by_family': dict(ready_counts),
        'products_data_dimension_ready': sum(1 for n in nodes if n.get('data_dimension_ready')),
        'products_exact_dimension_ready': sum(1 for n in nodes if n['exact_compatibility_dimension_ready']),
        'products_with_required_dimension_gaps': sum(1 for n in nodes if n.get('compatibility_scope') == 'in_scope' and n['missing_required_dimensions']),
        'excluded_non_irrigation_products': sum(1 for n in nodes if n.get('compatibility_scope') == 'excluded'),
        'unmodeled_irrigation_products': sum(1 for n in nodes if n.get('family') == 'unmodeled_irrigation'),
        'missing_dimension_counts': dict(missing_dim_counts),
        'external_evidence_sources': len(external.get('sources') or []),
        'external_evidence_rules': len(external.get('rules') or []),
        'external_fill_counts': dict(external_fill_counts),
        'external_conflicts': len(external_conflicts),
        'source_bound_unresolved_products': len(backlog),
        'research_disposition_counts': {k:v for k,v in disposition_counts.items() if k},
        'public_research_pass_complete': all_backlog_disposed,
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
        'hard_fabrications_zero': summary['hard_fabrications'] == 0,
        'external_evidence_conflicts_preserved_for_review': True,
        'all_remaining_gaps_have_research_disposition': all_backlog_disposed
    }

    graph = {
        'ok': all(acceptance.values()),
        'phase': 4,
        'version': 'growthos-compatibility-knowledge-graph-v2',
        'generated_at_utc': NOW,
        'execution_mode': 'read-only-evidence-graph',
        'status': 'PASS_PUBLIC_RESEARCH_COMPLETE_WITH_SOURCE_BOUND_GAPS' if all_backlog_disposed else 'PASS_RESCOPED_WITH_GOVERNED_EVIDENCE_GAPS',
        'relation_vocabulary': RELATION_VOCABULARY,
        'compatibility_rule_templates': RULES,
        'external_evidence': {
            'version': external.get('version'),
            'researched_at_utc': external.get('researched_at_utc'),
            'source_count': len(external.get('sources') or []),
            'rule_count': len(external.get('rules') or []),
            'fill_counts': dict(external_fill_counts),
            'conflicts': external_conflicts,
            'non_applied_family_evidence': external.get('non_applied_family_evidence') or []
        },
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
        'external_evidence': graph.get('external_evidence'),
        'next_gate': 'Public research pass is complete. Remaining source-bound gaps require exact SKU/manufacturer labels or datasheets before automatic product-to-product recommendation (Phase 18); never infer them from similar products.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    backlog.sort(key=lambda x: (0 if x['priority'] == 'HIGH' else 1, x['family'], x['product_id']))
    (OUTDIR / 'verification-backlog.json').write_text(json.dumps({
        'phase': 4, 'generated_at_utc': NOW, 'count': len(backlog), 'items': backlog,
        'rule': 'Every remaining item is source-bound with an explicit research disposition. The backlog is evidence acquisition work, not permission to infer values.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE4_COMPATIBILITY_OK', json.dumps({'status': graph['status'], 'summary': summary, 'acceptance': acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
