#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("growthos-membership/customer-lifecycle-v1.json")
x=json.loads(p.read_text(encoding="utf-8"))
assert x["dependency"]["phase21_required_status"]=="PASS_MEMBERSHIP_VALUE_LIVE"
assert x["consent_rules"]["marketing_requires_explicit_consent"] is True
assert x["consent_rules"]["no_unsolicited_bulk_messaging"] is True
assert x["acceptance"]["live_trigger_execution_verified"] is False
states=x["states"]
for k in ["project_saved_no_proforma","proforma_requested_no_purchase","purchase_completed","seasonal_project_review_due"]:
    assert k in states
assert states["seasonal_project_review_due"]["marketing_message_allowed"]=="requires_explicit_marketing_consent"
print("PASS lifecycle contract")
