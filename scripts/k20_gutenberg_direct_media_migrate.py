import base64
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT=pathlib.Path('.')
OPS=ROOT/'direct-content-migrate-ops'
OUT=ROOT/'content-media-results'
for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(key,'').strip(): raise SystemExit(f'Missing secret {key}')
base=os.environ['WP_BASE_URL'].rstrip('/'); auth=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def qurl(u):
    p=urllib.parse.urlsplit(str(u)); return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/%'),p.query,p.fragment))
def api(method,url,body=None,auth_header=True):
    headers={'Accept':'application/json','User-Agent':'K20-Gutenberg-Direct-Media/1.0'}
    if auth_header: headers['Authorization']='Basic '+auth
    data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode(); headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            raw=r.read().decode('utf-8','replace')
            try:o=json.loads(raw) if raw else {}
            except Exception:o={'raw':raw}
            return int(r.status),o
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:500]}
        return int(e.code),o
def public_get(url):
    req=urllib.request.Request(qurl(url),headers={'User-Agent':'K20-Gutenberg-Direct-Media/1.0','Cache-Control':'no-cache'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:return int(r.status),r.read().decode('utf-8','replace')
    except Exception:return 0,''
def get_post(pid): return api('GET',f'{base}/wp-json/wp/v2/posts/{pid}?context=edit&_fields=id,status,link,featured_media,content')
def get_media(aid): return api('GET',f'{base}/wp-json/wp/v2/media/{aid}?context=edit&_fields=id,source_url,mime_type,media_details,alt_text')

def find_block(raw,old):
    blocks=[]
    pat=re.compile(r'<!--\s*wp:image\s+(\{.*?\})\s*-->(.*?)<!--\s*/wp:image\s*-->',re.S|re.I)
    for m in pat.finditer(raw):
        try: meta=json.loads(m.group(1))
        except Exception: continue
        if int(meta.get('id') or 0)==old:
            blocks.append((m,meta,m.group(2)))
    return blocks

def large_url(media):
    details=media.get('media_details') or {}; sizes=details.get('sizes') or {}
    large=sizes.get('large') or {}
    return str(large.get('source_url') or media.get('source_url') or '')

def apply_one(spec):
    pid=int(spec.get('post_id') or 0); old=int(spec.get('old_attachment_id') or 0); expected_featured=int(spec.get('expected_replacement_attachment_id') or 0)
    row={'post_id':pid,'old_attachment_id':old,'success':False,'stage':'start'}; original_raw=''; wrote=False
    try:
        if pid<=0 or old<=0 or expected_featured<=0: raise RuntimeError('invalid guarded request')
        pc,post=get_post(pid)
        if not (200<=pc<300 and isinstance(post,dict)): raise RuntimeError(f'post read failed http={pc}')
        if str(post.get('status') or '')!='publish': raise RuntimeError('post is not published')
        if int(post.get('featured_media') or 0)!=expected_featured: raise RuntimeError('expected replacement is not current featured media')
        content=post.get('content') or {}; original_raw=str(content.get('raw') or '') if isinstance(content,dict) else ''
        blocks=find_block(original_raw,old)
        if len(blocks)!=1: raise RuntimeError(f'expected exactly one Gutenberg image block, found {len(blocks)}')
        oc,oldm=get_media(old); nc,newm=get_media(expected_featured)
        if not (200<=oc<300 and 200<=nc<300): raise RuntimeError('media read failed')
        if str(newm.get('mime_type') or '').lower()!='image/webp': raise RuntimeError('replacement is not WebP')
        new_src=str(newm.get('source_url') or '')
        if f'a{old}' not in new_src and str(old) not in new_src: raise RuntimeError('replacement URL does not prove source attachment mapping')
        od=oldm.get('media_details') or {}; nd=newm.get('media_details') or {}
        if int(od.get('width') or 0)!=int(nd.get('width') or 0) or int(od.get('height') or 0)!=int(nd.get('height') or 0): raise RuntimeError('replacement dimensions differ from source')
        new_large=large_url(newm)
        if not new_large: raise RuntimeError('replacement has no usable public URL')
        m,meta,inner=blocks[0]
        if f'wp-image-{old}' not in inner: raise RuntimeError('expected wp-image class missing from target block')
        img_match=re.search(r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'][^>]*>)',inner,re.I|re.S)
        if not img_match: raise RuntimeError('target block img src not found')
        old_rendered_src=img_match.group(2)
        meta['id']=expected_featured
        new_comment='<!-- wp:image '+json.dumps(meta,ensure_ascii=False,separators=(',',':'))+' -->'
        new_inner=inner.replace(f'wp-image-{old}',f'wp-image-{expected_featured}',1)
        new_inner=new_inner[:img_match.start(2)]+new_large+new_inner[img_match.end(2):]
        new_block=new_comment+new_inner+'<!-- /wp:image -->'
        new_raw=original_raw[:m.start()]+new_block+original_raw[m.end():]
        if find_block(new_raw,old): raise RuntimeError('old Gutenberg block id remained after transform')
        if len(find_block(new_raw,expected_featured))!=1: raise RuntimeError('new Gutenberg block id not unique after transform')
        uc,_=api('POST',f'{base}/wp-json/wp/v2/posts/{pid}',{'content':new_raw}); row['update_http']=uc
        if not (200<=uc<300): raise RuntimeError(f'post update failed http={uc}')
        wrote=True
        rc,rb=get_post(pid); rr=(rb.get('content') or {}).get('raw') if isinstance(rb,dict) and isinstance(rb.get('content'),dict) else ''
        if not (200<=rc<300 and isinstance(rr,str)): raise RuntimeError('post readback failed')
        if len(find_block(rr,old))!=0 or len(find_block(rr,expected_featured))!=1: raise RuntimeError('post readback block ids mismatch')
        if f'wp-image-{old}' in rr or f'wp-image-{expected_featured}' not in rr: raise RuntimeError('post readback image class mismatch')
        if old_rendered_src in rr or new_large not in rr: raise RuntimeError('post readback image src mismatch')
        link=str(rb.get('link') or post.get('link') or '')
        check_url=link+('&' if '?' in link else '?')+f'k20_media_verify={int(time.time())}' if link else ''
        hc,html=public_get(check_url) if check_url else (0,'')
        row['public_http']=hc; row['public_new_class']=html.count(f'wp-image-{expected_featured}'); row['public_old_class']=html.count(f'wp-image-{old}')
        if hc!=200 or row['public_new_class']<1 or row['public_old_class']!=0: raise RuntimeError('public readback did not confirm Gutenberg migration')
        row.update({'success':True,'stage':'verified','new_attachment_id':expected_featured,'old_rendered_src':old_rendered_src,'new_rendered_src':new_large,'reused_existing_webp':True})
    except Exception as e:
        row.update({'stage':'error','error':str(e)})
        if wrote and original_raw:
            try:
                rbcode,_=api('POST',f'{base}/wp-json/wp/v2/posts/{pid}',{'content':original_raw}); row['rollback_http']=rbcode; row['rollback_ok']=200<=rbcode<300
            except Exception as rollback_err:
                row['rollback_ok']=False; row['rollback_error']=str(rollback_err)
    return row

requests=sorted(OPS.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
if not requests: raise SystemExit('No request found')
req_path=requests[0]; req=json.loads(req_path.read_text(encoding='utf-8'))
if req.get('action')!='content_media.gutenberg_migrate_existing_webp': raise SystemExit('Unsupported action')
items=req.get('items') or []
if not (1<=len(items)<=2): raise SystemExit('Requires 1..2 items')
rows=[apply_one(x) for x in items]
result={'executed_at_utc':now(),'action':req.get('action'),'items':rows,'success_count':sum(1 for x in rows if x.get('success')),'all_success':all(x.get('success') for x in rows)}
OUT.mkdir(parents=True,exist_ok=True); dest=OUT/(req_path.stem+'-migration.json'); dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'success_count':result['success_count'],'all_success':result['all_success']},ensure_ascii=False))
if not result['all_success']: raise SystemExit(2)
