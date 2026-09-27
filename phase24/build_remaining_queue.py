#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/"phase24"/"prompt-bank-200-fa.json"
OBS=ROOT/"phase24"/"direct-observations-v2.json"
OUT=ROOT/"phase24-results"/"remaining-direct-surface-queue.json"

bank=json.loads(BANK.read_text(encoding="utf-8"))
obs=json.loads(OBS.read_text(encoding="utf-8"))
observed={x["prompt_id"] for x in obs.get("observations",[]) if x.get("evidence_type")=="DIRECT_SURFACE_CAPTURE"}
rows=[]
for row in bank.get("records",[]):
    if row.get("prompt_id") in observed:
        continue
    rows.append({
        "prompt_id":row.get("prompt_id"),
        "surface":row.get("planned_platform_model"),
        "intent_bucket":row.get("intent_bucket"),
        "prompt":row.get("prompt"),
        "execution_status":"PENDING_DIRECT_SURFACE_CAPTURE"
    })
by_surface={}
for row in rows:
    by_surface[row["surface"]]=by_surface.get(row["surface"],0)+1

out={
    "phase":24,
    "source_prompt_bank_count":len(bank.get("records",[])),
    "validated_observed_count":len(observed),
    "remaining_count":len(rows),
    "by_surface":by_surface,
    "rules":{
        "actual_named_surface_required":True,
        "ordinary_web_search_is_not_direct_capture":True,
        "referral_is_not_citation":True,
        "login_or_2fa_may_be_completed_only_in_the_actual_surface_session":True
    },
    "queue":rows
}
assert len(bank.get("records",[]))==200
assert len(observed)+len(rows)==200
assert by_surface.get("Google AI Mode / AI Overviews",0)==0
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"remaining":len(rows),"by_surface":by_surface},ensure_ascii=False))
