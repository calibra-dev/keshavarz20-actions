import base64, io, json, os, pathlib, subprocess, urllib.request, urllib.error
from PIL import Image, ImageOps
ROOT=pathlib.Path('.')
OPS=ROOT/'content-webp-probe-ops'; OUT=ROOT/'content-webp-probe-results'
base=os.environ['WP_BASE_URL'].rstrip('/'); user=os.environ['WP_USERNAME']; pw=os.environ['WP_APP_PASSWORD']
auth=base64.b64encode(f'{user}:{pw}'.encode()).decode()
def req(method,url,data=None,headers=None):
    h={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-WebP-Probe/1.0'}
    if headers:h.update(headers)
    r=urllib.request.Request(url,data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(r,timeout=180) as x:
            raw=x.read();
            try:o=json.loads(raw.decode() or '{}')
            except:o={'raw':raw[:200].decode('utf-8','replace')}
            return x.status,o
    except urllib.error.HTTPError as e:
        raw=e.read();
        try:o=json.loads(raw.decode() or '{}')
        except:o={'raw':raw[:200].decode('utf-8','replace')}
        return e.code,o
def getb(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'K20-WebP-Probe/1.0'}),timeout=180) as r:return r.read()
def changed():
    p=subprocess.check_output(['git','show','--pretty=','--name-only','HEAD','--','content-webp-probe-ops'],text=True).strip().splitlines()
    p=[x for x in p if x.startswith('content-webp-probe-ops/') and x.endswith('.json')]
    if len(p)!=1: raise SystemExit(f'expected one probe request, got {len(p)}')
    return pathlib.Path(p[0])
op=changed(); spec=json.loads(op.read_text()); ids=[int(x) for x in spec.get('ids',[])]
OUT.mkdir(exist_ok=True); result={'action':'webp.upload_probe','request_file':op.name,'items':[]}
for aid in ids:
    item={'source_id':aid}; new_id=0
    try:
        c,m=req('GET',f'{base}/wp-json/wp/v2/media/{aid}?context=edit&_fields=id,source_url,mime_type,media_details')
        item['source_http']=c; item['source_url']=m.get('source_url'); item['source_media_details']=m.get('media_details'); item['source_mime']=m.get('mime_type')
        raw=getb(item['source_url']); im=ImageOps.exif_transpose(Image.open(io.BytesIO(raw))); im.load()
        buf=io.BytesIO(); kwargs={'format':'WEBP','lossless':True,'method':6}
        if im.info.get('icc_profile'): kwargs['icc_profile']=im.info['icc_profile']
        if im.info.get('exif'): kwargs['exif']=im.info['exif']
        im.save(buf,**kwargs); data=buf.getvalue(); item['encoded_bytes']=len(data); item['encoded_size']=list(im.size)
        c,u=req('POST',base+'/wp-json/wp/v2/media',data,{'Content-Type':'image/webp','Content-Disposition':f'attachment; filename="k20-probe-a{aid}.webp"'})
        item['upload_http']=c; item['upload_response_id']=u.get('id'); item['upload_response_url']=u.get('source_url'); new_id=int(u.get('id') or 0)
        if new_id:
            c,v=req('GET',f'{base}/wp-json/wp/v2/media/{new_id}?context=edit&_fields=id,source_url,mime_type,media_details')
            item['verify_http']=c; item['verify_mime']=v.get('mime_type'); item['verify_url']=v.get('source_url'); item['verify_media_details']=v.get('media_details')
    except Exception as e:item['error']=str(e)
    finally:
        if new_id:
            c,d=req('DELETE',f'{base}/wp-json/wp/v2/media/{new_id}?force=true'); item['cleanup_http']=c; item['cleanup_deleted']=bool(d.get('deleted')) if isinstance(d,dict) else False
            c,_=req('GET',f'{base}/wp-json/wp/v2/media/{new_id}'); item['cleanup_readback_http']=c
    result['items'].append(item)
(OUT/op.name).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
