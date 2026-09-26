#!/usr/bin/env python3
import json,os,re,requests
from datetime import datetime,timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE=os.environ['WP_BASE_URL'].rstrip('/');AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase10-activate/1.0'})
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.5,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(['GET','POST']))
S.mount('https://',HTTPAdapter(max_retries=retry));S.mount('http://',HTTPAdapter(max_retries=retry))
START='<!-- K20-GROWTHOS-PHASE10-MEASUREMENT-START -->';END='<!-- K20-GROWTHOS-PHASE10-MEASUREMENT-END -->'
TARGETS=[('post',143698,'drip_calculator'),('page',144236,'layflat_calculator'),('page',144238,'filter_selector'),('page',144239,'compatibility_checker'),('page',144266,'pipe_size_selector'),('page',145233,'basket_builder'),('page',145234,'product_comparator'),('page',145286,'smart_proforma')]
def get(kind,pid):
 typ='posts' if kind=='post' else 'pages';r=S.get(urljoin(BASE+'/',f'wp-json/wp/v2/{typ}/{pid}'),params={'context':'edit'},timeout=60);r.raise_for_status();return r.json()
def post(kind,pid,body):
 typ='posts' if kind=='post' else 'pages';r=S.post(urljoin(BASE+'/',f'wp-json/wp/v2/{typ}/{pid}'),json=body,timeout=90);r.raise_for_status();return r.json()
def patch(raw,block):
 p=re.compile(re.escape(START)+r'[\s\S]*?'+re.escape(END))
 return p.sub(block,raw,count=1) if p.search(raw) else raw.rstrip()+'\n\n'+block+'\n'
block=open(os.path.join(ROOT,'growthos-phase10-assets/measurement-forwarder.html'),encoding='utf-8').read().strip()
results=[]
for kind,pid,key in TARGETS:
 o=get(kind,pid);before=((o.get('content') or {}).get('raw') or '');after=patch(before,block)
 if after!=before:post(kind,pid,{'content':after})
 rb=get(kind,pid);raw=((rb.get('content') or {}).get('raw') or '')
 results.append({'key':key,'id':pid,'status':rb.get('status'),'changed':after!=before,'marker_count':raw.count(START),'phase9_marker_count':raw.count('K20-GROWTHOS-PHASE9-FLOW-START'),'forwarder_present':'growthos_measurement_ready' in raw and '__k20GrowthOSMeasurementV1' in raw,'verified':rb.get('status')=='publish' and raw.count(START)==1 and raw.count('K20-GROWTHOS-PHASE9-FLOW-START')==1 and 'growthos_measurement_ready' in raw})
qa={'targets':len(results),'verified':sum(x['verified'] for x in results),'changed':sum(x['changed'] for x in results)}
out={'phase':10,'version':'growthos-measurement-activation-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_VERIFIED_WRITE' if qa['verified']==qa['targets'] else 'FAIL','results':results,'qa':qa,'behavior':'Forwards existing growthos_* dataLayer events to the installed Google tag through gtag when available and emits growthos_measurement_ready on each tool page.','prices_stock_changed':False}
os.makedirs('growthos-phase10-results',exist_ok=True);json.dump(out,open('growthos-phase10-results/instrumentation-activation.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('PHASE10_ACTIVATION',json.dumps({'status':out['status'],'qa':qa},ensure_ascii=False))
