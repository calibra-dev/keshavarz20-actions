#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"growthos-phase3-results"/"html-schema-feed-parity.json"
OUT=ROOT/"growthos-phase3-results"/"html-schema-feed-parity-summary-latest.json"

obj=json.loads(SRC.read_text(encoding="utf-8"))
failures=[]
for row in obj.get("failures",[]):
    checks=row.get("checks") or {}
    bad=[k for k,v in checks.items() if v is False]
    failures.append({
        "product_id":row.get("product_id"),
        "name":row.get("name"),
        "url":row.get("url"),
        "bad_checks":bad,
        "offer_schema_required":checks.get("offer_schema_required"),
        "error":row.get("error"),
    })
out={
    "phase":3,
    "generated_at_utc":obj.get("generated_at_utc"),
    "source_version":obj.get("version"),
    "ok":obj.get("ok"),
    "summary":obj.get("summary"),
    "acceptance":obj.get("acceptance"),
    "failure_count":len(failures),
    "failures":failures,
}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
