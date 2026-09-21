#!/usr/bin/env python3
import base64, json, os, pathlib, re, subprocess, time, urllib.error, urllib.parse, urllib.request, xmlrpc.client

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
AUTH=base64.b64encode(f"{USER}:{PASS}".encode()).decode()
PAGE_ID=644
OUT=pathlib.Path("phase7-results/home-heavy-webp-apply-v2-20260922.json")
SPECS=[
  {
    "stem":"neshaa",
    "old_full":"https://keshavarz20.com/wp-content/uploads/2024/07/neshaa.png",
    "old_768":"https://keshavarz20.com/wp-content/uploads/2024/07/neshaa-768x576.png",
    "new_id":145323,
    "new_full":"https://keshavarz20.com/wp-content/uploads/2026/09/k20-home-neshaa-768x576-wave1.webp",
    "new_300":"https://keshavarz20.com/wp-content/uploads/2026/09/k20-home-neshaa-768x576-wave1-300x225.webp",
    "new_600":"https://keshavarz20.com/wp-content/uploads/2026/09/k20-home-neshaa-768x576-wave1-600x450.webp",
    "alt":"تجهیزات آبیاری کشاورزی کشاورز بیست"
  },
  {
    "stem":"loole",
    "old_full":"https://keshavarz20.com/wp-content/uploads/2024/07/loole.png",
    "old_768":"https://keshavarz20.com/wp-content/uploads/2024/07/loole-768x576.png",
    "new_id":145324,
    "new_full":"https://keshavarz20.com/wp-content/uploads/2026/09/k20-home-loole-768x576-wave1.webp",
    "new_300":"https://keshavarz20.com/wp-content/uploads/2026/09/k20-home-loole-768x576-wave1-300x225.webp",
    "new_600":"https://keshavarz20.com/wp-content/uploads/2026/09/k20-home-loole-768x576-wave1-600x450.webp",
    "alt":"لوله و اتصالات آبیاری کشاورز بیست"
  }
]

def qurl(url):
    p=urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe="/%"),p.query,p.fragment))

def api(method,path,body=None,timeout=180):
    url=path if str(path).startswith("http") else BASE+path
    headers={"Authorization":"Basic "+AUTH,"Accept":"application/json","User-Agent":"K20-Home-WebP-ApplyV2/1.0"}
    data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        headers["Content-Type"]="application/json; charset=utf-8"
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read().decode("utf-8","replace")
            return int(r.status),json.loads(raw) if raw else {},dict(r.headers)
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","replace")
        try: obj=json.loads(raw)
        except Exception: obj={"raw":raw[:1000]}
        return int(e.code),obj,dict(e.headers)

def public_get(url):
    req=urllib.request.Request(qurl(url),headers={
        "User-Agent":"K20-Home-WebP-ApplyV2/1.0",
        "Cache-Control":"no-cache",
        "Pragma":"no-cache"
    })
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            return int(r.status),r.read().decode("utf-8","replace"),dict(r.headers)
    except Exception as e:
        return 0,"",{"error":str(e)}

def changed_request():
    paths=[]
    for cmd in (
        ["git","diff","--name-only","HEAD^","HEAD","--","phase7-home-webp-apply-v2-ops/*.json"],
        ["git","show","--pretty=","--name-only","HEAD","--","phase7-home-webp-apply-v2-ops/*.json"],
    ):
        try: out=subprocess.check_output(cmd,text=True).splitlines()
        except Exception: continue
        paths=sorted({x.strip() for x in out if x.strip().startswith("phase7-home-webp-apply-v2-ops/") and x.strip().endswith(".json")})
        if paths: break
    if len(paths)!=1: raise RuntimeError(f"expected exactly one request; found {len(paths)}")
    req=json.loads(pathlib.Path(paths[0]).read_text(encoding="utf-8"))
    if req.get("action")!="home_heavy_webp.apply_v2" or int(req.get("page_id",0))!=PAGE_ID:
        raise RuntimeError("request guard failed")
    if [int(x) for x in req.get("expected_new_media_ids",[])] != [145323,145324]:
        raise RuntimeError("media id guard failed")
    return paths[0]

def attr_replace(tag,name,value):
    pat=rf'\s{name}=(["\']).*?\1'
    repl=f' {name}="{value}"'
    if re.search(pat,tag,flags=re.I|re.S):
        return re.sub(pat,repl,tag,count=1,flags=re.I|re.S)
    return tag[:-1]+repl+">" if tag.endswith(">") else tag

def purge(url):
    code,obj,_=api("POST","/wp-json/wpvibe/v1/cli/run",{
      "command":f"litespeed-purge url {url}",
      "confirm_write":True
    })
    return {"http":code,"ok":200<=code<300,"stdout":str(obj.get("stdout") or "")[:300] if isinstance(obj,dict) else ""}

request_file=changed_request()
result={
  "ok":False,
  "action":"home_heavy_webp.apply_v2",
  "request_file":request_file,
  "page_id":PAGE_ID,
  "executed_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
  "items":[],
  "site_mutation_attempted":False
}
original_raw=None
page_link=BASE+"/"
wrote=False

