#!/usr/bin/env python3
import base64, io, json, math, os, pathlib, subprocess, time, urllib.error, urllib.parse, urllib.request, xmlrpc.client
from PIL import Image, ImageChops, ImageOps

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
AUTH=base64.b64encode(f"{USER}:{PASS}".encode()).decode()
PAGE_ID=644
SPECS=[
  {
    "stem":"neshaa",
    "source":"https://keshavarz20.com/wp-content/uploads/2024/07/neshaa-768x576.png",
    "filename":"k20-home-neshaa-768x576-wave1.webp",
    "title":"تصویر تجهیزات آبیاری کشاورز بیست",
    "alt":"تجهیزات آبیاری کشاورزی کشاورز بیست"
  },
  {
    "stem":"loole",
    "source":"https://keshavarz20.com/wp-content/uploads/2024/07/loole-768x576.png",
    "filename":"k20-home-loole-768x576-wave1.webp",
    "title":"تصویر لوله آبیاری کشاورز بیست",
    "alt":"لوله و اتصالات آبیاری کشاورز بیست"
  }
]
OUT=pathlib.Path("phase7-results/home-heavy-webp-stage-20260922.json")
server=xmlrpc.client.ServerProxy(BASE+"/xmlrpc.php",allow_none=True,use_builtin_types=True)

def qurl(url):
    p=urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe="/%"),p.query,p.fragment))

def api(method,path,body=None):
    url=path if str(path).startswith("http") else BASE+path
    headers={"Authorization":"Basic "+AUTH,"Accept":"application/json","User-Agent":"K20-Home-WebP-Stage/1.0"}
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
    req=urllib.request.Request(qurl(url),headers={"User-Agent":"K20-Home-WebP-Stage/1.0"})
    with urllib.request.urlopen(req,timeout=180) as r:
        return r.read(),str(r.headers.get("Content-Type") or "")

def rgb(img):
    if "A" in img.getbands():
        rgba=img.convert("RGBA")
        bg=Image.new("RGBA",rgba.size,(255,255,255,255))
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    return img.convert("RGB")

def psnr(a,b):
    aa=rgb(a); bb=rgb(b)
    diff=ImageChops.difference(aa,bb)
    hist=diff.histogram()
    sq=sum(count*((i%256)**2) for i,count in enumerate(hist))
    mse=sq/float(aa.size[0]*aa.size[1]*3)
    return 99.0 if mse<=0 else 20.0*math.log10(255.0/math.sqrt(mse))

def encode(data):
    src=Image.open(io.BytesIO(data))
    src=ImageOps.exif_transpose(src)
    src.load()
    if src.size!=(768,576):
        raise RuntimeError(f"unexpected source dimensions {src.size}")
    attempts=[]
    for q in (84,88,92):
        out=io.BytesIO()
        src.save(out,format="WEBP",quality=q,method=6)
        webp=out.getvalue()
        dec=Image.open(io.BytesIO(webp)); dec.load()
        score=psnr(src,dec)
        attempts.append({"quality":q,"bytes":len(webp),"psnr_db":round(score,2)})
        if score>=36.0:
            return webp,q,round(score,2),attempts
    raise RuntimeError("PSNR guard failed")

def delete_media(mid):
    try:
        return bool(server.wp.deleteFile(0,USER,PASS,int(mid)))
    except Exception:
        return False

def changed_request():
    candidates=[]
    for cmd in (
        ["git","diff","--name-only","HEAD^","HEAD","--","phase7-home-webp-stage-ops/*.json"],
        ["git","show","--pretty=","--name-only","HEAD","--","phase7-home-webp-stage-ops/*.json"],
    ):
        try:
            out=subprocess.check_output(cmd,text=True).splitlines()
        except Exception:
            continue
        candidates=sorted({x.strip() for x in out if x.strip().startswith("phase7-home-webp-stage-ops/") and x.strip().endswith(".json")})
        if candidates:
            break
    if len(candidates)!=1:
        raise RuntimeError(f"expected exactly one stage request, found {len(candidates)}")
    req=json.loads(pathlib.Path(candidates[0]).read_text(encoding="utf-8"))
    if req.get("action")!="home_heavy_webp.stage" or int(req.get("page_id",0))!=PAGE_ID:
        raise RuntimeError("request guard failed")
    return candidates[0]

request_file=changed_request()
result={
    "ok":False,
    "action":"home_heavy_webp.stage",
    "request_file":request_file,
    "page_id":PAGE_ID,
    "executed_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
    "items":[]
}
uploaded=[]
try:
    for spec in SPECS:
        src_bytes,ctype=fetch_bytes(spec["source"])
        if "image/png" not in ctype.lower():
            raise RuntimeError(f"{spec['stem']} source content-type is {ctype}")
        webp,quality,score,attempts=encode(src_bytes)
        saving=round((1-len(webp)/float(len(src_bytes)))*100,2)
        if saving<35.0:
            raise RuntimeError(f"{spec['stem']} saving guard failed: {saving}%")
        upload=server.wp.uploadFile(0,USER,PASS,{
            "name":spec["filename"],
            "type":"image/webp",
            "bits":xmlrpc.client.Binary(webp),
            "overwrite":False,
            "post_id":PAGE_ID
        })
        mid=int(upload.get("id") or 0)
        url=str(upload.get("url") or "")
        if mid<=0 or not url:
            raise RuntimeError(f"{spec['stem']} upload returned no valid media")
        uploaded.append(mid)

        code,media=api("GET",f"/wp-json/wp/v2/media/{mid}?context=edit")
        md=(media.get("media_details") or {}) if isinstance(media,dict) else {}
        if not (200<=code<300 and str(media.get("mime_type") or "").lower()=="image/webp"):
            raise RuntimeError(f"{spec['stem']} media verification failed http={code}")
        if int(md.get("width") or 0)!=768 or int(md.get("height") or 0)!=576:
            raise RuntimeError(f"{spec['stem']} dimensions changed to {md.get('width')}x{md.get('height')}")
        final_bytes=int(md.get("filesize") or len(webp))
        if final_bytes>=int(len(src_bytes)*0.65):
            raise RuntimeError(f"{spec['stem']} final size guard failed")

        mcode,_=api("POST",f"/wp-json/wp/v2/media/{mid}",{
            "title":spec["title"],
            "alt_text":spec["alt"],
            "caption":"",
            "description":"نسخه بهینه WebP برای تصویر صفحه اصلی کشاورز بیست"
        })
        if not 200<=mcode<300:
            raise RuntimeError(f"{spec['stem']} metadata update failed http={mcode}")

        rcode,rb=api("GET",f"/wp-json/wp/v2/media/{mid}?context=edit")
        if not (200<=rcode<300 and str(rb.get("source_url") or "")==url and str(rb.get("alt_text") or "")==spec["alt"]):
            raise RuntimeError(f"{spec['stem']} readback verification failed")

        result["items"].append({
            "stem":spec["stem"],
            "source_url":spec["source"],
            "source_bytes":len(src_bytes),
            "new_attachment_id":mid,
            "new_url":url,
            "new_bytes":final_bytes,
            "saving_pct":saving,
            "quality":quality,
            "psnr_db":score,
            "encoder_attempts":attempts,
            "alt_text":spec["alt"],
            "verified":True
        })
    result["ok"]=True
except Exception as e:
    result["error"]=str(e)
    result["cleanup"]={str(mid):delete_media(mid) for mid in uploaded}

OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":result["ok"],"items":result["items"],"error":result.get("error"),"cleanup":result.get("cleanup")},ensure_ascii=False))
if not result["ok"]:
    raise SystemExit(2)
