from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

def lighthouse(url: str, runs: int=3) -> dict[str,Any]:
    samples=[]
    deep=[]
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
                net=(audits.get("network-requests") or {}).get("details",{}).get("items",[])
                top=sorted(net,key=lambda x:x.get("transferSize") or 0,reverse=True)[:25]
                deep=[{
                    "url":x.get("url"),"resource_type":x.get("resourceType"),
                    "transfer_size":x.get("transferSize"),"resource_size":x.get("resourceSize"),
                    "priority":x.get("priority")
                } for x in top]
        finally:
            try: os.remove(path)
            except OSError: pass
    good=[x for x in samples if not x.get("error") and x.get("lcp_ms") is not None]
    representative=sorted(good,key=lambda x:x["lcp_ms"])[len(good)//2] if good else None
    return {
        "samples":samples,"representative":representative,
        "successful_runs":len(good),"top_network_requests":deep
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
