#!/usr/bin/env python3
import json,os,requests
from datetime import datetime,timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ['WP_BASE_URL'].rstrip('/')
AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S=requests.Session();S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.2,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(['GET']))
S.mount('https://',HTTPAdapter(max_retries=retry));S.mount('http://',HTTPAdapter(max_retries=retry))
S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase12/1.0'})

def load(rel):
    with open(os.path.join(ROOT,rel),encoding='utf-8') as f:return json.load(f)
def get(path,params=None,auth=True,timeout=60):
    sess=S if auth else requests
    headers=None if auth else {'User-Agent':'k20-growthos-phase12/1.0','Cache-Control':'no-cache'}
    return sess.get(urljoin(BASE+'/',path.lstrip('/')),params=params,timeout=timeout,headers=headers)
def api(path,params=None):
    r=get(path,params,True);r.raise_for_status();return r.json()

p11=load('growthos-phase11-results/summary.json')
feed=load('growthos-phase11-results/openai-product-feed-readiness.json')
if not p11.get('ok'):
    raise SystemExit('Phase 11 must pass its guarded readiness gate before Phase 12.')

# Never publish a fake UCP profile. Inspect current public state only.
ucp_resp=get('.well-known/ucp',auth=False)
ucp_public={
  'http':ucp_resp.status_code,
  'content_type':ucp_resp.headers.get('content-type'),
  'bytes':len(ucp_resp.content),
  'published_profile_detected':ucp_resp.status_code==200 and 'ucp' in ucp_resp.text.lower()
}

# Public Woo Store API capability: discovery/cart primitives, not UCP equivalence.
store={}
for key,path in [
  ('products','wp-json/wc/store/v1/products?per_page=1'),
  ('cart','wp-json/wc/store/v1/cart'),
  ('routes','wp-json/')
]:
    try:
        r=get(path,auth=False);store[key]={'http':r.status_code,'ok':r.status_code==200,'bytes':len(r.content)}
        if key=='routes' and r.status_code==200:
            j=r.json();routes=j.get('routes') or {}
            store[key]['has_checkout_route']=any('/wc/store/v1/checkout' in k for k in routes)
            store[key]['has_cart_route']=any('/wc/store/v1/cart' in k for k in routes)
            store[key]['has_product_route']=any('/wc/store/v1/products' in k for k in routes)
    except Exception as e:
        store[key]={'http':0,'ok':False,'error':type(e).__name__}

# Fresh commerce/policy surface inventory, without customer/order data.
policy_terms=['ارسال','مرجوعی','حریم خصوصی','قوانین','پیش فاکتور','پیش‌فاکتور']
policies=[]
seen=set()
for term in policy_terms:
    try:
        rows=api('wp-json/wp/v2/pages',{'search':term,'context':'edit','per_page':50})
    except Exception:
        rows=[]
    for o in rows:
        if o.get('id') in seen:continue
        seen.add(o.get('id'))
        policies.append({'id':o.get('id'),'slug':o.get('slug'),'status':o.get('status'),'link':o.get('link'),'title':((o.get('title') or {}).get('raw') or (o.get('title') or {}).get('rendered'))})

shipping=[]
try:
    zones=api('wp-json/wc/v3/shipping/zones')
    zone_ids=[0]+[z['id'] for z in zones]
    for zid in zone_ids:
        try:
            methods=api(f'wp-json/wc/v3/shipping/zones/{zid}/methods')
        except Exception: methods=[]
        for m in methods:
            shipping.append({'zone_id':zid,'method_id':m.get('method_id'),'instance_id':m.get('instance_id'),'title':m.get('title'),'enabled':m.get('enabled')})
except Exception:
    pass

# Google Merchant architecture mapping. No Merchant account/submission is attempted.
merchant_map={
 'version':'growthos-google-merchant-field-map-v1',
 'generated_at_utc':datetime.now(timezone.utc).isoformat(),
 'policy_gate':{
   'merchant_center_country':'IR',
   'merchant_center_available':False,
   'account_creation_attempted':False,
   'feed_submission_attempted':False,
   'fake_country_or_address_used':False
 },
 'catalog':{
   'candidate_rows_from_phase11':feed.get('candidate_feed_rows'),
   'basic_required_rows_ready':feed.get('fully_ready_rows'),
   'ready_percent':feed.get('ready_percent'),
   'currency_code_observed':feed.get('currency_code_observed'),
   'actual_price_values_persisted':False,
   'actual_stock_values_persisted':False
 },
 'field_mapping':[
   {'google':'id','k20':'stable Woo SKU else k20_<product_id>/k20v_<variation_id>','status':'mapped'},
   {'google':'title','k20':'Woo product/variant title','status':'mapped'},
   {'google':'description','k20':'plain-text Woo description','status':'mapped_when_present'},
   {'google':'link','k20':'canonical Woo permalink','status':'mapped'},
   {'google':'image_link','k20':'variation image else primary product image','status':'mapped_when_present'},
   {'google':'availability','k20':'Woo stock_status vocabulary mapping','status':'mapped'},
   {'google':'price','k20':'current Woo price + Woo currency','status':'mapped_when_present_not_exported_here'},
   {'google':'brand','k20':'Woo product_brand / explicit brand only','status':'mapped_when_verified'},
   {'google':'item_group_id','k20':'stable parent product ID for real variants only','status':'mapped_for_variants'}
 ],
 'policy_pages':policies,
 'shipping_methods':shipping,
 'note':'Architecture is Merchant-ready where source data exists, but Google Merchant Center submission is intentionally blocked by the Iran country restriction.'
}

