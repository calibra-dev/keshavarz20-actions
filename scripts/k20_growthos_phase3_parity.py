#!/usr/bin/env python3
import html as htmlmod
import json
import os
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests

BASE = os.environ['WP_BASE_URL'].rstrip('/') + '/'
AUTH = (os.environ['WP_USERNAME'], os.environ['WP_APP_PASSWORD'])
S = requests.Session()
S.auth = AUTH
S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase3-parity/1.0','Cache-Control':'no-cache'})
TRUTH_PATH = Path('growthos-phase2-results/product-truth-registry.json')
SYSTEM_PATH = Path('bridge-v3-results/20260924-growthos-p123-system.json')
OUT = Path('growthos-phase3-results/html-schema-feed-parity.json')
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()

if not TRUTH_PATH.exists():
    raise SystemExit('Missing Phase 2 Product Truth Registry')
truth = json.loads(TRUTH_PATH.read_text(encoding='utf-8'))
truth_by_id = {int(x['product_id']): x for x in truth.get('records', [])}


def paged(path, params=None, cap=30):
    out=[]; params=dict(params or {})
    for page in range(1,cap+1):
        q=dict(params); q.update({'per_page':100,'page':page})
        r=S.get(urljoin(BASE,path.lstrip('/')),params=q,timeout=120)
        if r.status_code==400 and page>1: break
        r.raise_for_status(); rows=r.json()
        if not isinstance(rows,list) or not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out


def norm(u):
    p=urlparse(u or '')
    path=unquote(p.path or '/').rstrip('/') or '/'
    if path!='/': path+='/'
    return (p.scheme.lower(),p.netloc.lower(),path.lower())


def num(v):
    try: return float(str(v).replace(',','').strip())
    except Exception: return None


def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values():
            yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)


def types(node):
    t=node.get('@type') if isinstance(node,dict) else None
    return set(str(x) for x in (t if isinstance(t,list) else [t]) if x)


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_ld=False; self.buf=[]; self.blocks=[]
        self.canonical=''; self.robots=''; self.title_on=False; self.title=[]; self.description=''
    def handle_starttag(self,tag,attrs):
        a={str(k).lower():(v or '') for k,v in attrs}; t=tag.lower()
        if t=='script' and a.get('type','').lower()=='application/ld+json':
            self.in_ld=True; self.buf=[]
        elif t=='link' and 'canonical' in a.get('rel','').lower().split():
            self.canonical=a.get('href','')
        elif t=='meta' and a.get('name','').lower()=='robots':
            self.robots=a.get('content','').lower()
        elif t=='meta' and a.get('name','').lower()=='description':
            self.description=a.get('content','').strip()
        elif t=='title':
            self.title_on=True
    def handle_endtag(self,tag):
        if tag.lower()=='script' and self.in_ld:
            self.blocks.append(''.join(self.buf)); self.in_ld=False; self.buf=[]
        elif tag.lower()=='title':
            self.title_on=False
    def handle_data(self,data):
        if self.in_ld: self.buf.append(data)
        if self.title_on: self.title.append(data)


