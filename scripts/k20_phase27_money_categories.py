#!/usr/bin/env python3
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import unquote, urlsplit, urlunsplit
from html.parser import HTMLParser
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "phase27-input" / "money-category-modules-20261010.json"
OUTPUT = ROOT / "phase27-results" / "money-category-execution-20261010.json"

BASE = os.environ["WP_BASE_URL"].rstrip("/")
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
START = "<!--k20-phase27-money-category:start-->"
END = "<!--k20-phase27-money-category:end-->"

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def raw_description(obj):
    value = obj.get("description")
    if isinstance(value, dict):
        return value.get("raw") or value.get("rendered") or ""
    return value or ""

def hidden_artifacts(text):
    bad=set()
    for ch in text:
        cp=ord(ch)
        if (cp in {0x180E,0x200B,0x200C,0x200D,0x2060,0xFEFF}
            or 0x200E <= cp <= 0x200F
            or 0x202A <= cp <= 0x202E
            or 0x2066 <= cp <= 0x2069
            or 0xE0000 <= cp <= 0xE007F):
            bad.add(f"U+{cp:04X}")
    return sorted(bad)

class SemanticHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text=[]
        self.links=[]
    def handle_data(self,data):
        v=re.sub(r"\s+"," ",unescape(data)).strip()
        if v:
            self.text.append(v)
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a":
            href=dict(attrs).get("href")
            if href:
                self.links.append(href.strip())

def normalize_link(url):
    parts = urlsplit(unquote(url.strip()))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))

def signature(fragment):
    p=SemanticHTML()
    p.feed(fragment)
    return {
        "text":" ".join(p.text),
        "links":sorted({normalize_link(url) for url in p.links}),
    }

def get_category(session,cid):
    r=session.get(f"{BASE}/wp-json/wp/v2/product_cat/{cid}",params={"context":"edit"},timeout=60)
    r.raise_for_status()
    return r.json()

def write_category(session,cid,description):
    r=session.post(f"{BASE}/wp-json/wp/v2/product_cat/{cid}",json={"description":description},timeout=90)
    r.raise_for_status()
    return r.status_code

def desired(old,module):
    sc=old.count(START)
    ec=old.count(END)
    if sc==0 and ec==0:
        return (old.rstrip()+"\n\n"+module).strip(),"append"
    if sc!=1 or ec!=1:
        raise RuntimeError(f"marker integrity failure start={sc} end={ec}")
    a=old.index(START)
    b=old.index(END,a)+len(END)
    current=old[a:b]
    if signature(current)==signature(module):
        return old,"noop"
    return old[:a]+module+old[b:],"replace"

def public_get(url):
    sep="&" if "?" in url else "?"
    return requests.get(
        url+sep+"k20_phase27_verify="+str(int(time.time())),
        headers={"User-Agent":"K20-Phase27-Verify/1.0","Cache-Control":"no-cache"},
        timeout=60,
        allow_redirects=True,
    )

def main():
    data=json.loads(INPUT.read_text(encoding="utf-8"))
    categories=data["categories"]
    if len(categories)!=5:
        raise RuntimeError(f"expected 5 categories, got {len(categories)}")

    session=requests.Session()
    session.auth=AUTH
    session.headers.update({"Accept":"application/json","User-Agent":"K20-Phase27-MoneyCategories/1.0"})
    retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.0,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
    session.mount("https://",HTTPAdapter(max_retries=retry))
    session.mount("http://",HTTPAdapter(max_retries=retry))

    before={}
    changed=[]
    rows=[]
    try:
        for key,spec in categories.items():
            cid=int(key)
            module=spec["html"]
            if hidden_artifacts(module):
                raise RuntimeError(f"sanitizer gate failed for {cid}: {hidden_artifacts(module)}")
            if module.count(START)!=1 or module.count(END)!=1:
                raise RuntimeError(f"module marker count failed for {cid}")
            obj=get_category(session,cid)
            old=raw_description(obj)
            new,mode=desired(old,module)
            before[cid]=old
            if mode!="noop":
                write_category(session,cid,new)
                changed.append(cid)

            rb=get_category(session,cid)
            final=raw_description(rb)
            if final.count(START)!=1 or final.count(END)!=1:
                raise RuntimeError(f"readback marker count failed for {cid}")
            a=final.index(START)
            b=final.index(END,a)+len(END)
            final_module=final[a:b]
            if signature(final_module)!=signature(module):
                raise RuntimeError(f"semantic readback mismatch for {cid}")
            if hidden_artifacts(final_module):
                raise RuntimeError(f"readback sanitizer failure for {cid}")

            link=rb.get("link") or obj.get("link")
            pub=public_get(link)
            if pub.status_code!=200 or "k20-phase27-money-category:start" not in pub.text:
                raise RuntimeError(f"public verify failed for {cid} http={pub.status_code}")

            links=sorted(set(re.findall(r'href="(https://keshavarz20\.com/[^"]+)"',final_module)))
            product_links=[u for u in links if "/product/" in u]
            rows.append({
                "id":cid,
                "name":rb.get("name"),
                "link":link,
                "mode":mode,
                "before_sha256":sha256(old),
                "after_sha256":sha256(final),
                "old_chars":len(old),
                "new_chars":len(final),
                "product_links":len(product_links),
                "has_quote_link":any("request-quotation" in u for u in links),
                "has_comparator_link":any("irrigation-product-comparator" in u for u in links),
                "public_http":pub.status_code,
                "sanitizer_clean":not hidden_artifacts(final_module),
            })

        unique_links=sorted({u for row in rows for u in re.findall(r'https://keshavarz20\.com/[^"\s<]+', data["categories"][str(row["id"])]["html"])})
        checks=[]
        for u in unique_links:
            r=requests.get(u,headers={"User-Agent":"K20-Phase27-LinkCheck/1.0"},timeout=60,allow_redirects=True)
            checks.append({"url":u,"http":r.status_code,"final_url":r.url,"ok":r.status_code==200})
        if not all(x["ok"] for x in checks):
            raise RuntimeError("one or more Phase 27 links failed HTTP 200")
    except Exception:
        for cid in reversed(changed):
            try:
                write_category(session,cid,before[cid])
            except Exception:
                pass
        raise

    out={
        "schema_version":"k20-phase27-money-category-execution-v1",
        "phase":27,
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "status":"PASS",
        "scope_count":len(rows),
        "changed_count":len(changed),
        "noop_count":len(rows)-len(changed),
        "changed_ids":changed,
        "categories":rows,
        "link_checks":checks,
        "acceptance":{
            "five_money_categories":len(rows)==5,
            "all_public_http_200":all(r["public_http"]==200 for r in rows),
            "all_sanitized":all(r["sanitizer_clean"] for r in rows),
            "all_quote_links":all(r["has_quote_link"] for r in rows),
            "all_comparator_links":all(r["has_comparator_link"] for r in rows),
            "all_external_link_checks_ok":all(x["ok"] for x in checks),
            "price_writes":0,
            "stock_writes":0,
            "product_assignment_writes":0,
        },
        "guardrails":{
            "preserve_existing_description_outside_marker":True,
            "rollback_on_failure":True,
            "no_price_or_stock_write":True,
            "no_customer_or_order_data":True,
        },
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"status":"PASS","changed":len(changed),"categories":len(rows)},ensure_ascii=False))

if __name__=="__main__":
    main()
