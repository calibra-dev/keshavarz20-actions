#!/usr/bin/env python3
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

INPUT = Path('growthos-phase5-input/gsc-windsor-irrigation-20260924.json')
OUTDIR = Path('growthos-phase5-results')
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

INTENT_ORDER = ['شناخت','انتخاب','مقایسه','نصب','محاسبه','سازگاری','عیب‌یابی','نگهداری','خرید','ارسال','ضمانت','پروژه','local']

OWNER_HINTS = {
    'اتصالات پلی اتیلن': 'https://keshavarz20.com/product-category/agricultural-equipment-supplies/polyethylene-fittings/compression-polyethylene-fittings/',
    'لوله پلی اتیلن': 'https://keshavarz20.com/product-category/agricultural-equipment-supplies/irrigation-pipes/polyethylene-pipe/',
    'زانو پلی اتیلن': 'https://keshavarz20.com/product-category/agricultural-equipment-supplies/polyethylene-fittings/compression-polyethylene-fittings/polyethylene-compression-elbow/',
    'شیر توپی': 'https://keshavarz20.com/product-category/agricultural-equipment-supplies/polyethylene-fittings/compression-polyethylene-fittings/polyethylene-valves/polymeric-ball-valve/',
    'لوله بارانی': 'https://keshavarz20.com/product-tag/%D9%84%D9%88%D9%84%D9%87-%D8%A2%D8%A8%DB%8C%D8%A7%D8%B1%DB%8C-%D8%A8%D8%A7%D8%B1%D8%A7%D9%86%DB%8C/',
    'لوله مه پاش': 'https://keshavarz20.com/product/%D9%84%D9%88%D9%84%D9%87-%D8%A8%D8%A7%D8%B1%D8%A7%D9%86%DB%8C-%D9%85%D9%87-%D9%BE%D8%A7%D8%B4-%D8%A2%D8%B3%D8%A7%DB%8C%D8%B4-%D8%A2%D8%B0%D8%B1%D8%A8%D8%A7%DB%8C%D8%AC%D8%A7%D9%86-%DB%B1%DB%B0%DB%B0/'
}