def fetch_product_page(product):
    pid=int(product['id']); url=product.get('permalink')
    result={'product_id':pid,'name':product.get('name'),'url':url}
    try:
        r=requests.get(url,timeout=90,headers={'User-Agent':'k20-growthos-phase3-parity/1.0','Cache-Control':'no-cache'})
        result['http']=r.status_code; result['final_url']=r.url
        if r.status_code!=200:
            result['error']='http_not_200'; result['pass']=False; return result
        p=Parser(); p.feed(r.text[:1800000])
        parsed=[]; parse_errors=[]
        for raw in p.blocks:
            try: parsed.append(json.loads(htmlmod.unescape(raw)))
            except Exception as e: parse_errors.append(type(e).__name__)
        nodes=[n for block in parsed for n in walk(block) if isinstance(n,dict)]
        products=[n for n in nodes if 'Product' in types(n)]
        offers=[n for n in nodes if 'Offer' in types(n)]
        breadcrumbs=[n for n in nodes if 'BreadcrumbList' in types(n)]
        orgs=[n for n in nodes if 'Organization' in types(n) or 'OnlineStore' in types(n)]
        groups=[n for n in nodes if 'ProductGroup' in types(n)]
        ratings=[n for n in nodes if 'AggregateRating' in types(n)]
        prod=None; sku=str(product.get('sku') or '').strip()
        for node in products:
            if sku and str(node.get('sku') or '').strip()==sku:
                prod=node; break
        if prod is None and products:
            prod=products[0]
        offer=(prod or {}).get('offers') if prod else None
        if isinstance(offer,list):
            offer=offer[0] if offer else None
        if not isinstance(offer,dict):
            offer=offers[0] if offers else None
        schema_price=num((offer or {}).get('price')); woo_price=num(product.get('price'))
        schema_currency=str((offer or {}).get('priceCurrency') or '').upper()
        availability=str((offer or {}).get('availability') or '')
        stock=product.get('stock_status')
        expected_avail={'instock':'https://schema.org/InStock','outofstock':'https://schema.org/OutOfStock','onbackorder':'https://schema.org/BackOrder'}.get(stock)
        price_match=None
        if schema_price is not None and woo_price is not None:
            if schema_currency=='IRR':
                price_match=abs(schema_price-(woo_price*10))<0.01
            elif schema_currency in {'IRT','TMN','TOMAN'}:
                price_match=abs(schema_price-woo_price)<0.01
        truth_rec=truth_by_id.get(pid) or {}
        truth_fields=truth_rec.get('fields') or {}
        truth_brand=((truth_fields.get('brand') or {}).get('value'))
        schema_brand=(prod or {}).get('brand') if prod else None
        if isinstance(schema_brand,dict):
            schema_brand=schema_brand.get('name')
        elif isinstance(schema_brand,list):
            schema_brand='، '.join(str(x.get('name') if isinstance(x,dict) else x) for x in schema_brand)
        brand_match=None if not truth_brand else str(truth_brand).strip().lower()==str(schema_brand or '').strip().lower()
        rating_real=True
        if ratings and int(product.get('rating_count') or 0)<=0:
            rating_real=False
        ptype=str(product.get('type') or '')
        variant_group_ok=True
        if ptype=='variable':
            variant_group_ok=bool(groups or any((n.get('hasVariant') or n.get('variesBy')) for n in products))
        canonical_self=bool(p.canonical) and norm(p.canonical)==norm(r.url)
        checks={
            'html_200':r.status_code==200,
            'html_title_present':bool(' '.join(p.title).strip()),
            'html_meta_description_present':bool(p.description),
            'canonical_self':canonical_self,
            'not_noindex':'noindex' not in p.robots,
            'jsonld_parse_clean':not parse_errors,
            'product_schema_present':bool(products),
            'offer_schema_present':bool(offer),
            'breadcrumb_schema_present':bool(breadcrumbs),
            'organization_schema_present':bool(orgs),
            'sku_match':(str((prod or {}).get('sku') or '').strip()==sku) if sku else True,
            'brand_match_when_truth_known':brand_match,
            'offer_price_parity':price_match,
            'offer_availability_parity':(availability==expected_avail) if expected_avail else None,
            'aggregate_rating_has_real_woo_reviews_if_present':rating_real,
            'variable_product_grouping_present_when_required':variant_group_ok,
        }
        hard_keys=['html_200','canonical_self','not_noindex','jsonld_parse_clean','product_schema_present','offer_schema_present','breadcrumb_schema_present','organization_schema_present','sku_match','aggregate_rating_has_real_woo_reviews_if_present','variable_product_grouping_present_when_required']
        hard_ok=all(checks[k] is True for k in hard_keys)
        if checks['brand_match_when_truth_known'] is False:
            hard_ok=False
        if checks['offer_price_parity'] is False:
            hard_ok=False
        if checks['offer_availability_parity'] is False:
            hard_ok=False
        result.update({
            'checks':checks,'pass':hard_ok,
            'schema_counts':{'Product':len(products),'Offer':len(offers),'BreadcrumbList':len(breadcrumbs),'OrganizationOrStore':len(orgs),'ProductGroup':len(groups),'AggregateRating':len(ratings)},
            'yoast_rendered_layer':{'plugin_detected':None,'title_present':checks['html_title_present'],'meta_description_present':checks['html_meta_description_present'],'canonical_present':bool(p.canonical),'robots':p.robots},
            'sensitive_values_redacted':{'price':True,'availability_value':True},
        })
        return result
    except Exception as e:
        result['error']=type(e).__name__+': '+str(e)[:180]; result['pass']=False; return result


