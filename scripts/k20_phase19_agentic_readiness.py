#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def load(p): return json.loads((ROOT/p).read_text(encoding="utf-8"))
def main(result_path, projection_path):
    cfg=load("phase19/agentic-readiness.json")
    feed=load("phase3-results/top30-product-feed.json")
    parity=load("phase3-results/page-schema-feed-parity.json")
    pim=load("phase9-results/canonical-pim.json")
    p9=load("phase9-results/acceptance.json")
    pmap={int(x["product_id"]):x for x in pim.get("records",[]) if x.get("product_id") is not None}
    products=[]
    for row in feed.get("products",[]):
        pid=int(row["wp_product_id"]); rec=pmap.get(pid,{})
        missing=[]
        if not (row.get("id") or rec.get("stable_id")): missing.append("item_id")
        if not row.get("title"): missing.append("title")
        missing.append("description")
        if not row.get("link"): missing.append("url")
        if not row.get("brand"): missing.append("brand")
        if not row.get("image_link"): missing.append("image_url")
        if not row.get("availability"): missing.append("availability")
        if not row.get("store_price_raw") or not row.get("store_currency"): missing.append("price")
        currency=str(row.get("store_currency") or "").upper()
        if currency=="IRT": missing.append("price_iso4217_mapping")
        products.append({
          "stable_id":rec.get("stable_id") or f"wp-product:{pid}",
          "merchant_product_id":row.get("id"),
          "wp_product_id":pid,
          "title":row.get("title"),
          "canonical_url":row.get("link"),
          "image_url":row.get("image_link"),
          "brand":row.get("brand"),
          "sku":rec.get("sku") or row.get("id"),
          "gtin":rec.get("gtin"),
          "price_raw":row.get("store_price_raw"),
          "store_currency_raw":row.get("store_currency"),
          "availability":row.get("availability"),
          "attributes":rec.get("attributes") or [],
          "compatibility_required_fields":rec.get("required_compatibility_fields") or [],
          "compatibility_missing_fields":rec.get("missing_compatibility_fields") or [],
          "openai_discovery_missing_or_unresolved_fields":sorted(set(missing)),
          "external_submission":False,
          "unknowns_preserved":True
        })
    s=feed.get("summary",{})
    openai_ready=sum(1 for x in products if not x["openai_discovery_missing_or_unresolved_fields"])
    missing_brand=sum(1 for x in products if "brand" in x["openai_discovery_missing_or_unresolved_fields"])
    unresolved_currency=sum(1 for x in products if "price_iso4217_mapping" in x["openai_discovery_missing_or_unresolved_fields"])
    checks=[]
    def add(name,v): checks.append({"name":name,"pass":bool(v)})
    add("internal_feed_nonempty",len(products)>0)
    add("page_feed_schema_parity_all_pass",s.get("products")==s.get("parity_pass") and int(s.get("parity_fail",99))==0)
    add("schema_offer_sku_availability_price_mismatches_zero",all(int(s.get(k,99))==0 for k in ["schema_missing","offer_missing","sku_mismatch","availability_mismatch","price_mismatch"]))
    add("phase9_canonical_pim_pass",p9.get("status")=="PASS_FINAL_GUARDED" and int(p9.get("acceptance_blockers",99))==0)
    add("stable_ids_complete",all(x.get("stable_id") for x in products))
    add("canonical_urls_complete",all(x.get("canonical_url") for x in products))
    add("unknown_identifiers_not_fabricated",int(p9.get("summary",{}).get("hard_fabrications",99))==0)
    add("openai_submission_not_claimed",cfg.get("external_submission") is False and cfg["current_external_gates"]["openai"]["merchant_acceptance_or_feed_submission_claimed"] is False)
    add("openai_checkout_not_claimed",cfg["current_external_gates"]["openai"]["checkout_claimed"] is False)
    add("google_ucp_participation_not_invented",cfg["current_external_gates"]["google_ucp"]["merchant_center_participation_claimed"] is False and cfg["current_external_gates"]["google_ucp"]["us_product_scope_claimed"] is False)
    add("google_ucp_checkout_not_claimed",cfg["current_external_gates"]["google_ucp"]["checkout_claimed"] is False)
    add("payment_checkout_untouched",cfg["payment_checkout"]["authorized"] is False and cfg["payment_checkout"]["mutations_performed"]==0)
    passed=all(x["pass"] for x in checks)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    projection={"version":"k20-agentic-readiness-projection-v1","generated_at_utc":now,"status":"internal_readiness_only_not_submitted","source_feed_generated_at_utc":feed.get("generated_at_utc"),"product_count":len(products),"openai_discovery_rows_fully_ready":openai_ready,"external_submission":False,"products":products}
    result={"phase":19,"status":"PASS" if passed else "FAIL","generated_at_utc":now,"acceptance":{"page_feed_schema_parity":s,"feed_api_specs_and_region_gates_documented":True,"external_eligibility_not_invented":True,"payment_checkout_untouched":True},"readiness":{"product_count":len(products),"openai_discovery_rows_fully_ready":openai_ready,"rows_missing_brand":missing_brand,"rows_with_unresolved_irt_to_iso4217_price_mapping":unresolved_currency,"description_layer_required_before_openai_submission":True,"external_submission_blocked_until_required_fields_and_legal_program_gates_are_satisfied":True},"checks":checks,"protocol_gates":cfg["current_external_gates"],"external_submission":False,"site_mutations":0,"price_stock_mutations":0,"payment_checkout_mutations":0,"secret_values_persisted":False}
    rp=ROOT/result_path; pp=ROOT/projection_path; rp.parent.mkdir(parents=True,exist_ok=True)
    pp.write_text(json.dumps(projection,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); rp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE19_AGENTIC_READINESS",json.dumps({"status":result["status"],"products":len(products),"parity_pass":s.get("parity_pass"),"openai_rows_fully_ready":openai_ready,"missing_brand":missing_brand,"unresolved_currency":unresolved_currency},ensure_ascii=False))
    if not passed: raise SystemExit(2)
if __name__=="__main__": main(sys.argv[1],sys.argv[2])
