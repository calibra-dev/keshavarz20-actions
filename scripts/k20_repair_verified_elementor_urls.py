"""Repair only hash-locked Elementor URLs pointing at 8 already-verified WebPs.

No media upload/deletion, no content/status/commerce writes. All pages are
prepared before mutation; any failure rolls back every attempted page.
"""
import base64
import copy
import hashlib
import html as html_module
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path('media-reconciliation/20260916-content-webp75')
request = json.loads((ROOT / 'repair-request.json').read_text())
allowed_pairs = {143246:145114, 141157:145124, 140164:145122, 141767:145126,
                 141768:145128, 142332:145130, 142637:145132, 141920:145197}
allowed_pages = {128612,128614,140157,141762,142329,143320,143336,143353,143362,644}
assert request['action'] == 'content_media.repair_verified_elementor_urls'
assert len(request['pages']) == 10 and {r['page_id'] for r in request['pages']} == allowed_pages
assert sum(len(r['replacements']) for r in request['pages']) == 13
base = os.environ['WP_BASE_URL'].rstrip('/')
assert urllib.parse.urlsplit(base).hostname == 'keshavarz20.com'
auth = base64.b64encode((os.environ['WP_USERNAME'] + ':' + os.environ['WP_APP_PASSWORD']).encode()).decode()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def api(method, path, body=None):
    if method == 'POST':
        assert path in {f'/wp-json/wp/v2/pages/{x}' for x in allowed_pages}
        assert set(body) == {'meta'} and set(body['meta']) == {'_elementor_data'}
    elif method == 'DELETE':
        assert path == '/wp-json/elementor/v1/cache' and body is None
    else:
        assert method == 'GET' and path.startswith('/wp-json/wp/v2/')
    headers = {'Authorization': 'Basic '+auth, 'Accept': 'application/json', 'User-Agent': 'K20-Verified-Elementor-Repair/1.0'}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers['Content-Type'] = 'application/json; charset=utf-8'
    with urllib.request.urlopen(urllib.request.Request(base+path, data=data, method=method, headers=headers), timeout=120) as response:
        return json.loads(response.read())


def get_page(pid):
    obj = api('GET', f'/wp-json/wp/v2/pages/{pid}?context=edit&_fields=id,status,slug,link,content,meta')
    assert obj['id'] == pid and obj['status'] == 'publish'
    assert isinstance(obj['meta']['_elementor_data'], str)
    return obj


def public(url):
    parsed = urllib.parse.urlsplit(url)
    assert parsed.scheme == 'https' and parsed.hostname == 'keshavarz20.com'
    url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, urllib.parse.quote(urllib.parse.unquote(parsed.path), safe='/%'), parsed.query, ''))
    url += ('&' if '?' in url else '?') + 'k20_elementor_repair=' + str(int(time.time()))
    headers = {'User-Agent':'K20-Verified-Elementor-Repair/1.0', 'Cache-Control':'no-cache'}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
        assert response.status == 200
        return response.read().decode('utf-8','replace')


def replace_nodes(node, replacement, hits, path='$'):
    if isinstance(node, dict):
        if node.get('url') in replacement['old_url_variants']:
            old = replacement['old_id']; new = replacement['new_id']
            if 'id' in node:
                assert str(node['id']) in (str(old), str(new)), 'unexpected paired image id'
                node['id'] = str(new) if isinstance(node['id'], str) else new
            node['url'] = replacement['new_url']
            hits.append(path)
        for key, value in node.items():
            replace_nodes(value, replacement, hits, path+'.'+key)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            replace_nodes(value, replacement, hits, path+f'[{i}]')


def contains_source(text, source):
    def canonical(url):
        path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
        path = re.sub(r'-\d{2,5}x\d{2,5}(?=\.[^.]+$)', '', path)
        return re.sub(r'-scaled(?=\.[^.]+$)', '', path)
    text = html_module.unescape(text).replace('\\/', '/')
    pattern = r'(?:https?:)?//[^\s\"\'<>)]*/wp-content/uploads/[^\s\"\'<>)]*\.(?:jpe?g|png|webp)|/wp-content/uploads/[^\s\"\'<>)]*\.(?:jpe?g|png|webp)'
    return any(canonical(url) == canonical(source) for url in re.findall(pattern,text,re.I))


result = {'action': request['action'], 'source_readback_at': request['source_readback_at'],
          'request_sha256': digest((ROOT/'repair-request.json').read_text()),
          'originals_deleted': False, 'media_uploaded': 0, 'protected_ids': [142597],
          'pages': [], 'success': False, 'writes_performed': 0}
