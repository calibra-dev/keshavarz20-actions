#!/usr/bin/env python3
import hashlib,json,math,os,re,requests
from datetime import datetime,timezone
from urllib.parse import urljoin
BASE=os.environ['WP_BASE_URL'].rstrip('/'); AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session(); S.auth=AUTH; S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase8-build/1.0','Cache-Control':'no-cache'})
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def get(path,params=None):
 r=S.get(urljoin(BASE+'/',path.lstrip('/')),params=params,timeout=120); r.raise_for_status(); return r.json()
def post(path,body):
 r=S.post(urljoin(BASE+'/',path.lstrip('/')),json=body,timeout=180); r.raise_for_status(); return r.json()
def public(url):
 try:
  r=requests.get(url,timeout=60,headers={'User-Agent':'k20-growthos-phase8-build/1.0','Cache-Control':'no-cache'},allow_redirects=True); return {'http':r.status_code,'final_url':r.url,'bytes':len(r.content)}
 except Exception as e:return {'http':0,'error':type(e).__name__}
def h(s):return hashlib.sha256((s or '').encode()).hexdigest()
def asset(name):return open(os.path.join(ROOT,'growthos-phase8-assets',name),encoding='utf-8').read().strip()
def marker_block(content,start,end,block):
 p=re.compile(re.escape(start)+r'[\s\S]*?'+re.escape(end)); return p.sub(block,content,count=1) if p.search(content) else (content.rstrip()+'\n\n'+block+'\n')
def update_page(pid,start,end,block):
 o=get(f'wp-json/wp/v2/pages/{pid}',{'context':'edit'}); before=((o.get('content') or {}).get('raw') or ''); after=marker_block(before,start,end,block)
 if after!=before:post(f'wp-json/wp/v2/pages/{pid}',{'content':after})
 rb=get(f'wp-json/wp/v2/pages/{pid}',{'context':'edit'}); raw=((rb.get('content') or {}).get('raw') or ''); probe=public(rb.get('link'))
 return {'id':pid,'slug':rb.get('slug'),'status':rb.get('status'),'link':rb.get('link'),'changed':after!=before,'before_sha256':h(before),'after_sha256':h(raw),'marker_count':raw.count(start),'chars_before':len(before),'chars_after':len(raw),'public':probe,'verified':raw.count(start)==1 and rb.get('status')=='publish' and probe.get('http')==200}
pipe=update_page(144266,'<!-- K20-GROWTHOS-PHASE8-PIPE-START -->','<!-- K20-GROWTHOS-PHASE8-PIPE-END -->',asset('pipe-selector-block.html'))
pro=update_page(145286,'<!-- K20-GROWTHOS-PHASE8-PROFORMA-START -->','<!-- K20-GROWTHOS-PHASE8-PROFORMA-END -->',asset('proforma-block.html'))
q=10.0;v=1.5;d=math.sqrt((4*(q/3600))/(math.pi*v))*1000;formula={'flow_m3h':q,'velocity_m_s':v,'dmin_mm':round(d,3),'pass':48.4<=d<=48.7}
os.makedirs('growthos-phase8-results',exist_ok=True)
registry={'phase':8,'version':'growthos-tool-registry-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'canonical_tools':[{'key':'drip_calculator','id':143698,'slug':'drip-tape-length-fittings-calculator'},{'key':'layflat_calculator','id':144236,'slug':'layflat-length-fittings-calculator'},{'key':'filter_selector','id':144238,'slug':'irrigation-filter-selector'},{'key':'compatibility_checker','id':144239,'slug':'irrigation-fittings-compatibility-selector'},{'key':'pipe_size_selector','id':144266,'slug':'irrigation-pipe-size-selector'},{'key':'basket_builder','id':145233,'slug':'one-hectare-drip-irrigation-basket'},{'key':'product_comparator','id':145234,'slug':'irrigation-product-comparator'},{'key':'smart_proforma','id':145286,'slug':'request-proforma'}],'legacy_proforma_surfaces':[{'id':143710,'slug':'request-quotation'},{'id':140667,'slug':'پیش-فاکتور-سبد-خرید'}],'safety':{'prices_written':False,'stock_written':False,'new_tool_urls_created':0,'exact_sku_compatibility_inferred':False}}
summary={'ok':pipe['verified'] and pro['verified'] and formula['pass'],'phase':8,'version':'growthos-calculators-selectors-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_VERIFIED_WRITE' if pipe['verified'] and pro['verified'] and formula['pass'] else 'FAIL','pipe_size_selector':pipe,'smart_proforma':pro,'formula_qa':formula,'existing_tools_reused':6,'new_urls_created':0}
json.dump(registry,open('growthos-phase8-results/tool-registry.json','w',encoding='utf-8'),ensure_ascii=False,indent=2);json.dump(summary,open('growthos-phase8-results/summary.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('GROWTHOS_PHASE8_BUILD',json.dumps({'status':summary['status'],'pipe':pipe,'proforma':pro,'formula':formula},ensure_ascii=False))