try:
    pc,page,_=api("GET",f"/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,status,link,content,modified_gmt")
    if not (200<=pc<300 and isinstance(page,dict) and page.get("status")=="publish"):
        raise RuntimeError(f"page precondition failed http={pc}")
    page_link=str(page.get("link") or page_link)
    original_raw=((page.get("content") or {}).get("raw") or "")
    if not original_raw:
        raise RuntimeError("homepage raw content unavailable")

    # Verify the already-staged media before touching page content.
    for spec in SPECS:
        mc,m,_=api("GET",f"/wp-json/wp/v2/media/{spec['new_id']}?context=edit&_fields=id,source_url,mime_type,alt_text,media_details")
        md=(m.get("media_details") or {}) if isinstance(m,dict) else {}
        if not (200<=mc<300 and int(m.get("id") or 0)==spec["new_id"] and str(m.get("source_url") or "")==spec["new_full"]):
            raise RuntimeError(f"{spec['stem']} staged media readback failed")
        if str(m.get("mime_type") or "").lower()!="image/webp" or int(md.get("width") or 0)!=768 or int(md.get("height") or 0)!=576:
            raise RuntimeError(f"{spec['stem']} staged media guard failed")
        if str(m.get("alt_text") or "")!=spec["alt"]:
            raise RuntimeError(f"{spec['stem']} alt guard failed")

    new_raw=original_raw
    for spec in SPECS:
        matches=list(re.finditer(r"<img\b[^>]*>",new_raw,re.I|re.S))
        target=[m for m in matches if spec["old_full"].lower() in m.group(0).lower()]
        if len(target)!=1:
            raise RuntimeError(f"{spec['stem']} img tag count={len(target)}")
        old_tag=target[0].group(0)
        if 'width="4000"' not in old_tag and "width='4000'" not in old_tag:
            raise RuntimeError(f"{spec['stem']} width precondition failed")
        if 'height="3000"' not in old_tag and "height='3000'" not in old_tag:
            raise RuntimeError(f"{spec['stem']} height precondition failed")

        tag=old_tag
        tag=attr_replace(tag,"width","768")
        tag=attr_replace(tag,"height","576")
        tag=attr_replace(tag,"src",spec["new_full"])
        tag=attr_replace(tag,"alt",spec["alt"])
        tag=attr_replace(tag,"srcset",f"{spec['new_300']} 300w, {spec['new_600']} 600w, {spec['new_full']} 768w")
        tag=attr_replace(tag,"sizes","(max-width: 768px) 100vw, 768px")

        # Leave loading/decoding/class/style behavior intact; only media identity/responsive attrs change.
        start,end=target[0].span()
        new_raw=new_raw[:start]+tag+new_raw[end:]
        result["items"].append({
          "stem":spec["stem"],
          "new_attachment_id":spec["new_id"],
          "old_tag_sha256":__import__("hashlib").sha256(old_tag.encode()).hexdigest(),
          "new_tag_sha256":__import__("hashlib").sha256(tag.encode()).hexdigest(),
          "old_full":spec["old_full"],
          "old_768":spec["old_768"],
          "new_full":spec["new_full"],
          "new_srcset":[spec["new_300"],spec["new_600"],spec["new_full"]]
        })

    if new_raw==original_raw:
        raise RuntimeError("no content delta produced")

    # Exact residual guard: neither original family base nor 768 variant may remain in post_content.
    for spec in SPECS:
        if spec["old_full"] in new_raw or spec["old_768"] in new_raw:
            raise RuntimeError(f"{spec['stem']} old URL remains in new raw")
        if new_raw.count(spec["new_full"])<2:
            raise RuntimeError(f"{spec['stem']} expected new URL in src + srcset")

    result["site_mutation_attempted"]=True
    uc,updated,_=api("POST",f"/wp-json/wp/v2/pages/{PAGE_ID}",{"content":new_raw})
    result["update_http"]=uc
    if not 200<=uc<300:
        raise RuntimeError(f"page update failed http={uc}")
    wrote=True

    rc,rb,_=api("GET",f"/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content,modified_gmt")
    rr=((rb.get("content") or {}).get("raw") or "") if isinstance(rb,dict) else ""
    if not (200<=rc<300 and rr==new_raw):
        raise RuntimeError("raw content readback mismatch")
    result["raw_readback"]={"ok":True,"modified_gmt":rb.get("modified_gmt") if isinstance(rb,dict) else None}

    result["cache_purge"]=purge(page_link)
    if not result["cache_purge"]["ok"]:
        raise RuntimeError("LiteSpeed URL purge failed")

    time.sleep(2)
    public_ok=False
    last={}
    for attempt in range(1,6):
        hc,html,h=public_get(page_link)
        checks={}
        for spec in SPECS:
            checks[spec["stem"]]={
              "new_present":spec["new_full"] in html,
              "old_full_present":spec["old_full"] in html,
              "old_768_present":spec["old_768"] in html
            }
        last={
          "attempt":attempt,
          "http":hc,
          "litespeed_cache":str(h.get("x-litespeed-cache") or h.get("X-LiteSpeed-Cache") or ""),
          "checks":checks
        }
        if hc==200 and all(v["new_present"] and not v["old_full_present"] and not v["old_768_present"] for v in checks.values()):
            public_ok=True
            break
        time.sleep(2)
    result["public_readback"]=last
    if not public_ok:
        raise RuntimeError("public readback did not confirm replacement")

    result["ok"]=True

except Exception as e:
    result["error"]=str(e)
    if wrote and original_raw is not None:
        bc,_,_=api("POST",f"/wp-json/wp/v2/pages/{PAGE_ID}",{"content":original_raw})
        rb_purge=purge(page_link) if 200<=bc<300 else {"ok":False,"skipped":True}
        result["rollback"]={"page_restore_http":bc,"page_restored":200<=bc<300,"cache_purge":rb_purge}
    else:
        result["rollback"]={"page_restored":True,"mutation_not_started":not wrote}

OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"ok":result["ok"],"items":result["items"],"public_readback":result.get("public_readback"),"error":result.get("error"),"rollback":result.get("rollback")},ensure_ascii=False))
if not result["ok"]:
    raise SystemExit(2)
