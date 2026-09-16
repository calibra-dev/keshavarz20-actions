import base64
import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT=pathlib.Path('.')
STATE=ROOT/'media-rest-rescue'/'state.json'
OUT=ROOT/'media-rest-rescue'/'gallery-rest-bridge-probe.json'
for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(key,'').strip(): raise SystemExit(f'Missing secret {key}')
base=os.environ['WP_BASE_URL'].rstrip('/'); auth=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode(); bridge=base+'/wp-json/keshavarz20-ops/v2/execute'
state=json.loads(STATE.read_text(encoding='utf-8'))

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def api(method,url,body=None):
    headers={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Gallery-REST-Bridge-Probe/1.0'}; data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode(); headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(url,data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            raw=r.read().decode('utf-8','replace'); return int(r.status),json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:500]}
        return int(e.code),o
rows=[]
for key,meta in sorted((state.get('skipped') or {}).items()):
    if str((meta or {}).get('reason') or '')!='product readback did not confirm REST rescue': continue
    pid,old=[int(x) for x in key.split(':',1)]
    row={'key':key,'product_id':pid,'old_attachment_id':old,'read_only':True}
    code,obj=api('GET',f'{base}/wp-json/wp/v2/product/{pid}?context=edit&_fields=id,status,featured_media,meta')
    row['wp_rest_http']=code
    if isinstance(obj,dict):
        m=obj.get('meta') if isinstance(obj.get('meta'),dict) else {}
        row['wp_rest_meta_keys']=sorted(m.keys())
        row['wp_rest_gallery_present']='_product_image_gallery' in m
        if '_product_image_gallery' in m: row['wp_rest_gallery_value']=m.get('_product_image_gallery')
        row['wp_rest_featured_media']=int(obj.get('featured_media') or 0)
    bc,bo=api('POST',bridge,{'mode':'inspect','resource':'product','id':pid,'changes':{}})
    row['bridge_http']=bc
    before=bo.get('before') if isinstance(bo,dict) and isinstance(bo.get('before'),dict) else {}
    row['bridge_ok']=bool(isinstance(bo,dict) and bo.get('ok') is True)
    row['bridge_before_keys']=sorted(before.keys())
    gallery_candidates={}
    for k,v in before.items():
        lk=str(k).lower()
        if 'gallery' in lk or 'image' in lk or 'thumbnail' in lk:
            if isinstance(v,(str,int,float,bool,type(None))): gallery_candidates[str(k)]=v
            elif isinstance(v,list): gallery_candidates[str(k)]=v[:20]
    row['bridge_gallery_candidates']=gallery_candidates
    rows.append(row)
result={'executed_at_utc':now(),'action':'media.gallery_rest_bridge_meta_probe','read_only':True,'items':rows}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'items':len(rows),'rest_gallery_present':sum(1 for x in rows if x.get('wp_rest_gallery_present')),'bridge_ok':sum(1 for x in rows if x.get('bridge_ok'))},ensure_ascii=False))
