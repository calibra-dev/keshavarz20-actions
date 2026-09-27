#!/usr/bin/env python3
import importlib.util
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe19", os.path.join(ROOT, "engine_v19.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


def product(name):
    return {
        "id": 1,
        "name": name,
        "status": "publish",
        "categories": [],
        "tags": [],
        "attributes": [],
        "description": "",
        "short_description": "",
        "reviews_allowed": True,
    }


p = product("نوار تیپ آبیاری 20 سانتی")
items = q.guarded_candidates(p, q.fam_of(p), "experienced", random.Random(19))
v19 = [x for x in items if str(x.get("key") or "").startswith("v19:")]
assert v19
for item in v19:
    ok, reason = q.consistency_guard(p, item, item["core"])
    assert ok, (item, reason)
    score, reason = q.question_quality(p, item["core"] + "؟", item, q.fam_of(p), [])
    assert score >= 97, (score, reason, item)

plan = {
    "product": {**p, "permalink": "https://keshavarz20.com/product/test/"},
    "family": q.fam_of(p),
    "candidate": v19[0],
    "question": v19[0]["core"] + "؟",
    "style": "experienced",
    "polite": False,
    "score": 100,
    "catalog_size": 1,
}
pub = q.public_plan(plan)
assert pub["engine_version"] == 19
assert pub["canonical_intent_id"].startswith("question-intent-")
assert pub["scenario_dimensions"]
assert pub["evidence_classification"] == "synthetic_editorial_question_generator_not_customer_evidence"

bad = {
    "intent": "selection",
    "key": "v19:test:fake-experience",
    "core": "من هفته پیش از شما خریدم و حالا می‌خوام بدونم این محصول خوبه",
}
ok, reason = q.consistency_guard(p, bad, bad["core"])
assert not ok and "experience" in reason

print("PASS v19")
