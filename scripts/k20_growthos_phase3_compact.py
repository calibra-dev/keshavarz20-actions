#!/usr/bin/env python3
import json
from pathlib import Path

src=Path("growthos-phase3-results/html-schema-feed-parity.json")
truthp=Path("growthos-phase2-results/product-truth-registry.json")
outp=Path("growthos-phase3-results/html-schema-feed-parity-summary.json")
j=json.loads(src.read_text(encoding="utf-8"))
truth=json.loads(truthp.read_text(encoding="utf-8")) if truthp.exists() else {"records":[]}
tmap={int(x["product_id"]):x for x in truth.get("records",[])}

def compact(row):
    pid=int(row.get("product_id") or 0)
    tr=tmap.get(pid,{})
    fields=tr.get("fields") or {}
    return {
      "product_id":pid,
      "name":row.get("name"),
      "product_type":tr.get("product_type"),
      "checks":row.get("checks"),
      "schema_counts":row.get("schema_counts"),
      "truth_brand_status":(fields.get("brand") or {}).get("status"),
      "truth_brand_value":(fields.get("brand") or {}).get("value"),
      "truth_sku_status":(fields.get("sku") or {}).get("status"),
      "truth_sku_value":(fields.get("sku") or {}).get("value"),
      "error":row.get("error"),
    }

rows=j.get("products") or []
buckets={}
preds={
 "product_schema_missing":lambda r:(r.get("checks") or {}).get("product_schema_present") is False,
 "offer_schema_missing":lambda r:(r.get("checks") or {}).get("offer_schema_present") is False,
 "sku_mismatch":lambda r:(r.get("checks") or {}).get("sku_match") is False,
 "brand_mismatch":lambda r:(r.get("checks") or {}).get("brand_match_when_truth_known") is False,
 "availability_mismatch":lambda r:(r.get("checks") or {}).get("offer_availability_parity") is False,
 "canonical_fail":lambda r:(r.get("checks") or {}).get("canonical_self") is False,
 "noindex":lambda r:(r.get("checks") or {}).get("not_noindex") is False,
 "variable_grouping_fail":lambda r:(r.get("checks") or {}).get("variable_product_grouping_present_when_required") is False,
}
for name,pred in preds.items():
    matches=[compact(r) for r in rows if pred(r)]
    type_counts={}
    for x in matches:
        t=x.get("product_type") or "UNKNOWN"
        type_counts[t]=type_counts.get(t,0)+1
    buckets[name]={"count":len(matches),"product_type_counts":type_counts,"sample":matches[:20]}

out={
 "phase":3,
 "version":"growthos-html-schema-feed-parity-diagnostic-v1",
 "source_version":j.get("version"),
 "generated_at_utc":j.get("generated_at_utc"),
 "summary":j.get("summary"),
 "acceptance":j.get("acceptance"),
 "buckets":buckets,
}
outp.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"summary":out["summary"],"buckets":{k:{"count":v["count"],"product_type_counts":v["product_type_counts"]} for k,v in buckets.items()}},ensure_ascii=False))
