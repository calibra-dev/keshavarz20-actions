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

fitting={"id":2,"name":"رابط مساوی آبلوله 1 اینچ (32 میلیمتر)","status":"publish","categories":[],"tags":[],"attributes":[],"description":"","short_description":"","reviews_allowed":True}
fc=[x for x in q.guarded_candidates(fitting,"fitting","conversational",random.Random(11)) if x.get("intent")=="experience_request"]
assert fc, "fitting experience candidates missing"
for x in fc:
    text=q.b.norm(x["core"])
    assert "باز و بسته" not in text, x["core"]
    assert any(w in text for w in ["نشتی","آب بندی","آب‌بندی","اتصال","نصب"]), x["core"]

valve={"id":3,"name":"شیر توپی 2 اینچ","status":"publish","categories":[],"tags":[],"attributes":[],"description":"","short_description":"","reviews_allowed":True}
vc=[x for x in q.guarded_candidates(valve,"valve","conversational",random.Random(13)) if x.get("intent")=="experience_request"]
assert vc, "valve experience candidates missing"
assert any("باز و بسته" in q.b.norm(x["core"]) for x in vc), vc
print("PASS v8")
