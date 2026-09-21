#!/usr/bin/env python3
import os,json,re,requests
from datetime import datetime,timezone
from urllib.parse import quote,urljoin
BASE=os.environ['WP_BASE_URL'].rstrip('/')
AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-seogod1-phase7/1.0'})
def get(path,params=None):
    r=S.get(urljoin(BASE+'/',path.lstrip('/')),params=params,timeout=120);r.raise_for_status();return r.json()
def paged(path,params=None,cap=10):
    out=[];params=dict(params or {})
    for page in range(1,cap+1):
      p=dict(params);p.update({'per_page':100,'page':page})
      r=S.get(urljoin(BASE+'/',path.lstrip('/')),params=p,timeout=120)
      if r.status_code==400 and page>1:break
      r.raise_for_status();rows=r.json()
      if not isinstance(rows,list) or not rows:break
      out.extend(rows)
      if len(rows)<100:break
    return out
def norm(s):
    return re.sub(r'\s+',' ',(s or '').replace('ي','ی').replace('ك','ک').replace('‌',' ')).strip().lower()
groups=[
 {'key':'63mm','queries':['63','۶۳','63mm','63 میلی متر','۶۳ میلی متر']},
 {'key':'2inch','queries':['2 inch','2 اینچ','۲ اینچ']},
 {'key':'threaded','queries':['نخ دار','نخدار']},
 {'key':'driptape','queries':['تیپ','نوار تیپ']},
 {'key':'pe','queries':['PE','پلی اتیلن','پلی‌اتیلن']}
]
products=paged('wp-json/wc/v3/products',{'status':'publish'},cap=30)
search=[]
for g in groups:
  variants=[]
  union=set()
  for q in g['queries']:
    nq=norm(q)
    toks=[t for t in nq.split(' ') if t]
    rows=[]
    for x in products:
      corpus=norm((x.get('name') or '')+' '+(x.get('sku') or '')+' '+' '.join((c.get('name') or '') for c in x.get('categories') or [])+' '+' '.join((a.get('name') or '')+' '+' '.join(str(v) for v in (a.get('options') or [])) for a in x.get('attributes') or []))
      if all(t in corpus for t in toks): rows.append(x)
    ids=[int(x['id']) for x in rows]; union.update(ids)
    variants.append({'query':q,'count':len(rows),'top':[{'id':int(x['id']),'name':x.get('name')} for x in rows[:10]]})
  search.append({'group':g['key'],'variants':variants,'union_count':len(union)})
category_terms=['نوار تیپ','نخدار','پلی اتیلن','فیلتر']
cats=[]
allcats=paged('wp-json/wc/v3/products/categories',{'hide_empty':'false'})
for term in category_terms:
  nt=norm(term); matched=[c for c in allcats if nt in norm(c.get('name')) or nt in norm(c.get('slug'))]
  rows=[]
  for c in matched:
    ps=paged('wp-json/wc/v3/products',{'status':'publish','category':c['id']},cap=10)
    attrs={}
    for p in ps:
      for a in p.get('attributes') or []:
        n=a.get('name') or ''
        if n: attrs[n]=attrs.get(n,0)+1
    rows.append({'id':int(c['id']),'name':c.get('name'),'count':int(c.get('count') or 0),'product_count_live':len(ps),'attribute_coverage':sorted([{'name':k,'products':v} for k,v in attrs.items()],key=lambda z:(-z['products'],z['name']))[:30]})
  cats.append({'query':term,'matches':rows})
public={}
for path in ['shop/','?s=%D9%86%D8%AE%D8%AF%D8%A7%D8%B1&post_type=product']:
  try:
    u=BASE+'/'+path
    r=requests.get(u,timeout=45,headers={'User-Agent':'k20-seogod1-phase7/1.0','Cache-Control':'no-cache'})
    body=r.text[:1000000].lower()
    public[path]={'http':r.status_code,'bytes':len(r.content),'signals':{
      'compare':('compare' in body or 'مقایسه' in body),
      'filter':('filter' in body or 'فیلتر' in body),
      'result_count':('woocommerce-result-count' in body),
      'sort':('woocommerce-ordering' in body)
    }}
  except Exception as e: public[path]={'error':type(e).__name__}
out={'program':'SEO God1','phase':7,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'mode':'read-only','search_synonym_probe':search,'categories':cats,'public_probe':public}
os.makedirs('seo-god1-results',exist_ok=True)
with open('seo-god1-results/phase07-discovery-live-audit.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print('PHASE07_DISCOVERY_OK')
