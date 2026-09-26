#!/usr/bin/env python3
import json,os,re,requests
from datetime import datetime,timezone
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE=os.environ['WP_BASE_URL'].rstrip('/');AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase9-a11y/1.0'})
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.5,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(['GET','POST']))
S.mount('https://',HTTPAdapter(max_retries=retry));S.mount('http://',HTTPAdapter(max_retries=retry))
TARGETS=[
 (144236,'layflat-length-fittings-calculator',{'lf_len':'طول مورد نیاز لی فلت به متر','lf_roll':'طول هر رول لی فلت به متر','lf_out':'تعداد خروجی یا انشعاب','lf_end':'تعداد انتهای خط','lf_res':'نتیجه محاسبه لی فلت'}),
 (144238,'irrigation-filter-selector',{'fs_source':'منبع آب','fs_use':'نوع کاربرد آبیاری','fs_flow':'دبی طراحی','fs_micron':'درجه فیلتراسیون مورد نیاز','fs_conn':'سایز اتصال'}),
 (144239,'irrigation-fittings-compatibility-selector',{'ic_system':'نوع سیستم آبیاری','ic_size':'سایز خط یا اتصال','ic_task':'نوع اتصال مورد نیاز','ic_out':'خروجی مورد نیاز','ic_valve':'نیاز به شیر'})
]
def get(pid):
 r=S.get(urljoin(BASE+'/',f'wp-json/wp/v2/pages/{pid}'),params={'context':'edit'},timeout=60);r.raise_for_status();return r.json()
def post(pid,body):
 r=S.post(urljoin(BASE+'/',f'wp-json/wp/v2/pages/{pid}'),json=body,timeout=90);r.raise_for_status();return r.json()
def add_aria(raw,control_id,label):
 pat=re.compile(r'(<(?:input|select|textarea)\b[^>]*\bid=["\']'+re.escape(control_id)+r'["\'][^>]*)(>)',re.I)
 m=pat.search(raw)
 if not m:return raw,False,'missing'
 tag=m.group(1)
 if re.search(r'\baria-label\s*=',tag,re.I) or re.search(r'\baria-labelledby\s*=',tag,re.I):return raw,False,'already'
 repl=tag+' aria-label="'+label+'"'+m.group(2)
 return raw[:m.start()]+repl+raw[m.end():],True,'added'
results=[]
for pid,slug,mapping in TARGETS:
 o=get(pid);raw=((o.get('content') or {}).get('raw') or '');before=raw;changes={}
 for cid,label in mapping.items():
  raw,changed,state=add_aria(raw,cid,label);changes[cid]={'changed':changed,'state':state}
 if raw!=before:post(pid,{'content':raw})
 rb=get(pid);after=((rb.get('content') or {}).get('raw') or '')
 verify={}
 for cid,label in mapping.items():
  pat=re.compile(r'<(?:input|select|textarea)\b[^>]*\bid=["\']'+re.escape(cid)+r'["\'][^>]*\baria-label=["\']'+re.escape(label)+r'["\']',re.I)
  verify[cid]=bool(pat.search(after))
 results.append({'id':pid,'slug':slug,'changed':raw!=before,'changes':changes,'verify':verify,'verified':all(verify.values())})
qa={'targets':len(results),'verified':sum(x['verified'] for x in results),'controls':sum(len(x['verify']) for x in results),'controls_verified':sum(sum(1 for v in x['verify'].values() if v) for x in results)}
out={'phase':9,'version':'growthos-phase9-a11y-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_VERIFIED_WRITE' if qa['verified']==qa['targets'] else 'FAIL','results':results,'qa':qa}
os.makedirs('growthos-phase9-results',exist_ok=True)
json.dump(out,open('growthos-phase9-results/accessibility-fix.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('PHASE9_A11Y',json.dumps({'status':out['status'],'qa':qa},ensure_ascii=False))
