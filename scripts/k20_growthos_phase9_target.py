#!/usr/bin/env python3
import json,os,re,sys,requests
from datetime import datetime,timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE=os.environ['WP_BASE_URL'].rstrip('/');AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase9-target/1.0'})
retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(['GET','POST','PUT']))
S.mount('https://',HTTPAdapter(max_retries=retry));S.mount('http://',HTTPAdapter(max_retries=retry))
FLOW_START='<!-- K20-GROWTHOS-PHASE9-FLOW-START -->';FLOW_END='<!-- K20-GROWTHOS-PHASE9-FLOW-END -->'
ROUTE_START='<!-- K20-GROWTHOS-PHASE9-ROUTE-START -->';ROUTE_END='<!-- K20-GROWTHOS-PHASE9-ROUTE-END -->'
LINKS=['/irrigation-pipe-size-selector/','/irrigation-filter-selector/','/irrigation-product-comparator/','/irrigation-fittings-compatibility-selector/','/drip-tape-length-fittings-calculator/','/layflat-length-fittings-calculator/','/one-hectare-drip-irrigation-basket/','/request-proforma/']
def req(method,path,body=None,params=None):
 r=S.request(method,urljoin(BASE+'/',path.lstrip('/')),json=body,params=params,timeout=35);r.raise_for_status()
 if not r.text.strip():return {'http':r.status_code}
 return r.json()
def asset(name):return open(os.path.join(ROOT,'growthos-phase9-assets',name),encoding='utf-8').read().strip()
def patch(s,start,end,block):
 p=re.compile(re.escape(start)+r'[\s\S]*?'+re.escape(end));return p.sub(block,s,count=1) if p.search(s) else s.rstrip()+'\n\n'+block+'\n'
op_path=sys.argv[1];op=json.load(open(op_path,encoding='utf-8'));kind=op['kind'];pid=int(op['id'])
if kind=='hub':
 c=req('GET',f'wp-json/wc/v3/products/categories/{pid}');before=c.get('description') or '';after=patch(before,FLOW_START,FLOW_END,asset('flow-block.html'))
 if after!=before:req('POST',f'wp-json/wc/v3/products/categories/{pid}',{'description':after})
 rb=req('GET',f'wp-json/wc/v3/products/categories/{pid}');raw=rb.get('description') or ''
 out={'ok':raw.count(FLOW_START)==1 and all(x in raw for x in LINKS),'kind':'hub','id':pid,'name':rb.get('name'),'marker_count':raw.count(FLOW_START),'all_flow_links':all(x in raw for x in LINKS),'taxonomy_sanitized_data_attributes':raw.count('data-growthos-step=')==0}
elif kind=='legacy':
 o=req('GET',f'wp-json/wp/v2/pages/{pid}',params={'context':'edit'});before=((o.get('content') or {}).get('raw') or '');after=patch(before,ROUTE_START,ROUTE_END,asset('legacy-proforma-route.html'))
 if after!=before:req('POST',f'wp-json/wp/v2/pages/{pid}',{'content':after})
 rb=req('GET',f'wp-json/wp/v2/pages/{pid}',params={'context':'edit'});raw=((rb.get('content') or {}).get('raw') or '')
 out={'ok':rb.get('status')=='publish' and raw.count(ROUTE_START)==1 and '/request-proforma/' in raw,'kind':'legacy','id':pid,'slug':rb.get('slug'),'status':rb.get('status'),'marker_count':raw.count(ROUTE_START),'owner_link':'/request-proforma/' in raw}
else:raise SystemExit('unsupported kind')
out['executed_at_utc']=datetime.now(timezone.utc).isoformat();out['op']=os.path.basename(op_path)
os.makedirs('growthos-phase9-results/targets',exist_ok=True)
name=os.path.splitext(os.path.basename(op_path))[0]
json.dump(out,open('growthos-phase9-results/targets/'+name+'.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('PHASE9_TARGET',json.dumps(out,ensure_ascii=False))
if not out['ok']:raise SystemExit(2)
