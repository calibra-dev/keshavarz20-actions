import base64
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
PLAN = ROOT / 'gallery-meta-rescue' / 'apply-plan.json'
OUT = ROOT / 'gallery-meta-rescue' / 'woo-verified.json'
for key in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(key,'').strip():
        raise SystemExit(f'Missing secret {key}')
base=os.environ['WP_BASE_URL'].rstrip('/')
auth=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def qurl(url):
    p=urllib.parse.urlsplit(str(url)); return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/%'),p.query,p.fragment))
def get(url):
    req=urllib.request.Request(qurl(url),headers={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Gallery-Final-Verify/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r: return int(r.status),json.loads(r.read().decode('utf-8','replace'))
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:500]}
        return int(e.code),o
plan=json.loads(PLAN.read_text(encoding='utf-8'))
rows=[]
for row in plan.get('products') or []:
    pid=int(row['product_id']); expected=[int(x) for x in row['expected_woo_images_after']]
    code,obj=get(f'{base}/wp-json/wc/v3/products/{pid}?_fields=id,status,images')
    live=[int(x.get('id') or 0) for x in (obj.get('images') or [])] if isinstance(obj,dict) else []
    replacements=row.get('replacements') or []
    olds=[int(x['old_attachment_id']) for x in replacements]; news=[int(x['new_attachment_id']) for x in replacements]
    ok=200<=code<300 and str(obj.get('status') or '')=='publish' and live==expected and all(x not in live for x in olds) and all(x in live for x in news)
    rows.append({'product_id':pid,'http':code,'expected':expected,'live':live,'old_ids':olds,'new_ids':news,'woo_readback_ok':ok,'old_absent':all(x not in live for x in olds),'new_present':all(x in live for x in news)})
result={'executed_at_utc':now(),'action':'gallery_meta_rescue.final_woo_verify','read_only':True,'items':rows,'all_ok':bool(rows) and all(x['woo_readback_ok'] for x in rows)}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'products':len(rows),'all_ok':result['all_ok']},ensure_ascii=False))
if not result['all_ok']: raise SystemExit(2)
