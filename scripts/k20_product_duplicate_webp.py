import base64, io, json, math, os, pathlib, subprocess, time, urllib.error, urllib.parse, urllib.request, xmlrpc.client
from PIL import Image, ImageChops, ImageOps

for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(key,'').strip(): raise SystemExit(f'Missing secret {key}')
base=os.environ['WP_BASE_URL'].rstrip('/'); user=os.environ['WP_USERNAME']; pw=os.environ['WP_APP_PASSWORD']
auth=base64.b64encode(f'{user}:{pw}'.encode()).decode(); bridge=base+'/wp-json/keshavarz20-ops/v2/execute'
server=xmlrpc.client.ServerProxy(base+'/xmlrpc.php',allow_none=True,use_builtin_types=True)

def changed():
    for cmd in (["git","diff","--name-only","HEAD^","HEAD","--","duplicate-webp-ops/*.json"],["git","show","--pretty=","--name-only","HEAD","--","duplicate-webp-ops/*.json"]):
        paths=sorted({x.strip() for x in subprocess.check_output(cmd,text=True).splitlines() if x.strip().startswith('duplicate-webp-ops/') and x.strip().endswith('.json')})
        if paths:return paths
    return []

def qurl(url):
    p=urllib.parse.urlsplit(str(url)); return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/%'),p.query,p.fragment))

def api(method,url,body=None):
    headers={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Duplicate-WebP/1.0'}; data=None
    if body is not None: data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode(); headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=180) as r: return int(r.status),json.loads(r.read().decode('utf-8','replace'))
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:800]}
        return int(e.code),o

def inspect(aid):
    data=json.dumps({'mode':'inspect','resource':'attachment','id':int(aid),'changes':{}},separators=(',',':')).encode()
    req=urllib.request.Request(bridge,data=data,method='POST',headers={'Authorization':'Basic '+auth,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:return int(r.status),json.loads(r.read().decode('utf-8','replace'))
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:800]}
        return int(e.code),o

def getbytes(url):
    with urllib.request.urlopen(urllib.request.Request(qurl(url),headers={'User-Agent':'K20-Duplicate-WebP/1.0'}),timeout=180) as r:return r.read()

def head(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(qurl(url),method='HEAD',headers={'User-Agent':'K20-Duplicate-WebP/1.0'}),timeout=90) as r:return {'status':int(r.status),'bytes':int(r.headers.get('Content-Length') or 0),'content_type':str(r.headers.get('Content-Type') or '')}
    except Exception:return {'status':0,'bytes':0,'content_type':''}

def flatten(im):
    if 'A' in im.getbands():
        rgba=im.convert('RGBA'); bg=Image.new('RGBA',rgba.size,(255,255,255,255)); bg.alpha_composite(rgba); return bg.convert('RGB')
    return im.convert('RGB')

def psnr(a,b):
    aa=flatten(a); bb=flatten(b); hist=ImageChops.difference(aa,bb).histogram(); sq=sum(c*((i%256)**2) for i,c in enumerate(hist)); mse=sq/float(aa.size[0]*aa.size[1]*3)
    return 99.0 if mse<=0 else 20.0*math.log10(255.0/math.sqrt(mse))

def encode(raw,mime,min_psnr,min_lossy,min_lossless):
    src=ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); src.load(); w,h=src.size
    if mime=='image/png':
        b=io.BytesIO(); src.save(b,format='WEBP',lossless=True,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); exact=ImageChops.difference(src.convert('RGBA'),dec.convert('RGBA')).getbbox() is None; saving=round((1-len(data)/float(len(raw)))*100,2)
        if exact and saving>=min_lossless:return data,w,h,99.0,'lossless',True,saving
        raise RuntimeError('no acceptable lossless candidate')
    for q in (88,92,95):
        b=io.BytesIO(); src.save(b,format='WEBP',quality=q,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); score=round(psnr(src,dec),2); saving=round((1-len(data)/float(len(raw)))*100,2)
        if score>=min_psnr and saving>=min_lossy:return data,w,h,score,f'lossy-q{q}',False,saving
    b=io.BytesIO(); src.save(b,format='WEBP',lossless=True,method=6); data=b.getvalue(); dec=Image.open(io.BytesIO(data)); dec.load(); exact=ImageChops.difference(src.convert('RGBA'),dec.convert('RGBA')).getbbox() is None; saving=round((1-len(data)/float(len(raw)))*100,2)
    if exact and saving>=min_lossless:return data,w,h,99.0,'lossless-fallback',True,saving
    raise RuntimeError('no WebP candidate met quality and saving guards')

