from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from typing import Any

import requests

def _audit_items(audits: dict[str,Any], audit_id: str, limit: int=30) -> list[dict[str,Any]]:
    items=(audits.get(audit_id) or {}).get("details",{}).get("items",[])
    return items[:limit] if isinstance(items,list) else []

def _compact_item(item: dict[str,Any]) -> dict[str,Any]:
    node=item.get("node") or {}
    compact={
        "selector":node.get("selector"),
        "snippet":node.get("snippet"),
        "node_label":node.get("nodeLabel"),
    }
    for key in ("contrastRatio","expectedContrastRatio","fontSize","fontWeight","url","displayValue","failureSummary"):
        if key in item:
            compact[key]=item.get(key)
    return {k:v for k,v in compact.items() if v not in (None,"",[])}

def _category_failures(cats: dict[str,Any], audits: dict[str,Any]) -> list[dict[str,Any]]:
    out=[]
    for category_id in ("accessibility","best-practices","seo"):
        category=cats.get(category_id) or {}
        for ref in category.get("auditRefs") or []:
            aid=ref.get("id")
            audit=audits.get(aid) or {}
            score=audit.get("score")
            if score is not None and score < 1:
                items=(audit.get("details") or {}).get("items") or []
                out.append({
                    "category":category_id,
                    "id":aid,
                    "title":audit.get("title"),
                    "score":score,
                    "display_value":audit.get("displayValue"),
                    "items":[_compact_item(x) for x in items[:12] if isinstance(x,dict)],
                })
    return out[:100]

def http_probe(url: str, runs: int=5) -> list[dict[str,Any]]:
    out=[]
    session=requests.Session()
    headers={"User-Agent":"Mozilla/5.0 Keshavarz20-Product-Audit/1.0","Accept":"text/html,application/xhtml+xml"}
    for i in range(runs):
        started=time.perf_counter()
        try:
            r=session.get(url,headers=headers,timeout=45,allow_redirects=True)
            elapsed_ms=round((time.perf_counter()-started)*1000,1)
            h={k.lower():v for k,v in r.headers.items()}
            out.append({
                "run":i+1,
                "status":r.status_code,
                "elapsed_ms":elapsed_ms,
                "bytes":len(r.content),
                "cache_control":h.get("cache-control"),
                "x_litespeed_cache":h.get("x-litespeed-cache"),
                "x_litespeed_cache_control":h.get("x-litespeed-cache-control"),
                "x_litespeed_tag":h.get("x-litespeed-tag"),
                "set_cookie":h.get("set-cookie"),
                "age":h.get("age"),
                "server":h.get("server"),
                "vary":h.get("vary"),
            })
        except Exception as exc:
            out.append({"run":i+1,"error":f"{type(exc).__name__}: {exc}"})
    return out

def lighthouse(url: str, runs: int=3) -> dict[str,Any]:
    samples=[]
    deep=[]
    diagnostics={}
    for i in range(runs):
        fd,path=tempfile.mkstemp(prefix=f"k20-product-{i+1}-",suffix=".json")
        os.close(fd)
        try:
            cp=subprocess.run([
                "lighthouse",url,"--quiet",
                "--only-categories=performance,accessibility,best-practices,seo",
                "--form-factor=mobile",
                "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
                "--output=json",f"--output-path={path}"
            ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=260)
            if cp.returncode!=0:
                samples.append({"error":(cp.stderr or cp.stdout)[-1000:]})
                continue
            data=json.loads(open(path,encoding="utf-8").read())
            audits=data.get("audits") or {}
            cats=data.get("categories") or {}
            def num(aid: str):
                return (audits.get(aid) or {}).get("numericValue")
            metric={
                "performance":round(((cats.get("performance") or {}).get("score") or 0)*100),
                "accessibility":round(((cats.get("accessibility") or {}).get("score") or 0)*100),
                "best_practices":round(((cats.get("best-practices") or {}).get("score") or 0)*100),
                "seo":round(((cats.get("seo") or {}).get("score") or 0)*100),
                "fcp_ms":num("first-contentful-paint"),
                "lcp_ms":num("largest-contentful-paint"),
                "speed_index_ms":num("speed-index"),
                "tbt_ms":num("total-blocking-time"),
                "cls":num("cumulative-layout-shift"),
                "ttfb_ms":num("server-response-time"),
                "total_bytes":num("total-byte-weight"),
                "unused_css":(audits.get("unused-css-rules") or {}).get("displayValue"),
                "unused_js":(audits.get("unused-javascript") or {}).get("displayValue"),
            }
            samples.append(metric)
            if i==1:
                net=_audit_items(audits,"network-requests",200)
                top=sorted(net,key=lambda x:x.get("transferSize") or 0,reverse=True)[:25]
                deep=[{
                    "url":x.get("url"),"resource_type":x.get("resourceType"),
                    "transfer_size":x.get("transferSize"),"resource_size":x.get("resourceSize"),
                    "priority":x.get("priority")
                } for x in top]
                diagnostics={
                    "failing_audits":_category_failures(cats,audits),
                    "lcp_element":_audit_items(audits,"largest-contentful-paint-element",5),
                    "layout_shifts":_audit_items(audits,"layout-shifts",12),
                    "render_blocking":_audit_items(audits,"render-blocking-resources",30),
                    "unused_css_items":_audit_items(audits,"unused-css-rules",30),
                    "unused_js_items":_audit_items(audits,"unused-javascript",30),
                    "long_tasks":_audit_items(audits,"long-tasks",20),
                    "mainthread_work":_audit_items(audits,"mainthread-work-breakdown",30),
                    "font_display":_audit_items(audits,"font-display",30),
                    "image_delivery":_audit_items(audits,"uses-optimized-images",30),
                    "modern_image_formats":_audit_items(audits,"modern-image-formats",30),
                }
        finally:
            try: os.remove(path)
            except OSError: pass
    good=[x for x in samples if not x.get("error") and x.get("lcp_ms") is not None]
    representative=sorted(good,key=lambda x:x["lcp_ms"])[len(good)//2] if good else None
    return {
        "samples":samples,"representative":representative,
        "successful_runs":len(good),"top_network_requests":deep,
        "diagnostics":diagnostics
    }

def passes(result: dict[str,Any]) -> bool:
    m=result.get("representative") or {}
    return (
        result.get("successful_runs")==3
        and all(int(m.get(k) or 0)>=96 for k in ("performance","accessibility","best_practices","seo"))
        and float(m.get("cls") or 0)<=0.1
        and float(m.get("tbt_ms") or 999999)<=200
    )

def regressions(before: dict[str,Any], after: dict[str,Any]) -> list[str]:
    b=before.get("representative") or {}
    a=after.get("representative") or {}
    if not b or not a:
        return []
    out=[]
    if (a.get("lcp_ms") or 0)>(b.get("lcp_ms") or 0)+250:
        out.append("LCP worsened by >250ms")
    if (a.get("speed_index_ms") or 0)>(b.get("speed_index_ms") or 0)+500:
        out.append("Speed Index worsened by >500ms")
    if (a.get("cls") or 0)>max(0.1,(b.get("cls") or 0)+0.05):
        out.append("CLS regressed")
    if (a.get("performance") or 0)<(b.get("performance") or 0)-3:
        out.append("Performance score materially regressed")
    return out
