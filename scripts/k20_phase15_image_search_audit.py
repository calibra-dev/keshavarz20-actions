import datetime
import html.parser
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://keshavarz20.com'


def fetch(url, method='GET', timeout=45):
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            'User-Agent': 'K20-Phase15-ImageSearch/1.1',
            'Accept': '*/*',
            'Cache-Control': 'no-cache',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = b'' if method == 'HEAD' else resp.read()
            return int(resp.status), resp.geturl(), raw, dict(resp.headers)
    except Exception as exc:
        return (
            int(getattr(exc, 'code', 0) or 0),
            str(getattr(exc, 'url', url) or url),
            b'',
            dict(getattr(exc, 'headers', {}) or {}),
        )


def norm(url):
    parts = urllib.parse.urlsplit(str(url or ''))
    path = urllib.parse.unquote(parts.path or '/').rstrip('/') or '/'
    if path != '/':
        path += '/'
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, '', ''))


def local(tag):
    return str(tag).rsplit('}', 1)[-1].lower()


def image_family(url):
    name = urllib.parse.unquote(urllib.parse.urlsplit(str(url or '')).path).rsplit('/', 1)[-1]
    stem, ext = os.path.splitext(name)
    stem = re.sub(r'-\d{2,5}x\d{2,5}$', '', stem)
    return (stem + ext).lower()


class ImgParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'img':
            self.images.append({str(k).lower(): (v or '') for k, v in attrs})


def media_read(attachment_id):
    status, _, raw, _ = fetch(f'{BASE}/wp-json/wp/v2/media/{attachment_id}')
    if not (200 <= status < 300) or not raw:
        return {'http': status}
    obj = json.loads(raw.decode('utf-8', 'replace'))
    details = obj.get('media_details') or {}
    return {
        'http': status,
        'id': obj.get('id'),
        'alt_text': obj.get('alt_text') or '',
        'title': ((obj.get('title') or {}).get('rendered') or ''),
        'source_url': obj.get('source_url') or '',
        'mime_type': obj.get('mime_type') or '',
        'width': details.get('width'),
        'height': details.get('height'),
        'file': details.get('file') or '',
    }


def crawl_sitemaps():
    queue = [BASE + '/sitemap_index.xml', BASE + '/wp-sitemap.xml']
    seen = set()
    rows = []
    failures = []
    while queue and len(seen) < 150:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        status, _, raw, _ = fetch(url)
        if not (200 <= status < 300) or not raw:
            failures.append({'url': url, 'http': status})
            continue
        try:
            root = ET.fromstring(raw)
        except Exception:
            failures.append({'url': url, 'http': status, 'parse_error': True})
            continue
        kind = local(root.tag)
        if kind == 'sitemapindex':
            for sitemap in list(root):
                if local(sitemap.tag) != 'sitemap':
                    continue
                loc = ''
                for child in list(sitemap):
                    if local(child.tag) == 'loc' and (child.text or '').strip():
                        loc = (child.text or '').strip()
                        break
                if loc.startswith(BASE) and loc not in seen and loc not in queue:
                    queue.append(loc)
        elif kind == 'urlset':
            for entry in list(root):
                if local(entry.tag) != 'url':
                    continue
                loc = ''
                images = []
                for child in list(entry):
                    if local(child.tag) == 'loc' and (child.text or '').strip():
                        loc = (child.text or '').strip()
                    elif local(child.tag) == 'image':
                        for image_child in list(child):
                            if local(image_child.tag) == 'loc' and (image_child.text or '').strip():
                                images.append((image_child.text or '').strip())
                if loc:
                    rows.append({'sitemap': url, 'url': loc, 'images': images})
    return seen, rows, failures


