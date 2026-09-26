#!/usr/bin/env python3
import datetime, hashlib, json, os, sys

def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main(out):
    policy_path="phase17/evidence-policy.json"
    cards_path="phase17/evidence-cards.json"
    qas_path="phase17/expert-qa-templates.json"
    research_path="phase17/research-manifest.json"
    case_req_path="phase17/case-study-requirements.json"
    case_gate_path="phase2-results/case-study-gate.json"

    policy=load(policy_path)
    cards=load(cards_path)
    qas=load(qas_path)
    research=load(research_path)
    case_req=load(case_req_path)
    case_gate=load(case_gate_path)

    required_card=policy["evidence_card_required_fields"]
    required_qa=policy["expert_qa_required_fields"]

    card_rows=[]
    for c in cards:
        miss=[k for k in required_card if k not in c or c[k] in (None,"",[])]
        grade=c.get("evidence_grade")
        valid=(not miss and c.get("status")=="verified" and bool(c.get("source_refs")) and grade in ("A","B"))
        card_rows.append({
            "evidence_id":c.get("evidence_id"),
            "grade":grade,
            "source_type":c.get("source_type"),
            "missing":miss,
            "valid":valid
        })

    qa_rows=[]
    known_evidence={c.get("evidence_id") for c in cards if c.get("evidence_id")}
    for q in qas:
        miss=[k for k in required_qa if k not in q or q[k] in (None,"",[])]
        if q.get("status")=="template_only" and "evidence_sources" in miss:
            miss.remove("evidence_sources")
        refs=q.get("evidence_sources") or []
        refs_valid=all(x in known_evidence for x in refs)
        sd_ok=q.get("structured_data_policy")=="editorial_template_only_no_qapage"
        valid=(
            not miss and q.get("status")=="template_only"
            and q.get("reviewer")=="real_expert_required_before_publication"
            and refs_valid and sd_ok
        )
        qa_rows.append({
            "template_id":q.get("template_id"),
            "missing":miss,
            "evidence_refs_valid":refs_valid,
            "structured_data_guard":sd_ok,
            "valid":valid
        })

    principle_keys=[
        "impersonated_customer_forbidden",
        "invented_review_forbidden",
        "invented_case_outcome_forbidden",
        "negative_valid_review_suppression_forbidden",
        "method_date_limits_required",
        "consent_required_for_identifiable_case_study",
        "ai_image_cannot_substitute_for_technical_evidence",
        "unsupported_expert_identity_forbidden",
        "sku_must_not_be_promoted_to_gtin_without_source",
        "evidence_gap_must_remain_explicit",
        "static_editorial_qa_must_not_be_marked_qapage"
    ]
    principles=policy.get("principles",{})
    anti_fake=all(principles.get(k) is True for k in principle_keys)

    sd=policy.get("structured_data_guards",{})
    sd_keys=[
        "qapage_requires_single_question_focus",
        "qapage_requires_user_answer_submission",
        "static_editorial_qa_qapage_forbidden",
        "review_schema_requires_authentic_review",
        "fabricated_aggregate_rating_forbidden",
        "faq_rich_result_eligibility_not_assumed",
        "persian_reviews_system_language_coverage_not_assumed",
        "person_author_or_reviewer_identity_must_be_verified"
    ]
    structured_data_guard=all(sd.get(k) is True for k in sd_keys)

    research_sources=research.get("sources") or []
    official_primary=sum(1 for s in research_sources if s.get("authority")=="official_primary" and s.get("url") and s.get("applied_rule"))
    research_ok=(research.get("version")=="v2" and len(research_sources)>=5 and official_primary>=5)

    req_gates=case_req.get("gates") or {}
    case_requirements_ok=all(v is True for v in req_gates.values()) and len(case_req.get("publication_required_fields") or [])>=10
    cases_ok=(case_gate.get("ok") is True and int(case_gate.get("slots",0))>=4)
    cases_pub=int(case_gate.get("publication_ready",0))
    blocked=int(case_gate.get("blocked_real_evidence",0))
    no_fake_publish=(cases_pub==0 and blocked>=4)

    phase_inputs={}
    phase_expect={
        13:("growthos-phase13-results/summary.json","PASS_LIVE_ORIGIN_TRIAL"),
        14:("growthos-phase14-results/summary.json","PASS_GUARDED_NO_VERIFIED_GS1_IDS"),
        15:("growthos-phase15-results/summary.json","PASS_ENTITY_OS_WITH_SOURCE_GAPS"),
        16:("growthos-phase16-results/summary.json","PASS_EDITORIAL_TRUST_OS")
    }
    cross_phase_ok=True
    for phase,(p,expected) in phase_expect.items():
        data=load(p)
        good=(data.get("ok") is True and data.get("status")==expected)
        phase_inputs[str(phase)]={"path":p,"status":data.get("status"),"valid":good,"sha256":sha256_file(p)}
        cross_phase_ok = cross_phase_ok and good

    input_hashes={
        p:sha256_file(p) for p in [policy_path,cards_path,qas_path,research_path,case_req_path,case_gate_path]
    }

    grade_a=sum(1 for x in card_rows if x["valid"] and x["grade"]=="A")
    cards_ok=(len(cards)>=7 and grade_a>=7 and all(x["valid"] for x in card_rows))
    qas_ok=(len(qas)>=6 and all(x["valid"] for x in qa_rows))

    ok=all([
        policy.get("version")=="phase17-evidence-expert-case-v2",
        anti_fake, structured_data_guard, research_ok,
        cards_ok, qas_ok, case_requirements_ok,
        cases_ok, no_fake_publish, cross_phase_ok
    ])

    rec={
      "phase":17,
      "version":"phase17-evidence-expert-case-v2",
      "title":"Evidence, Expert Q&A & Case Studies",
      "generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "status":"PASS_V2" if ok else "PARTIAL_V2",
      "verified_evidence_cards":sum(1 for x in card_rows if x["valid"]),
      "grade_a_evidence_cards":grade_a,
      "evidence_cards":card_rows,
      "expert_qa_templates":len(qa_rows),
      "expert_qa_valid":sum(1 for x in qa_rows if x["valid"]),
      "official_primary_research_sources":official_primary,
      "research_manifest_valid":research_ok,
      "structured_data_guard":structured_data_guard,
      "anti_fake_review_policy":anti_fake,
      "case_templates":case_gate.get("slots",0),
      "case_publication_ready":cases_pub,
      "case_blocked_real_evidence":blocked,
      "case_gate_preserved":cases_ok and no_fake_publish and case_requirements_ok,
      "cross_phase_evidence_valid":cross_phase_ok,
      "cross_phase_inputs":phase_inputs,
      "input_sha256":input_hashes,
      "site_mutations":0,
      "price_stock_discount_mutations":0,
      "orders_created":0,
      "messages_sent":0,
      "publication_note":"No customer identity, review, testimonial, expert identity, project outcome, rating, GTIN, or case-study metric was invented. Static editorial Q&A remains non-QAPage. Case slots remain blocked until real evidence, consent, privacy review, measurement method, dates, limitations and verified reviewer identity exist.",
      "review_policy":policy.get("review_policy")
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out,"w",encoding="utf-8") as fh:
        json.dump(rec,fh,ensure_ascii=False,indent=2)
        fh.write("\n")
    print("PHASE17_V2",json.dumps(rec,ensure_ascii=False))
    if not ok:
        raise SystemExit(2)

if __name__=="__main__":
    main(sys.argv[1])
