from __future__ import annotations

import json
import os
import statistics
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
    compact={"selector":node.get("selector"),"snippet":node.get("snippet"),"node_label":node.get("nodeLabel")}
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
            if score is not None and score<1:
                items=(audit.get("details") or {}).get("items") or []
                out.append({
                    "category":category_id,"id":aid,"title":audit.get("title"),"score":score,
                    "display_value":audit.get("displayValue"),
                    "items":[_compact_item(x) for x in items[:12] if isinstance(x,dict)]
                })
    return out[:100]


def http_probe(url: str, runs: int=5) -> list[dict[str,Any]]:
    out=[]
    session=requests.Session()
    headers={"User-Agent":"Mozilla/5.0 Keshavarz20-Product-Audit/2.0","Accept":"text/html,application/xhtml+xml"}
    for i in range(runs):
        started=time.perf_counter()
        try:
            r=session.get(url,headers=headers,timeout=45,allow_redirects=True)
            h={k.lower():v for k,v in r.headers.items()}
            out.append({
                "run":i+1,"status":r.status_code,
                "elapsed_ms":round((time.perf_counter()-started)*1000,1),
                "bytes":len(r.content),"cache_control":h.get("cache-control"),
                "x_litespeed_cache":h.get("x-litespeed-cache"),
                "x_litespeed_cache_control":h.get("x-litespeed-cache-control"),
                "x_k20_canary_guard":h.get("x-k20-canary-guard"),
                "x_k20_recent_view":h.get("x-k20-recent-view"),
                "x_k20_wc_cache_compat":h.get("x-k20-wc-cache-compat"),
                "x_k20_wc_prevent_hook":h.get("x-k20-wc-prevent-hook"),
                "x_k20_donotcache":h.get("x-k20-donotcache"),
                "x_k20_ls_cacheable":h.get("x-k20-ls-cacheable"),
                "x_k20_preheader_cache":h.get("x-k20-preheader-cache"),
                "x_litespeed_tag":h.get("x-litespeed-tag"),"set_cookie":h.get("set-cookie"),
                "age":h.get("age"),"server":h.get("server"),"vary":h.get("vary")
            })
        except Exception as exc:
            out.append({"run":i+1,"error":f"{type(exc).__name__}: {exc}"})
    return out


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def summarize(result: dict[str,Any]) -> dict[str,Any]:
    good=[x for x in (result.get("samples") or []) if not x.get("error") and x.get("lcp_ms") is not None]
    out={"successful_runs":len(good)}
    for key in ("performance","accessibility","best_practices","seo","lcp_ms","cls","tbt_ms","ttfb_ms","total_bytes"):
        vals=[float(x[key]) for x in good if x.get(key) is not None]
        if vals:
            out[key]={"median":_median(vals),"min":min(vals),"max":max(vals)}
    return out


