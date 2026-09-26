#!/usr/bin/env python3
import html,json,os,re,requests,urllib.robotparser
from datetime import datetime,timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ['WP_BASE_URL'].rstrip('/')
AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session();S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.2,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(['GET']))
S.mount('https://',HTTPAdapter(max_retries=retry));S.mount('http://',HTTPAdapter(max_retries=retry))
S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase11/1.0'})
TOOLS=[('post',143698,'drip-tape-length-fittings-calculator'),('page',144236,'layflat-length-fittings-calculator'),('page',144238,'irrigation-filter-selector'),('page',144239,'irrigation-fittings-compatibility-selector'),('page',144266,'irrigation-pipe-size-selector'),('page',145233,'one-hectare-drip-irrigation-basket'),('page',145234,'irrigation-product-comparator'),('page',145286,'request-proforma')]
HUBS=[(755,'نوار تیپ'),(768,'لوله نخدار'),(761,'انشعابات و بست ها'),(754,'لوله پلی اتیلن'),(825,'فیلتر و فیلتراسیون')]
REQ=['item_id','title','description','url','brand','seller_name','image_url','availability','price']

def get(path,params=None,auth=True,timeout=90):
    sess=S if auth else requests
    headers=None if auth else {'User-Agent':'k20-growthos-phase11/1.0','Cache-Control':'no-cache'}
    r=sess.get(urljoin(BASE+'/',path.lstrip('/')),params=params,timeout=timeout,headers=headers)
    r.raise_for_status(); return r

