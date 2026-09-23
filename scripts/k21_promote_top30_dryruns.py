#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/"bridge-v3-ops"
RESULTS=ROOT/"bridge-v3-results"

dryruns=sorted(OPS.glob("20260923-k21-top30-*-dryrun.json"))
if len(dryruns)!=30:
    raise SystemExit(f"Expected 30 dry-run requests, found {len(dryruns)}")

promoted=[]
for req_path in dryruns:
    stem=req_path.stem
    res_path=RESULTS/f"{stem}.json"
    if not res_path.exists():
        raise SystemExit(f"Missing dry-run result: {res_path.name}")
    res=json.loads(res_path.read_text(encoding="utf-8"))
    if not res.get("ok") or int(res.get("http_code") or 0)!=200 or res.get("error_code"):
        raise SystemExit(f"Dry-run failed policy gate: {res_path.name}: {res}")
    req=json.loads(req_path.read_text(encoding="utf-8"))
    if req.get("dry_run") is not True:
        raise SystemExit(f"Source request is not a dry-run: {req_path.name}")
    req["dry_run"]=False
    pid=int(req["path"].rstrip("/").split("/")[-1])
    req["request_id"]=f"k21-top30-{pid}-apply-20260923"
    out=OPS/f"20260923-k21-top30-{pid}-apply.json"
    out.write_text(json.dumps(req,ensure_ascii=False,indent=2),encoding="utf-8")
    promoted.append({"product_id":pid,"dry_run_result":str(res_path.relative_to(ROOT)),"apply_request":str(out.relative_to(ROOT))})

manifest=ROOT/"geo-aeo-results"/"k21-top30-apply-manifest.json"
manifest.write_text(json.dumps({"ok":True,"version":"k21-top30-apply-v1","products":promoted,"count":len(promoted),"policy":"Only dry-runs with ok=true, HTTP 200 and no error_code are promoted."},ensure_ascii=False,indent=2),encoding="utf-8")
print("K21_TOP30_PROMOTED",len(promoted))
