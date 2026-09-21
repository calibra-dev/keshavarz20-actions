#!/usr/bin/env python3
import base64,json,os,pathlib,re,subprocess,time,urllib.error,urllib.parse,urllib.request

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]; PASS=os.environ["WP_APP_PASSWORD"]
AUTH=base64.b64encode(f"{USER}:{PASS}".encode()).decode()
PAGE_ID=644
OLD="https://keshavarz20.com/wp-content/uploads/2024/07/loole.png"
NEW="https://keshavarz20.com/wp-content/uploads/2026/09/k20-home-loole-768x576-wave1.webp"
OUT=pathlib.Path("phase7-results/home-render-source-probe-20260922.json")

def qurl(url):
    p=urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe="/%"),p.query,p.fragment))

def api(method,path,body=None):
    url=path if str(path).startswith("http") else BASE+path
    h={"Authorization":"Basic "+AUTH,"Accept":"application/json","User-Agent":"K20-Render-Source-Probe/1.0"}
    data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode()
        h["Content-Type"]="application/json; charset=utf-8"
    req=urllib.request.Request(qurl(url),data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            raw=r.read().decode("utf-8","replace")
            return int(r.status),json.loads(raw) if raw else {},dict(r.headers)
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","replace")
        try: obj=json.loads(raw)
        except Exception: obj={"raw":raw[:1000]}
        return int(e.code),obj,dict(e.headers)

def pub(url):
    req=urllib.request.Request(qurl(url),headers={"User-Agent":"K20-Render-Source-Probe/1.0","Cache-Control":"no-cache","Pragma":"no-cache"})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            return int(r.status),r.read().decode("utf-8","replace"),dict(r.headers)
    except Exception as e:
        return 0,"",{"error":str(e)}

def purge(url):
    code,obj,_=api("POST","/wp-json/wpvibe/v1/cli/run",{"command":f"litespeed-purge url {url}","confirm_write":True})
    return {"http":code,"ok":200<=code<300,"stdout":str(obj.get("stdout") or "")[:200] if isinstance(obj,dict) else ""}

pc,page,_=api("GET",f"/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,status,link,content")
if not (200<=pc<300 and page.get("status")=="publish"): raise SystemExit("precondition failed")
raw=((page.get("content") or {}).get("raw") or "")
link=str(page.get("link") or BASE+"/")
matches=list(re.finditer(r"<img\b[^>]*>",raw,re.I|re.S))
target=[m for m in matches if OLD.lower() in m.group(0).lower()]
if len(target)!=1: raise SystemExit(f"target count {len(target)}")
old_tag=target[0].group(0)
new_tag=re.sub(r'\bsrc=(["\']).*?\1',f'src="{NEW}"',old_tag,count=1,flags=re.I|re.S)
if new_tag==old_tag: raise SystemExit("no tag delta")
probe_raw=raw[:target[0].start()]+new_tag+raw[target[0].end():]
nonce=str(int(time.time()*1000))
probe_url=link+("?k20_wave1_render_probe="+nonce if "?" not in link else "&k20_wave1_render_probe="+nonce)
result={"ok":False,"action":"home.render_source_probe","page_id":PAGE_ID,"probe_url":probe_url,"site_mutation_temporary":True}
wrote=False
try:
    uc,_,_=api("POST",f"/wp-json/wp/v2/pages/{PAGE_ID}",{"content":probe_raw})
    if not 200<=uc<300: raise RuntimeError(f"probe write failed http={uc}")
    wrote=True
    rc,rb,_=api("GET",f"/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content")
    rr=((rb.get("content") or {}).get("raw") or "")
    result["raw_readback_new"]=NEW in rr
    if not result["raw_readback_new"]: raise RuntimeError("raw readback did not contain probe URL")

    hc,html,h=pub(probe_url)
    result["uncached_probe"]={
      "http":hc,
      "litespeed_cache":str(h.get("x-litespeed-cache") or h.get("X-LiteSpeed-Cache") or ""),
      "new_present":NEW in html,
      "old_present":OLD in html,
      "html_bytes":len(html.encode("utf-8"))
    }
    result["classification"]="POST_CONTENT_IS_RENDER_SOURCE" if NEW in html else "POST_CONTENT_NOT_RENDER_SOURCE_OR_RENDER_CACHE_PRECEDES_PAGE_CONTENT"
    result["ok"]=hc==200
finally:
    if wrote:
        bc,_,_=api("POST",f"/wp-json/wp/v2/pages/{PAGE_ID}",{"content":raw})
        result["rollback_http"]=bc
        result["rollback_ok"]=200<=bc<300
        result["cache_purge_after_rollback"]=purge(link) if result["rollback_ok"] else {"ok":False,"skipped":True}
        rc,rb,_=api("GET",f"/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,content")
        rr=((rb.get("content") or {}).get("raw") or "")
        result["rollback_readback"]={"old_present":OLD in rr,"new_present":NEW in rr}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
if not (result.get("ok") and result.get("rollback_ok") and result.get("rollback_readback",{}).get("old_present") and not result.get("rollback_readback",{}).get("new_present")):
    raise SystemExit(2)
