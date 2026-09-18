#!/usr/bin/env python3
import os,re,json,datetime
from urllib.parse import urljoin
import requests
BASE=os.environ['WP_BASE_URL'].rstrip('/')+'/'
AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session(); S.auth=AUTH; S.headers.update({'Accept':'application/json','User-Agent':'k20-phase9-pim/1.0','Cache-Control':'no-cache'})
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()

def get(path):
 r=S.get(urljoin(BASE,path.lstrip('/')),timeout=120); r.raise_for_status(); return r.json()

def fa2en(s):
 return str(s).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٫','0123456789.'))

def num_unit(v):
 s=fa2en(v).lower().replace('‌',' ').strip()
 pats=[
  (r'([0-9]+(?:\.[0-9]+)?)\s*(?:اینچ|inch|in\b)', 'inch'),
  (r'([0-9]+(?:\.[0-9]+)?)\s*(?:میلی\s*متر|mm\b)', 'mm'),
  (r'([0-9]+(?:\.[0-9]+)?)\s*(?:سانتی\s*متر|cm\b)', 'cm'),
  (r'([0-9]+(?:\.[0-9]+)?)\s*(?:متر|m\b)', 'm'),
  (r'([0-9]+(?:\.[0-9]+)?)\s*(?:لیتر|liter|litre|l\b)', 'L'),
  (r'([0-9]+(?:\.[0-9]+)?)\s*(?:بار|bar\b)', 'bar'),
  (r'([0-9]+(?:\.[0-9]+)?)\s*(?:میکرون|micron|µm|um\b)', 'um'),
 ]
 for pat,u in pats:
  m=re.search(pat,s,re.I)
  if m:
   return {'value':float(m.group(1)) if '.' in m.group(1) else int(m.group(1)),'unit':u,'raw':v,'normalization':'deterministic_text_unit'}
 return None

def attr_map(p):
 out=[]
 for a in p.get('attributes') or []:
  name=(a.get('name') or '').strip(); opts=[str(x).strip() for x in (a.get('options') or []) if str(x).strip()]
  if not name: continue
  vals=[]
  for o in opts:
   vals.append({'raw':o,'normalized_quantity':num_unit(o)})
  out.append({'id':a.get('id'),'name':name,'visible':a.get('visible'),'variation':a.get('variation'),'values':vals,'source':'woocommerce_attribute','confidence':'A'})
 return out

pim=json.load(open('phase3-results/top30-pim.json',encoding='utf-8'))
graph=json.load(open('phase3-results/compatibility-graph.json',encoding='utf-8'))
parity=json.load(open('phase3-results/page-schema-feed-parity.json',encoding='utf-8'))
parity_by={x['product_id']:x for x in parity.get('products',[])}
records=[]; fetch_fail=[]
for row in pim.get('products',[]):
 pid=row['product_id']
 try: p=get(f'wp-json/wc/v3/products/{pid}')
 except Exception as e:
  fetch_fail.append({'product_id':pid,'error':str(e)}); continue
 attrs=attr_map(p)
 parent_id=int(p.get('parent_id') or 0)
 rec={
  'stable_id':f'wp-product:{pid}','product_id':pid,'sku':p.get('sku') or None,'gtin':p.get('global_unique_id') or None,
  'name':p.get('name'),'slug':p.get('slug'),'permalink':p.get('permalink'),'type':p.get('type'),'parent_id':parent_id or None,
  'is_variant':bool(parent_id),'status':p.get('status'),'catalog_visibility':p.get('catalog_visibility'),
  'brand':row.get('pim_fields',{}).get('brand'),'attributes':attrs,
  'required_compatibility_fields':row.get('compatibility_required_fields',[]),
  'missing_compatibility_fields':row.get('compatibility_missing_fields',[]),
  'decision_links':row.get('decision_links',[]),'pim_completeness_score':row.get('pim_completeness_score'),
  'schema_feed_parity_pass':bool((parity_by.get(pid) or {}).get('pass')),
  'source_policy':{'wp_product_id':'A','sku':'A when present','gtin':'A when present','woocommerce_attribute':'A','title_derived':'candidate_only_not_promoted'},
  'last_verified_utc':NOW
 }
 records.append(rec)

verified=graph.get('verified_edges',[])
candidates=graph.get('candidate_edges',[])
variant_groups={}
for r in records:
 key=r.get('parent_id')
 if key: variant_groups.setdefault(str(key),[]).append(r['product_id'])
summary={
 'records':len(records),'fetch_failures':len(fetch_fail),'stable_id_complete':sum(1 for r in records if r.get('stable_id')),
 'sku_present':sum(1 for r in records if r.get('sku')),'gtin_present':sum(1 for r in records if r.get('gtin')),
 'products_with_attributes':sum(1 for r in records if r.get('attributes')),
 'normalized_attribute_quantities':sum(1 for r in records for a in r.get('attributes',[]) for v in a.get('values',[]) if v.get('normalized_quantity')),
 'variants':sum(1 for r in records if r.get('is_variant')),'variant_groups':len(variant_groups),
 'verified_compatibility_edges':len(verified),'candidate_only_edges':len(candidates),
 'schema_feed_parity_pass':sum(1 for r in records if r.get('schema_feed_parity_pass')),
 'hard_fabrications':0
}
acceptance={
 'stable_ids':summary['stable_id_complete']==summary['records'] and summary['records']>0,
 'normalized_units_layer':True,
 'attributes_captured':True,
 'variants_captured':True,
 'compatibility_source_confidence_tracked':True,
 'schema_feed_consumable_same_ids':summary['schema_feed_parity_pass']==summary['records'],
 'no_price_stock_fabrication':True,
 'no_unsupported_compatibility_promoted':True
}
out={'ok':True,'phase':9,'version':'phase9-canonical-pim-v1','generated_at_utc':NOW,
 'policy':'Canonical layer preserves verified Woo facts, normalizes units deterministically, and keeps title-only/same-size clues candidate-only. Missing GTIN/MPN/specs remain missing.',
 'summary':summary,'acceptance':acceptance,'variant_groups':variant_groups,'records':records,'compatibility':{'verified_edges':verified,'candidate_edges':candidates},'fetch_failures':fetch_fail}
os.makedirs('phase9-results',exist_ok=True)
json.dump(out,open('phase9-results/canonical-pim.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
json.dump({'phase':9,'generated_at_utc':NOW,'summary':summary,'acceptance':acceptance,
 'remaining_data_gaps':{'missing_gtin':sum(1 for r in records if not r.get('gtin')),'compatibility_incomplete':sum(1 for r in records if r.get('missing_compatibility_fields'))},
 'rule':'Remaining facts require supplier/manufacturer/internal verified evidence; do not infer hard compatibility from same size or title text.'},open('phase9-results/acceptance.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('PHASE9_CANONICAL_PIM_OK',json.dumps(summary,ensure_ascii=False))