def resolve_media_urls(urls):
    wanted = {str(x) for x in urls if str(x)}
    if not wanted:
        return []
    found = set()
    resolved = []
    fields = 'id,slug,source_url,alt_text,title,mime_type,media_details'
    for page in range(1, 101):
        query = urllib.parse.urlencode({'per_page': 100, 'page': page, '_fields': fields})
        status, _, raw, _ = fetch(f'{BASE}/wp-json/wp/v2/media?{query}')
        if status == 400 and page > 1:
            break
        if not (200 <= status < 300) or not raw:
            break
        items = json.loads(raw.decode('utf-8', 'replace'))
        if not isinstance(items, list) or not items:
            break
        for obj in items:
            src = str(obj.get('source_url') or '')
            if src not in wanted:
                continue
            details = obj.get('media_details') or {}
            resolved.append({
                'id': obj.get('id'),
                'slug': obj.get('slug') or '',
                'source_url': src,
                'alt_text': obj.get('alt_text') or '',
                'title': ((obj.get('title') or {}).get('rendered') or ''),
                'mime_type': obj.get('mime_type') or '',
                'width': details.get('width'),
                'height': details.get('height'),
            })
            found.add(src)
        if found == wanted or len(items) < 100:
            break
    return resolved


def audit_target(target, sitemap_rows):
    attachment_id = int(target['attachment_id'])
    page_url = str(target['page_url'])
    expected_alt = str(target.get('expected_alt') or '')
    media = media_read(attachment_id)
    source_url = media.get('source_url') or ''
    basename = urllib.parse.unquote(urllib.parse.urlsplit(source_url).path).rsplit('/', 1)[-1] if source_url else ''

    page_http, page_final_url, raw, _ = fetch(page_url)
    page_html = raw.decode('utf-8', 'replace') if raw else ''
    parser = ImgParser()
    if page_html:
        try:
            parser.feed(page_html)
        except Exception:
            pass

    matches = []
    for image in parser.images:
        blob = ' '.join([
            image.get('src', ''),
            image.get('data-src', ''),
            image.get('srcset', ''),
            image.get('data-srcset', ''),
            image.get('class', ''),
            image.get('alt', ''),
        ])
        if (
            (basename and basename in urllib.parse.unquote(blob))
            or f'wp-image-{attachment_id}' in blob
            or (expected_alt and image.get('alt', '') == expected_alt)
        ):
            matches.append(image)

    source_http = 0
    if source_url:
        source_http, _, _, _ = fetch(source_url, method='HEAD')
        if source_http in (0, 405):
            source_http, _, _, _ = fetch(source_url)

    page_entries = [x for x in sitemap_rows if norm(x['url']) == norm(page_url)]
    image_locs = [image for entry in page_entries for image in entry['images']]
    exact = bool(source_url and source_url in image_locs)
    family = image_family(source_url)
    family_match = bool(family and any(image_family(x) == family for x in image_locs))
    first = matches[0] if matches else {}

    return {
        'attachment_id': attachment_id,
        'page_url': page_url,
        'page_http': page_http,
        'page_final_url': page_final_url,
        'media': media,
        'source_http': source_http,
        'rendered_match_count': len(matches),
        'rendered_img_sample': matches[:3],
        'sitemap': {
            'page_entries': [
                {'sitemap': x['sitemap'], 'image_count': len(x['images'])}
                for x in page_entries
            ],
            'target_image_exact': exact,
            'target_image_family_match': family_match,
            'image_loc_sample': image_locs[:10],
        },
        'checks': {
            'media_http_200': media.get('http') == 200,
            'source_http_200': source_http == 200,
            'alt_matches_expected': bool(expected_alt and media.get('alt_text') == expected_alt),
            'rendered_img_found': bool(matches),
            'rendered_alt_matches_expected': bool(expected_alt and any(x.get('alt', '') == expected_alt for x in matches)),
            'rendered_dimensions_present': bool(first.get('width') and first.get('height')),
            'rendered_srcset_present': bool(first.get('srcset') or first.get('data-srcset')),
            'page_in_sitemap': bool(page_entries),
            'page_has_image_sitemap_entries': bool(image_locs),
            'target_image_in_sitemap': bool(exact or family_match),
        },
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: audit.py REQUEST_JSON RESULT_JSON')
    request_path, result_path = sys.argv[1:]
    with open(request_path, encoding='utf-8') as f:
        request = json.load(f)

    seen, sitemap_rows, sitemap_failures = crawl_sitemaps()
    result = {
        'mode': 'read-only',
        'executed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'sitemaps_seen': len(seen),
        'sitemap_failures': sitemap_failures,
        'resolved_media': resolve_media_urls(request.get('resolve_urls') or []),
        'targets': [audit_target(x, sitemap_rows) for x in (request.get('targets') or [])],
        'site_mutations': 0,
    }
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