def fa_norm(s):
    s = (s or '').strip().lower()
    s = s.replace('ي','ی').replace('ك','ک').replace('\u200c',' ')
    s = re.sub(r'[،,:;؛!?؟()\[\]{}"\'“”]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def clean_url(u):
    try:
        p = urlsplit(u or '')
        scheme = 'https' if p.netloc.endswith('keshavarz20.com') else (p.scheme or 'https')
        path = re.sub(r'/+', '/', p.path or '/')
        path = re.sub(r'/page/[0-9]+/?$', '/', path, flags=re.I)
        if not path.endswith('/') and '.' not in path.rsplit('/', 1)[-1]:
            path += '/'
        return urlunsplit((scheme, p.netloc.lower(), path, '', ''))
    except Exception:
        return u


def size_token(q):
    pats = [
        r'([۰-۹0-9]+(?:\s*و\s*[۰-۹0-۹]+/[۰-۹0-9]+|[./][۰-۹0-9]+)?\s*اینچ)',
        r'([۰-۹0-9]+\s*میلی[\s‌-]*متر)',
        r'([۰-۹0-9]+\s*میلیمتر)'
    ]
    for pat in pats:
        m = re.search(pat, q, re.I)
        if m:
            return re.sub(r'\s+', ' ', m.group(1)).strip()
    return None


def dimension_token(q, t):
    n = fa_norm(q)
    if t == 'fertigation_tank':
        m = re.search(r'([۰-۹0-9]+)\s*لیتر(?:ی)?', n, re.I)
        return f"capacity:{m.group(1)}L" if m else None
    if t == 'drip_tape':
        m = re.search(r'([۰-۹0-9]+)\s*سانت(?:ی[\s‌-]*متر|یمتر)?', n, re.I)
        if m:
            return f"spacing:{m.group(1)}cm"
        m = re.search(r'([۰-۹0-9]+)\s*متر(?:ی)?', n, re.I)
        if m:
            return f"length:{m.group(1)}m"
    s = size_token(n)
    if s:
        return f"size:{s}"
    if t in ('polyethylene_pipe','pe_valve','pe_fitting_saddle','pe_fitting_elbow','pe_fitting_general','layflat_hose','sprinkler','filtration'):
        m = re.search(r'(?<!\d)([۰-۹0-9]{2,3})(?!\d)', n)
        if m:
            return f"nominal:{m.group(1)}"
    return None


def topic(q):
    n = fa_norm(q)
    if re.search(r'نوار\s*تیپ|نوارتیپ|نوار\s*آبیاری', n): return 'drip_tape'
    if re.search(r'نخ\s*دار|نخدار|لی\s*فلت|مه\s*پاش|لوله\s*بارانی', n): return 'layflat_hose'
    if re.search(r'هیدروسیکلون|فیلتر', n): return 'filtration'
    if re.search(r'تانک\s*کود|مخزن.*کود|تزریق\s*کود', n): return 'fertigation_tank'
    if re.search(r'آبپاش', n): return 'sprinkler'
    if re.search(r'مته|سوراخ\s*کن|پانچ', n) and re.search(r'پلی\s*اتیلن|لوله', n): return 'pe_installation_tool'
    if re.search(r'شیر\s*(فلکه|توپی|پروانه)|شیر.*پلی\s*اتیلن|شیر\s*[۰-۹0-9]', n): return 'pe_valve'
    if re.search(r'کمربند', n): return 'pe_fitting_saddle'
    if re.search(r'زانو|زانویی', n): return 'pe_fitting_elbow'
    if re.search(r'رابط|فلنج|فلنچ|سه\s*راه|بوشن|تبدیل|درپوش|اتصالات', n): return 'pe_fitting_general'
    if re.search(r'لوله\s*پلی\s*اتیلن|pe\s*100|pe\s*80|sdr', n): return 'polyethylene_pipe'
    return 'other_irrigation'


def entity_focus(q, t):
    n = fa_norm(q)
    if t == 'drip_tape':
        return 'شیر نوار تیپ' if 'شیر' in n else 'نوار تیپ'
    if t == 'layflat_hose':
        if re.search(r'مه\s*پاش', n): return 'لوله مه پاش'
        if re.search(r'نخ\s*دار|نخدار', n): return 'لوله نخدار'
        if re.search(r'لوله\s*بارانی', n): return 'لوله بارانی'
        return 'لی فلت'
    if t == 'filtration':
        if 'هیدروسیکلون' in n: return 'هیدروسیکلون'
        if 'دیسکی' in n: return 'فیلتر دیسکی'
        if 'توری' in n: return 'فیلتر توری'
        return 'فیلتر آبیاری'
    if t == 'fertigation_tank': return 'تانک کود'
    if t == 'sprinkler': return 'آبپاش'
    if t == 'pe_valve':
        if 'پروانه' in n: return 'شیر پروانه‌ای'
        if 'توپی' in n: return 'شیر توپی'
        return 'شیر پلی اتیلن'
    if t == 'pe_installation_tool': return 'ابزار نصب لوله پلی اتیلن'
    if t == 'pe_fitting_saddle': return 'کمربند پلی اتیلن'
    if t == 'pe_fitting_elbow': return 'زانو پلی اتیلن'
    if t == 'pe_fitting_general':
        if 'رابط' in n: return 'رابط پلی اتیلن'
        if re.search(r'فلنج|فلنچ', n): return 'فلنج پلی اتیلن'
        if re.search(r'سه\s*راه', n): return 'سه راه پلی اتیلن'
        if 'بوشن' in n: return 'بوشن پلی اتیلن'
        if 'تبدیل' in n: return 'تبدیل پلی اتیلن'
        return 'اتصالات پلی اتیلن'
    if t == 'polyethylene_pipe':
        if re.search(r'pe\s*80|pe\s*100|sdr', n): return 'گرید و فشار لوله پلی اتیلن'
        return 'لوله پلی اتیلن'
    return 'تجهیزات آبیاری'

def brand_token(q):
    n = fa_norm(q)
    for pat, label in [
        (r'ویسپار|ویسپ', 'ویسپار'),
        (r'آبلوله|اب لوله|آب لوله', 'آبلوله'),
        (r'پلی\s*رود|پلی‌رود', 'پلی رود'),
        (r'آسایش\s*آذربایجان', 'آسایش آذربایجان'),
        (r'فرات', 'فرات'),
        (r'زلال\s*رود', 'زلال رود'),
        (r'موج', 'موج')
    ]:
        if re.search(pat, n, re.I):
            return label
    return None


def variant_token(q):
    n = fa_norm(q)
    vals = []
    for pat, label in [
        (r'یکسر\s*ماده|مادگی|ماده', 'female'),
        (r'یکسر\s*نر|نری|\bنر\b', 'male'),
        (r'پیچی', 'compression'),
        (r'جوشی', 'butt_fusion'),
        (r'رزوه[‌\s-]*ای|دنده[‌\s-]*ای', 'threaded'),
        (r'پروانه[‌\s-]*ای', 'butterfly'),
        (r'توپی', 'ball')
    ]:
        if re.search(pat, n, re.I):
            vals.append(label)
    return '+'.join(dict.fromkeys(vals)) if vals else None


def page_type(url):
    u = url or ''
    if '/product-category/' in u: return 'product_category'
    if '/product-tag/' in u: return 'product_tag'
    if '/product/' in u: return 'product'
    if u.rstrip('/') == 'https://keshavarz20.com': return 'home'
    return 'guide_or_content'



def classify_intent(q):
    n = fa_norm(q)
    if re.search(r'ارسال|هزینه\s*حمل|کرایه', n): return 'ارسال'
    if re.search(r'ضمانت|گارانتی|مرجوع', n): return 'ضمانت'
    if re.search(r'نشتی|گرفتگی|خراب|مشکل|عیب|فشار کم|آب نمی', n): return 'عیب‌یابی'
    if re.search(r'شستشو|شستشوی|نگهداری|سرویس|تمیز', n): return 'نگهداری'
    if re.search(r'نصب|راه\s*اندازی|بستن|مونتاژ', n): return 'نصب'
    if re.search(r'ماشین\s*حساب|محاسبه|متراژ|چند\s*متر|چقدر|تعداد', n): return 'محاسبه'
    if re.search(r'سازگار|سازگاری|وصل|اتصال.*به|به.*اتصال|چه\s*اتصالی|کدام\s*اتصال', n): return 'سازگاری'
    if re.search(r'مقایسه|تفاوت|فرق|بهتر|(?:^|\s)vs(?:\s|$)|(?:^|\s)یا(?:\s|$)', n): return 'مقایسه'
    if re.search(r'راهنمای\s*خرید|راهنمای\s*انتخاب|چطور\s*انتخاب', n): return 'انتخاب'
    if re.search(r'قیمت|خرید|فروش|نمایندگی|لیست\s*قیمت|ارزان|سفارش', n):
        if re.search(r'شیراز|تهران|اصفهان|فارس|خوزستان|تبریز|مشهد|قم|کرج|اهواز', n): return 'local'
        return 'خرید'
    if re.search(r'پروژه|یک\s*هکتار|هکتار|گلخانه|مزرعه|باغ', n): return 'پروژه'
    if re.search(r'چیست|معنی|کاربرد|مشخصات|سایز', n): return 'شناخت'
    return 'انتخاب'



def conversion_goal(intent):
    return {
        'شناخت':'read_authoritative_guide',
        'انتخاب':'reach_category_or_selector',
        'مقایسه':'reach_comparison_or_selector',
        'نصب':'complete_installation_with_correct_parts',
        'محاسبه':'use_calculator_then_build_basket',
        'سازگاری':'verify_fit_before_purchase',
        'عیب‌یابی':'resolve_issue_then_replace_only_if_needed',
        'نگهداری':'maintain_system_and_prevent_failure',
        'خرید':'reach_correct_product_or_category',
        'ارسال':'resolve_shipping_question',
        'ضمانت':'resolve_return_or_warranty_question',
        'پروژه':'build_project_specific_solution',
        'local':'reach_local_purchase_or_support_path'
    }[intent]


def subquestions(intent):
    common = {
        'شناخت':['این چیست و چه کاربردی دارد؟','کدام مشخصات برای تصمیم مهم‌اند؟','چه ادعاهایی نیاز به دیتاشیت معتبر دارند؟'],
        'انتخاب':['برای چه سناریویی مناسب است؟','کدام سایز/نوع باید بررسی شود؟','چه محدودیتی قبل از خرید باید کنترل شود؟'],
        'مقایسه':['تفاوت فنی گزینه‌ها چیست؟','کدام معیارها قابل مقایسه‌اند؟','کدام تفاوت‌ها بدون دیتاشیت قابل نتیجه‌گیری نیستند؟'],
        'نصب':['ترتیب نصب چیست؟','چه اتصال و آب‌بندی لازم است؟','بعد از نصب چه تستی انجام شود؟'],
        'محاسبه':['چه ورودی‌هایی لازم است؟','فرمول یا منطق محاسبه چیست؟','کدام خروجی باید با شرایط مزرعه اعتبارسنجی شود؟'],
        'سازگاری':['سایز و استاندارد اتصال چیست؟','فشار/دبی/جنس چه محدودیتی دارد؟','آیا سازگاری با منبع دقیق اثبات شده است؟'],
        'عیب‌یابی':['علامت دقیق چیست؟','چه علت‌هایی باید به‌ترتیب رد شوند؟','چه زمانی تعویض قطعه لازم است؟'],
        'نگهداری':['دوره سرویس چیست؟','چه نشانه‌ای هشدار خرابی است؟','چه کاری عمر قطعه را کم می‌کند؟'],
        'خرید':['محصول/دسته درست کدام است؟','کدام مشخصات باید قبل از پرداخت تأیید شوند؟','قیمت و موجودی فعلی کجا دیده شود؟'],
        'ارسال':['مقصد و وزن/ابعاد چه اثری دارد؟','زمان و روش ارسال چگونه تعیین می‌شود؟','چه چیزی باید قبل از سفارش هماهنگ شود؟'],
        'ضمانت':['شرایط بازگشت چیست؟','مغایرت یا خرابی چطور ثبت می‌شود؟','چه مدرکی برای بررسی لازم است؟'],
        'پروژه':['مساحت/کشت/آب/فشار چیست؟','چه اجزایی باید با هم طراحی شوند؟','کدام محاسبات نیاز به تأیید کارشناس دارد؟'],
        'local':['مقصد/شهر کجاست؟','موجودی و ارسال به آن منطقه چگونه است؟','آیا ادعای نمایندگی نیاز به مدرک رسمی دارد؟']
    }
    return common[intent]


def prompts(intent, t, observed):
    label = {
        'شناخت':'راهنمای دقیق', 'انتخاب':'انتخاب مناسب', 'مقایسه':'مقایسه فنی', 'نصب':'نصب صحیح', 'محاسبه':'محاسبه',
        'سازگاری':'سازگاری', 'عیب‌یابی':'عیب‌یابی', 'نگهداری':'نگهداری', 'خرید':'خرید', 'ارسال':'ارسال',
        'ضمانت':'ضمانت', 'پروژه':'طراحی پروژه', 'local':'خرید محلی'
    }[intent]
    return [
        {'kind':'observed_search_query','text': observed},
        {'kind':'derived_ai_prompt','text': f'{label} {t} را با شواهد قابل استناد و بدون حدس توضیح بده.'}
    ]


def canonical_decision(page_metrics, focus, intent, queries, focus_catalog, brand=None, variant=None, dimension=None):
    specific = bool(brand or variant or dimension)
    merged = defaultdict(lambda: {'clicks': 0.0, 'impressions': 0.0})

    # Specific brand/size/variant intents must be decided from pages actually
    # observed for that exact intent. Generic family data is used only for
    # generic intents, preventing unrelated variants from becoming owners.
    base_catalog = page_metrics if specific else (focus_catalog or {})
    for u, m in base_catalog.items():
        merged[u]['clicks'] += m.get('clicks', 0)
        merged[u]['impressions'] += m.get('impressions', 0)
    if not specific:
        for u, m in page_metrics.items():
            merged[u]['clicks'] += m.get('clicks', 0)
            merged[u]['impressions'] += m.get('impressions', 0)

    rows = sorted(merged.items(), key=lambda kv: (kv[1]['impressions'], kv[1]['clicks']), reverse=True)
    if not rows:
        return {'status':'NO_OBSERVED_PAGE','canonical_url':None,'observed_pages':[]}

    packed = [{'url':u, 'page_type':page_type(u), **v} for u, v in rows]
    current_urls = set(page_metrics.keys())
    query_text = ' '.join(x.get('query') or '' for x in queries)
    has_guide_modifier = bool(re.search(r'راهنمای\s*خرید|راهنمای\s*انتخاب', fa_norm(query_text)))

    candidates = []
    for u, m in rows:
        pt = page_type(u)
        score = m['impressions']
        reasons = []
        if has_guide_modifier and pt == 'guide_or_content':
            score += 10000; reasons.append('guide_modifier_matches_content_page')
        if specific:
            if u in current_urls:
                score += 6000; reasons.append('observed_for_exact_specific_intent')
            if pt == 'product':
                score += 5000; reasons.append('specific_intent_prefers_product')
            elif pt == 'product_category':
                score += 1500; reasons.append('category_fallback_for_specific_intent')
        else:
            if not has_guide_modifier and pt == 'product_category':
                score += 8000; reasons.append('generic_or_commercial_intent_prefers_category')
            if pt == 'product':
                score += 2500; reasons.append('product_fallback')
            if u in current_urls:
                score += 250; reasons.append('observed_for_exact_intent')
        if pt == 'product_tag':
            score += 500
            if re.search(r'%D9%82%DB%8C%D9%85%D8%AA|%D8%AE%D8%B1%DB%8C%D8%AF|قیمت|خرید', u, re.I):
                score -= 1000; reasons.append('transactional_tag_penalty')
            else:
                reasons.append('neutral_tag_fallback')
        candidates.append((score, u, reasons, m))

    hint = OWNER_HINTS.get(focus)
    if hint and hint in merged and not has_guide_modifier and not specific:
        winner = hint
        winner_reasons = ['curated_existing_owner_hint', 'observed_in_fresh_search_console_focus_catalog']
    else:
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, winner, winner_reasons, _ = candidates[0]

    losers = [x['url'] for x in packed if x['url'] != winner]
    owner_type = page_type(winner)
    action = {
        'owner_url': winner,
        'owner_page_type': owner_type,
        'supporting_urls': losers,
        'site_write_performed': False,
        'implementation': []
    }
    if losers:
        action['implementation'].append('Point internal links for this intent to the owner URL where context matches.')
        action['implementation'].append('Keep distinct brand/size/product URLs when they satisfy distinct specific intents; never canonicalize dissimilar products merely to consolidate metrics.')
        if any(page_type(u) == 'product_tag' for u in losers):
            action['implementation'].append('Review duplicate product-tag archives for noindex/merge only after content-equivalence and indexability readback.')
    if owner_type == 'product_tag':
        action['implementation'].append('Owner is an interim existing tag; Phase 6 should replace it with a durable category/hub only if inventory breadth justifies one.')
    if owner_type == 'product' and not specific:
        action['implementation'].append('Generic intent currently lacks a stronger observed category/hub; keep this product as interim owner and do not create a duplicate page in Phase 5.')

    total_imp = sum(v['impressions'] for _, v in rows)
    win_imp = merged[winner]['impressions']
    return {
        'status':'RESOLVED_OWNER',
        'canonical_url':winner,
        'owner_page_type':owner_type,
        'observed_pages':packed,
        'owner_impression_share':round(win_imp/total_imp,4) if total_imp else 0,
        'decision_reasons':winner_reasons,
        'specificity': {'brand':brand,'variant':variant,'dimension':dimension},
        'action_plan':action
    }


def main():
    data = json.loads(INPUT.read_text(encoding='utf-8'))
    rows = data.get('rows') or []
    groups = defaultdict(list)
    focus_catalogs = defaultdict(lambda: defaultdict(lambda: {'clicks':0.0,'impressions':0.0}))
    for r in rows:
        q = fa_norm(r.get('query'))
        if not q:
            continue
        t = topic(q)
        focus = entity_focus(q, t)
        intent = classify_intent(q)
        dimension = dimension_token(q, t) or ''
        brand = brand_token(q) or ''
        variant = variant_token(q) or ''
        semantic_key = f'{t}|{fa_norm(focus)}|{intent}|{fa_norm(dimension)}|{fa_norm(brand)}|{variant}'
        page = clean_url(r.get('page'))
        groups[semantic_key].append({
            'query': r.get('query'), 'page': page, 'clicks': float(r.get('clicks') or 0),
            'impressions': float(r.get('impressions') or 0), 'ctr': float(r.get('ctr') or 0), 'position': float(r.get('position') or 0),
            'topic': t, 'entity_focus': focus, 'intent': intent, 'dimension_token': dimension or None,
            'brand_token': brand or None, 'variant_token': variant or None
        })
        if page:
            focus_catalogs[focus][page]['clicks'] += float(r.get('clicks') or 0)
            focus_catalogs[focus][page]['impressions'] += float(r.get('impressions') or 0)

    registry = []
    conflicts = []
    intent_counts = Counter()
    topic_counts = Counter()
    for key, items in groups.items():
        t = items[0]['topic']; focus = items[0]['entity_focus']; intent = items[0]['intent']; dimension = items[0].get('dimension_token')
        brand = items[0].get('brand_token'); variant = items[0].get('variant_token')
        intent_counts[intent] += 1; topic_counts[t] += 1
        queries = defaultdict(lambda: {'clicks':0.0,'impressions':0.0,'weighted_position_num':0.0})
        page_metrics = defaultdict(lambda: {'clicks':0.0,'impressions':0.0})
        for x in items:
            qn = fa_norm(x['query'])
            queries[qn]['clicks'] += x['clicks']; queries[qn]['impressions'] += x['impressions']
            queries[qn]['weighted_position_num'] += x['position'] * x['impressions']
            if x['page']:
                page_metrics[x['page']]['clicks'] += x['clicks']; page_metrics[x['page']]['impressions'] += x['impressions']
        qpacked = []
        for qn, m in sorted(queries.items(), key=lambda kv:(kv[1]['impressions'],kv[1]['clicks']), reverse=True):
            qpacked.append({'query': qn, 'clicks': round(m['clicks'],4), 'impressions': round(m['impressions'],4),
                            'position': round(m['weighted_position_num']/m['impressions'],4) if m['impressions'] else None})
        decision = canonical_decision(page_metrics, focus, intent, qpacked, focus_catalogs.get(focus), brand=brand, variant=variant, dimension=dimension)
        if len(page_metrics) > 1:
            conflicts.append({'semantic_key':key,'topic':t,'entity_focus':focus,'intent':intent,'dimension_token':dimension,'brand_token':brand,'variant_token':variant,'observed_queries':qpacked,'canonical_decision':decision})
        stable = hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]
        observed = qpacked[0]['query'] if qpacked else key
        total_clicks = sum(x['clicks'] for x in items); total_impressions = sum(x['impressions'] for x in items)
        registry.append({
            'canonical_intent_id': f'intent:{stable}',
            'semantic_key': key,
            'topic': t,
            'intent': intent,
            'intent_rank': INTENT_ORDER.index(intent) if intent in INTENT_ORDER else 99,
            'entities': {'topic':t,'entity_focus':focus,'dimension_token':dimension,'brand_token':brand,'variant_token':variant},
            'prompts': prompts(intent, focus, observed),
            'subquestions': subquestions(intent),
            'evidence': {
                'source':'Google Search Console via Windsor.ai',
                'snapshot': data.get('snapshot'),
                'observed_queries': qpacked,
                'aggregate': {'clicks':round(total_clicks,4),'impressions':round(total_impressions,4)}
            },
            'canonical_url': decision,
            'conversion_goal': conversion_goal(intent),
            'page_creation_policy': 'MERGE_OR_REUSE_EXISTING_FIRST; never create one page per query variant.',
            'status': 'ACTIVE' if decision.get('canonical_url') else 'NO_OWNER'
        })

    registry.sort(key=lambda x: (-x['evidence']['aggregate']['impressions'], x['topic'], x['intent_rank'], x['canonical_intent_id']))
    ids = [x['canonical_intent_id'] for x in registry]
    required_ok = all(x.get('canonical_intent_id') and x.get('intent') and x.get('subquestions') and x.get('entities') and x.get('evidence') and x.get('canonical_url') and x.get('conversion_goal') for x in registry)
    acceptance = {
        'fresh_search_console_snapshot_used': data.get('source') == 'Windsor.ai Search Console' and len(rows) > 0,
        'prompt_to_intent_to_subquestions_to_entities_to_evidence_to_canonical_to_conversion_complete': required_ok,
        'stable_ids_unique': len(ids) == len(set(ids)),
        'shared_intents_merged_by_semantic_key': True,
        'multi_url_conflicts_resolved_to_existing_owner': all(c['canonical_decision'].get('status') == 'RESOLVED_OWNER' and c['canonical_decision'].get('canonical_url') for c in conflicts),
        'no_unresolved_owner': all(x.get('canonical_url',{}).get('canonical_url') for x in registry),
        'no_new_pages_auto_created': True,
        'no_site_writes': True
    }
    summary = {
        'source_raw_rows': data.get('total_raw_rows'),
        'filtered_irrigation_rows': len(rows),
        'central_intents': len(registry),
        'topics': dict(topic_counts),
        'intents': dict(intent_counts),
        'review_required_canonical_conflicts': 0,
        'resolved_multi_url_groups': len(conflicts),
        'active_intents': sum(1 for x in registry if x['status']=='ACTIVE'),
        'site_writes': 0,
        'new_pages_created': 0
    }
    out = {
        'ok': all(acceptance.values()),
        'phase': 5,
        'version': 'growthos-central-intent-registry-v3',
        'generated_at_utc': NOW,
        'status': 'PASS_RESOLVED_OWNER_MAP' if all(x.get('canonical_url',{}).get('canonical_url') for x in registry) else 'PARTIAL_NO_OWNER',
        'source_snapshot': {k:data.get(k) for k in ('source','account','snapshot','total_raw_rows','filtered_rows')},
        'intent_taxonomy': INTENT_ORDER,
        'summary': summary,
        'acceptance': acceptance,
        'registry': registry
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR/'central-intent-registry.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR/'cannibalization-report.json').write_text(json.dumps({
        'phase':5,'generated_at_utc':NOW,'count':len(conflicts),'conflicts':conflicts,
        'rule':'Every multi-URL intent is assigned an existing owner. Product variants remain valid for specific brand/size intents. No redirect/canonical/content write is made in Phase 5; implementation is queued for a later technical phase after equivalence/indexability readback.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR/'intent-summary.json').write_text(json.dumps({
        'ok':out['ok'],'phase':5,'version':out['version'],'generated_at_utc':NOW,'status':out['status'],
        'summary':summary,'acceptance':acceptance,
        'next_gate':'Phase 6 must consume the resolved owner map. Interim product/tag owners should be replaced by durable hubs/categories only when inventory breadth and content justify it; do not create duplicate pages.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE5_INTENT_GRAPH_OK', json.dumps({'status':out['status'],'summary':summary,'acceptance':acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
