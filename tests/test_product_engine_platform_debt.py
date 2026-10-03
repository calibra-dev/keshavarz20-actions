#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT / "product-engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0,str(ENGINE))

from perf import acceptance_delta, regressions

POLICY={
    "successful_runs":3,
    "performance":{"median_min":92,"each_run_min":91},
    "accessibility":{"median_min":92,"each_run_min":91},
    "best_practices":{"median_min":90,"each_run_min":90},
    "seo":{"median_min":96,"each_run_min":96},
    "lcp_median_max_ms":2500,
    "cls_each_run_max":0.1,
    "tbt_median_max_ms":200,
    "inherited_platform_debt_is_warning":True,
}

def sample(performance=67,accessibility=79,lcp=4455,tbt=180,runs=3):
    return {"summary":{
        "successful_runs":runs,
        "performance":{"median":performance,"min":performance,"max":performance},
        "accessibility":{"median":accessibility,"min":accessibility,"max":accessibility},
        "best_practices":{"median":92,"min":92,"max":92},
        "seo":{"median":100,"min":100,"max":100},
        "lcp_ms":{"median":lcp,"min":lcp,"max":lcp},
        "cls":{"median":0.02,"min":0.01,"max":0.03},
        "tbt_ms":{"median":tbt,"min":tbt,"max":tbt},
    }}

before=sample()
after=sample(performance=66,accessibility=78,lcp=4624,tbt=153)
delta=acceptance_delta(before,after,POLICY)
assert delta["ok"] is True, delta
assert not delta["new_reasons"], delta
assert "performance median below 92" in delta["inherited_reasons"], delta
assert "accessibility median below 92" in delta["inherited_reasons"], delta
assert "LCP median above gate" in delta["inherited_reasons"], delta
assert regressions(before,after)==[], regressions(before,after)

new_failure=sample(tbt=260)
delta2=acceptance_delta(before,new_failure,POLICY)
assert delta2["ok"] is False, delta2
assert "TBT median above gate" in delta2["new_reasons"], delta2

insufficient_before=sample(runs=2)
insufficient_after=sample(runs=2)
delta3=acceptance_delta(insufficient_before,insufficient_after,POLICY)
assert delta3["ok"] is False, delta3
assert any(x.startswith("successful Lighthouse runs <") for x in delta3["new_reasons"]), delta3

print("PRODUCT_PLATFORM_DEBT_GATE_OK")
