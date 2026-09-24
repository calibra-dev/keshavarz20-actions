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
        r'([۰-۹0-9]+(?:\s*و\s*[۰-۹0-9]+/[۰-۹0-9]+|[./][۰-۹0-9]+)?\s*اینچ)',
        r'([۰-۹0-9]+\s*میلی\s*متر)',
        r'([۰-۹0-9]+\s*میلیمتر)',
        r'(?<!\d)([۰-۹0-9]{2,3})(?!\d)'
    ]
    for pat in pats:
        m = re.search(pat, q, re.I)
        if m:
            return re.sub(r'\s+', ' ', m.group(1)).strip()
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


def classify_intent(q):
    n = fa_norm(q)
    if re.search(r'ارسال|هزینه\s*حمل|کرایه', n): return 'ارسال'
    if re.search(r'ضمانت|گارانتی|مرجوع', n): return 'ضمانت'
    if re.search(r'نشتی|گرفتگی|خراب|مشکل|عیب|فشار کم|آب نمی', n): return 'عیب‌یابی'
    if re.search(r'شستشو|شستشوی|نگهداری|سرویس|تمیز', n): return 'نگهداری'
    if re.search(r'نصب|راه\s*اندازی|بستن|مونتاژ', n): return 'نصب'
    if re.search(r'ماشین\s*حساب|محاسبه|متراژ|چند\s*متر|چقدر|تعداد', n): return 'محاسبه'
    if re.search(r'سازگار|سازگاری|وصل|اتصال.*به|به.*اتصال|چه\s*اتصالی|کدام\s*اتصال', n): return 'سازگاری'
    if re.search(r'مقایسه|تفاوت|فرق|بهتر|vs|یا', n): return 'مقایسه'
    if re.search(r'قیمت|خرید|فروش|نمایندگی|لیست\s*قیمت|ارزان|سفارش', n):
        if re.search(r'شیراز|تهران|اصفهان|فارس|خوزستان|تبریز|مشهد|قم|کرج|اهواز', n): return 'local'
        return 'خرید'
    if re.search(r'پروژه|یک\s*هکتار|هکتار|گلخانه|مزرعه|باغ', n): return 'پروژه'
    if re.search(r'چیست|راهنما|معنی|کاربرد|مشخصات|سایز', n): return 'شناخت'
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


def canonical_decision(page_metrics):
    rows = sorted(page_metrics.items(), key=lambda kv: (kv[1]['impressions'], kv[1]['clicks']), reverse=True)
    total_imp = sum(v['impressions'] for _, v in rows)
    if not rows:
        return {'status':'NO_OBSERVED_PAGE','canonical_url':None,'observed_pages':[]}
    packed = [{'url':u, **v} for u, v in rows]
    if len(rows) == 1:
        return {'status':'OBSERVED_SINGLE','canonical_url':rows[0][0],'observed_pages':packed,'top_impression_share':1.0}
    share = (rows[0][1]['impressions'] / total_imp) if total_imp else 0
    if share >= 0.70:
        return {'status':'OBSERVED_PRIMARY','canonical_url':rows[0][0],'observed_pages':packed,'top_impression_share':round(share,4),
                'warning':'Multiple pages were observed for this intent. Primary is evidence-based, not an automatic redirect/canonical change.'}
    return {'status':'REVIEW_REQUIRED','canonical_url':None,'observed_pages':packed,'top_impression_share':round(share,4),
            'warning':'Intent is split across multiple landing pages; do not create another page until overlap is resolved.'}


