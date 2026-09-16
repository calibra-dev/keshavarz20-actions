import base64
import io
import json
import math
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageChops, ImageOps

ROOT=pathlib.Path('.')
OPS=ROOT/'elementor-content-migrate-ops'
OUT=ROOT/'content-media-results'
for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(key,'').strip(): raise SystemExit(f'Missing secret {key}')
base=os.environ['WP_BASE_URL'].rstrip('/'); auth=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def qurl(u):
    p=urllib.parse.urlsplit(str(u)); return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/%'),p.query,p.fragment))
def api(method,url,body=None,raw=None,extra=None,timeout=180):
    h={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Elementor-Content-Media/1.0'}
    if extra: h.update(extra)
    data=raw
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode(); h['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            text=r.read().decode('utf-8','replace')
            try:o=json.loads(text) if text else {}
            except Exception:o={'raw':text[:1000]}
            return int(r.status),o
    except urllib.error.HTTPError as e:
        text=e.read().decode('utf-8','replace')
        try:o=json.loads(text)
        except Exception:o={'raw':text[:1000]}
        return int(e.code),o
def get_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(qurl(url),headers={'User-Agent':'K20-Elementor-Content-Media/1.0'}),timeout=180) as r:return r.read()
def public_get(url):
    req=urllib.request.Request(qurl(url),headers={'User-Agent':'K20-Elementor-Content-Media/1.0','Cache-Control':'no-cache'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:return int(r.status),r.read().decode('utf-8','replace')
    except Exception:return 0,''
def head(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(qurl(url),method='HEAD',headers={'User-Agent':'K20-Elementor-Content-Media/1.0'}),timeout=90) as r:return {'status':int(r.status),'content_type':str(r.headers.get('Content-Type') or ''),'bytes':int(r.headers.get('Content-Length') or 0)}
    except Exception:return {'status':0,'content_type':'','bytes':0}
def flat(im):
    if 'A' in im.getbands():
        rgba=im.convert('RGBA'); bg=Image.new('RGBA',rgba.size,(255,255,255,255)); bg.alpha_composite(rgba); return bg.convert('RGB')
    return im.convert('RGB')
def psnr(a,b):
    aa=flat(a); bb=flat(b); hist=ImageChops.difference(aa,bb).histogram(); sq=sum(c*((i%256)**2) for i,c in enumerate(hist)); mse=sq/float(aa.size[0]*aa.size[1]*3); return 99.0 if mse<=0 else 20*math.log10(255/math.sqrt(mse))
def encode(raw,mime,min_psnr=40.0,min_lossy=15.0,min_lossless=5.0):
    src=ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); src.load(); w,h=src.size
    if mime=='image/png':
        b=io.BytesIO(); src.save(b,format='WEBP',lossless=True,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); exact=ImageChops.difference(src.convert('RGBA'),dec.convert('RGBA')).getbbox() is None; saving=round((1-len(data)/len(raw))*100,2)
        if exact and saving>=min_lossless:return data,w,h,99.0,'lossless',True,saving
        raise RuntimeError(f'quality guard: PNG lossless exact={exact} saving={saving}')
    for q in (88,92,95):
        b=io.BytesIO(); src.save(b,format='WEBP',quality=q,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); score=round(psnr(src,dec),2); saving=round((1-len(data)/len(raw))*100,2)
        if score>=min_psnr and saving>=min_lossy:return data,w,h,score,f'lossy-q{q}',False,saving
    b=io.BytesIO(); src.save(b,format='WEBP',lossless=True,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); exact=ImageChops.difference(src.convert('RGBA'),dec.convert('RGBA')).getbbox() is None; saving=round((1-len(data)/len(raw))*100,2)
    if exact and saving>=min_lossless:return data,w,h,99.0,'lossless-fallback',True,saving
    raise RuntimeError(f'quality guard: no acceptable WebP saving={saving}')
def upload_webp(pid,old,data,alt):
    name=f'k20-content-p{pid}-a{old}.webp'; code,obj=api('POST',base+'/wp-json/wp/v2/media',raw=data,extra={'Content-Type':'image/webp','Content-Disposition':f'attachment; filename="{name}"'})
    if not (200<=code<300 and isinstance(obj,dict) and int(obj.get('id') or 0)>0): raise RuntimeError(f'media upload failed http={code}')
    aid=int(obj['id']); url=str(obj.get('source_url') or '')
    if alt:
        ac,_=api('POST',f'{base}/wp-json/wp/v2/media/{aid}',{'alt_text':alt})
        if not 200<=ac<300: raise RuntimeError(f'alt update failed http={ac}')
    return aid,url
def delete_media(aid):
    code,_=api('DELETE',f'{base}/wp-json/wp/v2/media/{aid}?force=true',timeout=120); return 200<=code<300
def get_post(pid): return api('GET',f'{base}/wp-json/wp/v2/posts/{pid}?context=edit&_fields=id,status,link,featured_media,content,meta')
def get_media(aid): return api('GET',f'{base}/wp-json/wp/v2/media/{aid}?context=edit&_fields=id,source_url,mime_type,media_details,alt_text')

def numeric_id(value):
    if isinstance(value,int): return value
    if isinstance(value,str) and value.isdigit(): return int(value)
    return 0

def find_image_nodes(obj,aid,url,path='$'):
    hits=[]
    if isinstance(obj,dict):
        if str(obj.get('url') or '')==url and numeric_id(obj.get('id'))==aid:
            hits.append((path,obj))
        for k,v in obj.items(): hits.extend(find_image_nodes(v,aid,url,f'{path}.{k}'))
    elif isinstance(obj,list):
        for i,v in enumerate(obj): hits.extend(find_image_nodes(v,aid,url,f'{path}[{i}]'))
    return hits

def apply_request(req):
    pid=int(req.get('post_id') or 0); olds=[int(x) for x in (req.get('attachment_ids') or [])]
    result={'post_id':pid,'attachment_ids':olds,'success':False,'stage':'start','media':[]}; uploaded=[]; wrote=False; original_raw=''; original_elem=''
    try:
        if pid<=0 or not (1<=len(olds)<=3) or len(set(olds))!=len(olds): raise RuntimeError('invalid guarded request')
        pc,post=get_post(pid)
        if not (200<=pc<300 and isinstance(post,dict) and str(post.get('status') or '')=='publish'): raise RuntimeError(f'post precondition failed http={pc}')
        content=post.get('content') or {}; original_raw=str(content.get('raw') or '') if isinstance(content,dict) else ''
        meta=post.get('meta') or {}; original_elem=meta.get('_elementor_data') if isinstance(meta,dict) else ''
        if not isinstance(original_elem,str) or not original_elem: raise RuntimeError('Elementor data missing or not string')
        elem=json.loads(original_elem)
        replacements={}
        for old in olds:
            mc,oldm=get_media(old)
            if not (200<=mc<300 and isinstance(oldm,dict)): raise RuntimeError(f'old media {old} read failed')
            src=str(oldm.get('source_url') or ''); mime=str(oldm.get('mime_type') or '').lower(); alt=str(oldm.get('alt_text') or '')
            if mime not in ('image/jpeg','image/png') or not src: raise RuntimeError(f'unsupported source media {old}')
            nodes=find_image_nodes(elem,old,src)
            if len(nodes)!=1: raise RuntimeError(f'Elementor precondition old={old} nodes={len(nodes)}')
            raw_bytes=get_bytes(src); data,w,h,score,mode,exact,saving=encode(raw_bytes,mime)
            new_id,new_url=upload_webp(pid,old,data,alt); uploaded.append(new_id)
            nc,newm=get_media(new_id); nd=newm.get('media_details') or {} if isinstance(newm,dict) else {}
            if not (200<=nc<300 and str(newm.get('mime_type') or '').lower()=='image/webp' and int(nd.get('width') or 0)==w and int(nd.get('height') or 0)==h): raise RuntimeError(f'new media {new_id} verification failed')
            hd=head(new_url)
            if not (200<=hd['status']<400 and 'image/webp' in hd['content_type'].lower()): raise RuntimeError(f'new media {new_id} public HEAD failed')
            replacements[old]={'old_url':src,'new_id':new_id,'new_url':new_url}
            result['media'].append({'old_attachment_id':old,'new_attachment_id':new_id,'old_url':src,'new_url':new_url,'original_bytes':len(raw_bytes),'webp_bytes':len(data),'saving_pct':saving,'psnr_db':score,'encoder_mode':mode,'pixel_exact':exact,'width':w,'height':h,'head':hd})
        new_raw=original_raw
        for old,r in replacements.items():
            count=new_raw.count(r['old_url'])
            if old==142591:
                if count!=1: raise RuntimeError(f'raw content precondition old={old} url_count={count}')
                new_raw=new_raw.replace(r['old_url'],r['new_url'],1)
            elif count!=0:
                raise RuntimeError(f'unexpected raw content URL reference old={old} count={count}')
            nodes=find_image_nodes(elem,old,r['old_url'])
            if len(nodes)!=1: raise RuntimeError(f'Elementor mutation precondition old={old} nodes={len(nodes)}')
            nodes[0][1]['id']=r['new_id']; nodes[0][1]['url']=r['new_url']
        new_elem=json.dumps(elem,ensure_ascii=False,separators=(',',':'))
        uc,_=api('POST',f'{base}/wp-json/wp/v2/posts/{pid}',{'content':new_raw,'meta':{'_elementor_data':new_elem}}); result['update_http']=uc
        if not 200<=uc<300: raise RuntimeError(f'post update failed http={uc}')
        wrote=True
        rc,rb=get_post(pid)
        if not (200<=rc<300 and isinstance(rb,dict)): raise RuntimeError('post readback failed')
        rr=(rb.get('content') or {}).get('raw') if isinstance(rb.get('content'),dict) else ''; rm=(rb.get('meta') or {}).get('_elementor_data') if isinstance(rb.get('meta'),dict) else ''
        if not isinstance(rr,str) or not isinstance(rm,str) or not rm: raise RuntimeError('post readback fields invalid')
        rem=json.loads(rm)
        for old,r in replacements.items():
            if find_image_nodes(rem,old,r['old_url']): raise RuntimeError(f'old Elementor node remained {old}')
            if len(find_image_nodes(rem,r['new_id'],r['new_url']))!=1: raise RuntimeError(f'new Elementor node missing {r["new_id"]}')
            if old==142591 and (r['old_url'] in rr or rr.count(r['new_url'])!=1): raise RuntimeError('raw content readback mismatch')
        link=str(rb.get('link') or post.get('link') or ''); public_ok=False; last={}
        for attempt in range(1,4):
            check=link+('&' if '?' in link else '?')+f'k20_media_verify={int(time.time())}-{attempt}' if link else ''
            hc,html=public_get(check) if check else (0,''); last={'http':hc,'attempt':attempt}
            if hc==200:
                old_classes=sum(html.count(f'wp-image-{old}') for old in olds); new_classes=sum(html.count(f'wp-image-{r["new_id"]}') for r in replacements.values())
                last.update({'old_classes':old_classes,'new_classes':new_classes})
                if old_classes==0 and new_classes>=len(olds): public_ok=True; break
            time.sleep(2)
        result['public_readback']=last
        if not public_ok: raise RuntimeError('public page did not confirm Elementor migration')
        result.update({'success':True,'stage':'verified','new_attachment_ids':[r['new_id'] for r in replacements.values()]})
    except Exception as e:
        result.update({'stage':'error','error':str(e)})
        rollback_ok=True
        if wrote:
            try:
                bc,_=api('POST',f'{base}/wp-json/wp/v2/posts/{pid}',{'content':original_raw,'meta':{'_elementor_data':original_elem}}); rollback_ok=200<=bc<300; result['rollback_http']=bc
            except Exception as rb_err:
                rollback_ok=False; result['rollback_error']=str(rb_err)
        result['rollback_ok']=rollback_ok
        cleanup=[]
        if rollback_ok:
            for aid in uploaded:
                try: cleanup.append({'attachment_id':aid,'deleted':delete_media(aid)})
                except Exception: cleanup.append({'attachment_id':aid,'deleted':False})
        result['cleanup']=cleanup
    return result

requests=sorted(OPS.glob('*.json'))
if not requests: raise SystemExit('No request found')
req_path=requests[-1]; req=json.loads(req_path.read_text(encoding='utf-8'))
if req.get('action')!='content_media.elementor_pair_migrate': raise SystemExit('Unsupported action')
result=apply_request(req); wrapper={'executed_at_utc':now(),'action':req.get('action'),'request_file':req_path.name,'result':result}
OUT.mkdir(parents=True,exist_ok=True); dest=OUT/(req_path.stem+'-migration.json'); dest.write_text(json.dumps(wrapper,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'success':result.get('success'),'stage':result.get('stage')},ensure_ascii=False))
if not result.get('success'): raise SystemExit(2)
