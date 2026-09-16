import base64
import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT=pathlib.Path('.')
STATE=ROOT/'media-rest-rescue'/'state.json'
OUT=ROOT/'media-rest-rescue'/'gallery-woo-meta-probe.json'
for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(key,'').strip(): raise SystemExit(f'Missing secret {key}')
base=os.environ['WP_BASE_URL'].rstrip('/'); auth=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode(); state=json.loads(STATE.read_text(encoding='utf-8'))

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def get(url):
    req=urllib.request.Request(url,headers={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Gallery-Woo-Meta-Probe/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:return int(r.status),json.loads(r.read().decode('utf-8','replace'))
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:500]}
        return int(e.code),o
rows=[]
for key,meta in sorted((state.get('skipped') or {}).items()):
    if str((meta or {}).get('reason') or '')!='product readback did not confirm REST rescue': continue
    pid,old=[int(x) for x in key.split(':',1)]
    code,obj=get(f'{base}/wp-json/wc/v3/products/{pid}?_fields=id,status,images,meta_data')
    md=obj.get('meta_data') or [] if isinstance(obj,dict) else []
    gallery=[]
    for item in md:
        if not isinstance(item,dict): continue
        k=str(item.get('key') or '')
        if 'gallery' in k.lower() or k=='_product_image_gallery':
            gallery.append({'id':int(item.get('id') or 0),'key':k,'value':item.get('value')})
    rows.append({'key':key,'product_id':pid,'old_attachment_id':old,'http':code,'woo_image_ids':[int(x.get('id') or 0) for x in (obj.get('images') or [])] if isinstance(obj,dict) else [],'meta_data_count':len(md),'gallery_meta':gallery,'gallery_meta_present':bool(gallery)})
result={'executed_at_utc':now(),'action':'media.gallery_woo_meta_probe','read_only':True,'items':rows,'gallery_meta_present_count':sum(1 for x in rows if x['gallery_meta_present'])}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'items':len(rows),'gallery_meta_present_count':result['gallery_meta_present_count']},ensure_ascii=False))
