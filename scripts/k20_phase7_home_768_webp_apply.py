#!/usr/bin/env python3
import base64, io, json, math, os, re, time, urllib.error, urllib.parse, urllib.request, xmlrpc.client
from pathlib import Path
from PIL import Image, ImageChops, ImageOps

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]; PASS=os.environ["WP_APP_PASSWORD"]
AUTH=base64.b64encode(f"{USER}:{PASS}".encode()).decode()
PAGE_ID=644
SPECS=[
 {"stem":"neshaa","old_id":141437,"source":"https://keshavarz20.com/wp-content/uploads/2024/07/neshaa-768x576.png"},
 {"stem":"loole","old_id":141441,"source":"https://keshavarz20.com/wp-content/uploads/2024/07/loole-768x576.png"},
]
OUT=Path("phase7-results/home-heavy-webp-apply.json")
server=xmlrpc.client.ServerProxy(BASE+"/xmlrpc.php",allow_none=True,use_builtin_types=True)

def qurl(url):
    p=urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe="/%"),p.query,p.fragment))

def api(method,path,body=None):
    url=path if str(path).startswith("http") else BASE+path
    headers={"Authorization":"Basic "+AUTH,"Accept":"application/json","User-Agent":"K20-Phase7-Home-WebP/1.0"}
    data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        headers["Content-Type"]="application/json; charset=utf-8"
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=180) as r:
            raw=r.read().decode("utf-8","replace")
            return int(r.status),json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","replace")
        try: obj=json.loads(raw)
        except Exception: obj={"raw":raw[:500]}
        return int(e.code),obj

def fetch_bytes(url):
    req=urllib.request.Request(qurl(url),headers={"User-Agent":"K20-Phase7-Home-WebP/1.0"})
    with urllib.request.urlopen(req,timeout=180) as r:
        return r.read(),str(r.headers.get("Content-Type") or "")

def public_get(url):
    req=urllib.request.Request(qurl(url),headers={"User-Agent":"K20-Phase7-Home-WebP/1.0","Cache-Control":"no-cache","Pragma":"no-cache"})
    try:
        with urllib.request.urlopen(req,timeout=180) as r:
            return int(r.status),r.read().decode("utf-8","replace"),dict(r.headers)
    except Exception as e:
        return 0,"",{"error":str(e)}

def rgb(img):
    if "A" in img.getbands():
        rgba=img.convert("RGBA"); bg=Image.new("RGBA",rgba.size,(255,255,255,255)); bg.alpha_composite(rgba); return bg.convert("RGB")
    return img.convert("RGB")

def psnr(a,b):
    aa=rgb(a); bb=rgb(b); diff=ImageChops.difference(aa,bb); hist=diff.histogram()
    sq=sum(count*((i%256)**2) for i,count in enumerate(hist))
    mse=sq/float(aa.size[0]*aa.size[1]*3)
    return 99.0 if mse<=0 else 20.0*math.log10(255.0/math.sqrt(mse))

def encode(data):
    src=Image.open(io.BytesIO(data)); src=ImageOps.exif_transpose(src); src.load()
    if src.size!=(768,576): raise RuntimeError(f"unexpected source dimensions {src.size}")
    attempts=[]
    for q in (84,88,92):
        out=io.BytesIO(); src.save(out,format="WEBP",quality=q,method=6)
        b=out.getvalue(); dec=Image.open(io.BytesIO(b)); dec.load(); score=psnr(src,dec)
        attempts.append({"quality":q,"bytes":len(b),"psnr":round(score,2)})
        if score>=36.0:
            return b,round(score,2),q,attempts
    raise RuntimeError("PSNR guard failed")

def delete_media(mid):
    try: return bool(server.wp.deleteFile(0,USER,PASS,int(mid)))
    except Exception: return False

