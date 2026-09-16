import base64
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('.')
OPS = ROOT / 'home-contextual-reuse-v2-ops'
OUTDIR = ROOT / 'home-contextual-reuse-results'
PAGE_ID = 644
PLAN = [
    {'old_id': 139388, 'product_id': 140545, 'new_id': 144642},
    {'old_id': 140408, 'product_id': 140406, 'new_id': 144585},
    {'old_id': 140408, 'product_id': 140407, 'new_id': 144586},
    {'old_id': 140629, 'product_id': 140628, 'new_id': 144678},
    {'old_id': 140629, 'product_id': 140630, 'new_id': 144679},
    {'old_id': 140629, 'product_id': 140631, 'new_id': 144680},
    {'old_id': 142972, 'product_id': 142971, 'new_id': 145073},
]

for key in ('WP_BASE_URL', 'WP_USERNAME', 'WP_APP_PASSWORD'):
    if not os.environ.get(key, '').strip():
        raise SystemExit(f'Missing required repository secret: {key}')
base = os.environ['WP_BASE_URL'].rstrip('/')
auth = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def qurl(url):
    p = urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path), safe='/%'), p.query, p.fragment))


def api(method, path, body=None, timeout=120):
    url = path if str(path).startswith('http') else base + path
    headers = {'Authorization': 'Basic ' + auth, 'Accept': 'application/json', 'User-Agent': 'K20-Home-Contextual-Reuse/2.0'}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(qurl(url), data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            return int(r.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try: obj = json.loads(raw)
        except Exception: obj = {'raw': raw[:500]}
        return int(e.code), obj


def public_get(url):
    req = urllib.request.Request(qurl(url), headers={'User-Agent':'K20-Home-Contextual-Reuse/2.0','Cache-Control':'no-cache','Pragma':'no-cache'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return int(r.status), r.read().decode('utf-8', 'replace')
    except Exception:
        return 0, ''


def upload_key(url):
    try: path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path)
    except Exception: return ''
    marker = '/wp-content/uploads/'
    pos = path.find(marker)
    return path[pos + len(marker):].lstrip('/') if pos >= 0 else ''


def canonical_key(url):
    key = upload_key(url)
    head, sep, name = key.rpartition('/')
    stem, dot, ext = name.rpartition('.')
    if not dot: return key
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    stem = re.sub(r'-scaled$', '', stem)
    clean = stem + '.' + ext.lower()
    return head + '/' + clean if sep else clean


UPLOAD_RE = re.compile(r'(?:https?:)?//[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*\.(?:jpe?g|png|webp)', re.I)


def has_family(text, url):
    target = canonical_key(url)
    return bool(target and any(canonical_key(m.group(0)) == target for m in UPLOAD_RE.finditer(text or '')))


def card_match(text, permalink):
    pattern = re.compile(r'<a\b[^>]*href=["\']' + re.escape(permalink) + r'["\'][^>]*>(.*?)</a>', re.I | re.S)
    matches = list(pattern.finditer(text or ''))
    return matches[0] if len(matches) == 1 else None


def changed_request():
    for cmd in (
        ['git','diff-tree','--no-commit-id','--name-only','-r','HEAD','--','home-contextual-reuse-v2-ops'],
        ['git','show','--pretty=','--name-only','HEAD','--','home-contextual-reuse-v2-ops'],
    ):
        try: paths=[x.strip() for x in subprocess.check_output(cmd,text=True).splitlines() if x.strip().startswith('home-contextual-reuse-v2-ops/') and x.strip().endswith('.json')]
        except Exception: paths=[]
        if paths:
            if len(paths)!=1: raise SystemExit(f'Expected one request, found {len(paths)}')
            return pathlib.Path(paths[0])
    raise SystemExit('No contextual v2 request found')

request_path = changed_request()
request = json.loads(request_path.read_text(encoding='utf-8'))
if request.get('action') != 'content_media.home_contextual_reuse_v2' or int(request.get('page_id') or 0) != PAGE_ID:
    raise SystemExit('Unsupported request')

pc, page = api('GET', f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,status,link,content')
if not (200 <= pc < 300 and isinstance(page, dict) and str(page.get('status') or '') == 'publish'):
    raise SystemExit(f'page precondition failed http={pc}')
original_raw = (page.get('content') or {}).get('raw') if isinstance(page.get('content'), dict) else ''
if not isinstance(original_raw, str) or not original_raw: raise SystemExit('home raw unavailable')
link = str(page.get('link') or base + '/')

items=[]; new_raw=original_raw
for row in PLAN:
    old_id=int(row['old_id']); pid=int(row['product_id']); new_id=int(row['new_id'])
    oc, om = api('GET', f'/wp-json/wp/v2/media/{old_id}?context=edit&_fields=id,source_url,mime_type')
    nc, nm = api('GET', f'/wp-json/wp/v2/media/{new_id}?context=edit&_fields=id,source_url,mime_type')
    wc, product = api('GET', f'/wp-json/wc/v3/products/{pid}?_fields=id,name,status,permalink,images')
    if not (200 <= oc < 300 and isinstance(om, dict)): raise SystemExit(f'old media read failed {old_id}')
    if not (200 <= nc < 300 and isinstance(nm, dict) and str(nm.get('mime_type') or '').lower()=='image/webp'): raise SystemExit(f'new media invalid {new_id}')
    images=[int(x.get('id') or 0) for x in (product.get('images') or [])] if isinstance(product,dict) else []
    if not (200 <= wc < 300 and str(product.get('status') or '')=='publish' and images and images[0]==new_id): raise SystemExit(f'product image precondition failed {pid}')
    old_url=str(om.get('source_url') or ''); new_url=str(nm.get('source_url') or ''); permalink=str(product.get('permalink') or '')
    pattern=re.compile(r'(<a\b[^>]*href=["\']'+re.escape(permalink)+r'["\'][^>]*>)(.*?)(</a>)',re.I|re.S)
    matches=list(pattern.finditer(new_raw))
    if len(matches)!=1: raise SystemExit(f'raw product card count {pid}={len(matches)}')
    m=matches[0]; inside=m.group(2); im=re.search(r'<img\b[^>]*>',inside,re.I|re.S)
    if not im or not has_family(im.group(0),old_url): raise SystemExit(f'raw card old image precondition failed {pid}')
    tag=im.group(0)
    tag=re.sub(r'\s+srcset=("[^"]*"|\'[^\']*\')','',tag,flags=re.I)
    tag=re.sub(r'\s+sizes=("[^"]*"|\'[^\']*\')','',tag,flags=re.I)
    tag,n=re.subn(r'\bsrc=("[^"]*"|\'[^\']*\')',lambda _:f'src="{new_url}"',tag,count=1,flags=re.I)
    if n!=1: raise SystemExit(f'raw img src replace failed {pid}')
    inside=inside[:im.start()]+tag+inside[im.end():]
    new_raw=new_raw[:m.start()]+m.group(1)+inside+m.group(3)+new_raw[m.end():]
    items.append({'old_attachment_id':old_id,'product_id':pid,'new_attachment_id':new_id,'permalink':permalink,'old_url':old_url,'new_url':new_url})

pre_http, pre_html = public_get(link + ('&' if '?' in link else '?') + f'k20_context_v2_pre={int(time.time())}')
if pre_http != 200: raise SystemExit(f'public pre-read failed http={pre_http}')
for item in items:
    m=card_match(pre_html,item['permalink'])
    card=m.group(1) if m else ''
    item['public_card_present_before']=bool(m)
    item['public_old_before']=has_family(card,item['old_url']) if m else False
    item['public_new_before']=has_family(card,item['new_url']) if m else False

result={'executed_at_utc':now_iso(),'action':request.get('action'),'request_file':request_path.name,'page_id':PAGE_ID,'success':False,'items':items}
wrote=False
try:
    uc,_=api('POST',f'/wp-json/wp/v2/pages/{PAGE_ID}',{'content':new_raw})
    result['update_http']=uc
    if not 200 <= uc < 300: raise RuntimeError(f'page update failed http={uc}')
    wrote=True
    rc,rb=api('GET',f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content')
    rr=(rb.get('content') or {}).get('raw') if isinstance(rb,dict) and isinstance(rb.get('content'),dict) else ''
    if not (200 <= rc < 300 and isinstance(rr,str)): raise RuntimeError('raw readback failed')
    for item in items:
        m=card_match(rr,item['permalink'])
        card=m.group(1) if m else ''
        if not m or not has_family(card,item['new_url']) or has_family(card,item['old_url']): raise RuntimeError(f'raw card readback failed {item["product_id"]}')

    public_ok=False; last={}
    for attempt in range(1,4):
        hc,html=public_get(link+('' if '?' not in link else '&')+('?' if '?' not in link else '')+f'k20_context_v2_verify={int(time.time())}-{attempt}')
        stale=0; required=0; confirmed=0
        if hc==200:
            for item in items:
                m=card_match(html,item['permalink']); card=m.group(1) if m else ''
                if m and has_family(card,item['old_url']): stale+=1
                if item['public_old_before']:
                    required+=1
                    if m and has_family(card,item['new_url']): confirmed+=1
        last={'attempt':attempt,'http':hc,'required_public_changes':required,'confirmed_public_changes':confirmed,'stale_cards':stale}
        if hc==200 and stale==0 and confirmed==required:
            public_ok=True; break
        time.sleep(2)
    result['public_readback']=last
    if not public_ok: raise RuntimeError('public contextual v2 readback failed')
    result['success']=True; result['stage']='verified'
except Exception as error:
    result['stage']='error'; result['error']=str(error); rollback_ok=True
    if wrote:
        bc,_=api('POST',f'/wp-json/wp/v2/pages/{PAGE_ID}',{'content':original_raw}); result['rollback_http']=bc; rollback_ok=200 <= bc < 300
        if rollback_ok:
            vc,vb=api('GET',f'/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content')
            vr=(vb.get('content') or {}).get('raw') if isinstance(vb,dict) and isinstance(vb.get('content'),dict) else None
            rollback_ok=200 <= vc < 300 and vr==original_raw
    result['rollback_ok']=rollback_ok

OUTDIR.mkdir(parents=True,exist_ok=True)
out=OUTDIR/(request_path.stem+'.json'); out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'success':result.get('success'),'stage':result.get('stage'),'items':len(items),'error':result.get('error')},ensure_ascii=False))
if not result.get('success'): raise SystemExit(2)
