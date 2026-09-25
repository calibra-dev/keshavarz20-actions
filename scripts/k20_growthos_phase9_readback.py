#!/usr/bin/env python3
import json,os,requests
from datetime import datetime,timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE=os.environ['WP_BASE_URL'].rstrip('/');AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase9-readback/1.0'})
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.5,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(['GET','POST','PUT']))
S.mount('https://',HTTPAdapter(max_retries=retry));S.mount('http://',HTTPAdapter(max_retries=retry))
START='<!-- K20-GROWTHOS-PHASE9-FLOW-START -->';RSTART='<!-- K20-GROWTHOS-PHASE9-ROUTE-START -->'
TOOLS=[('post',143698,'drip-tape-length-fittings-calculator'),('page',144236,'layflat-length-fittings-calculator'),('page',144238,'irrigation-filter-selector'),('page',144239,'irrigation-fittings-compatibility-selector'),('page',144266,'irrigation-pipe-size-selector'),('page',145233,'one-hectare-drip-irrigation-basket'),('page',145234,'irrigation-product-comparator'),('page',145286,'request-proforma')]
HUBS=[(755,'نوار تیپ'),(768,'لوله نخدار'),(761,'انشعابات و بست ها'),(754,'لوله پلی اتیلن'),(825,'فیلتر و فیلتراسیون')]
LEGACY=[143710,140667]
LINKS=['/irrigation-pipe-size-selector/','/irrigation-filter-selector/','/irrigation-product-comparator/','/irrigation-fittings-compatibility-selector/','/drip-tape-length-fittings-calculator/','/layflat-length-fittings-calculator/','/one-hectare-drip-irrigation-basket/','/request-proforma/']
def get(path,params=None):
 r=S.get(urljoin(BASE+'/',path.lstrip('/')),params=params,timeout=45);r.raise_for_status();return r.json()
tools=[]
for kind,pid,slug in TOOLS:
 typ='posts' if kind=='post' else 'pages';o=get(f'wp-json/wp/v2/{typ}/{pid}',{'context':'edit'});raw=((o.get('content') or {}).get('raw') or '')
 tools.append({'kind':kind,'id':pid,'slug':slug,'status':o.get('status'),'marker_count':raw.count(START),'all_flow_links':all(x in raw for x in LINKS),'event':'growthos_flow_step' in raw,'verified':o.get('status')=='publish' and raw.count(START)==1 and all(x in raw for x in LINKS) and 'growthos_flow_step' in raw})
hubs=[]
for cid,name in HUBS:
 c=get(f'wp-json/wc/v3/products/categories/{cid}');raw=c.get('description') or ''
 hubs.append({'id':cid,'name':name,'marker_count':raw.count(START),'all_flow_links':all(x in raw for x in LINKS),'taxonomy_sanitized_data_attributes':raw.count('data-growthos-step=')==0,'verified':raw.count(START)==1 and all(x in raw for x in LINKS)})
legacy=[]
for pid in LEGACY:
 o=get(f'wp-json/wp/v2/pages/{pid}',{'context':'edit'});raw=((o.get('content') or {}).get('raw') or '')
 legacy.append({'id':pid,'slug':o.get('slug'),'status':o.get('status'),'marker_count':raw.count(RSTART),'owner_link':'/request-proforma/' in raw,'verified':o.get('status')=='publish' and raw.count(RSTART)==1 and '/request-proforma/' in raw})
qa={'tools_verified':sum(x['verified'] for x in tools),'tools_total':len(tools),'hubs_verified':sum(x['verified'] for x in hubs),'hubs_total':len(hubs),'legacy_verified':sum(x['verified'] for x in legacy),'legacy_total':len(legacy)}
ok=qa['tools_verified']==len(tools) and qa['hubs_verified']==len(hubs) and qa['legacy_verified']==len(legacy)
out={'ok':ok,'phase':9,'version':'growthos-phase9-independent-readback-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_VERIFIED_READBACK' if ok else 'PARTIAL','tools':tools,'hubs':hubs,'legacy':legacy,'qa':qa,'evidence_note':'Exact authenticated WordPress/WooCommerce readback. No writes in this workflow.'}
os.makedirs('growthos-phase9-results',exist_ok=True);json.dump(out,open('growthos-phase9-results/independent-readback.json','w',encoding='utf-8'),ensure_ascii=False,indent=2);print('PHASE9_READBACK',json.dumps({'status':out['status'],'qa':qa},ensure_ascii=False))