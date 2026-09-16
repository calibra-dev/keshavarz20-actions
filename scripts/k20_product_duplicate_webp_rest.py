import base64, io, json, math, os, pathlib, subprocess, time, urllib.error, urllib.parse, urllib.request
from PIL import Image, ImageChops, ImageOps

for k in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(k,'').strip(): raise SystemExit(f'Missing secret {k}')
base=os.environ['WP_BASE_URL'].rstrip('/'); user=os.environ['WP_USERNAME']; pw=os.environ['WP_APP_PASSWORD']
auth=base64.b64encode(f'{user}:{pw}'.encode()).decode(); bridge=base+'/wp-json/keshavarz20-ops/v2/execute'

def changed():
    for cmd in (["git","diff","--name-only","HEAD^","HEAD","--","duplicate-webp-rest-ops/*.json"],["git","show","--pretty=","--name-only","HEAD","--","duplicate-webp-rest-ops/*.json"]):
        p=sorted({x.strip() for x in subprocess.check_output(cmd,text=True).splitlines() if x.strip().startswith('duplicate-webp-rest-ops/') and x.strip().endswith('.json')})
        if p:return p
    return []

def qurl(u):
    p=urllib.parse.urlsplit(str(u)); return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/%'),p.query,p.fragment))

def api(method,url,body=None,headers_extra=None,raw_body=None,timeout=180):
    h={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Duplicate-WebP-REST/1.0'}
    if headers_extra:h.update(headers_extra)
    data=raw_body
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode(); h['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read().decode('utf-8','replace'); return int(r.status),json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:800]}
        return int(e.code),o

def inspect(aid):
    data=json.dumps({'mode':'inspect','resource':'attachment','id':int(aid),'changes':{}},separators=(',',':')).encode()
    return api('POST',bridge,raw_body=data,headers_extra={'Content-Type':'application/json; charset=utf-8'},timeout=120)

def getbytes(url):
    with urllib.request.urlopen(urllib.request.Request(qurl(url),headers={'User-Agent':'K20-Duplicate-WebP-REST/1.0'}),timeout=180) as r:return r.read()

def head(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(qurl(url),method='HEAD',headers={'User-Agent':'K20-Duplicate-WebP-REST/1.0'}),timeout=90) as r:return {'status':int(r.status),'bytes':int(r.headers.get('Content-Length') or 0),'content_type':str(r.headers.get('Content-Type') or '')}
    except Exception:return {'status':0,'bytes':0,'content_type':''}

def flat(im):
    if 'A' in im.getbands():
        x=im.convert('RGBA'); bg=Image.new('RGBA',x.size,(255,255,255,255)); bg.alpha_composite(x); return bg.convert('RGB')
    return im.convert('RGB')

def score_psnr(a,b):
    aa=flat(a); bb=flat(b); hist=ImageChops.difference(aa,bb).histogram(); sq=sum(c*((i%256)**2) for i,c in enumerate(hist)); mse=sq/float(aa.size[0]*aa.size[1]*3); return 99.0 if mse<=0 else 20*math.log10(255/math.sqrt(mse))

def encode(raw,mime,min_psnr,min_lossy,min_lossless):
    src=ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); src.load(); w,h=src.size
    def lossless():
        b=io.BytesIO(); src.save(b,format='WEBP',lossless=True,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); exact=ImageChops.difference(src.convert('RGBA'),dec.convert('RGBA')).getbbox() is None; saving=round((1-len(data)/float(len(raw)))*100,2); return data,exact,saving
    if mime=='image/png':
        data,exact,saving=lossless()
        if exact and saving>=min_lossless:return data,w,h,99.0,'lossless',True,saving
        raise RuntimeError('no acceptable lossless candidate')
    for q in (88,92,95):
        b=io.BytesIO(); src.save(b,format='WEBP',quality=q,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); ps=round(score_psnr(src,dec),2); saving=round((1-len(data)/float(len(raw)))*100,2)
        if ps>=min_psnr and saving>=min_lossy:return data,w,h,ps,f'lossy-q{q}',False,saving
    data,exact,saving=lossless()
    if exact and saving>=min_lossless:return data,w,h,99.0,'lossless-fallback',True,saving
    raise RuntimeError('no candidate met guards')

def upload_webp(filename,data):
    code,obj=api('POST',base+'/wp-json/wp/v2/media',raw_body=data,headers_extra={'Content-Type':'image/webp','Content-Disposition':f'attachment; filename="{filename}"'},timeout=180)
    if not (200<=code<300):raise RuntimeError(f'REST media upload failed http={code} body={str(obj)[:300]}')
    return int(obj.get('id') or 0),str(obj.get('source_url') or '')

def delete_media(aid):
    code,_=api('DELETE',f'{base}/wp-json/wp/v2/media/{aid}?force=true',timeout=120); return 200<=code<300

reqs=changed()
if not reqs:raise SystemExit('No request')
outdir=pathlib.Path('duplicate-webp-rest-results'); outdir.mkdir(parents=True,exist_ok=True)
for rp in reqs:
    req=json.loads(pathlib.Path(rp).read_text(encoding='utf-8')); items=req.get('items') or []
    if req.get('action')!='product.duplicate_webp_rest_migrate' or not (1<=len(items)<=5):raise SystemExit('Unsupported request')
    result={'action':'product.duplicate_webp_rest_migrate','executed_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'items':[]}
    for spec in items:
        pid=int(spec['product_id']); old=int(spec['attachment_id']); expected=int(spec.get('expected_occurrences',2)); row={'product_id':pid,'old_attachment_id':old,'success':False}; result['items'].append(row); new_id=0; original=[]; attempted=False
        try:
            pc,p=api('GET',f'{base}/wp-json/wc/v3/products/{pid}'); original=list(p.get('images') or []) if 200<=pc<300 else []
            pos=[i for i,x in enumerate(original) if int(x.get('id') or 0)==old]
            if len(pos)!=expected or expected<2:raise RuntimeError(f'expected {expected} occurrences; found {len(pos)}')
            ic,obj=inspect(old); before=obj.get('before') if isinstance(obj,dict) else None
            if not (200<=ic<300 and isinstance(before,dict)):raise RuntimeError('source inspect failed')
            mime=str(before.get('mime_type') or '').lower(); src=str(before.get('url') or '')
            raw=getbytes(src); data,w,h,ps,mode,exact,saving=encode(raw,mime,float(req.get('min_psnr',40)),float(req.get('min_saving_lossy_pct',15)),float(req.get('min_saving_lossless_pct',5)))
            alt=str(original[pos[0]].get('alt') or p.get('name') or '')
            row.update({'positions':pos,'original_bytes':len(raw),'webp_bytes_local':len(data),'saving_pct':saving,'psnr_db':ps,'pixel_exact':exact,'encoder_mode':mode,'width':w,'height':h,'alt_before':alt})
            new_id,new_url=upload_webp(f'k20-p{pid}-a{old}-duplicate-rest.webp',data)
            if new_id<=0 or not new_url:raise RuntimeError('REST upload returned invalid media')
            row.update({'new_attachment_id':new_id,'new_url':new_url})
            nc,no=inspect(new_id); nb=no.get('before') if isinstance(no,dict) else None
            if not (200<=nc<300 and isinstance(nb,dict) and str(nb.get('mime_type') or '').lower()=='image/webp'):raise RuntimeError('new media inspect failed')
            if int(nb.get('width') or 0)!=w or int(nb.get('height') or 0)!=h:raise RuntimeError('dimension mismatch')
            hd=head(new_url); row['new_head']=hd
            if not (200<=hd['status']<400 and 'image/webp' in hd['content_type'].lower()):raise RuntimeError('public WebP check failed')
            if alt:
                ac,_=api('POST',f'{base}/wp-json/wp/v2/media/{new_id}',{'alt_text':alt}); row['alt_update_http']=ac
                if not (200<=ac<300):raise RuntimeError('ALT update failed')
            payload=[{'id':new_id,'alt':alt} if int(x.get('id') or 0)==old else {'id':int(x.get('id') or 0)} for x in original]
            attempted=True; uc,_=api('PUT',f'{base}/wp-json/wc/v3/products/{pid}',{'images':payload}); row['update_http']=uc
            if not (200<=uc<300):raise RuntimeError(f'product update failed http={uc}')
            good=False
            for a in range(1,4):
                if a>1:time.sleep(2)
                rc,rb=api('GET',f'{base}/wp-json/wc/v3/products/{pid}'); imgs=list(rb.get('images') or []) if 200<=rc<300 else []; ids=[int(x.get('id') or 0) for x in imgs]
                if len(ids)==len(original) and ids.count(new_id)==expected and all(ids[i]==(new_id if i in pos else int(original[i].get('id') or 0)) for i in range(len(ids))):
                    row.update({'readback_attempts':a,'readback_ids':ids,'readback_occurrences':expected}); good=True; break
            if not good:raise RuntimeError('readback did not preserve duplicate positions exactly')
            row.update({'success':True,'stage':'verified'})
        except Exception as e:
            row.update({'stage':'error','error':str(e)})
            if attempted and original:
                try:
                    rc,_=api('PUT',f'{base}/wp-json/wc/v3/products/{pid}',{'images':[{'id':int(x.get('id') or 0)} for x in original]}); row['rollback_http']=rc
                except Exception as re:row['rollback_error']=str(re)
            if new_id:
                try:row['cleanup_uploaded_webp']=delete_media(new_id)
                except Exception:row['cleanup_uploaded_webp']=False
    result['success_count']=sum(1 for x in result['items'] if x.get('success')); result['all_success']=result['success_count']==len(result['items'])
    (outdir/(pathlib.Path(rp).stem+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
