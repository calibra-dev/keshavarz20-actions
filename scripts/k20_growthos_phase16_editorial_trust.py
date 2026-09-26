#!/usr/bin/env python3
from __future__ import annotations
import html, json, os, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=1.0,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry)); S.mount("http://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase16-editorial-trust/1.0","Cache-Control":"no-cache"})
NOW=datetime.now(timezone.utc).isoformat()
P15=Path("growthos-phase15-results/summary.json")
POLICY=Path("automation-policy/editorial-trust-2026.json")

def api(path,params=None):
    r=S.get(urljoin(BASE+"/",path.lstrip("/")),params=params,timeout=90)
    r.raise_for_status()
    return r.json()

def paged(route,params=None):
    out=[]; params=dict(params or {})
    for page in range(1,30):
        q=dict(params); q.update({"per_page":100,"page":page})
        r=S.get(urljoin(BASE+"/",route.lstrip("/")),params=q,timeout=90)
        if r.status_code==400 and page>1: break
        r.raise_for_status()
        rows=r.json()
        if not isinstance(rows,list) or not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

def types(node):
    t=node.get("@type") if isinstance(node,dict) else None
    return set(str(x) for x in (t if isinstance(t,list) else [t]) if x)

def parse_jsonld(text):
    blocks=re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',text,re.I)
    nodes=[]; errors=[]
    for raw in blocks:
        try:
            data=json.loads(html.unescape(raw.strip()))
            nodes.extend([n for n in walk(data) if isinstance(n,dict)])
        except Exception as e:
            errors.append(type(e).__name__)
    return nodes,errors

def text_only(value):
    s=re.sub(r"<script[\s\S]*?</script>"," ",str(value or ""),flags=re.I)
    s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",html.unescape(s)).strip()

def author_info(article):
    raw=article.get("author")
    vals=raw if isinstance(raw,list) else ([raw] if raw else [])
    out=[]
    for a in vals:
        if isinstance(a,dict):
            out.append({
              "type":sorted(types(a)),
              "name":a.get("name"),
              "url":a.get("url"),
              "sameAs":a.get("sameAs")
            })
        elif isinstance(a,str):
            out.append({"type":[],"name":a,"url":None,"sameAs":None})
    return out

def pub_info(article):
    p=article.get("publisher")
    if isinstance(p,list): p=p[0] if p else None
    if not isinstance(p,dict): return None
    return {"type":sorted(types(p)),"name":p.get("name"),"url":p.get("url"),"id":p.get("@id")}

def audit_post(post):
    url=post.get("link") or ""
    content=((post.get("content") or {}).get("rendered") or "")
    row={
      "id":int(post["id"]),"title":text_only((post.get("title") or {}).get("rendered") or ""),
      "url":url,"date":post.get("date_gmt"),"modified":post.get("modified_gmt")
    }
    try:
        r=requests.get(url,timeout=60,headers={"User-Agent":"k20-growthos-phase16-editorial-trust/1.0","Cache-Control":"no-cache"})
        row["http"]=r.status_code
        nodes,errs=parse_jsonld(r.text)
        articles=[n for n in nodes if types(n) & {"Article","BlogPosting","NewsArticle"}]
        a=articles[0] if articles else {}
        authors=author_info(a)
        publisher=pub_info(a)
        row.update({
          "jsonld_parse_clean":not errs,
          "article_schema_present":bool(articles),
          "authors":authors,
          "author_present":bool(authors and any(str(x.get("name") or "").strip() for x in authors)),
          "author_identity_url_present":bool(authors and any(x.get("url") or x.get("sameAs") for x in authors)),
          "publisher":publisher,
          "publisher_present":bool(publisher and publisher.get("name")),
          "datePublished_present":bool(a.get("datePublished")),
          "dateModified_present":bool(a.get("dateModified")),
        })
    except Exception as e:
        row.update({"http":0,"error":type(e).__name__+": "+str(e)[:160],"article_schema_present":False,"author_present":False,"author_identity_url_present":False,"publisher_present":False,"datePublished_present":False,"dateModified_present":False,"jsonld_parse_clean":False})
    raw=content
    row["sources_section_visible"]="منابع" in raw
    row["editorial_analysis_visible"]="نظر کارشناسی کشاورز بیست" in raw
    row["review_method_visible"]="روش تهیه و بازبینی" in raw
    row["editorial_policy_link_visible"]="/editorial-policy/" in raw
    row["phase16_provenance_full"]=all([
      row["sources_section_visible"],row["editorial_analysis_visible"],
      row["review_method_visible"],row["editorial_policy_link_visible"]
    ])
    return row

