#!/usr/bin/env python3
import json, os, sys, datetime

MANIFEST="phase16-results/internal-link-authority-manifest-latest.json"

def main(outpath):
    with open(MANIFEST,encoding="utf-8") as f:
        m=json.load(f)

    recs=m.get("recommendations") or []
    urls=m.get("priority_zero_urls") or []
    checks=[]

    checks.append(("phase_is_16", m.get("phase")==16))
    checks.append(("manifest_mode_read_only", m.get("mode")=="read-only-manifest-first"))
    checks.append(("no_body_mutations", int(m.get("body_mutations", -1))==0))
    checks.append(("priority_broken_links_zero", int(m.get("proposed_priority_links_broken", -1))==0))
    checks.append(("orphan_count_matches_urls", int(m.get("orphan_priority_zero_count", -1))==len(urls)))
    checks.append(("orphan_count_matches_recommendations", int(m.get("orphan_priority_zero_count", -1))==len(recs)))
    checks.append(("recommendations_present", len(recs)>0))

    bad=[]
    for i,r in enumerate(recs):
        reasons=[]
        if r.get("priority") != 0:
            reasons.append("priority_not_zero")
        receiver=r.get("receiver")
        canonical=r.get("canonical_target")
        if not receiver or not canonical:
            reasons.append("missing_receiver_or_canonical")
        elif receiver != canonical:
            reasons.append("canonical_target_differs_from_receiver")
        status=int(r.get("receiver_http_status") or 0)
        if status < 200 or status >= 400:
            reasons.append(f"receiver_status_{status}")
        anchor=(r.get("anchor_candidate") or "").strip()
        if not anchor:
            reasons.append("missing_anchor")
        if anchor.startswith("http://") or anchor.startswith("https://"):
            reasons.append("anchor_is_url")
        if r.get("apply_state") != "apply-later-after-wave-gate":
            reasons.append("apply_state_not_gated")
        if not r.get("location_module"):
            reasons.append("missing_location_module")
        if not isinstance(r.get("donor_candidates"), list):
            reasons.append("donor_candidates_not_list")
        if not isinstance(r.get("conflict_cannibalization_flags"), list):
            reasons.append("conflict_flags_not_list")
        if reasons:
            bad.append({"index":i,"receiver":receiver,"reasons":reasons})

    checks.append(("all_priority_records_valid", len(bad)==0))

    apply_policy=(m.get("apply_policy") or "").lower()
    checks.append(("apply_policy_no_body_edits", "no body edits" in apply_policy))
    checks.append(("apply_policy_wave_gate", "wave 4" in apply_policy or "wave gate" in apply_policy))

    passed=all(ok for _,ok in checks)
    record={
      "phase":16,
      "title":"Internal Link Authority Graph — Acceptance Gate",
      "generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "status":"PASS" if passed else "FAIL",
      "manifest_commit_evidence":os.environ.get("PHASE16_MANIFEST_COMMIT") or None,
      "manifest_generated_at_utc":m.get("generated_at_utc"),
      "manifest_diagnostic_status":m.get("status"),
      "diagnostic_coverage_ratio":m.get("coverage_ratio"),
      "sitemap_urls":m.get("sitemap_urls"),
      "pages_fetched":m.get("pages_fetched"),
      "indexable_canonical_pages":m.get("indexable_canonical_pages"),
      "internal_graph_edges":m.get("internal_graph_edges"),
      "orphan_priority_zero_count":m.get("orphan_priority_zero_count"),
      "proposed_priority_links_broken":m.get("proposed_priority_links_broken"),
      "body_mutations":m.get("body_mutations"),
      "checks":[{"name":name,"pass":ok} for name,ok in checks],
      "invalid_recommendations":bad[:50],
      "invalid_recommendation_count":len(bad),
      "acceptance_basis":{
        "resource_lock":"link-manifest",
        "manifest_first":True,
        "no_concurrent_body_edits":True,
        "orphan_priority_zero":True,
        "canonical_targets_required":True,
        "broken_priority_links_zero":True,
        "apply_after_wave_gate":True,
        "note":"Coverage ratio is retained as a diagnostic metric; the package acceptance criteria do not define a minimum coverage percentage."
      }
    }

    os.makedirs(os.path.dirname(outpath),exist_ok=True)
    with open(outpath,"w",encoding="utf-8") as f:
        json.dump(record,f,ensure_ascii=False,indent=2)
    print("PHASE16_ACCEPTANCE",json.dumps({
      "status":record["status"],
      "orphan_priority_zero_count":record["orphan_priority_zero_count"],
      "broken":record["proposed_priority_links_broken"],
      "body_mutations":record["body_mutations"],
      "invalid_recommendations":record["invalid_recommendation_count"],
      "diagnostic_coverage_ratio":record["diagnostic_coverage_ratio"]
    },ensure_ascii=False))
    if not passed:
        raise SystemExit(2)

if __name__=="__main__":
    main(sys.argv[1])
