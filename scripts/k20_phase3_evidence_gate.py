#!/usr/bin/env python3
import json, os
from pathlib import Path

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
try:
    overrides=json.load(open("phase3/verified-evidence-overrides.json",encoding="utf-8")).get("products",{})
except Exception:
    overrides={}

rows=[]
for x in pim.get("products",[]):
    pid=str(x["product_id"]); ov=overrides.get(pid,{})
    identifiers=x.get("stable_identifiers") or {}
    pimf=x.get("pim_fields") or {}
    missing=[]
    if not ((identifiers.get("gtin") or {}).get("value") or ov.get("gtin")): missing.append("gtin")
    if not ((identifiers.get("mpn") or {}).get("value") or ov.get("mpn")): missing.append("mpn")
    if not ((pimf.get("brand") or {}).get("value") or ov.get("brand")): missing.append("brand")
    for f in x.get("compatibility_missing_fields") or []:
        if not ov.get(f): missing.append(f)
    real_images_ok=(x.get("content") or {}).get("image_count",0)>=4 and (x.get("content") or {}).get("all_image_alt_present") is True
    if not real_images_ok and not ov.get("real_product_media_verified"): missing.append("real_product_media")
    row={
      "product_id":x["product_id"],"rank":x["rank"],"name":x["name"],"family":x["family"],
      "required_external_evidence":sorted(set(missing)),
      "status":"evidence_ready" if not missing else "needs_verified_evidence",
      "accepted_evidence_types":["manufacturer_datasheet","supplier_catalog","real_product_label_photo","verified_supplier_record"],
      "forbidden":["invented_gtin","invented_mpn","compatibility_by_size_alone","ai_image_as_real_product_evidence"]
    }
    rows.append(row)

summary={
 "products":len(rows),
 "evidence_ready":sum(1 for x in rows if x["status"]=="evidence_ready"),
 "blocked":sum(1 for x in rows if x["status"]!="evidence_ready"),
 "missing_gtin":sum(1 for x in rows if "gtin" in x["required_external_evidence"]),
 "missing_mpn":sum(1 for x in rows if "mpn" in x["required_external_evidence"]),
 "missing_brand":sum(1 for x in rows if "brand" in x["required_external_evidence"]),
 "missing_real_product_media":sum(1 for x in rows if "real_product_media" in x["required_external_evidence"]),
 "compatibility_blocked":sum(1 for x in rows if any(k in x["required_external_evidence"] for k in ["nominal_size","connection_type","material","pressure_class","connection_size","pressure_requirement","filtration_requirement","emitter_spacing","flow_rate","filtration_grade"]))
}
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":True,"version":"phase3-evidence-gate-v1","summary":summary,"products":rows},
          open("phase3-results/evidence-gate.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_EVIDENCE_GATE_OK",summary)
