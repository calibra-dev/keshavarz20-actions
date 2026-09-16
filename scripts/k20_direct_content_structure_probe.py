import base64
import json
import os
import pathlib
import re
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
DIRECT = ROOT / 'content-media-results' / 'direct-probe.json'
OUT = ROOT / 'content-media-results' / 'direct-structure-probe.json'

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required secret: {key}')
base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
direct = json.loads(DIRECT.read_text(encoding='utf-8'))


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def get_post(pid):
    url = f'{base}/wp-json/wp/v2/posts/{pid}?context=edit&_fields=id,status,link,content,meta'
    req = urllib.request.Request(url, headers={'Authorization':'Basic '+auth,'Accept':'application/json','User-Agent':'K20-Direct-Structure-Probe/1.0'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode('utf-8','replace'))


def clean_snip(text, start, end, radius=100):
    lo=max(0,start-radius); hi=min(len(text),end+radius)
    s=text[lo:hi].replace('\n',' ').replace('\r',' ')
    s=re.sub(r'\s+',' ',s)
    return s[:400]


def raw_hits(text, aid, url):
    pats=[
        ('wp_image_class', re.compile(rf'wp-image-{aid}(?!\d)', re.I)),
        ('json_id', re.compile(rf'(["\']id["\']\s*[:=]\s*["\']?){aid}(?!\d)', re.I)),
        ('attachment_id', re.compile(rf'(["\'](?:attachment_id|image_id)["\']\s*[:=]\s*["\']?){aid}(?!\d)', re.I)),
        ('bare_id', re.compile(rf'(?<!\d){aid}(?!\d)')),
    ]
    if url:
        pats.insert(0, ('exact_url', re.compile(re.escape(url), re.I)))
    found=[]; seen=set()
    for kind,pat in pats:
        for m in pat.finditer(text):
            key=(m.start(),m.end())
            if key in seen: continue
            seen.add(key)
            found.append({'kind':kind,'start':m.start(),'end':m.end(),'snippet':clean_snip(text,m.start(),m.end())})
    return sorted(found,key=lambda x:(x['start'],x['kind']))


def walk(obj, aid, url, path='$'):
    hits=[]
    if isinstance(obj, dict):
        for k,v in obj.items(): hits.extend(walk(v,aid,url,f'{path}.{k}'))
    elif isinstance(obj, list):
        for i,v in enumerate(obj): hits.extend(walk(v,aid,url,f'{path}[{i}]'))
    elif isinstance(obj, int) and obj==aid:
        hits.append({'path':path,'match':'exact_int_id','value':obj})
    elif isinstance(obj, str):
        if obj==str(aid): hits.append({'path':path,'match':'exact_string_id','value':obj})
        if url and obj==url: hits.append({'path':path,'match':'exact_url','value':obj})
        elif url and url in obj: hits.append({'path':path,'match':'url_inside_string','value':obj[:500]})
    return hits

post_cache={}
rows=[]
for item in direct.get('items') or []:
    aid=int(item.get('attachment_id') or 0); pid=int(item.get('post_id') or 0); src=str(item.get('source_url') or '')
    if pid not in post_cache: post_cache[pid]=get_post(pid)
    post=post_cache[pid]; content=post.get('content') or {}; raw=str(content.get('raw') or '') if isinstance(content,dict) else ''
    meta=post.get('meta') or {}; elem=meta.get('_elementor_data') if isinstance(meta,dict) else None
    elem_obj=None
    if isinstance(elem,(dict,list)): elem_obj=elem
    elif isinstance(elem,str) and elem:
        try: elem_obj=json.loads(elem)
        except Exception: elem_obj=None
    rows.append({
        'attachment_id':aid,'post_id':pid,'source_url':src,
        'raw_hits':raw_hits(raw,aid,src),
        'elementor_hits':walk(elem_obj,aid,src) if elem_obj is not None else [],
        'elementor_value_type':type(elem).__name__,
        'elementor_json_valid':elem_obj is not None,
    })
result={'executed_at_utc':now(),'action':'content_media.direct_structure_probe','read_only':True,'items':rows}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'items':len(rows),'raw_hits':sum(len(x['raw_hits']) for x in rows),'elementor_hits':sum(len(x['elementor_hits']) for x in rows)},ensure_ascii=False))
