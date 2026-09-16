import base64, json, os, pathlib, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT=pathlib.Path('.')
STATE=ROOT/'media-rest-rescue/state.json'
OUT=ROOT/'media-rest-rescue/skipped-diagnostic.json'

def load(p): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
for k in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(k,'').strip(): raise SystemExit(f'Missing secret {k}')
base=os.environ['WP_BASE_URL'].rstrip('/'); auth=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()

def qurl(u):
    p=urllib.parse.urlsplit(str(u)); return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/%'),p.query,p.fragment))
def get(url,timeout=120):
    req=urllib.request.Request(qurl(url),headers={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-REST-Rescue-Diagnostic/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read().decode('utf-8','replace'); return int(r.status),json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:o=json.loads(raw)
        except Exception:o={'raw':raw[:600]}
        return int(e.code),o
state=load(STATE); skipped=state.get('skipped') or {}; rows=[]
for key,meta in sorted(skipped.items()):
    try: pid,old=[int(x) for x in key.split(':',1)]
    except Exception: continue
    wc,p=get(f'{base}/wp-json/wc/v3/products/{pid}?_fields=id,name,slug,status,permalink,images')
    images=list(p.get('images') or []) if 200<=wc<300 and isinstance(p,dict) else []
    ids=[int(x.get('id') or 0) for x in images]
    positions=[i for i,x in enumerate(ids) if x==old]
    wp,po=get(f'{base}/wp-json/wp/v2/product/{pid}?context=edit&_fields=id,status,slug,featured_media')
    mc,m=get(f'{base}/wp-json/wp/v2/media/{old}?context=edit&_fields=id,parent,source_url,mime_type,media_details')
    rows.append({
      'key':key,'product_id':pid,'old_attachment_id':old,'skip_reason':str((meta or {}).get('reason') or ''),'skip_attempts':int((meta or {}).get('attempts') or 0),
      'woo_http':wc,'product_name':str(p.get('name') or '') if isinstance(p,dict) else '', 'product_slug':str(p.get('slug') or '') if isinstance(p,dict) else '', 'product_status':str(p.get('status') or '') if isinstance(p,dict) else '',
      'image_ids':ids,'old_occurrences':len(positions),'old_positions':positions,'primary_is_old':bool(ids and ids[0]==old),
      'wp_product_http':wp,'wp_featured_media':int(po.get('featured_media') or 0) if isinstance(po,dict) else 0,'wp_status':str(po.get('status') or '') if isinstance(po,dict) else '',
      'media_http':mc,'media_parent':int(m.get('parent') or 0) if isinstance(m,dict) else 0,'media_mime':str(m.get('mime_type') or '') if isinstance(m,dict) else '', 'media_url':str(m.get('source_url') or '') if isinstance(m,dict) else '',
    })
summary={
  'executed_at_utc':now(),'skipped_count':len(rows),
  'old_still_referenced_once':sum(r['old_occurrences']==1 for r in rows),
  'old_not_current':sum(r['old_occurrences']==0 for r in rows),
  'duplicate_old_reference':sum(r['old_occurrences']>1 for r in rows),
  'primary_cases':sum(r['primary_is_old'] for r in rows),
  'gallery_cases':sum((r['old_occurrences']==1 and not r['primary_is_old']) for r in rows),
  'trash_or_nonpublish':sum(r['product_status']!='publish' for r in rows),
}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({'summary':summary,'items':rows},ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False))