# UCP 2026-04-08 readiness: do not confuse Woo routes with UCP endpoints.
ucp={
 'version':'growthos-ucp-readiness-v1',
 'ucp_spec_version':'2026-04-08',
 'generated_at_utc':datetime.now(timezone.utc).isoformat(),
 'public_profile':ucp_public,
 'publication_gate':{
   'publish_now':False,
   'reason_codes':['MERCHANT_ELIGIBILITY_NOT_PROVEN','UCP_PROGRAM_ACCESS_NOT_PROVEN','NO_UCP_AUTHENTICATED_ADAPTER_ENDPOINT'],
   'well_known_path':'/.well-known/ucp',
   'required_before_publish':['authorized Google/UCP participation','real HTTPS UCP service endpoint','authentication/security implementation','cart/checkout/order contract tests','customer-data/privacy review']
 },
 'existing_site_primitives':store,
 'capabilities':{
   'product_discovery':{'state':'DATA_MODEL_READY_PARTIAL','evidence':'Phase 11 product-feed readiness + Product/Offer schema parity'},
   'cart_transfer':{'state':'ADAPTER_REQUIRED','woo_store_cart_route':bool((store.get('routes') or {}).get('has_cart_route'))},
   'native_checkout':{'state':'NOT_IMPLEMENTED_AS_UCP','woo_checkout_route':bool((store.get('routes') or {}).get('has_checkout_route'))},
   'order_lifecycle':{'state':'NOT_IMPLEMENTED_AS_UCP','reason':'No UCP order/webhook contract is exposed; no customer/order data persisted in repo.'},
   'identity_linking':{'state':'NOT_IMPLEMENTED'},
   'returns':{'state':'POLICY_SURFACE_AVAILABLE_IF_MATCHED','policy_page_count':len(policies)},
   'shipping':{'state':'WOO_METHODS_OBSERVED_NOT_UCP_CONTRACT','enabled_method_count':sum(1 for x in shipping if x.get('enabled'))}
 },
 'adapter_contract':{
   'future_service_base':'not_assigned_until_authorized',
   'future_endpoints':[
      {'method':'POST','path':'/carts','purpose':'UCP cart transfer','live_now':False},
      {'method':'POST','path':'/checkout-sessions','purpose':'UCP native checkout session','live_now':False},
      {'method':'GET','path':'/checkout-sessions/{id}','purpose':'UCP checkout state','live_now':False},
      {'method':'webhook','path':'order lifecycle endpoint','purpose':'authorized order updates','live_now':False}
   ],
   'implementation_rule':'Build an adapter over Woo commerce primitives only after authorization; never expose ordinary Woo REST credentials or customer/order data.'
 }
}
ok=bool(p11.get('ok')) and store.get('products',{}).get('ok') and not ucp_public['published_profile_detected']
summary={
 'ok':ok,
 'phase':12,'title':'Google Merchant / UCP','generated_at_utc':datetime.now(timezone.utc).isoformat(),
 'status':'PASS_ARCHITECTURE_READY_POLICY_GUARD' if ok else 'PARTIAL',
 'merchant_center_iran_restriction_respected':True,
 'merchant_center_submission_attempted':False,
 'fake_country_or_address_used':False,
 'ucp_spec_version':'2026-04-08',
 'ucp_public_profile_published':ucp_public['published_profile_detected'],
 'ucp_live_adapter_claimed':False,
 'merchant_basic_ready_rows':feed.get('fully_ready_rows'),
 'merchant_candidate_rows':feed.get('candidate_feed_rows'),
 'woo_store_products_public':store.get('products',{}).get('ok'),
 'woo_store_cart_public':store.get('cart',{}).get('ok'),
 'next_gate':'Only activate Merchant/UCP publication after real eligibility/authorization and a tested authenticated UCP adapter; until then keep architecture ready and public claims off.'
}
os.makedirs('growthos-phase12-results',exist_ok=True)
for name,obj in [('merchant-field-map.json',merchant_map),('ucp-readiness-contract.json',ucp),('summary.json',summary)]:
    with open('growthos-phase12-results/'+name,'w',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
print('GROWTHOS_PHASE12',json.dumps(summary,ensure_ascii=False))