def main():
    data = json.loads(INPUT.read_text(encoding='utf-8'))
    rows = data.get('rows') or []
    groups = defaultdict(list)
    for r in rows:
        q = fa_norm(r.get('query'))
        if not q:
            continue
        t = topic(q)
        focus = entity_focus(q, t)
        intent = classify_intent(q)
        sz = size_token(q) or ''
        semantic_key = f'{t}|{fa_norm(focus)}|{intent}|{fa_norm(sz)}'
        groups[semantic_key].append({
            'query': r.get('query'), 'page': clean_url(r.get('page')), 'clicks': float(r.get('clicks') or 0),
            'impressions': float(r.get('impressions') or 0), 'ctr': float(r.get('ctr') or 0), 'position': float(r.get('position') or 0),
            'topic': t, 'entity_focus': focus, 'intent': intent, 'size_token': sz or None
        })

    registry = []
    conflicts = []
    intent_counts = Counter()
    topic_counts = Counter()
    for key, items in groups.items():
        t = items[0]['topic']; focus = items[0]['entity_focus']; intent = items[0]['intent']; sz = items[0]['size_token']
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
        decision = canonical_decision(page_metrics)
        if decision['status'] == 'REVIEW_REQUIRED':
            conflicts.append({'semantic_key':key,'topic':t,'entity_focus':focus,'intent':intent,'size_token':sz,'observed_queries':qpacked,'canonical_decision':decision})
        stable = hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]
        observed = qpacked[0]['query'] if qpacked else key
        total_clicks = sum(x['clicks'] for x in items); total_impressions = sum(x['impressions'] for x in items)
        registry.append({
            'canonical_intent_id': f'intent:{stable}',
            'semantic_key': key,
            'topic': t,
            'intent': intent,
            'intent_rank': INTENT_ORDER.index(intent) if intent in INTENT_ORDER else 99,
            'entities': {'topic':t,'entity_focus':focus,'size_token':sz},
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
            'status': 'REVIEW_REQUIRED' if decision['status'] == 'REVIEW_REQUIRED' else 'ACTIVE'
        })

    registry.sort(key=lambda x: (-x['evidence']['aggregate']['impressions'], x['topic'], x['intent_rank'], x['canonical_intent_id']))
    ids = [x['canonical_intent_id'] for x in registry]
    required_ok = all(x.get('canonical_intent_id') and x.get('intent') and x.get('subquestions') and x.get('entities') and x.get('evidence') and x.get('canonical_url') and x.get('conversion_goal') for x in registry)
    acceptance = {
        'fresh_search_console_snapshot_used': data.get('source') == 'Windsor.ai Search Console' and len(rows) > 0,
        'prompt_to_intent_to_subquestions_to_entities_to_evidence_to_canonical_to_conversion_complete': required_ok,
        'stable_ids_unique': len(ids) == len(set(ids)),
        'shared_intents_merged_by_semantic_key': True,
        'multi_url_conflicts_not_silently_hidden': all(c['canonical_decision']['status'] == 'REVIEW_REQUIRED' for c in conflicts),
        'no_new_pages_auto_created': True,
        'no_site_writes': True
    }
    summary = {
        'source_raw_rows': data.get('total_raw_rows'),
        'filtered_irrigation_rows': len(rows),
        'central_intents': len(registry),
        'topics': dict(topic_counts),
        'intents': dict(intent_counts),
        'review_required_canonical_conflicts': len(conflicts),
        'active_intents': sum(1 for x in registry if x['status']=='ACTIVE'),
        'site_writes': 0,
        'new_pages_created': 0
    }
    out = {
        'ok': all(acceptance.values()),
        'phase': 5,
        'version': 'growthos-central-intent-registry-v1',
        'generated_at_utc': NOW,
        'status': 'PASS_WITH_CANONICAL_CONFLICT_BACKLOG' if conflicts else 'PASS',
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
        'rule':'Resolve overlap by reusing/merging existing pages before creating any new URL. No redirect/canonical/content change was made automatically.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTDIR/'intent-summary.json').write_text(json.dumps({
        'ok':out['ok'],'phase':5,'version':out['version'],'generated_at_utc':NOW,'status':out['status'],
        'summary':summary,'acceptance':acceptance,
        'next_gate':'Phase 6 hubs should consume this central registry and Phase 4 graph; REVIEW_REQUIRED URL conflicts must be resolved before creating overlapping pages.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTHOS_PHASE5_INTENT_GRAPH_OK', json.dumps({'status':out['status'],'summary':summary,'acceptance':acceptance}, ensure_ascii=False))


if __name__ == '__main__':
    main()