def lighthouse(url: str, runs: int=3) -> dict[str,Any]:
    samples=[]
    deep=[]
    diagnostics={}
    warmup={"attempted":True,"ok":False}
    fd,warm_path=tempfile.mkstemp(prefix="k20-product-warmup-",suffix=".json")
    os.close(fd)
    try:
        warm_cp=subprocess.run([
            "lighthouse",url,"--quiet",
            "--only-categories=performance",
            "--form-factor=mobile",
            "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
            "--output=json",f"--output-path={warm_path}"
        ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=260)
        warmup={"attempted":True,"ok":warm_cp.returncode==0,"returncode":warm_cp.returncode}
    except Exception as exc:
        warmup={"attempted":True,"ok":False,"error":f"{type(exc).__name__}: {exc}"}
    finally:
        try: os.remove(warm_path)
        except OSError: pass

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
                "fcp_ms":num("first-contentful-paint"),"lcp_ms":num("largest-contentful-paint"),
                "speed_index_ms":num("speed-index"),"tbt_ms":num("total-blocking-time"),
                "cls":num("cumulative-layout-shift"),"ttfb_ms":num("server-response-time"),
                "total_bytes":num("total-byte-weight"),
                "unused_css":(audits.get("unused-css-rules") or {}).get("displayValue"),
                "unused_js":(audits.get("unused-javascript") or {}).get("displayValue")
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
                    "cls_culprits":_audit_items(audits,"cls-culprits",30),
                    "non_composited_animations":_audit_items(audits,"non-composited-animations",30),
                    "unsized_images":_audit_items(audits,"unsized-images",30),
                    "render_blocking":_audit_items(audits,"render-blocking-resources",30),
                    "unused_css_items":_audit_items(audits,"unused-css-rules",30),
                    "unused_js_items":_audit_items(audits,"unused-javascript",30),
                    "long_tasks":_audit_items(audits,"long-tasks",20),
                    "mainthread_work":_audit_items(audits,"mainthread-work-breakdown",30),
                    "font_display":_audit_items(audits,"font-display",30),
                    "image_delivery":_audit_items(audits,"uses-optimized-images",30),
                    "modern_image_formats":_audit_items(audits,"modern-image-formats",30)
                }
        finally:
            try: os.remove(path)
            except OSError: pass
    good=[x for x in samples if not x.get("error") and x.get("lcp_ms") is not None]
    representative=sorted(good,key=lambda x:x["lcp_ms"])[len(good)//2] if good else None
    result={
        "samples":samples,"representative":representative,"successful_runs":len(good),
        "warmup":warmup,
        "top_network_requests":deep,"diagnostics":diagnostics
    }
    result["summary"]=summarize(result)
    return result


def acceptance(result: dict[str,Any], policy: dict[str,Any]) -> dict[str,Any]:
    summary=result.get("summary") or summarize(result)
    reasons=[]
    required=int(policy.get("successful_runs") or 3)
    if int(summary.get("successful_runs") or 0)<required:
        reasons.append(f"successful Lighthouse runs < {required}")
    for key in ("performance","accessibility","best_practices","seo"):
        cfg=policy.get(key) or {}
        stats=summary.get(key) or {}
        if not stats:
            reasons.append(f"{key} metrics unavailable")
            continue
        median_min=float(cfg.get("median_min") or 0)
        each_min=float(cfg.get("each_run_min") or 0)
        if float(stats.get("median") or 0)<median_min:
            reasons.append(f"{key} median below {median_min:g}")
        if float(stats.get("min") or 0)<each_min:
            reasons.append(f"{key} run below {each_min:g}")
    lcp=(summary.get("lcp_ms") or {}).get("median")
    cls=(summary.get("cls") or {}).get("max")
    tbt=(summary.get("tbt_ms") or {}).get("median")
    if lcp is None or float(lcp)>float(policy.get("lcp_median_max_ms") or 2500):
        reasons.append("LCP median above gate")
    if cls is None or float(cls)>float(policy.get("cls_each_run_max") or 0.1):
        reasons.append("CLS run above gate")
    if tbt is None or float(tbt)>float(policy.get("tbt_median_max_ms") or 200):
        reasons.append("TBT median above gate")
    return {"ok":not reasons,"reasons":reasons,"summary":summary}


def passes(result: dict[str,Any], policy: dict[str,Any] | None=None) -> bool:
    if policy is None:
        policy={
            "successful_runs":3,
            "performance":{"median_min":96,"each_run_min":96},
            "accessibility":{"median_min":96,"each_run_min":96},
            "best_practices":{"median_min":96,"each_run_min":96},
            "seo":{"median_min":96,"each_run_min":96},
            "cls_each_run_max":0.1,"tbt_median_max_ms":200,"lcp_median_max_ms":2500
        }
    return acceptance(result,policy)["ok"]


def regressions(before: dict[str,Any], after: dict[str,Any]) -> list[str]:
    b=before.get("summary") or summarize(before)
    a=after.get("summary") or summarize(after)
    if not b or not a:
        return []
    out=[]
    def med(obj: dict[str,Any],key: str) -> float:
        return float(((obj.get(key) or {}).get("median") or 0))
    if med(a,"lcp_ms")>med(b,"lcp_ms")+750:
        out.append("LCP median worsened by >750ms")
    if med(a,"tbt_ms")>med(b,"tbt_ms")+500:
        out.append("TBT median worsened by >500ms")
    if float(((a.get("cls") or {}).get("max") or 0))>max(0.1,float(((b.get("cls") or {}).get("max") or 0))+0.05):
        out.append("CLS regressed")
    if med(a,"performance")<med(b,"performance")-5:
        out.append("Performance median materially regressed")
    if med(a,"accessibility")<med(b,"accessibility")-2:
        out.append("Accessibility median materially regressed")
    return out
