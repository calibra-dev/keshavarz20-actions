#!/usr/bin/env python3
import concurrent.futures
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

BASE=os.environ.get("K20_BASE_URL","https://keshavarz20.com").rstrip("/")
UA="K20-Phase16-LinkGraph/1.0 (+https://keshavarz20.com)"
MAX_URLS=int(os.environ.get("K20_PHASE16_MAX_URLS","1200"))
WORKERS=int(os.environ.get("K20_PHASE16_WORKERS","12"))
TIMEOUT=int(os.environ.get("K20_PHASE16_TIMEOUT","20"))
TECHNICAL_EXCLUDES={"/elementor-143320/"}

def norm(url):
    try:
        p=urllib.parse.urlsplit(url)
        if p.scheme not in ("http","https"):
            return None
        host=p.netloc.lower()
        if host.startswith("www."):
            host=host[4:]
        path=re.sub(r"/+","/",p.path or "/")
        if not path.endswith("/") and "." not in path.rsplit("/",1)[-1]:
            path += "/"
        return urllib.parse.urlunsplit(("https",host,path,"",""))
    except Exception:
        return None

BASE_N=norm(BASE+"/")
HOST=urllib.parse.urlsplit(BASE_N).netloc

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r:
            data=r.read()
            return int(getattr(r,"status",200)), r.headers.get("Content-Type",""), data, r.geturl()
    except urllib.error.HTTPError as e:
        return int(e.code), e.headers.get("Content-Type",""), e.read()[:200000], url
    except Exception as e:
        return 0, "", str(e).encode(), url

def sitemap_urls():
    queue=[BASE+"/sitemap_index.xml"]
    seen=set()
    urls=[]
    while queue and len(seen)<100 and len(urls)<MAX_URLS:
        sm=queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        code,ct,data,final=fetch(sm)
        if code<200 or code>=400:
            continue
        try:
            root=ET.fromstring(data)
        except Exception:
            continue
        tag=root.tag.lower()
        locs=[(x.text or "").strip() for x in root.iter() if x.tag.lower().endswith("loc")]
        if tag.endswith("sitemapindex"):
            for u in locs:
                if u and u not in seen and u.startswith(BASE):
                    queue.append(u)
        else:
            for u in locs:
                nu=norm(u)
                if nu and urllib.parse.urlsplit(nu).netloc==HOST:
                    urls.append(nu)
                    if len(urls)>=MAX_URLS:
                        break
    return sorted(set(urls)), sorted(seen)

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]
        self.canonical=None
        self.robots=""
        self.title=[]
        self.h1=[]
        self.in_title=False
        self.in_h1=False
    def handle_starttag(self,tag,attrs):
        d={k.lower():v for k,v in attrs if k}
        t=tag.lower()
        if t=="a" and d.get("href"):
            self.links.append(d["href"])
        elif t=="link":
            rel=(d.get("rel") or "").lower()
            if "canonical" in rel and d.get("href"):
                self.canonical=d["href"]
        elif t=="meta":
            name=(d.get("name") or "").lower()
            if name=="robots":
                self.robots=(d.get("content") or "").lower()
        elif t=="title":
            self.in_title=True
        elif t=="h1":
            self.in_h1=True
    def handle_endtag(self,tag):
        if tag.lower()=="title":
            self.in_title=False
        elif tag.lower()=="h1":
            self.in_h1=False
    def handle_data(self,data):
        s=" ".join(data.split())
        if not s:
            return
        if self.in_title:
            self.title.append(s)
        if self.in_h1:
            self.h1.append(s)

def parse_page(url):
    code,ct,data,final=fetch(url)
    out={"url":url,"status":code,"ok":200<=code<400,"content_type":ct}
    if not out["ok"] or "html" not in ct.lower():
        return out
    try:
        text=data.decode("utf-8","replace")
        p=PageParser(); p.feed(text)
        finaln=norm(final) or url
        can=norm(urllib.parse.urljoin(final,p.canonical)) if p.canonical else finaln
        links=[]
        for href in p.links:
            if href.startswith(("mailto:","tel:","javascript:","#")):
                continue
            u=norm(urllib.parse.urljoin(final,href))
            if u and urllib.parse.urlsplit(u).netloc==HOST:
                links.append(u)
        out.update({
            "final_url":finaln,
            "canonical":can,
            "noindex":"noindex" in p.robots,
            "title":" ".join(p.title).strip(),
            "h1":" ".join(p.h1).strip(),
            "links":sorted(set(links))
        })
    except Exception as e:
        out["parse_error"]=str(e)
    return out

STOP={"کشاورز","بیست","خرید","فروش","محصول","صفحه","راهنما","و","یا","برای","از","به","در","با","the","and","for","keshavarz20"}

