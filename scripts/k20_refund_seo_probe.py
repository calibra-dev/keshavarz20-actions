import html
import json
import os
import re
import urllib.request
import xmlrpc.client
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def public_description(url):
    req = urllib.request.Request(url, headers={'User-Agent':'K20-Refund-SEO-Probe/1.0','Cache-Control':'no-cache','Pragma':'no-cache'})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = r.read().decode('utf-8','replace')
        m = re.search(r'(?is)<meta\b[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\'][^>]*>|<meta\b[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\'][^>]*>', text)
        value = html.unescape((m.group(1) or m.group(2) or '').strip()) if m else ''
        return int(r.status), value


def main():
    for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
        if not os.environ.get(key,'').strip():
            raise SystemExit(f'Missing required secret: {key}')
    base=os.environ['WP_BASE_URL'].rstrip('/')
    server=xmlrpc.client.ServerProxy(base+'/xmlrpc.php', allow_none=True, use_builtin_types=True)
    post=server.wp.getPost(0,os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'],13,['post_id','post_status','post_modified_gmt','custom_fields'])
    if int(post.get('post_id') or 0)!=13:
        raise SystemExit('Unexpected page id')
    wanted={'_yoast_wpseo_metadesc','_yoast_wpseo_title','_yoast_wpseo_focuskw'}
    seo={}
    for item in post.get('custom_fields') or []:
        key=str(item.get('key') or '')
        if key in wanted:
            seo[key]=str(item.get('value') or '')
    code,desc=public_description(base+'/refund_returns/?k20_seo_probe=1')
    result={'executed_at_utc':now(),'page_id':13,'post_status':str(post.get('post_status') or ''),'post_modified_gmt':str(post.get('post_modified_gmt') or ''),'seo_meta':seo,'public_http':code,'public_meta_description':desc}
    pathlib = __import__('pathlib')
    out=pathlib.Path('results/refund-seo-live.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'page_id':13,'public_http':code,'metadesc_present':bool(seo.get('_yoast_wpseo_metadesc')),'public_description_present':bool(desc)},ensure_ascii=False))

if __name__=='__main__':
    main()