pc,page=api("GET",f"/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,status,link,content")
if not (200<=pc<300 and isinstance(page,dict) and page.get("status")=="publish"): raise SystemExit(f"page precondition failed http={pc}")
raw=((page.get("content") or {}).get("raw") or "")
if not raw: raise SystemExit("homepage raw unavailable")
original_raw=raw; link=str(page.get("link") or BASE+"/")
result={"ok":False,"action":"phase7.home_768_webp","page_id":PAGE_ID,"items":[],"update_http":None,"rollback":None}
uploaded=[]; wrote=False
try:
    new_raw=raw
    for spec in SPECS:
        stem=spec["stem"]
        tags=[m for m in re.finditer(r"<img\b[^>]*>",new_raw,re.I|re.S) if stem.lower() in m.group(0).lower() and ".png" in m.group(0).lower()]
        if len(tags)!=1: raise RuntimeError(f"{stem} img tag count={len(tags)}")
        original_tag=tags[0].group(0)
        old_family_urls=re.findall(r"https?://[^\s\"'<>)]*/wp-content/uploads/[^\s\"'<>)]*"+re.escape(stem)+r"[^\s\"'<>)]*\.png",original_tag,re.I)
        if len(set(old_family_urls))<2: raise RuntimeError(f"{stem} responsive family guard failed")
        source_bytes,ctype=fetch_bytes(spec["source"])
        webp,score,quality,attempts=encode(source_bytes)
        saving=round((1-len(webp)/float(len(source_bytes)))*100,2)
        if saving<35.0: raise RuntimeError(f"{stem} saving guard {saving}%")
        upload=server.wp.uploadFile(0,USER,PASS,{
          "name":f"k20-home-{stem}-768x576-p7.webp",
          "type":"image/webp",
          "bits":xmlrpc.client.Binary(webp),
          "overwrite":False,
          "post_id":PAGE_ID,
        })
        mid=int(upload.get("id") or 0); url=str(upload.get("url") or "")
        if mid<=0 or not url: raise RuntimeError(f"{stem} upload invalid")
        uploaded.append(mid)
        vc,media=api("GET",f"/wp-json/wp/v2/media/{mid}?context=edit&_fields=id,source_url,mime_type,media_details")
        md=media.get("media_details") if isinstance(media,dict) else {}
        if not (200<=vc<300 and str(media.get("mime_type") or "").lower()=="image/webp" and int(md.get("width") or 0)==768 and int(md.get("height") or 0)==576):
            raise RuntimeError(f"{stem} uploaded media verification failed http={vc} dims={md.get('width')}x{md.get('height')}")
        final_bytes=int(md.get("filesize") or len(webp))
        if final_bytes>=len(source_bytes)*0.65: raise RuntimeError(f"{stem} final size guard failed {final_bytes}/{len(source_bytes)}")
        tag=original_tag
        tag=re.sub(r"\s+(?:data-)?srcset=(\"[^\"]*\"|'[^']*')","",tag,flags=re.I)
        tag=re.sub(r"\s+(?:data-)?sizes=(\"[^\"]*\"|'[^']*')","",tag,flags=re.I)
        if re.search(r"\bsrc=(\"[^\"]*\"|'[^']*')",tag,re.I):
            tag=re.sub(r"\bsrc=(\"[^\"]*\"|'[^']*')",f'src="{url}"',tag,count=1,flags=re.I)
        else:
            raise RuntimeError(f"{stem} src attribute missing")
        for attr in ("data-src","data-lazy-src"):
            if re.search(r"\b"+attr+r"=(\"[^\"]*\"|'[^']*')",tag,re.I):
                tag=re.sub(r"\b"+attr+r"=(\"[^\"]*\"|'[^']*')",f'{attr}="{url}"',tag,count=1,flags=re.I)
        start,end=tags[0].span()
        new_raw=new_raw[:start]+tag+new_raw[end:]
        result["items"].append({
          "stem":stem,"old_attachment_id":spec["old_id"],"source_768":spec["source"],
          "source_bytes":len(source_bytes),"new_attachment_id":mid,"new_url":url,
          "webp_bytes":final_bytes,"saving_pct":saving,"psnr_db":score,"quality":quality,"encoder_attempts":attempts,
          "old_family_url_count":len(set(old_family_urls))
        })
    for spec in SPECS:
        if re.search(r"https?://[^\s\"'<>)]*/wp-content/uploads/[^\s\"'<>)]*"+re.escape(spec["stem"])+r"[^\s\"'<>)]*\.png",new_raw,re.I):
            raise RuntimeError(f"{spec['stem']} old PNG remains in raw")
    uc,_=api("POST",f"/wp-json/wp/v2/pages/{PAGE_ID}",{"content":new_raw})
    result["update_http"]=uc
    if not 200<=uc<300: raise RuntimeError(f"page update failed http={uc}")
    wrote=True
    rc,rb=api("GET",f"/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content")
    rr=((rb.get("content") or {}).get("raw") or "") if isinstance(rb,dict) else ""
    if not (200<=rc<300 and rr==new_raw): raise RuntimeError("raw readback mismatch")
    for item in result["items"]:
        if rr.count(item["new_url"])!=1: raise RuntimeError(f"{item['stem']} new URL raw count={rr.count(item['new_url'])}")
    purge_code,purge_resp=api("POST","/wp-json/wpvibe/v1/cli/run",{"command":f"litespeed-purge url {link}","confirm_write":True})
    result["cache_purge"]={"http":purge_code,"ok":bool(200<=purge_code<300),"stdout":str(purge_resp.get("stdout") or "")[:300] if isinstance(purge_resp,dict) else ""}
    if not 200<=purge_code<300: raise RuntimeError(f"LiteSpeed URL purge failed http={purge_code}")
    time.sleep(2)
    public_ok=False; last={}
    for attempt in range(1,5):
        hc,html,headers=public_get(link)
        checks={}
        for item in result["items"]:
            checks[item["stem"]]={"new_present":item["new_url"] in html,"old_768_present":item["source_768"] in html}
        last={"attempt":attempt,"http":hc,"checks":checks,"litespeed_cache":str(headers.get("x-litespeed-cache") or headers.get("X-LiteSpeed-Cache") or "")}
        if hc==200 and all(v["new_present"] and not v["old_768_present"] for v in checks.values()):
            public_ok=True; break
        time.sleep(2)
    result["public_readback"]=last
    if not public_ok: raise RuntimeError("public readback failed after LiteSpeed purge")
    result["ok"]=True
except Exception as e:
    result["error"]=str(e)
    rb_ok=True
    if wrote:
        bc,_=api("POST",f"/wp-json/wp/v2/pages/{PAGE_ID}",{"content":original_raw})
        rb_ok=200<=bc<300
    cleanup={str(mid):delete_media(mid) for mid in uploaded}
    result["rollback"]={"page_restored":rb_ok,"uploaded_media_cleanup":cleanup}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"ok":result["ok"],"items":result["items"],"error":result.get("error"),"rollback":result.get("rollback")},ensure_ascii=False))
if not result["ok"]: raise SystemExit(2)