reqs=changed()
if not reqs:raise SystemExit('No duplicate WebP request')
outdir=pathlib.Path('duplicate-webp-results'); outdir.mkdir(parents=True,exist_ok=True)
for rp in reqs:
    req=json.loads(pathlib.Path(rp).read_text(encoding='utf-8'))
    if req.get('action')!='product.duplicate_webp_migrate':raise SystemExit('Unsupported action')
    items=req.get('items') or []
    if not (1<=len(items)<=5):raise SystemExit('Requires 1..5 items')
    result={'action':'product.duplicate_webp_migrate','executed_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'items':[]}
    for spec in items:
        pid=int(spec.get('product_id',0)); old=int(spec.get('attachment_id',0)); row={'product_id':pid,'old_attachment_id':old,'success':False}; result['items'].append(row); new_id=None; original=[]; attempted=False
        try:
            pc,p=api('GET',f'{base}/wp-json/wc/v3/products/{pid}')
            if not (200<=pc<300):raise RuntimeError(f'product read failed http={pc}')
            original=list(p.get('images') or []); positions=[i for i,x in enumerate(original) if int(x.get('id') or 0)==old]
            expected=int(spec.get('expected_occurrences',2))
            if len(positions)!=expected or expected<2:raise RuntimeError(f'expected {expected} occurrences; found {len(positions)}')
            ic,obj=inspect(old); before=obj.get('before') if isinstance(obj,dict) else None
            if not (200<=ic<300 and obj.get('ok') is True and isinstance(before,dict)):raise RuntimeError('source inspect failed')
            mime=str(before.get('mime_type') or '').lower(); src=str(before.get('url') or '')
            if mime not in ('image/jpeg','image/png') or not src:raise RuntimeError(f'unsupported source {mime}')
            raw=getbytes(src); data,w,h,score,mode,exact,saving=encode(raw,mime,float(req.get('min_psnr',40)),float(req.get('min_saving_lossy_pct',15)),float(req.get('min_saving_lossless_pct',5)))
            alt=str(original[positions[0]].get('alt') or p.get('name') or '')
            row.update({'positions':positions,'original_bytes':len(raw),'webp_bytes_local':len(data),'saving_pct':saving,'psnr_db':score,'pixel_exact':exact,'encoder_mode':mode,'width':w,'height':h,'alt_before':alt})
            up=server.wp.uploadFile(0,user,pw,{'name':f'k20-p{pid}-a{old}-duplicate.webp','type':'image/webp','bits':xmlrpc.client.Binary(data),'overwrite':False,'post_id':pid}); new_id=int(up.get('id') or 0); new_url=str(up.get('url') or '')
            if new_id<=0 or not new_url:raise RuntimeError('invalid WebP upload')
            row.update({'new_attachment_id':new_id,'new_url':new_url})
            nc,no=inspect(new_id); nb=no.get('before') if isinstance(no,dict) else None
            if not (200<=nc<300 and no.get('ok') is True and isinstance(nb,dict) and str(nb.get('mime_type') or '').lower()=='image/webp'):raise RuntimeError('new inspect failed')
            if int(nb.get('width') or 0)!=w or int(nb.get('height') or 0)!=h:raise RuntimeError('dimension mismatch')
            hd=head(new_url); row['new_head']=hd
            if not (200<=hd['status']<400 and 'image/webp' in hd['content_type'].lower()):raise RuntimeError('public WebP verification failed')
            if alt:
                ac,_=api('POST',f'{base}/wp-json/wp/v2/media/{new_id}',{'alt_text':alt}); row['alt_update_http']=ac
                if not (200<=ac<300):raise RuntimeError('ALT update failed')
            payload=[]
            for x in original:
                if int(x.get('id') or 0)==old:payload.append({'id':new_id,'alt':alt})
                else:payload.append({'id':int(x.get('id') or 0)})
            attempted=True; uc,_=api('PUT',f'{base}/wp-json/wc/v3/products/{pid}',{'images':payload}); row['update_http']=uc
            if not (200<=uc<300):raise RuntimeError(f'product update failed http={uc}')
            confirmed=False
            for a in range(1,4):
                if a>1:time.sleep(2)
                rc,rb=api('GET',f'{base}/wp-json/wc/v3/products/{pid}'); imgs=list(rb.get('images') or []) if 200<=rc<300 else []
                ids=[int(x.get('id') or 0) for x in imgs]
                unchanged=all((i in positions and ids[i]==new_id) or (i not in positions and ids[i]==int(original[i].get('id') or 0)) for i in range(min(len(ids),len(original)))) if len(ids)==len(original) else False
                if unchanged and ids.count(new_id)==expected:
                    row.update({'readback_attempts':a,'readback_ids':ids,'readback_occurrences':ids.count(new_id)}); confirmed=True; break
            if not confirmed:raise RuntimeError('readback did not preserve duplicate positions exactly')
            row.update({'success':True,'stage':'verified'})
        except Exception as e:
            row.update({'stage':'error','error':str(e)})
            if attempted and original:
                try:
                    rc,_=api('PUT',f'{base}/wp-json/wc/v3/products/{pid}',{'images':[{'id':int(x.get('id') or 0)} for x in original]}); row['rollback_http']=rc
                except Exception as re:row['rollback_error']=str(re)
            if new_id:
                try:row['cleanup_uploaded_webp']=bool(server.wp.deleteFile(0,user,pw,new_id))
                except Exception:row['cleanup_uploaded_webp']=False
    result['success_count']=sum(1 for x in result['items'] if x.get('success')); result['all_success']=result['success_count']==len(result['items'])
    out=outdir/(pathlib.Path(rp).stem+'.json'); out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
