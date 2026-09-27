#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVENTS=ROOT/"growthos-phase10-results"/"event-taxonomy.json"
INSTR=ROOT/"growthos-phase10-results"/"instrumentation-audit.json"
OUT21=ROOT/"growthos-roadmap-results"/"phase21-membership-value.json"
OUT22=ROOT/"growthos-roadmap-results"/"phase22-customer-lifecycle.json"

REQUIRED_MEMBER_EVENTS={
    "registration_completed",
    "project_saved",
    "calculation_saved",
    "technical_question_submitted",
    "proforma_requested",
}
REQUIRED_VALUE_SURFACES={
    "account",
    "saved_project",
    "saved_calculation",
    "question_history",
    "proforma_history",
}

def load(p): return json.loads(p.read_text(encoding="utf-8"))

def build():
    events=load(EVENTS)
    instr=load(INSTR)
    event_names={str(x.get("event")) for x in events.get("events",[])}
    missing_events=sorted(REQUIRED_MEMBER_EVENTS-event_names)
    tool_ready=all(bool(x.get("verified")) for x in instr.get("targets",[]))
    # Current repository has no verified account-backed storage evidence.
    verified_value_surfaces=set()
    missing_surfaces=sorted(REQUIRED_VALUE_SURFACES-verified_value_surfaces)
    p21={
      "roadmap_phase":21,
      "title":"Membership Value Engine",
      "reference_manifest":"2026-09-24",
      "valid_member_definition":"non-bot account with at least one qualified behavior: saved project/calculation, relevant product view, technical question, proforma, add-to-cart or purchase",
      "phase10_tool_measurement_ready":tool_ready,
      "observed_event_names":sorted(event_names),
      "required_member_events":sorted(REQUIRED_MEMBER_EVENTS),
      "missing_member_events":missing_events,
      "verified_account_backed_value_surfaces":sorted(verified_value_surfaces),
      "missing_value_surfaces":missing_surfaces,
      "acceptance":{
        "registration_has_measurable_reason":False,
        "saved_project_or_calculation_account_value":False,
        "qualified_member_event_tracking":False,
      },
      "status":"BLOCKED_MEMBERSHIP_VALUE_ENGINE_NOT_IMPLEMENTED",
      "next_gate":[
        "Implement account-backed saved project/calculation storage through an approved application/plugin path.",
        "Instrument registration_completed and qualified-member events and verify them in the analytics delivery path.",
        "Expose member value in My Account without collecting unnecessary sensitive data."
      ]
    }
    p22={
      "roadmap_phase":22,
      "title":"Customer Lifecycle & Retention",
      "reference_manifest":"2026-09-24",
      "dependency_phase21_status":p21["status"],
      "required_triggers":[
        "project_saved_but_no_proforma",
        "proforma_created_but_no_purchase",
        "purchase_completed_followup",
        "seasonal_project_review_due"
      ],
      "consent_rules":{
        "marketing_requires_consent":True,
        "transactional_and_service_messages_separate":True,
        "no_unsolicited_bulk_messaging":True,
        "no_sensitive_profile_inference":True
      },
      "acceptance":{
        "event_taxonomy_operational":False,
        "member_to_purchase_loop_operational":False,
        "consent_safe_trigger_execution_verified":False
      },
      "status":"BLOCKED_BY_PHASE21_AND_UNVERIFIED_RETENTION_EXECUTION",
      "next_gate":"Implement Phase 21 account-backed value/events first, then verify consent-safe lifecycle triggers end-to-end."
    }
    return p21,p22

def main():
    p21,p22=build()
    OUT21.parent.mkdir(parents=True,exist_ok=True)
    OUT21.write_text(json.dumps(p21,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    OUT22.write_text(json.dumps(p22,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"phase21":p21["status"],"phase22":p22["status"]},ensure_ascii=False))

if __name__=="__main__": main()
