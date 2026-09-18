#!/usr/bin/env python3
import os, re, json, html, datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE=os.environ['WP_BASE_URL'].rstrip('/')+'/'
AUTH=(os.environ['WP_USERNAME'], os.environ['WP_APP_PASSWORD'])
S=requests.Session()
S.auth=AUTH
S.headers.update({'Accept':'application/json','User-Agent':'k20-phase8-entity-trust/1.1','Cache-Control':'no-cache'})
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()

def paged(path, params=None, cap=30):
    out=[]; params=dict(params or {})
    for page in range(1,cap+1):
        p=dict(params); p.update({'per_page':100,'page':page})
        r=S.get(urljoin(BASE,path.lstrip('/')),params=p,timeout=120)
        if r.status_code==400 and page>1:
            break
        r.raise_for_status()
        rows=r.json()
        if not isinstance(rows,list) or not rows:
            break
        out.extend(rows)
        if len(rows)<100:
            break
    return out

def textify(v):
    soup=BeautifulSoup(html.unescape(v or ''),'html.parser')
    return ' '.join(soup.stripped_strings)

def live(url):
    try:
        r=requests.get(url,timeout=90,headers={'User-Agent':'k20-phase8-live/1.1','Cache-Control':'no-cache'},allow_redirects=True)
        return {'ok':200<=r.status_code<400,'status':r.status_code,'final_url':r.url,'html':r.text[:2000000]}
    except Exception as e:
        return {'ok':False,'status':0,'final_url':url,'html':'','error':str(e)}

pages=paged('wp-json/wp/v2/pages',{'context':'edit','status':'publish'})
CATS={
 'about':['درباره','about'],
 'contact':['تماس','contact'],
 'shipping':['ارسال','حمل','shipping','delivery'],
 'returns':['مرجوع','بازگشت','refund','return','مغایرت'],
 'authenticity':['اصالت','authenticity','ضمانت'],
 'terms':['قوانین','شرایط','terms','خرید'],
 'privacy':['حریم خصوصی','privacy'],
 'why_us':['چرا کشاورز','چرا ما','why us'],
 'proforma':['پیش فاکتور','پیش‌فاکتور','proforma'],
 'content_methodology':['روش تولید محتوا','سیاست محتوا','منابع محتوا','editorial','content methodology','شفافیت محتوا']
}
page_rows=[]
for p in pages:
    title=textify((p.get('title') or {}).get('raw') or (p.get('title') or {}).get('rendered') or '')
    raw=(p.get('content') or {}).get('raw') or (p.get('content') or {}).get('rendered') or ''
    plain=textify(raw)
    hay=(title+' '+(p.get('slug') or '')+' '+plain).lower()
    matches=[cat for cat,keys in CATS.items() if any(k.lower() in hay for k in keys)]
    if matches:
        lv=live(p.get('link') or '')
        page_rows.append({
          'id':p.get('id'),'title':title,'slug':p.get('slug'),'status':p.get('status'),'link':p.get('link'),
          'modified_gmt':p.get('modified_gmt'),'categories':matches,'content_words':len(plain.split()),
          'live_ok':lv.get('ok'),'live_status':lv.get('status'),'live_final_url':lv.get('final_url')
        })

best={}
for cat in CATS:
    candidates=[x for x in page_rows if cat in x['categories']]
    candidates.sort(key=lambda x:(bool(x['live_ok']),x['content_words'],x['modified_gmt'] or ''),reverse=True)
    best[cat]=candidates[0] if candidates else None

home=live(BASE)
org_nodes=[]
if home.get('html'):
    soup=BeautifulSoup(home['html'],'html.parser')
    for tag in soup.find_all('script',attrs={'type':'application/ld+json'}):
        try:
            data=json.loads(tag.string or tag.get_text() or '')
        except Exception:
            continue
        stack=data if isinstance(data,list) else [data]
        while stack:
            obj=stack.pop()
            if isinstance(obj,dict):
                typ=obj.get('@type')
                types=typ if isinstance(typ,list) else [typ]
                if 'Organization' in types:
                    org_nodes.append({'id':obj.get('@id'),'name':obj.get('name'),'url':obj.get('url')})
                for v in obj.values():
                    if isinstance(v,dict):
                        stack.append(v)
                    elif isinstance(v,list):
                        stack.extend(v)
            elif isinstance(obj,list):
                stack.extend(obj)
org_keys=sorted(set((x.get('id') or x.get('url') or x.get('name') or '').strip() for x in org_nodes if (x.get('id') or x.get('url') or x.get('name'))))

posts=paged('wp-json/wp/v2/posts',{'context':'view','status':'publish','orderby':'date','order':'desc'},cap=1)[:5]
author_checks=[]
for p in posts:
    lv=live(p.get('link') or '')
    soup=BeautifulSoup(lv.get('html') or '','html.parser')
    public_text=' '.join(soup.stripped_strings).lower()
    has_rel=bool(soup.find(attrs={'rel':lambda v: v and 'author' in (v if isinstance(v,list) else [v])}))
    has_person=False
    for tag in soup.find_all('script',attrs={'type':'application/ld+json'}):
        txt=tag.string or tag.get_text() or ''
        if '"Person"' in txt or '"@type":"Person"' in txt.replace(' ',''):
            has_person=True; break
    has_author_word=('نویسنده' in public_text or 'author' in public_text)
    author_checks.append({'post_id':p.get('id'),'link':p.get('link'),'live_ok':lv.get('ok'),'public_author_signal':bool(has_rel or has_person or has_author_word)})

mandatory=['about','contact','shipping','returns','authenticity','terms','privacy']
gaps=[x for x in mandatory if not best.get(x)]
soft_gaps=[x for x in ['why_us','proforma','content_methodology'] if not best.get(x)]
org_guard={
 'homepage_live_ok':home.get('ok'),
 'organization_nodes_found':len(org_nodes),
 'distinct_organization_keys':org_keys,
 'duplicate_regression':len(org_keys)>1
}
author_summary={'checked':len(author_checks),'with_public_author_signal':sum(1 for x in author_checks if x['public_author_signal'])}
pass_core=(not gaps and bool(home.get('ok')) and not org_guard['duplicate_regression'])
out={
 'ok':True,'phase':8,'mode':'read-only-live-audit','version':'v1.1','generated_at_utc':NOW,
 'policy':'No credentials, licenses, certifications, reviews, business claims or policy promises are invented. Full P0-C schema audit is not repeated without regression evidence.',
 'summary':{'published_pages_scanned':len(pages),'trust_candidates':len(page_rows),'mandatory_gaps':gaps,'soft_gaps':soft_gaps,'core_acceptance_pass':pass_core},
 'best_pages':best,'trust_candidates':page_rows,'organization_regression_guard':org_guard,
 'recent_post_author_signals':author_checks,'author_summary':author_summary
}
rem={
 'phase':8,'generated_at_utc':NOW,'mandatory_gaps':gaps,'soft_gaps':soft_gaps,
 'safe_actions':[{'gap':g,'action':'Create/update only from verified business facts; otherwise remain blocked rather than fabricate.'} for g in gaps+soft_gaps]
}
os.makedirs('phase8-results',exist_ok=True)
json.dump(out,open('phase8-results/entity-trust-audit.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
json.dump(rem,open('phase8-results/trust-remediation.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('PHASE8_ENTITY_TRUST_AUDIT_OK',json.dumps(out['summary'],ensure_ascii=False))