def api(path,params=None): return get(path,params).json()
def text_only(s):
    s=re.sub(r'<script[\s\S]*?</script>',' ',s or '',flags=re.I)
    s=re.sub(r'<style[\s\S]*?</style>',' ',s,flags=re.I)
    s=re.sub(r'<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s)).strip()

def page(kind,pid):
    typ='posts' if kind=='post' else 'pages'
    return api(f'wp-json/wp/v2/{typ}/{pid}',{'context':'edit'})

def all_products():
    out=[];page_no=1
    while True:
        rows=api('wp-json/wc/v3/products',{'status':'publish','per_page':100,'page':page_no,'orderby':'id','order':'asc'})
        if not rows: break
        out.extend(rows)
        if len(rows)<100: break
        page_no+=1
    return out

def all_variations(pid):
    out=[];page_no=1
    while True:
        rows=api(f'wp-json/wc/v3/products/{pid}/variations',{'status':'publish','per_page':100,'page':page_no})
        if not rows: break
        out.extend(rows)
        if len(rows)<100: break
        page_no+=1
    return out

def brand_of(p):
    b=p.get('brands')
    if isinstance(b,list) and b:
        for x in b:
            if isinstance(x,dict) and str(x.get('name') or '').strip(): return str(x['name']).strip()
    for a in p.get('attributes') or []:
        n=str(a.get('name') or '').strip().lower()
        if n in ('brand','برند','نام برند') or 'برند' in n:
            opts=a.get('options') or []
            if opts and str(opts[0]).strip(): return str(opts[0]).strip()
    return ''

def availability_of(p):
    m={'instock':'in_stock','outofstock':'out_of_stock','onbackorder':'backorder'}
    return m.get(str(p.get('stock_status') or '').lower(),'unknown')

def product_row(p,parent=None):
    base=parent or p
    pid=p.get('id')
    sku=str(p.get('sku') or '').strip()
    item_id=('k20v_' if parent else 'k20_')+str(pid)
    title=str(base.get('name') or '').strip()
    if parent:
        attrs=[]
        for a in p.get('attributes') or []:
            v=str(a.get('option') or '').strip()
            if v: attrs.append(v)
        if attrs: title=(title+' — '+', '.join(attrs)).strip(' —')
    desc=text_only(p.get('description') or '') or text_only(base.get('short_description') or '') or text_only(base.get('description') or '')
    url=str(base.get('permalink') or '').strip()
    brand=brand_of(base)
    images=p.get('image')
    image_url=''
    if isinstance(images,dict): image_url=str(images.get('src') or '').strip()
    if not image_url:
        imgs=base.get('images') or []
        if imgs and isinstance(imgs[0],dict): image_url=str(imgs[0].get('src') or '').strip()
    price=str(p.get('price') or '').strip()
    row={
      'item_id':bool(item_id),'title':bool(title),'description':bool(desc),'url':bool(url),'brand':bool(brand),
      'seller_name':True,'image_url':bool(image_url),'availability':bool(availability_of(p)),'price':bool(price)
    }
    return item_id,row

# Fresh robots/OAI search access
rr=get('robots.txt',auth=False,timeout=45)
robots_text=rr.text
rp=urllib.robotparser.RobotFileParser();rp.set_url(BASE+'/robots.txt');rp.parse(robots_text.splitlines())
oai_home=rp.can_fetch('OAI-SearchBot',BASE+'/')
gptbot_home=rp.can_fetch('GPTBot',BASE+'/')
robots_relevant=[line.strip() for line in robots_text.splitlines() if re.search(r'OAI-SearchBot|GPTBot|User-agent|Disallow|Allow|Sitemap',line,re.I)][:250]

# Core citable/answerable surfaces: reuse phase 6/9, don't rewrite.
surfaces=[]
for kind,pid,slug in TOOLS:
    o=page(kind,pid);raw=((o.get('content') or {}).get('raw') or '');plain=text_only(raw)
    surfaces.append({'type':kind,'id':pid,'slug':slug,'status':o.get('status'),'chars':len(plain),'phase9_flow':raw.count('K20-GROWTHOS-PHASE9-FLOW-START')==1,'phase10_measurement':raw.count('K20-GROWTHOS-PHASE10-MEASUREMENT-START')==1,'answerable':len(plain)>=500,'citable_surface':o.get('status')=='publish' and len(plain)>=500})
for cid,name in HUBS:
    c=api(f'wp-json/wc/v3/products/categories/{cid}');raw=c.get('description') or '';plain=text_only(raw)
    surfaces.append({'type':'product_cat','id':cid,'slug':c.get('slug'),'name':name,'chars':len(plain),'phase6_decision':raw.count('K20-GROWTHOS-PHASE6-START')==1,'phase9_flow':raw.count('K20-GROWTHOS-PHASE9-FLOW-START')==1,'answerable':len(plain)>=500,'citable_surface':len(plain)>=500})

# Current catalog -> OpenAI stable feed completeness, with no price values persisted.
products=all_products()
candidate=[];variable_parents=0;variation_rows=0
for p in products:
    if p.get('type')=='variable' and p.get('variations'):
        variable_parents+=1
        vs=all_variations(p['id'])
        for v in vs:
            item_id,row=product_row(v,p);candidate.append((p['id'],v['id'],item_id,row));variation_rows+=1
    else:
        item_id,row=product_row(p);candidate.append((p['id'],None,item_id,row))
ids=[x[2] for x in candidate]
duplicate_item_ids=sorted({x for x in ids if ids.count(x)>1})
missing={k:[] for k in REQ}
ready=0
for product_id,variation_id,item_id,row in candidate:
    ok=True
    for k in REQ:
        if not row[k]:
            ok=False
            if len(missing[k])<100:
                missing[k].append({'product_id':product_id,'variation_id':variation_id})
    if ok: ready+=1

try:
    currency=api('wp-json/wc/v3/settings/general/woocommerce_currency').get('value')
except Exception:
    currency=None

crawl={
 'phase':11,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'robots_http':rr.status_code,
 'robots_sha256':__import__('hashlib').sha256(robots_text.encode()).hexdigest(),
 'oai_searchbot_home_allowed':oai_home,'gptbot_home_allowed':gptbot_home,
 'robots_relevant_lines':robots_relevant,
 'core_surfaces_total':len(surfaces),'core_surfaces_citable':sum(1 for x in surfaces if x['citable_surface']),
 'surfaces':surfaces,
 'note':'GPTBot training access is reported separately and is not used as the ChatGPT Search inclusion gate.'
}
feed={
 'phase':11,'version':'openai-stable-feed-readiness-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),
 'spec_required_fields':REQ,'seller_name':'کشاورز بیست','currency_code_observed':currency,
 'published_parent_products':len(products),'candidate_feed_rows':len(candidate),'variable_parent_products':variable_parents,'variation_rows':variation_rows,
 'fully_ready_rows':ready,'ready_percent':round(ready*100/len(candidate),2) if candidate else 0,
 'field_complete_counts':{k:len(candidate)-sum(1 for _,_,_,row in candidate if not row[k]) for k in REQ},
 'missing_samples':missing,'duplicate_item_id_count':len(duplicate_item_ids),'duplicate_item_id_samples':duplicate_item_ids[:50],
 'known_source_sku_conflict':{'sku':'430000300-2','product_ids':[140654,140655],'status':'SOURCE_CONFIRMATION_REQUIRED','feed_identity_impact':'none_after_stable_id_mapping'},
 'feed_submission_attempted':False,'partner_onboarding_gate':True,
 'price_values_persisted':False,'stock_values_persisted':False,
 'mapping':{
   'item_id':'Stable Keshavarz20 ID derived from immutable Woo entity ID: k20_<product_id> / k20v_<variation_id>; Woo SKU remains a separate source field and is not used as the feed primary key.',
   'title':'Woo product name plus selected variation options where applicable',
   'description':'variation description -> short description -> product description, plain text',
   'url':'canonical Woo product permalink',
   'brand':'Woo brands field or explicit brand attribute only; no inference',
   'seller_name':'کشاورز بیست',
   'image_url':'variation image, otherwise main product image',
   'availability':'Woo stock_status mapped to OpenAI availability vocabulary',
   'price':'current Woo price with observed Woo currency; audited for presence but value not committed'
 }
}
status='PASS_GUARDED_FEED_READY_PARTNER_APPROVAL_REQUIRED' if oai_home and crawl['core_surfaces_citable']==len(surfaces) and not duplicate_item_ids else 'PARTIAL'
summary={
 'ok':oai_home and crawl['core_surfaces_citable']==len(surfaces) and not duplicate_item_ids,
 'phase':11,'title':'ChatGPT Search','generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':status,
 'oai_searchbot_allowed':oai_home,'core_citable_surfaces':f"{crawl['core_surfaces_citable']}/{len(surfaces)}",
 'openai_feed_ready_rows':ready,'openai_feed_candidate_rows':len(candidate),'openai_feed_ready_percent':feed['ready_percent'],
 'direct_feed_submitted':False,'direct_feed_partner_access_proven':False,
 'fabricated_product_fields':0,'new_public_urls_created':0,
 'next_gate':'Improve only source-backed catalog gaps; submit a direct OpenAI feed only after approved partner access is actually granted.'
}
os.makedirs('growthos-phase11-results',exist_ok=True)
for name,obj in [('chatgpt-search-crawl-audit.json',crawl),('openai-product-feed-readiness.json',feed),('summary.json',summary)]:
    with open('growthos-phase11-results/'+name,'w',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
print('GROWTHOS_PHASE11',json.dumps(summary,ensure_ascii=False))
