import base64, io, json, math, os, pathlib, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageChops, ImageOps

ROOT=pathlib.Path('.'); SOURCE=ROOT/'media-autopilot/state.json'; CONFIG=ROOT/'media-rest-rescue/config.json'; STATE=ROOT/'media-rest-rescue/state.json'; OUT=ROOT/'media-rest-rescue-results'

def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def load(p,d):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
for k in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(k,'').strip():raise SystemExit(f'Missing secret {k}')
base=os.environ['WP_BASE_URL'].rstrip('/'); user=os.environ['WP_USERNAME']; pw=os.environ['WP_APP_PASSWORD']; auth=base64.b64encode(f'{user}:{pw}'.encode()).decode(); bridge=base+'/wp-json/keshavarz20-ops/v2/execute'
cfg=load(CONFIG,{})
if cfg.get('enabled') is not True:print('REST rescue disabled'); raise SystemExit(0)
source=load(SOURCE,{}); state=load(STATE,{'status':'running','cycles':0,'successful_migrations':0,'processed':{},'skipped':{},'critical_events':[]})
for k,d in (('processed',{}),('skipped',{}),('critical_events',[])):state.setdefault(k,d)
state.setdefault('cycles',0); state.setdefault('successful_migrations',0)
batch=max(1,min(10,int(cfg.get('batch_size',1)))); max_attempts=max(1,min(3,int(cfg.get('max_attempts',2)))); min_psnr=max(36,float(cfg.get('min_psnr',40))); min_lossy=max(0,float(cfg.get('min_saving_lossy_pct',15))); min_lossless=max(0,float(cfg.get('min_saving_lossless_pct',5))); run_id=str(os.environ.get('GITHUB_RUN_ID') or int(time.time()))

def qurl(u):
    p=urllib.parse.urlsplit(str(u));return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/%'),p.query,p.fragment))
