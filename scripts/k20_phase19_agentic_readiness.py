#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
def load(p): return json.loads((ROOT/p).read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def main(result_path, projection_path):
    cfg=load("phase19/agentic-readiness.json")
    p11s=load("growthos-phase11-results/summary.json")
    p11f=load("growthos-phase11-results/openai-product-feed-readiness.json")
    p12s=load("growthos-phase12-results/summary.json")
    p12m=load("growthos-phase12-results/merchant-field-map.json")
    p12u=load("growthos-phase12-results/ucp-readiness-contract.json")
    p14=load("growthos-phase14-results/summary.json")
    p15=load("growthos-phase15-results/summary.json")
    p3=load("growthos-phase3-results/html-schema-feed-parity.json")
    fresh=load("phase19-results/upstream-refresh-latest.json")

    candidates=int(p11f.get("candidate_feed_rows") or 0)
    ready=int(p11f.get("fully_ready_rows") or 0)
    counts=p11f.get("field_complete_counts") or {}
    missing_brand=max(0,candidates-int(counts.get("brand") or 0))
    missing_price=max(0,candidates-int(counts.get("price") or 0))
    missing_description=max(0,candidates-int(counts.get("description") or 0))
    missing_image=max(0,candidates-int(counts.get("image_url") or 0))
    observed_currency=str(p11f.get("currency_code_observed") or "").strip()
    currency_policy=cfg.get("currency_export_policy") or {}
    currency_mapping_resolved=bool(currency_policy.get("conversion_rule_verified")) and bool(currency_policy.get("unit_conversion_verified")) and bool(currency_policy.get("external_iso4217_currency"))
    external_price_export_allowed=bool(currency_policy.get("external_price_export_allowed")) and currency_mapping_resolved
    external_submission_ready_rows=ready if external_price_export_allowed else 0

    checks=[]
    def add(name,v): checks.append({"name":name,"pass":bool(v)})

    add("manifest_v3",cfg.get("version")=="phase19-agentic-readiness-v3" and cfg.get("verified_official_sources_date")=="2026-10-03")
    fresh_stamp=str(fresh.get("observed_at_utc") or "")
    try:
        fresh_dt=dt.datetime.fromisoformat(fresh_stamp.replace("Z","+00:00"))
        fresh_age_hours=max(0.0,(dt.datetime.now(dt.timezone.utc)-fresh_dt).total_seconds()/3600.0)
    except Exception:
        fresh_age_hours=999999.0
    add("fresh_upstream_run_recorded",int(fresh.get("source_run_id") or 0)>0 and fresh.get("observed_from_successful_steps") is True)
    add("fresh_upstream_within_24h",fresh_age_hours<=24)
    add("fresh_upstream_counts_match_persisted",int((fresh.get("phase11") or {}).get("candidate_rows") or 0)==candidates and int((fresh.get("phase11") or {}).get("ready_rows") or 0)==ready and int((fresh.get("phase15") or {}).get("external_single_brand_ready_products") or 0)==int(counts.get("brand") or 0))
    add("fresh_upstream_statuses_pass",all(str((fresh.get(k) or {}).get("status","")).startswith("PASS_") for k in ["phase11","phase12","phase14","phase15"]))
    add("phase11_guarded_pass",p11s.get("ok") is True and str(p11s.get("status","")).startswith("PASS_"))
    p3s=p3.get("summary") or {}
    p3a=p3.get("acceptance") or {}
    try:
        p3_dt=dt.datetime.fromisoformat(str(p3.get("generated_at_utc") or "").replace("Z","+00:00"))
        p3_age_hours=max(0.0,(dt.datetime.now(dt.timezone.utc)-p3_dt).total_seconds()/3600.0)
    except Exception:
        p3_age_hours=999999.0
    add("phase3_full_catalog_parity_fresh",p3.get("ok") is True and p3_age_hours<=24 and int(p3s.get("published_products") or 0)==candidates and int(p3s.get("audited_products") or 0)==candidates and int(p3s.get("pass") or 0)==candidates and int(p3s.get("fail") if p3s.get("fail") is not None else 1)==0)
    add("phase3_schema_offer_truth_parity",int(p3s.get("eligible_product_schema_missing") or 0)==0 and int(p3s.get("eligible_offer_schema_missing") or 0)==0 and int(p3s.get("eligible_sku_mismatch") or 0)==0 and int(p3s.get("eligible_brand_mismatch_when_truth_known") or 0)==0 and int(p3s.get("eligible_price_parity_fail") or 0)==0 and int(p3s.get("eligible_availability_parity_fail") or 0)==0)
    add("phase3_nonpurchasable_schema_fail_closed",p3a.get("non_purchasable_offer_schema_not_fabricated") is True and p3a.get("all_hard_parity_checks_pass") is True)
    add("full_catalog_scope",candidates==int(p11f.get("published_parent_products") or 0) and candidates>=600)
    add("stable_item_ids_complete",int(counts.get("item_id") or 0)==candidates)
    add("stable_item_ids_unique",int(p11f.get("duplicate_item_id_count",99))==0)
    add("titles_complete",int(counts.get("title") or 0)==candidates)
    add("descriptions_complete",int(counts.get("description") or 0)==candidates)
    add("canonical_urls_complete",int(counts.get("url") or 0)==candidates)
    add("images_complete",int(counts.get("image_url") or 0)==candidates)
    add("availability_complete",int(counts.get("availability") or 0)==candidates)
    add("seller_name_complete",int(counts.get("seller_name") or 0)==candidates)
    add("readiness_math_consistent",ready==int(p11s.get("openai_feed_ready_rows") or -1) and ready<=int(counts.get("brand") or 0) and ready<=int(counts.get("price") or 0) and ready<=candidates)
    add("known_sku_conflict_not_feed_identity",((p11f.get("known_source_sku_conflict") or {}).get("feed_identity_impact")=="none_after_stable_id_mapping"))
    add("phase11_external_feed_not_submitted",p11s.get("direct_feed_submitted") is False and p11f.get("feed_submission_attempted") is False)
    add("phase11_partner_access_not_invented",p11s.get("direct_feed_partner_access_proven") is False)

    add("phase12_policy_guard_pass",p12s.get("ok") is True and p12s.get("merchant_center_submission_attempted") is False)
    add("phase12_iran_restriction_respected",p12s.get("merchant_center_iran_restriction_respected") is True and p12s.get("fake_country_or_address_used") is False)
    add("phase12_no_fake_country_address",p12s.get("fake_country_or_address_used") is False)
    add("phase12_ucp_profile_not_published",p12s.get("ucp_public_profile_published") is False and (p12u.get("publication_gate") or {}).get("publish_now") is False)
    add("phase12_ucp_adapter_not_claimed",p12s.get("ucp_live_adapter_claimed") is False)
    add("phase12_catalog_count_matches",int(p12s.get("merchant_candidate_rows") or 0)==candidates and int(p12s.get("merchant_basic_ready_rows") or 0)==ready)

    add("phase14_no_gtin_fabrication",int(p14.get("gtins_fabricated") or 0)==0 and int(p14.get("skus_promoted_to_gtin") or 0)==0)
    add("phase14_verified_gtin_truth_preserved",int(p14.get("source_verified_gtins") or 0)==0 and int(p14.get("unbacked_schema_gtin_products") or 0)==0)
    add("phase14_no_fake_resolver",int(p14.get("public_resolver_urls_created") or 0)==0)

    add("phase15_entity_pass",p15.get("ok") is True and p15.get("seller_entity_found") is True and p15.get("seller_name_consistent") is True)
    add("phase15_brand_truth_consistent",int(p15.get("brand_truth_mismatches",99))==0)
    add("phase15_brand_counts_match",
    int(p15.get("external_single_brand_ready_products") or 0)==int(counts.get("brand") or 0)
    and int(p15.get("external_brand_truth_gap_products") or 0)==missing_brand
    and int(p15.get("products_without_woo_brand") or 0)==0)
    add("phase15_no_identity_fabrication",int(p15.get("identity_fields_fabricated",99))==0 and int(p15.get("sameAs_links_fabricated",99))==0 and int(p15.get("glns_fabricated",99))==0)

    oa=cfg["openai_stable_feed"]; gu=cfg["google_ucp"]; gg=cfg["google_compatible_feed"]; lg=cfg["legal_policy_gate"]
    add("openai_required_field_contract_current",oa.get("required_fields")==["item_id","title","description","url","brand","seller_name","image_url","availability","price"])
    add("openai_snapshot_delivery_guarded",oa.get("delivery_model")=="full_snapshot" and oa.get("stable_filename_required") is True)
    add("openai_market_scope_fail_closed",oa.get("standard_openai_format_default_market")=="US" and oa.get("additional_markets_require_openai_confirmation") is True)
    add("openai_currency_export_fail_closed",observed_currency==currency_policy.get("observed_store_currency") and currency_mapping_resolved is False and external_price_export_allowed is False and external_submission_ready_rows==0)
    add("openai_api_delivery_current",oa.get("api_delivery_supported") is True and oa.get("partner_onboarding_required") is True and oa.get("stable_schema_required") is True)
    add("openai_no_submission_claim",oa.get("merchant_acceptance_or_feed_submission_claimed") is False and cfg.get("external_submission") is False)
    add("openai_no_checkout_claim",oa.get("checkout_claimed") is False)
    add("google_feed_submission_guarded",gg.get("enabled_for_submission") is False and gg.get("gtin_must_be_source_verified") is True and gg.get("identifier_exists_false_requires_truth_evidence") is True)
    add("google_merchant_api_current",gu.get("merchant_api_current") is True and gu.get("content_api_for_shopping_sunset_date")=="2026-08-18" and gu.get("content_api_for_shopping_used") is False and p12s.get("merchant_api_current") is True and p12s.get("content_api_for_shopping_used") is False)
    add("google_ucp_scope_current",gu.get("eligible_market_scope_claimed") is False and p12s.get("ucp_current_eligible_markets")==["US","CA","AU"] and p12s.get("ucp_keshavarz20_eligibility_claimed") is False)
    add("google_ucp_access_not_invented",gu.get("merchant_center_participation_claimed") is False and gu.get("eligible_market_scope_claimed") is False and gu.get("public_profile_publish_authorized") is False and gu.get("live_adapter_authorized") is False)
    add("google_ucp_checkout_not_claimed",gu.get("checkout_claimed") is False)
    add("legal_terms_not_falsely_accepted",lg.get("openai_merchant_terms_acceptance_claimed") is False and lg.get("commerce_policy_review_complete_claimed") is False and lg.get("legal_and_trade_compliance_complete_claimed") is False)
    add("payment_checkout_untouched",cfg["payment_checkout"]["authorized"] is False and int(cfg["payment_checkout"]["mutations_performed"] or 0)==0)
    add("secrets_not_persisted",cfg.get("secret_values_persisted") is False)

    passed=all(x["pass"] for x in checks)
    now=dt.datetime.now(dt.timezone.utc).isoformat()

    projection={
      "version":"k20-agentic-readiness-projection-v3",
      "generated_at_utc":now,
      "status":"FULL_CATALOG_INTERNAL_READINESS_ONLY_NOT_SUBMITTED_V3",
      "catalog":{
        "candidate_rows":candidates,
        "basic_field_complete_rows":ready,
        "basic_field_complete_percent":round(ready*100/candidates,2) if candidates else 0,
        "external_submission_ready_rows":external_submission_ready_rows,
        "external_submission_ready_percent":round(external_submission_ready_rows*100/candidates,2) if candidates else 0,
        "observed_store_currency":observed_currency,
        "external_iso4217_currency":currency_policy.get("external_iso4217_currency"),
        "currency_mapping_resolved":currency_mapping_resolved,
        "missing_brand_rows":missing_brand,
        "missing_price_rows":missing_price,
        "missing_description_rows":missing_description,
        "missing_image_rows":missing_image,
        "source_verified_gtin_rows":int(p14.get("source_verified_gtins") or 0)
      },
      "openai":{
        "required_fields":oa["required_fields"],
        "basic_field_complete_rows":ready,
        "external_submission_ready_rows":external_submission_ready_rows,
        "observed_store_currency":observed_currency,
        "external_iso4217_currency":currency_policy.get("external_iso4217_currency"),
        "currency_mapping_resolved":currency_mapping_resolved,
        "submission_allowed_now":False,
        "submission_blockers":[
          "approved OpenAI merchant/feed onboarding not proven",
          "legal/trade/merchant terms acceptance not claimed",
          f"{missing_brand} catalog rows lack source-backed brand",
          f"{missing_price} catalog rows lack current price",
          "store currency IRT has no verified external ISO 4217 unit/conversion mapping in this integration"
        ]
      },
      "google_compatible_feed":{
        "submission_allowed_now":False,
        "identifier_policy":"No SKU-to-GTIN/MPN promotion; identifier_exists=false is not asserted without source evidence."
      },
      "google_ucp":{
        "publication_allowed_now":False,
        "current_eligible_product_markets":["US","CA","AU"],
        "merchant_api_current":True,
        "content_api_for_shopping_used":False,
        "public_profile_published":bool(p12s.get("ucp_public_profile_published")),
        "live_adapter_claimed":bool(p12s.get("ucp_live_adapter_claimed")),
        "existing_woo_products_public":bool(p12s.get("woo_store_products_public")),
        "existing_woo_cart_public":bool(p12s.get("woo_store_cart_public"))
      },
      "external_submission":False,
      "price_values_persisted":False,
      "stock_values_persisted":False,
      "payment_checkout_mutations":0,
      "secret_values_persisted":False
    }

    result={
      "phase":19,
      "version":"phase19-agentic-readiness-v3",
      "title":"Feeds, APIs & Agentic Readiness",
      "status":"PASS_V3_FULL_CATALOG_GUARDED" if passed else "FAIL_V3",
      "generated_at_utc":now,
      "check_count":len(checks),
      "passed_checks":sum(1 for x in checks if x["pass"]),
      "failed_checks":[x["name"] for x in checks if not x["pass"]],
      "readiness":{
        "candidate_rows":candidates,
        "fully_ready_rows":ready,
        "ready_percent":round(ready*100/candidates,2) if candidates else 0,
        "rows_missing_brand":missing_brand,
        "rows_missing_price":missing_price,
        "rows_missing_description":missing_description,
        "rows_missing_image":missing_image,
        "source_verified_gtins":int(p14.get("source_verified_gtins") or 0),
        "products_without_woo_brand":int(p15.get("products_without_woo_brand") or 0),
        "external_brand_truth_gap_products":int(p15.get("external_brand_truth_gap_products") or 0),
        "pseudo_brand_products":int(p15.get("pseudo_brand_products") or 0),
        "multi_brand_ambiguous_products":int(p15.get("multi_brand_ambiguous_products") or 0)
      },
      "acceptance":{
        "full_catalog_governed":all(x["pass"] for x in checks if x["name"] in ["full_catalog_scope","stable_item_ids_complete","stable_item_ids_unique","titles_complete","descriptions_complete","canonical_urls_complete","images_complete","availability_complete","seller_name_complete"]),
        "page_schema_feed_parity_governed":all(x["pass"] for x in checks if x["name"].startswith("phase3_")),
        "openai_feed_architecture_ready_partial":p11s.get("ok") is True,
        "openai_external_rows_fail_closed":external_submission_ready_rows==0 and external_price_export_allowed is False,
        "google_compatible_feed_fail_closed":gg.get("enabled_for_submission") is False,
        "ucp_fail_closed_until_authorized":gu.get("public_profile_publish_authorized") is False and gu.get("live_adapter_authorized") is False,
        "merchant_api_current":gu.get("merchant_api_current") is True and gu.get("content_api_for_shopping_used") is False,
        "openai_file_and_api_contract_current":oa.get("api_delivery_supported") is True and oa.get("partner_onboarding_required") is True,
        "identifier_truth_preserved":int(p14.get("gtins_fabricated") or 0)==0 and int(p14.get("skus_promoted_to_gtin") or 0)==0,
        "entity_truth_preserved":int(p15.get("brand_truth_mismatches",99))==0,
        "external_submission":False,
        "payment_checkout_mutations":0
      },
      "checks":checks,
      "source_summaries":{"phase11":p11s,"phase12":p12s,"phase14":p14,"phase15":p15},
      "fresh_upstream_refresh_evidence":fresh,
      "fresh_upstream_age_hours":round(fresh_age_hours,3),
      "input_sha256":{
        "phase19/agentic-readiness.json":sha("phase19/agentic-readiness.json"),
        "growthos-phase11-results/openai-product-feed-readiness.json":sha("growthos-phase11-results/openai-product-feed-readiness.json"),
        "growthos-phase12-results/summary.json":sha("growthos-phase12-results/summary.json"),
        "growthos-phase14-results/summary.json":sha("growthos-phase14-results/summary.json"),
        "growthos-phase15-results/summary.json":sha("growthos-phase15-results/summary.json"),
        "phase19-results/upstream-refresh-latest.json":sha("phase19-results/upstream-refresh-latest.json"),
        "growthos-phase3-results/html-schema-feed-parity.json":sha("growthos-phase3-results/html-schema-feed-parity.json")
      },
      "external_submission":False,
      "site_mutations":0,
      "price_stock_mutations":0,
      "payment_checkout_mutations":0,
      "secret_values_persisted":False
    }

    rp=ROOT/result_path; pp=ROOT/projection_path
    rp.parent.mkdir(parents=True,exist_ok=True)
    pp.write_text(json.dumps(projection,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE19_V3",json.dumps({"status":result["status"],"checks":len(checks),"passed":result["passed_checks"],"failed":result["failed_checks"],"candidate_rows":candidates,"ready_rows":ready},ensure_ascii=False))
    if not passed: raise SystemExit(2)

if __name__=="__main__": main(sys.argv[1],sys.argv[2])
