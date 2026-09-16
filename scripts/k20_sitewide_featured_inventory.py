import base64, json, os, pathlib, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

for k in ('WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'):
    if not os.environ.get(k,'').strip(): raise SystemExit(f'Missing secret {k}')
base=os.environ['WP_BASE_URL'].rstrip('/'); user=os.environ['WP_USERNAME']; pw=os.environ['WP_APP_PASSWORD']; auth=base64.b64encode(f'{user}:{pw}'.encode()).decode()
out=pathlib.Path('sitewide-media-results/inventory-phase1.json')

def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def get(path,params=None):
    url=base+path
    if params:url+='?'+urllib.parse.urlencode(params,doseq=True)
    req=urllib.request.Request(url,headers={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Featured-Inventory/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            raw=r.read().decode('utf-8','replace');
            try:obj=json.loads(raw) if raw else {}
            except Exception:obj={'_non_json':True}
            return int(r.status),obj,dict(r.headers)
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:obj=json.loads(raw)
        except Exception:obj={'raw':raw[:300]}
        return int(e.code),obj,dict(e.headers)

def ext(url):
    p=urllib.parse.urlsplit(str(url)).path.lower()
    if p.endswith(('.jpg','.jpeg')):return 'jpeg'
    if p.endswith('.png'):return 'png'
    if p.endswith('.webp'):return 'webp'
    return ''
media={}
for page in range(1,101):
    c,d,h=get('/wp-json/wp/v2/media',{'per_page':100,'page':page,'media_type':'image','_fields':'id,parent,source_url,alt_text'})
    if c==400 and page>1:break
    if not (200<=c<300) or not isinstance(d,list):raise SystemExit(f'media read failed page={page} http={c}')
    if not d:break
    for x in d:
        aid=int(x.get('id') or 0); url=str(x.get('source_url') or ''); f=ext(url)
        if aid>0 and f:media[aid]={'attachment_id':aid,'parent':int(x.get('parent') or 0),'url':url,'format':f,'alt_text':str(x.get('alt_text') or '')}
    tp=int(h.get('X-WP-TotalPages') or h.get('x-wp-totalpages') or 0)
    if (tp and page>=tp) or len(d)<100:break
refs=defaultdict(list)
def add(aid,kind,oid,otype,field,locator=''):
    try:aid=int(aid or 0)
    except Exception:return
    if aid not in media:return
    r={'kind':kind,'object_id':int(oid or 0),'object_type':otype,'field':field,'locator':locator}
    if r not in refs[aid]:refs[aid].append(r)
# Standard live content types. Products are handled by the separate product autopilot.
post_stats={}
for typ,route in (('post','/wp-json/wp/v2/posts'),('page','/wp-json/wp/v2/pages')):
    count=0
    for page in range(1,101):
        c,d,h=get(route,{'per_page':100,'page':page,'context':'edit','status':'any','_fields':'id,featured_media,link'})
        if c in (401,403) and page==1:c,d,h=get(route,{'per_page':100,'page':page,'context':'view','_fields':'id,featured_media,link'})
        if c==400 and page>1:break
        if not (200<=c<300) or not isinstance(d,list):break
        if not d:break
        count+=len(d)
        for x in d:add(x.get('featured_media'),'featured_image',x.get('id'),typ,'featured_media',str(x.get('link') or ''))
        tp=int(h.get('X-WP-TotalPages') or h.get('x-wp-totalpages') or 0)
        if (tp and page>=tp) or len(d)<100:break
    post_stats[typ]=count
# Mark all Woo product image attachments so phase1 never touches them.
products=0
for page in range(1,51):
    c,d,h=get('/wp-json/wc/v3/products',{'per_page':100,'page':page,'status':'any','orderby':'id','order':'asc','_fields':'id,images,permalink'})
    if c==400 and page>1:break
    if not (200<=c<300) or not isinstance(d,list):break
    if not d:break
    products+=len(d)
    for p in d:
        for pos,img in enumerate(p.get('images') or []):add(img.get('id'),'woo_product_image',p.get('id'),'product',f'images[{pos}]',str(p.get('permalink') or ''))
    tp=int(h.get('X-WP-TotalPages') or h.get('x-wp-totalpages') or 0)
    if (tp and page>=tp) or len(d)<100:break
# Product-category images.
categories=0
for page in range(1,21):
    c,d,h=get('/wp-json/wc/v3/products/categories',{'per_page':100,'page':page,'orderby':'id','order':'asc','_fields':'id,image'})
    if c==400 and page>1:break
    if not (200<=c<300) or not isinstance(d,list):break
    if not d:break
    categories+=len(d)
    for t in d:add((t.get('image') or {}).get('id'),'woo_category_image',t.get('id'),'product_cat','image')
    tp=int(h.get('X-WP-TotalPages') or h.get('x-wp-totalpages') or 0)
    if (tp and page>=tp) or len(d)<100:break
items=[]
for aid,m in sorted(media.items()):
    rs=refs.get(aid,[]); items.append({**m,'reference_count':len(rs),'references':rs})
eligible=0
for x in items:
    kinds={r['kind'] for r in x['references']}
    if x['format'] in ('jpeg','png') and kinds and 'woo_product_image' not in kinds and (kinds-{'featured_image','woo_category_image'})==set():eligible+=1
summary={'executed_at_utc':now(),'image_attachments':len(items),'jpeg':sum(x['format']=='jpeg' for x in items),'png':sum(x['format']=='png' for x in items),'webp':sum(x['format']=='webp' for x in items),'posts_read':post_stats.get('post',0),'pages_read':post_stats.get('page',0),'products_read':products,'product_categories_read':categories,'phase1_eligible_attachments':eligible}
out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({'summary':summary,'items':items,'phase':'featured_and_category_only'},ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False))
