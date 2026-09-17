#!/usr/bin/env python3
import json, glob, os, sys
policy=json.load(open("phase2/case-study-evidence-policy.json",encoding="utf-8"))
req=policy["required_fields"]; rows=[]
for p in sorted(glob.glob("phase2/case-studies/slot-*.json")):
    x=json.load(open(p,encoding="utf-8"))
    missing=[k for k in req if k not in x or x[k] in (None,"",[])]
    gate=(not missing and x.get("status")=="evidence_ready" and bool(x.get("evidence_sources")) and
          x.get("consent") is True and x.get("privacy_review")=="pass")
    rows.append({"file":p,"case_id":x.get("case_id"),"status":x.get("status"),"missing":missing,"publication_ready":gate})
record={"ok":True,"required_cases":policy["required_cases"],"slots":len(rows),
        "publication_ready":sum(1 for x in rows if x["publication_ready"]),
        "blocked_real_evidence":sum(1 for x in rows if not x["publication_ready"]),"cases":rows}
os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True)
json.dump(record,open(sys.argv[1],"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("CASE_STUDY_GATE",record)
