#!/usr/bin/env python3
import json, os, sys, glob, datetime

def load(p):
    with open(p,encoding="utf-8") as f:
        return json.load(f)

def main(out):
    policy=load("phase17/evidence-policy.json")
    cards=load("phase17/evidence-cards.json")
    qas=load("phase17/expert-qa-templates.json")
    case_gate=load("phase2-results/case-study-gate.json")
    required_card=policy["evidence_card_required_fields"]
    required_qa=policy["expert_qa_required_fields"]

    card_rows=[]
    for c in cards:
        miss=[k for k in required_card if k not in c or c[k] in (None,"",[])]
        valid=(not miss and c.get("status")=="verified" and bool(c.get("source_refs")))
        card_rows.append({"evidence_id":c.get("evidence_id"),"missing":miss,"valid":valid})

    qa_rows=[]
    for q in qas:
        miss=[k for k in required_qa if k not in q or q[k] in (None,"",[])]
        # evidence sources may intentionally be empty for a template that is explicitly non-publishable.
        if q.get("status")=="template_only" and "evidence_sources" in miss:
            miss.remove("evidence_sources")
        valid=(not miss and q.get("status")=="template_only" and q.get("reviewer")=="real_expert_required_before_publication")
        qa_rows.append({"template_id":q.get("template_id"),"missing":miss,"valid":valid})

    principles=policy.get("principles",{})
    anti_fake=all(principles.get(k) is True for k in [
        "impersonated_customer_forbidden",
        "invented_review_forbidden",
        "invented_case_outcome_forbidden",
        "negative_valid_review_suppression_forbidden",
        "method_date_limits_required",
        "consent_required_for_identifiable_case_study"
    ])

    cases_ok=(case_gate.get("ok") is True and case_gate.get("slots",0)>=4)
    cases_pub=int(case_gate.get("publication_ready",0))
    blocked=int(case_gate.get("blocked_real_evidence",0))
    no_fake_publish=(cases_pub==0 and blocked>=4)

    ok=(
        anti_fake and
        len(cards)>=3 and all(x["valid"] for x in card_rows) and
        len(qas)>=2 and all(x["valid"] for x in qa_rows) and
        cases_ok and no_fake_publish
    )

    rec={
      "phase":17,
      "title":"Evidence, Expert Q&A & Case Studies",
      "generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "status":"PASS" if ok else "PARTIAL",
      "verified_evidence_cards":sum(1 for x in card_rows if x["valid"]),
      "evidence_cards":card_rows,
      "expert_qa_templates":len(qa_rows),
      "expert_qa_valid":sum(1 for x in qa_rows if x["valid"]),
      "case_templates":case_gate.get("slots",0),
      "case_publication_ready":cases_pub,
      "case_blocked_real_evidence":blocked,
      "case_gate_preserved":cases_ok and no_fake_publish,
      "anti_fake_review_policy":anti_fake,
      "publication_note":"No customer identity, review, testimonial, project outcome, or case-study metric was invented. Case slots remain blocked until real evidence, consent and privacy review exist.",
      "site_mutations":0,
      "review_policy":policy.get("review_policy")
    }
    os.makedirs(os.path.dirname(out),exist_ok=True)
    with open(out,"w",encoding="utf-8") as f:
        json.dump(rec,f,ensure_ascii=False,indent=2)
    print("PHASE17",json.dumps(rec,ensure_ascii=False))
    if not ok:
        raise SystemExit(2)

if __name__=="__main__":
    main(sys.argv[1])
