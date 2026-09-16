import base64
import html
import json
import os
import pathlib
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

OUT=pathlib.Path('results/refund-seo-live.json')

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def api(method,url,body=None,auth=False):
    headers={'Accept':'application/json','User-Agent':'K20-Refund-SEO-Probe/2.0','Cache-Control':'no-cache'}
    if auth:
        token=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
        headers['Authorization']='Basic '+token
    data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(url,data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            raw=r.read().decode('utf-8','replace')
            try: obj=json.loads(raw) if raw else {}
            except Exception: obj={'raw':raw[:1000]}
            return int(r.status),obj
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try: obj=json.loads(raw)
        except Exception: obj={'raw':raw[:1000]}
        return int(e.code),obj

def public_description(url):
    req=urllib.request.Request(url,headers={'User-Agent':'K20-Refund-SEO-Probe/2.0','Cache-Control':'no-cache','Pragma':'no-cache'})
    with urllib.request.urlopen(req,timeout=120) as r:
        text=r.read().decode('utf-8','replace')
        m=re.search(r'(?is)<meta\b[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\'][^>]*>|<meta\b[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\'][^>]*>',text)
        value=html.unescape((m.group(1) or m.group(2) or '').strip()) if m else ''
        return int(r.status),value

def main():
    for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
        if not os.environ.get(key,'').strip(): raise SystemExit(f'Missing required secret: {key}')
    base=os.environ['WP_BASE_URL'].rstrip('/')
    public_http,desc=public_description(base+'/refund_returns/?k20_seo_probe=2')
    pattern=desc if desc else 'مرجوع'
    body={'target_type':'meta','post_id':13,'meta_key':'_yoast_wpseo_metadesc','pattern':pattern,'case_sensitive':True,'max_results':20}
    search_http,search_obj=api('POST',base+'/wp-json/wpvibe/v1/content/search',body,auth=True)
    result={'executed_at_utc':now(),'page_id':13,'public_http':public_http,'public_meta_description':desc,'search_http':search_http,'search_pattern':pattern,'search_response':search_obj}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'public_http':public_http,'description_length':len(desc),'search_http':search_http},ensure_ascii=False))
    if public_http!=200 or not (200<=search_http<300): raise SystemExit(2)

if __name__=='__main__': main()
