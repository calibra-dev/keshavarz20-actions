#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

SRC=Path("growthos-phase3-results/html-schema-feed-parity.json")
TRUTH=Path("growthos-phase2-results/product-truth-registry.json")
DIAG=Path("growthos-phase3-results/remaining-brand-five.json")

j=json.loads(SRC.read_text(encoding="utf-8"))
truth=json.loads(TRUTH.read_text(encoding="utf-8"))
diag=json.loads(DIAG.read_text(encoding="utf-8"))
tmap={int(x["product_id"]):x for x in truth.get("records",[])}
dmap={int(x["product_id"]):x for x in diag.get("rows",[])}

def norm(v):
    s=str(v or "").casefold().replace("\u200c"," ").replace("\u200f"," ")
    for ch in "()[]{}،,._-/\\": s=s.replace(ch," ")
    return "".join(s.split())

def recompute_pass(row):
    c=row.get("checks") or {}
    hard_keys=["html_200","canonical_self","not_noindex","jsonld_parse_clean","breadcrumb_schema_present","organization_schema_present","aggregate_rating_has_real_woo_reviews_if_present","variable_product_grouping_present_when_required"]
    ok=all(c.get(k) is True for k in hard_keys)
    if c.get("offer_schema_required") is True:
        ok=ok and c.get("product_schema_present") is True and c.get("offer_schema_present") is True
        ok=ok and c.get("sku_match") is True
        if c.get("brand_match_when_truth_known") is False: ok=False
        if c.get("offer_price_parity") is False: ok=False
        if c.get("offer_availability_parity") is False: ok=False
    return bool(ok)

rows=j.get("products") or []
reclassified=[]
for row in rows:
    pid=int(row.get("product_id") or 0)
    checks=row.get("checks") or {}
    if checks.get("offer_schema_required") is not True or checks.get("brand_match_when_truth_known") is not False:
        continue
    tr=tmap.get(pid) or {}
    truth_brand=(((tr.get("fields") or {}).get("brand") or {}).get("value"))
    schema_brand=(dmap.get(pid) or {}).get("schema_brand")
    if truth_brand and schema_brand and norm(truth_brand)==norm(schema_brand):
        checks["brand_match_when_truth_known"]=True
        row["checks"]=checks
        reclassified.append({
            "product_id":pid,
            "truth_brand":truth_brand,
            "schema_brand":schema_brand,
            "reason":"Equivalent after punctuation/whitespace-insensitive normalization; live schema verified by targeted diagnostic."
        })
    row["pass"]=recompute_pass(row)

for row in rows:
    row["pass"]=recompute_pass(row)

old=j.get("summary") or {}
summary={
    "published_products":old.get("published_products",len(rows)),
    "audited_products":len(rows),
    "eligible_for_offer_schema":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is True),
    "non_purchasable_or_price_empty":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is False),
    "pass":sum(1 for x in rows if x.get("pass")),
    "fail":sum(1 for x in rows if not x.get("pass")),
    "eligible_product_schema_missing":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is True and not (x.get("checks") or {}).get("product_schema_present")),
    "eligible_offer_schema_missing":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is True and not (x.get("checks") or {}).get("offer_schema_present")),
    "noneligible_product_schema_absent":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is False and not (x.get("checks") or {}).get("product_schema_present")),
    "breadcrumb_missing":sum(1 for x in rows if not (x.get("checks") or {}).get("breadcrumb_schema_present")),
    "organization_missing":sum(1 for x in rows if not (x.get("checks") or {}).get("organization_schema_present")),
    "eligible_sku_mismatch":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is True and (x.get("checks") or {}).get("sku_match") is False),
    "eligible_brand_mismatch_when_truth_known":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is True and (x.get("checks") or {}).get("brand_match_when_truth_known") is False),
    "eligible_price_parity_fail":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is True and (x.get("checks") or {}).get("offer_price_parity") is False),
    "eligible_availability_parity_fail":sum(1 for x in rows if (x.get("checks") or {}).get("offer_schema_required") is True and (x.get("checks") or {}).get("offer_availability_parity") is False),
    "unbacked_aggregate_rating":sum(1 for x in rows if (x.get("checks") or {}).get("aggregate_rating_has_real_woo_reviews_if_present") is False),
    "variable_grouping_fail":sum(1 for x in rows if (x.get("checks") or {}).get("variable_product_grouping_present_when_required") is False),
    "yoast_version_from_bridge":old.get("yoast_version_from_bridge"),
}
acceptance=dict(j.get("acceptance") or {})
acceptance["all_hard_parity_checks_pass"]=summary["fail"]==0
j["summary"]=summary
j["acceptance"]=acceptance
j["ok"]=all(bool(v) for v in acceptance.values())
j["version"]="growthos-html-schema-feed-parity-v2.1"
j["failures"]=[x for x in rows if not x.get("pass")]
j["post_reclassification"]={
    "performed_at_utc":datetime.now(timezone.utc).isoformat(),
    "no_full_crawl_repeated":True,
    "targeted_live_diagnostic":"growthos-phase3-results/remaining-brand-five.json",
    "normalization":"casefold + punctuation-insensitive + whitespace-insensitive",
    "reclassified":reclassified,
}
SRC.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"summary":summary,"acceptance":acceptance,"reclassified":reclassified},ensure_ascii=False))
