#!/usr/bin/env python3
import base64, concurrent.futures, html, json, math, os, re, sys, time
import urllib.parse, urllib.request, urllib.error
from collections import defaultdict

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
AUTH=base64.b64encode(f"{USER}:{PASS}".encode()).decode()
HEAD={"Authorization":f"Basic {AUTH}","Accept":"application/json","User-Agent":"k20-phase16-rest-link-graph/1.0"}
MAX_PAGES=50

def req_json(path, params=None, timeout=120):
    url=BASE+"/"+path.lstrip("/")
    if params:
        url += ("&" if "?" in url else "?")+urllib.parse.urlencode(params,doseq=True)
    r=urllib.request.Request(url,headers=HEAD)
    with urllib.request.urlopen(r,timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8","replace"))

def paged(path, params=None):
    out=[]
    p=dict(params or {})
    for page in range(1,MAX_PAGES+1):
        q=dict(p); q.update({"per_page":100,"page":page})
        try:
            rows=req_json(path,q)
        except urllib.error.HTTPError as e:
            if page>1 and e.code==400: break
            raise
        if not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

def norm(url):
    if not url: return None
    try:
        p=urllib.parse.urlsplit(url)
        host=p.netloc.lower()
        if host.startswith("www."): host=host[4:]
        basehost=urllib.parse.urlsplit(BASE).netloc.lower().removeprefix("www.")
        if host and host!=basehost: return None
        path=re.sub(r"/+","/",p.path or "/")
        if not path.endswith("/") and "." not in path.rsplit("/",1)[-1]:
            path+="/"
        return urllib.parse.urlunsplit(("https",basehost,path,"",""))
    except Exception:
        return None

def strip_text(s):
    s=html.unescape(s or "")
    s=re.sub(r"<script\b[^>]*>.*?</script>"," ",s,flags=re.I|re.S)
    s=re.sub(r"<style\b[^>]*>.*?</style>"," ",s,flags=re.I|re.S)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

HREF_RE=re.compile(r"""href\s*=\s*["']([^"']+)["']""",re.I)

def links_from_html(raw, base_url):
    out=set()
    for href in HREF_RE.findall(raw or ""):
        if href.startswith(("#","mailto:","tel:","javascript:")): continue
        u=norm(urllib.parse.urljoin(base_url,href))
        if u: out.add(u)
    return out

def tokens(title,slug):
    raw=strip_text(title)+" "+urllib.parse.unquote(slug or "")
    xs=[x.lower() for x in re.findall(r"[A-Za-z0-9_\u0600-\u06FF]+",raw)]
    stop={"کشاورز","بیست","خرید","فروش","محصول","صفحه","راهنما","و","یا","برای","از","به","در","با","the","and","for","keshavarz20"}
    return {x for x in xs if len(x)>1 and x not in stop}

def overlap(a,b):
    if not a or not b: return 0.0
    return len(a&b)/math.sqrt(len(a)*len(b))

def public_head(url):
    try:
        r=urllib.request.Request(url,method="HEAD",headers={"User-Agent":"k20-phase16-target-check/1.0"})
        with urllib.request.urlopen(r,timeout=30) as x:
            return int(getattr(x,"status",200))
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return 0

def main(outpath):
    posts=[]
    for typ,path in [("post","wp-json/wp/v2/posts"),("page","wp-json/wp/v2/pages")]:
        rows=paged(path,{"status":"publish","context":"edit","_fields":"id,slug,status,link,title,content"})
        for x in rows:
            raw=((x.get("content") or {}).get("raw") or (x.get("content") or {}).get("rendered") or "")
            link=norm(x.get("link"))
            if not link: continue
            posts.append({
              "id":x.get("id"),"type":typ,"title":((x.get("title") or {}).get("raw") or (x.get("title") or {}).get("rendered") or ""),
              "slug":x.get("slug") or "","url":link,"raw":raw
            })
    products=paged("wp-json/wc/v3/products",{"status":"publish","_fields":"id,name,slug,permalink,description,short_description"})
    for x in products:
        link=norm(x.get("permalink"))
        if not link: continue
        raw=(x.get("short_description") or "")+"\n"+(x.get("description") or "")
        posts.append({"id":x.get("id"),"type":"product","title":x.get("name") or "","slug":x.get("slug") or "","url":link,"raw":raw})

    by_url={x["url"]:x for x in posts}
    nodes=set(by_url)
    outgoing={u:set() for u in nodes}
    source_edges=0
    for u,row in by_url.items():
        for t in links_from_html(row["raw"],u):
            if t in nodes and t!=u:
                outgoing[u].add(t); source_edges+=1
    indegree={u:0 for u in nodes}
    for src,ts in outgoing.items():
        for t in ts: indegree[t]+=1

    tok={u:tokens(by_url[u]["title"],by_url[u]["slug"]) for u in nodes}
    candidates=[]
    excluded_paths={"/cart/","/checkout/","/my-account/","/elementor-143320/"}
    for u in nodes:
        path=urllib.parse.urlsplit(u).path
        if path in excluded_paths: continue
        if indegree[u]==0:
            donors=[]
            for d in nodes:
                if d==u: continue
                sc=overlap(tok[u],tok[d])
                if sc>0:
                    donors.append((sc,indegree[d],d))
            donors.sort(reverse=True)
            label=strip_text(by_url[u]["title"]) or urllib.parse.unquote(by_url[u]["slug"])
            candidates.append({
              "priority":0,
              "receiver":u,
              "receiver_type":by_url[u]["type"],
              "receiver_id":by_url[u]["id"],
              "canonical_target":u,
              "anchor_candidate":label[:120],
              "donor_candidates":[d for _,_,d in donors[:3]],
              "location_module":"contextual-body-or-owner-scoped-related-links",
              "apply_state":"apply-later-after-wave-gate",
              "note":"Zero inbound links within editable post/page/product body content. Theme/menu/archive links are outside this source graph."
            })

    # Validate all receiver URLs and the first donor candidate for each target.
    checks=sorted({x["receiver"] for x in candidates} | {d for x in candidates for d in x["donor_candidates"][:1]})
    statuses={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        vals=list(ex.map(public_head,checks))
    statuses=dict(zip(checks,vals))
    broken=[u for u,s in statuses.items() if s<200 or s>=400]
    for x in candidates:
        x["receiver_http_status"]=statuses.get(x["receiver"],0)
        x["first_donor_http_status"]=statuses.get(x["donor_candidates"][0],0) if x["donor_candidates"] else None

    coverage={
      "posts":sum(1 for x in posts if x["type"]=="post"),
      "pages":sum(1 for x in posts if x["type"]=="page"),
      "products":sum(1 for x in posts if x["type"]=="product"),
      "total_nodes":len(nodes)
    }
    record={
      "phase":16,
      "title":"Internal Link Authority Graph",
      "generated_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
      "mode":"authenticated-rest-source-graph-manifest-first",
      "coverage":coverage,
      "editable_body_internal_edges":sum(len(v) for v in outgoing.values()),
      "priority_zero_candidates":len(candidates),
      "recommendations":sorted(candidates,key=lambda x:(x["receiver_type"],x["receiver"])),
      "validated_urls":len(checks),
      "broken_validated_urls":broken,
      "body_mutations":0,
      "apply_policy":"No body edits in Phase 16. Apply only after Wave 4 freeze or via a dedicated owner-scoped component.",
      "scope_note":"Graph covers editable post/page/product body links from authenticated REST. Theme, menus, widgets and archive-loop links are intentionally not treated as body-authority edges.",
      "status":"PASS_MANIFEST_READY" if not broken and coverage["total_nodes"]>=700 else "PARTIAL"
    }
    os.makedirs(os.path.dirname(outpath),exist_ok=True)
    with open(outpath,"w",encoding="utf-8") as f: json.dump(record,f,ensure_ascii=False,indent=2)
    print("PHASE16_REST",json.dumps({k:record[k] for k in ["status","coverage","editable_body_internal_edges","priority_zero_candidates","validated_urls","broken_validated_urls"]},ensure_ascii=False))
    if record["status"]!="PASS_MANIFEST_READY":
        raise SystemExit(2)

if __name__=="__main__":
    main(sys.argv[1])
