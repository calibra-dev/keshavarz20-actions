#!/usr/bin/env python3
import importlib.util
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe15", os.path.join(ROOT, "engine_v15.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


class FakeWP:
    def __init__(self, products):
        self._products = products
    def products(self, cfg):
        return list(self._products)
    def product(self, pid):
        return next(p for p in self._products if int(p["id"]) == int(pid))
    def comments(self, pages=5, post=None):
        return []


def product(pid, name):
    return {
        "id": pid,
        "name": name,
        "status": "publish",
        "permalink": f"https://example.test/{pid}",
        "categories": [],
        "tags": [],
        "attributes": [],
        "description": "",
        "short_description": "",
        "reviews_allowed": True,
    }


cfg = {
    "quality_threshold": 97,
    "colloquial_target": 0.15,
    "politeness_target": 0.70,
    "quality_retry_products": 4,
    "quality_retry_candidates": 8,
    "quality_retry_wraps": 1,
}
state = {
    "total": 0,
    "colloquial": 0,
    "polite": 0,
    "product_counts": {},
    "recent_product_ids": [],
}

# Test 1: a score-80 candidate must be rejected and a later score-100
# candidate on the same product must be selected instead of failing the run.
p1 = product(1, "محصول نمونه")
orig_choose_product = q.choose_product
orig_fam_of = q.fam_of
orig_candidates = q.guarded_candidates
orig_guard = q.consistency_guard
orig_quality = q.question_quality
orig_wrap = q.b.wrap
orig_style = q.style_from_state
orig_polite = q.polite_from_state

q.choose_product = lambda products, st, rng: products[0]
q.fam_of = lambda p: "generic"
q.guarded_candidates = lambda p, fam, style, rng: [
    {"intent": "weak", "key": "weak", "core": "سوال ضعیف نمونه"},
    {"intent": "good", "key": "good", "core": "سوال خوب و مرتبط نمونه"},
]
q.consistency_guard = lambda p, c, text: (True, None)
q.question_quality = lambda p, text, c, fam, existing: ((80, None) if c["key"] == "weak" else (100, None))
q.b.wrap = lambda core, polite, style, rng: core + "؟"
q.style_from_state = lambda st, cfg, rng: "conversational"
q.polite_from_state = lambda st, cfg, rng: True

plan = q.prepare_plan(FakeWP([p1]), cfg, state, random.Random(15))
assert plan["candidate"]["key"] == "good", plan
assert plan["score"] == 100, plan

# Test 2: if a whole product cannot meet threshold, planner must move to
# another product without lowering threshold.
p2 = product(2, "محصول دوم")
calls = []
def choose_two(products, st, rng):
    # The v15 shadow state raises rejected product counts; choose the lowest.
    counts = st.get("product_counts") or {}
    out = min(products, key=lambda p: int(counts.get(str(p["id"]), 0)))
    calls.append(int(out["id"]))
    return out
q.choose_product = choose_two
q.guarded_candidates = lambda p, fam, style, rng: [
    {"intent": "test", "key": f"p{p['id']}", "core": f"سوال محصول {p['id']}"}
]
q.question_quality = lambda p, text, c, fam, existing: ((80, None) if int(p["id"]) == 1 else (100, None))
plan = q.prepare_plan(FakeWP([p1, p2]), cfg, state, random.Random(16))
assert int(plan["product"]["id"]) == 2, plan
assert calls[:2] == [1, 2], calls
assert plan["score"] == 100, plan

# Restore shared module functions so this test remains self-contained if run
# in a broader harness.
q.choose_product = orig_choose_product
q.fam_of = orig_fam_of
q.guarded_candidates = orig_candidates
q.consistency_guard = orig_guard
q.question_quality = orig_quality
q.b.wrap = orig_wrap
q.style_from_state = orig_style
q.polite_from_state = orig_polite

print("PASS v15")