def api(method,url,body=None,raw=None,extra=None,timeout=180):
    h={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Product-REST-Rescue/1.0'}
    if extra:h.update(extra)
    data=raw
    if body is not None:data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();h['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            s=r.read().decode('utf-8','replace');return int(r.status),json.loads(s) if s else {}
    except urllib.error.HTTPError as e:
        s=e.read().decode('utf-8','replace')
        try:o=json.loads(s)
        except Exception:o={'raw':s[:600]}
        return int(e.code),o
def inspect(aid):
    raw=json.dumps({'mode':'inspect','resource':'attachment','id':int(aid),'changes':{}},separators=(',',':')).encode();return api('POST',bridge,raw=raw,extra={'Content-Type':'application/json; charset=utf-8'},timeout=120)
def getbytes(url):
    with urllib.request.urlopen(urllib.request.Request(qurl(url),headers={'User-Agent':'K20-Product-REST-Rescue/1.0'}),timeout=180) as r:return r.read()
def head(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(qurl(url),method='HEAD',headers={'User-Agent':'K20-Product-REST-Rescue/1.0'}),timeout=90) as r:return {'status':int(r.status),'bytes':int(r.headers.get('Content-Length') or 0),'content_type':str(r.headers.get('Content-Type') or '')}
    except Exception:return {'status':0,'bytes':0,'content_type':''}
def flat(im):
    if 'A' in im.getbands():
        x=im.convert('RGBA');bg=Image.new('RGBA',x.size,(255,255,255,255));bg.alpha_composite(x);return bg.convert('RGB')
    return im.convert('RGB')
def psnr(a,b):
    aa=flat(a);bb=flat(b);hist=ImageChops.difference(aa,bb).histogram();sq=sum(c*((i%256)**2) for i,c in enumerate(hist));mse=sq/float(aa.size[0]*aa.size[1]*3);return 99.0 if mse<=0 else 20*math.log10(255/math.sqrt(mse))
def encode(raw,mime):
    src=ImageOps.exif_transpose(Image.open(io.BytesIO(raw)));src.load();w,h=src.size
    def lossless():
        b=io.BytesIO();src.save(b,format='WEBP',lossless=True,method=6);d=b.getvalue();dec=Image.open(io.BytesIO(d));dec.load();exact=ImageChops.difference(src.convert('RGBA'),dec.convert('RGBA')).getbbox() is None;s=round((1-len(d)/float(len(raw)))*100,2);return d,exact,s
    if mime=='image/png':
        d,e,s=lossless()
        if e and s>=min_lossless:return d,w,h,99.0,'lossless',True,s
        raise RuntimeError('TERMINAL: no acceptable lossless candidate')
    for q in (88,92,95):
        b=io.BytesIO();src.save(b,format='WEBP',quality=q,method=6);d=b.getvalue();dec=Image.open(io.BytesIO(d));dec.load();p=round(psnr(src,dec),2);s=round((1-len(d)/float(len(raw)))*100,2)
        if p>=min_psnr and s>=min_lossy:return d,w,h,p,f'lossy-q{q}',False,s
    d,e,s=lossless()
    if e and s>=min_lossless:return d,w,h,99.0,'lossless-fallback',True,s
    raise RuntimeError('TERMINAL: no WebP candidate met quality and saving guards')
def upload(name,data):
    c,o=api('POST',base+'/wp-json/wp/v2/media',raw=data,extra={'Content-Type':'image/webp','Content-Disposition':f'attachment; filename="{name}"'})
    if not (200<=c<300):raise RuntimeError(f'REST media upload failed http={c}')
    return int(o.get('id') or 0),str(o.get('source_url') or '')
def delete(aid):return 200<=api('DELETE',f'{base}/wp-json/wp/v2/media/{aid}?force=true',timeout=120)[0]<300

def migrate(pid,old):
    row={'product_id':pid,'old_attachment_id':old,'success':False};new_id=0;original=[];attempted=False;pos=-1;primary=False
    try:
        pc,p=api('GET',f'{base}/wp-json/wc/v3/products/{pid}');original=list(p.get('images') or []) if 200<=pc<300 else []
        positions=[i for i,x in enumerate(original) if int(x.get('id') or 0)==old]
        if len(positions)!=1:raise RuntimeError(f'TERMINAL: source occurrence={len(positions)}')
        pos=positions[0];primary=pos==0;row.update({'position':pos,'primary':primary})
        ic,obj=inspect(old);before=obj.get('before') if isinstance(obj,dict) else None
        if not (200<=ic<300 and isinstance(before,dict)):raise RuntimeError('source inspect failed')
        mime=str(before.get('mime_type') or '').lower();src=str(before.get('url') or '')
        if mime not in ('image/jpeg','image/png') or not src:raise RuntimeError(f'TERMINAL: source mime={mime}')
        raw=getbytes(src);d,w,h,ps,mode,exact,saving=encode(raw,mime);alt=str(original[pos].get('alt') or p.get('name') or '')
        row.update({'source_url':src,'original_bytes':len(raw),'webp_bytes_local':len(d),'saving_pct':saving,'psnr_db':ps,'pixel_exact':exact,'encoder_mode':mode,'width':w,'height':h,'alt_before':alt})
        new_id,new_url=upload(f'k20-p{pid}-a{old}-rest-rescue.webp',d)
        if new_id<=0 or not new_url:raise RuntimeError('invalid REST media upload')
        row.update({'new_attachment_id':new_id,'new_url':new_url})
        nc,no=inspect(new_id);nb=no.get('before') if isinstance(no,dict) else None
        if not (200<=nc<300 and isinstance(nb,dict) and str(nb.get('mime_type') or '').lower()=='image/webp'):raise RuntimeError('new media inspect failed')
        if int(nb.get('width') or 0)!=w or int(nb.get('height') or 0)!=h:raise RuntimeError('dimension mismatch')
        hd=head(new_url);row['new_head']=hd
        if not (200<=hd['status']<400 and 'image/webp' in hd['content_type'].lower()):raise RuntimeError('public WebP verification failed')
        if alt:
            ac,_=api('POST',f'{base}/wp-json/wp/v2/media/{new_id}',{'alt_text':alt});row['alt_update_http']=ac
            if not (200<=ac<300):raise RuntimeError('ALT update failed')
        attempted=True
        if primary:
            uc,_=api('POST',f'{base}/wp-json/wp/v2/product/{pid}',{'featured_media':new_id});row['wp_featured_update_http']=uc
            if not (200<=uc<300):raise RuntimeError(f'WP product featured update failed http={uc}')
        else:
            payload=[{'id':new_id,'alt':alt} if i==pos else {'id':int(x.get('id') or 0)} for i,x in enumerate(original)];uc,_=api('PUT',f'{base}/wp-json/wc/v3/products/{pid}',{'images':payload});row['woo_gallery_update_http']=uc
            if not (200<=uc<300):raise RuntimeError(f'Woo gallery update failed http={uc}')
        good=False
        for a in range(1,4):
            if a>1:time.sleep(2)
            rc,rb=api('GET',f'{base}/wp-json/wc/v3/products/{pid}');imgs=list(rb.get('images') or []) if 200<=rc<300 else []
            if pos<len(imgs) and int(imgs[pos].get('id') or 0)==new_id:
                if primary:
                    wc,wo=api('GET',f'{base}/wp-json/wp/v2/product/{pid}?context=edit&_fields=id,featured_media');row['wp_readback_http']=wc
                    if not (200<=wc<300 and int(wo.get('featured_media') or 0)==new_id):continue
                row.update({'readback_attempts':a,'readback_image_id':new_id,'readback_src':str(imgs[pos].get('src') or '')});good=True;break
        if not good:raise RuntimeError('product readback did not confirm REST rescue')
        row.update({'success':True,'stage':'verified'});return row,False
    except Exception as e:
        msg=str(e);row.update({'stage':'error','error':msg,'terminal':msg.startswith('TERMINAL:')});rollback=True
        if attempted and original:
            try:
                if primary:rc,_=api('POST',f'{base}/wp-json/wp/v2/product/{pid}',{'featured_media':old})
                else:rc,_=api('PUT',f'{base}/wp-json/wc/v3/products/{pid}',{'images':[{'id':int(x.get('id') or 0)} for x in original]})
                rollback=200<=rc<300;row['rollback_http']=rc
            except Exception as re:rollback=False;row['rollback_error']=str(re)
        cleanup=True
        if new_id:
            try:cleanup=delete(new_id);row['cleanup_uploaded_webp']=cleanup
            except Exception:cleanup=False;row['cleanup_uploaded_webp']=False
        return row,(not rollback or not cleanup)

# Only rescue source autopilot entries that were exhausted, never quality-terminal items.
candidates=[]
for key,meta in (source.get('terminal_skips') or {}).items():
    if not str((meta or {}).get('reason') or '').startswith('max_attempts_exhausted:'):continue
    if key in state['processed'] or key in state['skipped']:continue
    try:pid,aid=[int(x) for x in key.split(':',1)]
    except Exception:continue
    candidates.append((pid,aid,key))
candidates.sort()
selected=candidates[:batch];rows=[];critical=False
for pid,aid,key in selected:
    row,bad=migrate(pid,aid);rows.append(row)
    if row.get('success'):state['processed'][key]={'new_attachment_id':row.get('new_attachment_id'),'at_utc':now()};state['successful_migrations']+=1
    else:
        attempts=int((state.get('attempts') or {}).get(key,0))+1;state.setdefault('attempts',{})[key]=attempts
        if row.get('terminal') or attempts>=max_attempts:state['skipped'][key]={'reason':row.get('error'),'attempts':attempts,'at_utc':now()}
    if bad:state['critical_events'].append({'key':key,'error':row.get('error'),'at_utc':now()});state['status']='halted';critical=True;break
state['cycles']+=1;state['updated_at_utc']=now();remaining=[k for _,_,k in candidates if k not in state['processed'] and k not in state['skipped']]
if not critical:state['status']='running' if remaining else 'completed'
state['last_cycle']={'run_id':run_id,'selected':len(selected),'success':sum(1 for r in rows if r.get('success')),'remaining':len(remaining),'at_utc':now()}
OUT.mkdir(parents=True,exist_ok=True);save(OUT/f'{run_id}.json',{'action':'product.rest_rescue_cycle','run_id':run_id,'executed_at_utc':now(),'items':rows,'success_count':sum(1 for r in rows if r.get('success')),'critical_halt':critical});save(STATE,state)
print(json.dumps({'status':state['status'],'selected':len(selected),'success':sum(1 for r in rows if r.get('success')),'remaining':len(remaining)},ensure_ascii=False))
if critical:raise SystemExit(2)