if not P15.exists():
    raise SystemExit("Missing GrowthOS Phase 15 summary")
p15=json.loads(P15.read_text(encoding="utf-8"))
if not (p15.get("ok") and str(p15.get("status") or "").startswith("PASS")):
    raise SystemExit("Phase 15 prerequisite is not PASS")
policy=json.loads(POLICY.read_text(encoding="utf-8"))

pages=paged("wp-json/wp/v2/pages",{"status":"publish","context":"edit"})
policy_pages=[p for p in pages if str(p.get("slug") or "")=="editorial-policy"]
policy_page=policy_pages[0] if policy_pages else None
policy_content=((policy_page.get("content") or {}).get("raw") or (policy_page.get("content") or {}).get("rendered") or "") if policy_page else ""
policy_url=(policy_page or {}).get("link")
policy_public_http=0
if policy_url:
    try: policy_public_http=requests.get(policy_url,timeout=60,headers={"User-Agent":"k20-growthos-phase16-editorial-trust/1.0","Cache-Control":"no-cache"}).status_code
    except Exception: policy_public_http=0

posts=paged("wp-json/wp/v2/posts",{"status":"publish","context":"edit"})
rows=[]
with ThreadPoolExecutor(max_workers=8) as pool:
    futs=[pool.submit(audit_post,p) for p in posts]
    for f in as_completed(futs): rows.append(f.result())
rows.sort(key=lambda x:x["id"])

article_prompt=Path("daily-agri-articles/SCHEDULED_TASK_PROMPT.md").read_text(encoding="utf-8")
news_prompt=Path("daily-agri-news/SCHEDULED_TASK_PROMPT.md").read_text(encoding="utf-8")
article_validator=Path("daily-agri-articles/publish_queue_v2.py").read_text(encoding="utf-8")
news_validator=Path("daily-agri-news/publish_queue_v2.py").read_text(encoding="utf-8")

contract_checks={
  "editorial_policy_published":bool(policy_page and policy_page.get("status")=="publish"),
  "editorial_policy_http_200":policy_public_http==200,
  "policy_mentions_human_review":"بازبینی انسانی" in policy_content,
  "policy_mentions_ai":"هوش مصنوعی" in policy_content,
  "policy_mentions_sources":"منبع" in policy_content,
  "article_prompt_reads_editorial_policy":"editorial-trust-2026.json" in article_prompt,
  "news_prompt_reads_editorial_policy":"editorial-trust-2026.json" in news_prompt,
  "article_prompt_requires_review_method":"روش تهیه و بازبینی" in article_prompt,
  "news_prompt_requires_review_method":"روش تهیه و بازبینی" in news_prompt,
  "article_validator_requires_editorial_disclosure":"editorial_disclosure" in article_validator,
  "news_validator_requires_editorial_disclosure":"editorial_disclosure" in news_validator,
  "article_validator_requires_human_review_gate":"human_review_required_before_publish" in article_validator,
  "news_validator_requires_human_review_gate":"human_review_required_before_publish" in news_validator,
  "fake_authors_forbidden":bool(policy.get("principles",{}).get("fake_authors_forbidden")),
  "fake_reviewers_forbidden":bool(policy.get("principles",{}).get("fake_reviewers_forbidden")),
  "automatic_output_is_draft":policy.get("publication_gate",{}).get("automatic_engine_output_status")=="draft"
}
hard_pass=all(contract_checks.values())

