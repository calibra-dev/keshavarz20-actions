import base64, hashlib, json, os, pathlib, sys, urllib.request, urllib.parse, xmlrpc.client, time

REQ=pathlib.Path(sys.argv[1]); OUT=pathlib.Path(sys.argv[2])
req=json.loads(REQ.read_text(encoding='utf-8'))
page_id=int(req.get('id',0)); mode=str(req.get('mode','inspect'))
if page_id!=13: raise SystemExit('hard-limited to page ID 13')
base=os.environ['WP_BASE_URL'].rstrip('/'); user=os.environ['WP_USERNAME']; pw=os.environ['WP_APP_PASSWORD']
server=xmlrpc.client.ServerProxy(base+'/xmlrpc.php',allow_none=True,use_builtin_types=True)

def sha(s): return hashlib.sha256((s or '').encode('utf-8')).hexdigest()
def auth_get(url):
    tok=base64.b64encode(f'{user}:{pw}'.encode()).decode()
    r=urllib.request.Request(url,headers={'Authorization':'Basic '+tok,'Accept':'application/json','User-Agent':'K20-Elementor-Recovery/1.0'})
    with urllib.request.urlopen(r,timeout=180) as x: return json.loads(x.read().decode('utf-8','replace'))
def fetch_public(url):
    r=urllib.request.Request(url,headers={'Cache-Control':'no-cache','Pragma':'no-cache','User-Agent':'K20-Elementor-Recovery/1.0'})
    try:
        with urllib.request.urlopen(r,timeout=180) as x: return int(x.status),x.read().decode('utf-8','replace')
    except Exception as e:
        if hasattr(e,'code'): return int(e.code), e.read().decode('utf-8','replace')
        return 0,''

post=server.wp.getPost(0,user,pw,page_id,['post_id','post_title','post_status','custom_fields'])
fields=list(post.get('custom_fields') or [])
hits=[f for f in fields if str(f.get('key',''))=='_elementor_data']
result={'ok':True,'mode':mode,'page_id':page_id,'elementor_fields':len(hits),'before':[]}
for f in hits:
    val=str(f.get('value') or '')
    result['before'].append({'meta_id':int(f.get('id') or 0),'length':len(val),'sha256':sha(val)})

if mode=='restore':
    if len(hits)!=1: raise SystemExit(f'expected exactly one _elementor_data field, found {len(hits)}')
    revision_id=int(req.get('revision_id',0)); expected=str(req.get('expected_elementor_sha256',''))
    if revision_id!=144349 or expected!='5045936e3ba36035b68ec5a12ac001aad32abfcc51876edb22fdbff7dd8f9396': raise SystemExit('restore source guard failed')
    rev=auth_get(f'{base}/wp-json/wp/v2/pages/{page_id}/revisions/{revision_id}?context=edit')
    raw=str((rev.get('meta') or {}).get('_elementor_data') or '')
    if sha(raw)!=expected: raise SystemExit('revision hash mismatch')
    meta_id=int(hits[0].get('id') or 0)
    if meta_id<=0: raise SystemExit('invalid meta id')
    edited=server.wp.editPost(0,user,pw,page_id,{'custom_fields':[{'id':meta_id,'key':'_elementor_data','value':raw}]})
    if not edited: raise SystemExit('wp.editPost returned false')
    post2=server.wp.getPost(0,user,pw,page_id,['custom_fields'])
    hits2=[f for f in list(post2.get('custom_fields') or []) if str(f.get('key',''))=='_elementor_data']
    if len(hits2)!=1: raise SystemExit('readback field count mismatch')
    stored=str(hits2[0].get('value') or '')
    if sha(stored)!=expected: raise SystemExit(f'readback hash mismatch {sha(stored)}')
    result['restore']={'revision_id':revision_id,'meta_id':meta_id,'edited':bool(edited),'readback_sha256':sha(stored),'readback_length':len(stored)}
    time.sleep(2)
    status,html=fetch_public(base+'/refund_returns/?k20xmlrpcrecovery='+str(int(time.time()*1000)))
    result['live']={'http_status':status,'html_bytes':len(html.encode('utf-8'))}

OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('XMLRPC_ELEMENTOR_RECOVERY_OK',json.dumps({'mode':mode,'fields':len(hits),'live':result.get('live')},ensure_ascii=False))