def tokens(row):
    raw=" ".join([row.get("title",""),row.get("h1",""),urllib.parse.unquote(urllib.parse.urlsplit(row.get("canonical") or row["url"]).path)])
    xs=[x.lower() for x in re.findall(r"[A-Za-z0-9_\u0600-\u06FF]+",raw)]
    return {x for x in xs if len(x)>1 and x not in STOP}

def overlap(a,b):
    if not a or not b:
        return 0.0
    return len(a & b)/math.sqrt(len(a)*len(b))

def main():
    outpath=sys.argv[1]
    started=time.time()
    urls,sitemaps=sitemap_urls()
    if BASE_N not in urls:
        urls=[BASE_N]+urls
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        pages=list(ex.map(parse_page,urls))
    good=[p for p in pages if p.get("ok") and p.get("canonical") and not p.get("noindex")]
    canonical_nodes={p["canonical"] for p in good}
    page_by_can={}
    for p in good:
        page_by_can.setdefault(p["canonical"],p)
    indegree={u:0 for u in canonical_nodes}
    outgoing={u:set() for u in canonical_nodes}
    for p in good:
        src=p["canonical"]
        for t in p.get("links",[]):
            if t in canonical_nodes and t!=src:
                outgoing[src].add(t)
    for src,targets in outgoing.items():
        for t in targets:
            indegree[t]=indegree.get(t,0)+1
    excluded={norm(BASE+x) for x in TECHNICAL_EXCLUDES}
    orphans=[u for u,d in indegree.items() if d==0 and u!=BASE_N and u not in excluded]
    tok={u:tokens(page_by_can[u]) for u in canonical_nodes}
    recommendations=[]
    for recv in sorted(orphans):
        candidates=[]
        for donor in canonical_nodes:
            if donor==recv:
                continue
            sc=overlap(tok.get(recv,set()),tok.get(donor,set()))
            if sc>0:
                candidates.append((sc,indegree.get(donor,0),donor))
        candidates.sort(reverse=True)
        donors=[d for _,_,d in candidates[:3]]
        rr=page_by_can[recv]
        label=(rr.get("h1") or rr.get("title") or urllib.parse.unquote(urllib.parse.urlsplit(recv).path.strip("/")) or "صفحه مرتبط").strip()
        anchor=re.sub(r"\s+"," ",label)[:120]
        similar=[]
        for other in canonical_nodes:
            if other==recv:
                continue
            a,b=tok.get(recv,set()),tok.get(other,set())
            if a and b:
                j=len(a&b)/max(1,len(a|b))
                if j>=0.75:
                    similar.append({"url":other,"jaccard":round(j,3)})
        recommendations.append({
            "priority":0,
            "receiver":recv,
            "receiver_http_status":rr.get("status"),
            "canonical_target":recv,
            "anchor_candidate":anchor,
            "donor_candidates":donors,
            "location_module":"contextual-body-or-related-links-component",
            "apply_state":"apply-later-after-wave-gate",
            "conflict_cannibalization_flags":similar[:5]
        })
    proposed_broken=sum(1 for r in recommendations if r["canonical_target"] not in canonical_nodes or r["receiver_http_status"]<200 or r["receiver_http_status"]>=400)
    corpus_edges=sum(len(v) for v in outgoing.values())
    record={
        "phase":16,
        "title":"Internal Link Authority Graph",
        "generated_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "mode":"read-only-manifest-first",
        "base_url":BASE_N,
        "sitemaps_read":sitemaps,
        "sitemap_urls":len(urls),
        "pages_fetched":len(pages),
        "indexable_canonical_pages":len(canonical_nodes),
        "internal_graph_edges":corpus_edges,
        "orphan_priority_zero_count":len(orphans),
        "priority_zero_urls":sorted(orphans),
        "recommendations":recommendations,
        "proposed_priority_links_broken":proposed_broken,
        "body_mutations":0,
        "apply_policy":"No body edits in Phase 16. Apply only after Wave 4 content is frozen or via a dedicated owner-scoped component.",
        "coverage_ratio":round(len(good)/max(1,len(urls)),4),
        "status":"PASS_MANIFEST_READY" if len(good)>=max(1,int(len(urls)*0.70)) and proposed_broken==0 else "PARTIAL",
        "duration_seconds":round(time.time()-started,2)
    }
    os.makedirs(os.path.dirname(outpath),exist_ok=True)
    with open(outpath,"w",encoding="utf-8") as f:
        json.dump(record,f,ensure_ascii=False,indent=2)
    print("PHASE16",json.dumps({k:record[k] for k in ["status","sitemap_urls","pages_fetched","indexable_canonical_pages","internal_graph_edges","orphan_priority_zero_count","proposed_priority_links_broken","coverage_ratio"]},ensure_ascii=False))
    if record["status"]!="PASS_MANIFEST_READY":
        raise SystemExit(2)

if __name__=="__main__":
    main()