summary_counts={
  "published_normal_posts":len(rows),
  "http_200":sum(1 for x in rows if x.get("http")==200),
  "article_schema_present":sum(1 for x in rows if x.get("article_schema_present")),
  "author_present":sum(1 for x in rows if x.get("author_present")),
  "author_identity_url_present":sum(1 for x in rows if x.get("author_identity_url_present")),
  "publisher_present":sum(1 for x in rows if x.get("publisher_present")),
  "datePublished_present":sum(1 for x in rows if x.get("datePublished_present")),
  "dateModified_present":sum(1 for x in rows if x.get("dateModified_present")),
  "visible_sources_section":sum(1 for x in rows if x.get("sources_section_visible")),
  "visible_editorial_analysis":sum(1 for x in rows if x.get("editorial_analysis_visible")),
  "visible_review_method":sum(1 for x in rows if x.get("review_method_visible")),
  "editorial_policy_linked":sum(1 for x in rows if x.get("editorial_policy_link_visible")),
  "phase16_full_provenance":sum(1 for x in rows if x.get("phase16_provenance_full"))
}
legacy_backlog=[x for x in rows if not x.get("phase16_provenance_full")]

outdir=Path("growthos-phase16-results"); outdir.mkdir(exist_ok=True)
(outdir/"post-trust-audit.json").write_text(json.dumps({"phase":16,"generated_at_utc":NOW,"summary":summary_counts,"posts":rows},ensure_ascii=False,indent=2),encoding="utf-8")
(outdir/"legacy-backlog.json").write_text(json.dumps({"phase":16,"generated_at_utc":NOW,"count":len(legacy_backlog),"posts":[{"id":x["id"],"title":x["title"],"url":x["url"],"missing":[k for k in ["sources_section_visible","editorial_analysis_visible","review_method_visible","editorial_policy_link_visible"] if not x.get(k)]} for x in legacy_backlog]},ensure_ascii=False,indent=2),encoding="utf-8")
(outdir/"editorial-contract-audit.json").write_text(json.dumps({"phase":16,"generated_at_utc":NOW,"hard_checks":contract_checks,"hard_pass":hard_pass,"policy_page":{"id":(policy_page or {}).get("id"),"url":policy_url,"public_http":policy_public_http}},ensure_ascii=False,indent=2),encoding="utf-8")
summary={
  "ok":hard_pass,
  "phase":16,
  "title":"Human Expertise & Editorial Trust",
  "generated_at_utc":NOW,
  "status":"PASS_EDITORIAL_TRUST_OS_WITH_LEGACY_BACKLOG" if hard_pass and legacy_backlog else ("PASS_EDITORIAL_TRUST_OS" if hard_pass else "FAIL"),
  "editorial_policy_page_id":(policy_page or {}).get("id"),
  "editorial_policy_url":policy_url,
  "published_normal_posts":len(rows),
  "current_full_provenance_posts":summary_counts["phase16_full_provenance"],
  "legacy_provenance_backlog":len(legacy_backlog),
  "article_schema_author_present":summary_counts["author_present"],
  "article_schema_author_identity_url_present":summary_counts["author_identity_url_present"],
  "fake_authors_created":0,
  "fake_reviewers_created":0,
  "named_human_experts_created":0,
  "future_article_engine_hardened":contract_checks["article_validator_requires_editorial_disclosure"],
  "future_news_engine_hardened":contract_checks["news_validator_requires_editorial_disclosure"],
  "next_backlog":[
    "Retrofit high-value legacy posts with visible sources, review method and editorial-policy linkage when content is actually re-reviewed.",
    "Add a named Person author/reviewer profile only after identity, role and expertise are verified.",
    "Use reviewedBy only when a real reviewer and review event are documented."
  ]
}
(outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print("GROWTHOS_PHASE16",json.dumps(summary,ensure_ascii=False))
if not hard_pass:
    raise SystemExit("Phase 16 editorial trust hard gate failed")
