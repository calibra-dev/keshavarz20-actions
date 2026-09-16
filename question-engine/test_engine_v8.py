#!/usr/bin/env python3
import importlib.util, os, random
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe8",os.path.join(ROOT,"engine_v8.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
q=m.q
p={"id":1,"name":"کود کامل نمونه","status":"publish","categories":[],"tags":[],"attributes":[],"description":"","short_description":"","reviews_allowed":True}
rng=random.Random(7)
cands=q.guarded_candidates(p,"fertilizer","conversational",rng)
exp=[x for x in cands if x.get("intent")=="experience_request"]
assert exp, "experience_request candidates missing"
for x in exp:
    text=x["core"]
    assert any(w in text for w in ["کسی","اگر کسی","تجربه واقعی"]), text
    assert "من استفاده کردم راضی بودم" not in text
ok,reason=q.consistency_guard(p,{"intent":"experience_request","key":"x"},"من استفاده کردم راضی بودم و پیشنهادش می‌کنم؟")
assert not ok and "testimonial" in reason, (ok,reason)
ok,reason=q.consistency_guard(p,{"intent":"experience_request","key":"x"},"کسی تجربه واقعی استفاده از این محصول رو داره؟")
assert ok, reason
print("PASS v8")