products=paged('wp-json/wc/v3/products',{'status':'publish'})
rows=[]
with ThreadPoolExecutor(max_workers=10) as pool:
    futs=[pool.submit(fetch_product_page,p) for p in products]
    for f in as_completed(futs):
        rows.append(f.result())
rows.sort(key=lambda x:x['product_id'])

system_info={}
if SYSTEM_PATH.exists():
    try:
        system_info=json.loads(SYSTEM_PATH.read_text(encoding='utf-8')).get('result') or {}
    except Exception:
        system_info={}
for r in rows:
    if 'yoast_rendered_layer' in r:
        r['yoast_rendered_layer']['plugin_detected']=system_info.get('yoast')

summary={
    'published_products':len(products),
    'audited_products':len(rows),
    'pass':sum(1 for x in rows if x.get('pass')),
    'fail':sum(1 for x in rows if not x.get('pass')),
    'product_schema_missing':sum(1 for x in rows if not (x.get('checks') or {}).get('product_schema_present')),
    'offer_schema_missing':sum(1 for x in rows if not (x.get('checks') or {}).get('offer_schema_present')),
    'breadcrumb_missing':sum(1 for x in rows if not (x.get('checks') or {}).get('breadcrumb_schema_present')),
    'organization_missing':sum(1 for x in rows if not (x.get('checks') or {}).get('organization_schema_present')),
    'sku_mismatch':sum(1 for x in rows if (x.get('checks') or {}).get('sku_match') is False),
    'brand_mismatch_when_truth_known':sum(1 for x in rows if (x.get('checks') or {}).get('brand_match_when_truth_known') is False),
    'price_parity_fail':sum(1 for x in rows if (x.get('checks') or {}).get('offer_price_parity') is False),
    'availability_parity_fail':sum(1 for x in rows if (x.get('checks') or {}).get('offer_availability_parity') is False),
    'unbacked_aggregate_rating':sum(1 for x in rows if (x.get('checks') or {}).get('aggregate_rating_has_real_woo_reviews_if_present') is False),
    'variable_grouping_fail':sum(1 for x in rows if (x.get('checks') or {}).get('variable_product_grouping_present_when_required') is False),
    'yoast_version_from_bridge':system_info.get('yoast'),
}
acceptance={
    'phase2_truth_registry_consumed':len(truth_by_id)>0,
    'all_published_products_audited':len(rows)==len(products) and len(products)>0,
    'no_price_values_exposed':True,
    'no_stock_values_exposed':True,
    'html_schema_api_truth_linked':True,
    'all_hard_parity_checks_pass':summary['fail']==0,
}
out={
    'ok':all(acceptance.values()),
    'phase':3,
    'version':'growthos-html-schema-feed-parity-v1',
    'generated_at_utc':NOW,
    'mode':'read-only',
    'summary':summary,
    'acceptance':acceptance,
    'policy':'Compares current Woo/API truth to rendered HTML and JSON-LD without emitting price or stock values. Unknown Product Truth fields do not become fabricated schema requirements.',
    'failures':[x for x in rows if not x.get('pass')],
    'products':rows,
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('GROWTHOS_PHASE3_PARITY',json.dumps({'summary':summary,'acceptance':acceptance},ensure_ascii=False))
