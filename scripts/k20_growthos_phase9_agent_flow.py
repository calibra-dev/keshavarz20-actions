#!/usr/bin/env python3
import json,os,re,requests
from datetime import datetime,timezone
from urllib.parse import urljoin
BASE=os.environ['WP_BASE_URL'].rstrip('/'); AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase9/1.0','Cache-Control':'no-cache'})
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START='<!-- K20-GROWTHOS-PHASE9-FLOW-START -->';END='<!-- K20-GROWTHOS-PHASE9-FLOW-END -->';RSTART='<!-- K20-GROWTHOS-PHASE9-ROUTE-START -->';REND='<!-- K20-GROWTHOS-PHASE9-ROUTE-END -->'
TOOLS=[('post',143698,'drip-tape-length-fittings-calculator'),('page',144236,'layflat-length-fittings-calculator'),('page',144238,'irrigation-filter-selector'),('page',144239,'irrigation-fittings-compatibility-selector'),('page',144266,'irrigation-pipe-size-selector'),('page',145233,'one-hectare-drip-irrigation-basket'),('page',145234,'irrigation-product-comparator'),('page',145286,'request-proforma')]
HUBS=[(755,'نوار تیپ'),(768,'لوله نخدار'),(761,'انشعابات و بست ها'),(754,'لوله پلی اتیلن'),(825,'فیلتر و فیلتراسیون')]
LEGACY=[143710,140667]
def get(path,params=None):
 r=S.get(urljoin(BASE+'/',path.lstrip('/')),params=params,timeout=120);r.raise_for_status();return r.json()
def post(path,body):
 r=S.post(urljoin(BASE+'/',path.lstrip('/')),json=body,timeout=180);r.raise_for_status();return r.json()
def put(path,body):
 r=S.put(urljoin(BASE+'/',path.lstrip('/')),json=body,timeout=180);r.raise_for_status();return r.json()
def pub(url):
 try:
  r=requests.get(url,timeout=60,headers={'User-Agent':'k20-growthos-phase9/1.0','Cache-Control':'no-cache'},allow_redirects=True);return {'http':r.status_code,'bytes':len(r.content),'final_url':r.url}
 except Exception as e:return {'http':0,'error':type(e).__name__}
def asset(name):return open(os.path.join(ROOT,'growthos-phase9-assets',name),encoding='utf-8').read().strip()
def patch(s,start,end,block):
 p=re.compile(re.escape(start)+r'[\s\S]*?'+re.escape(end));return p.sub(block,s,count=1) if p.search(s) else s.rstrip()+'\n\n'+block+'\n'
def content_stats(raw):
 labels=set(re.findall(r'<label[^>]+for=["\']([^"\']+)',raw,re.I));ids=re.findall(r'<(?:input|select|textarea)[^>]+id=["\']([^"\']+)',raw,re.I);un=[x for x in ids if x not in labels];return {'controls_with_id':len(ids),'label_for_count':len(labels),'unlabeled_ids':un[:30]}
def update_tool(kind,pid,slug,block):
 typ='posts' if kind=='post' else 'pages';o=get(f'wp-json/wp/v2/{typ}/{pid}',{'context':'edit'});before=((o.get('content') or {}).get('raw') or '');after=patch(before,START,END,block)
 if after!=before:post(f'wp-json/wp/v2/{typ}/{pid}',{'content':after})
 rb=get(f'wp-json/wp/v2/{typ}/{pid}',{'context':'edit'});raw=((rb.get('content') or {}).get('raw') or '');p=pub(rb.get('link'))
 links=['/irrigation-pipe-size-selector/','/irrigation-filter-selector/','/irrigation-product-comparator/','/irrigation-fittings-compatibility-selector/','/drip-tape-length-fittings-calculator/','/layflat-length-fittings-calculator/','/one-hectare-drip-irrigation-basket/','/request-proforma/']
 return {'kind':kind,'id':pid,'slug':slug,'status':rb.get('status'),'http':p.get('http'),'marker_count':raw.count(START),'all_flow_links':all(x in raw for x in links),'data_layer':'growthos_flow_step' in raw,'accessibility':content_stats(raw),'verified':rb.get('status')=='publish' and p.get('http')==200 and raw.count(START)==1 and all(x in raw for x in links) and 'growthos_flow_step' in raw}
def update_hub(cid,name,block):
 c=get(f'wp-json/wc/v3/products/categories/{cid}');before=c.get('description') or '';after=patch(before,START,END,block)
 if after!=before:put(f'wp-json/wc/v3/products/categories/{cid}',{'description':after})
 rb=get(f'wp-json/wc/v3/products/categories/{cid}');raw=rb.get('description') or ''
 return {'id':cid,'name':name,'marker_count':raw.count(START),'flow_links':raw.count('data-growthos-step='),'verified':raw.count(START)==1 and raw.count('data-growthos-step=')>=8}
def route_legacy(pid,block):
 o=get(f'wp-json/wp/v2/pages/{pid}',{'context':'edit'});before=((o.get('content') or {}).get('raw') or '');after=patch(before,RSTART,REND,block)
 if after!=before:post(f'wp-json/wp/v2/pages/{pid}',{'content':after})
 rb=get(f'wp-json/wp/v2/pages/{pid}',{'context':'edit'});raw=((rb.get('content') or {}).get('raw') or '');p=pub(rb.get('link'))
 return {'id':pid,'slug':rb.get('slug'),'http':p.get('http'),'marker_count':raw.count(RSTART),'owner_link':'/request-proforma/' in raw,'verified':p.get('http')==200 and raw.count(RSTART)==1 and '/request-proforma/' in raw}
flow=asset('flow-block.html');legacy=asset('legacy-proforma-route.html')
tools=[update_tool(*x,flow) for x in TOOLS];hubs=[update_hub(*x,flow) for x in HUBS];legacy_rows=[route_legacy(x,legacy) for x in LEGACY]
qa={'tools_verified':sum(x['verified'] for x in tools),'tools_total':len(tools),'hubs_verified':sum(x['verified'] for x in hubs),'hubs_total':len(hubs),'legacy_routes_verified':sum(x['verified'] for x in legacy_rows),'legacy_routes_total':len(legacy_rows),'tool_unlabeled_controls':{x['slug']:x['accessibility']['unlabeled_ids'] for x in tools if x['accessibility']['unlabeled_ids']}}
os.makedirs('growthos-phase9-results',exist_ok=True)
json.dump({'phase':9,'version':'growthos-agent-flow-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'flow':['question/context','selection','filtration','comparison','compatibility','calculation','basket','proforma/expert-review','purchase'],'tools':tools,'hubs':hubs,'legacy_proforma_routes':legacy_rows,'qa':qa},open('growthos-phase9-results/flow-qa.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
ok=qa['tools_verified']==len(tools) and qa['hubs_verified']==len(hubs) and qa['legacy_routes_verified']==len(legacy_rows)
summary={'ok':ok,'phase':9,'version':'growthos-sxo-agent-ux-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_VERIFIED_WRITE' if ok else 'FAIL','qa':qa,'new_urls_created':0,'redirects_created':0,'prices_stock_changed':False,'compatibility_inferred':False,'canonical_proforma_owner':{'id':145286,'slug':'request-proforma'}}
json.dump(summary,open('growthos-phase9-results/summary.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('GROWTHOS_PHASE9',json.dumps(summary,ensure_ascii=False))