prepared = []
attempted = []
try:
    # Verify exact existing replacements before touching any page.
    for old, new in allowed_pairs.items():
        m = api('GET',f'/wp-json/wp/v2/media/{new}?context=edit&_fields=id,mime_type,source_url')
        assert m['id'] == new and m['mime_type'] == 'image/webp'
        assert m['source_url'].endswith(f'/k20-direct-a{old}.webp')
    for target in request['pages']:
        page = get_page(target['page_id'])
        raw = page['content']['raw']; elem = page['meta']['_elementor_data']
        assert digest(raw) == target['expected_content_sha256'], 'content drift'
        assert digest(elem) == target['expected_elementor_sha256'], 'Elementor drift'
        before = json.loads(elem); after = copy.deepcopy(before); mutations = []
        for replacement in target['replacements']:
            assert allowed_pairs.get(replacement['old_id']) == replacement['new_id']
            assert replacement['old_id'] != 142597 and replacement['old_url_variants']
            hits = []; replace_nodes(after,replacement,hits)
            assert hits, f'no exact URL node for {replacement["old_id"]}'
            mutations.append({'old_id':replacement['old_id'],'new_id':replacement['new_id'],'paths':hits})
        new_elem = json.dumps(after,ensure_ascii=False,separators=(',',':'))
        prepared.append({'target':target,'before':page,'old_elem':elem,'new_elem':new_elem,'new_obj':after,'mutations':mutations})
    for row in prepared:
        target = row['target']; pid = target['page_id']
        # Re-check immediately before a write; another actor may have edited it.
        current = get_page(pid)
        assert digest(current['meta']['_elementor_data']) == target['expected_elementor_sha256'], 'prewrite Elementor drift'
        assert digest(current['content']['raw']) == target['expected_content_sha256'], 'prewrite content drift'
        attempted.append(row)
        api('POST',f'/wp-json/wp/v2/pages/{pid}',{'meta':{'_elementor_data':row['new_elem']}})
        result['writes_performed'] += 1
        rb = get_page(pid)
        assert json.loads(rb['meta']['_elementor_data']) == row['new_obj'], 'Elementor readback differs'
        assert digest(rb['content']['raw']) == target['expected_content_sha256'], 'content changed'
        assert rb['slug'] == row['before']['slug'] and rb['link'] == row['before']['link'], 'identity changed'
        result['pages'].append({'page_id':pid,'mutations':row['mutations'],'rest_readback_ok':True,
                                'content_unchanged':True,'before_elementor_sha256':target['expected_elementor_sha256'],
                                'after_elementor_sha256':digest(rb['meta']['_elementor_data'])})
    api('DELETE','/wp-json/elementor/v1/cache')
    for row in prepared:
        html = public(row['target']['url']).replace('\\/','/')
        checks = []
        for replacement in row['target']['replacements']:
            if not replacement['rendered_before']:
                continue
            old_absent = not contains_source(html,replacement['old_url'])
            new_present = replacement['new_url'] in html or f'wp-image-{replacement["new_id"]}' in html
            assert old_absent and new_present, f'public readback failed page={row["target"]["page_id"]}'
            checks.append({'old_id':replacement['old_id'],'old_absent':old_absent,'new_present':new_present})
        page_result = next(x for x in result['pages'] if x['page_id']==row['target']['page_id'])
        page_result['public_http'] = 200; page_result['rendered_checks'] = checks
    result['success'] = True
except Exception as error:
    result['error'] = str(error)[:500]
    rollback = []
    for row in reversed(attempted):
        pid = row['target']['page_id']; ok = False
        try:
            current = get_page(pid)
            # Do not overwrite third-party drift while rolling back.
            cur = json.loads(current['meta']['_elementor_data'])
            assert cur in (row['new_obj'], json.loads(row['old_elem'])), 'rollback drift'
            api('POST',f'/wp-json/wp/v2/pages/{pid}',{'meta':{'_elementor_data':row['old_elem']}})
            rb = get_page(pid)
            ok = json.loads(rb['meta']['_elementor_data']) == json.loads(row['old_elem'])
        except Exception:
            ok = False
        rollback.append({'page_id':pid,'restored':ok})
    if attempted:
        try:
            api('DELETE','/wp-json/elementor/v1/cache')
        except Exception:
            result['rollback_cache_failed'] = True
    result['rollback'] = rollback
    result['rollback_ok'] = all(r['restored'] for r in rollback) and not result.get('rollback_cache_failed',False)
finally:
    result['executed_at_utc'] = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    (ROOT/'repair-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result.get(k) for k in ('success','writes_performed','error','rollback_ok')}))
if not result['success']:
    raise SystemExit(2)
