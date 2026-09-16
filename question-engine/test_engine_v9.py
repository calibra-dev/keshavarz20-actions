#!/usr/bin/env python3
import importlib.util, os, random
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe9",os.path.join(ROOT,"engine_v9.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
q=m.q

ans="برای بررسی دقیق عکس برگ جوان و پیر، وضعیت ریشه، آزمایش آب و خاک و برنامه تغذیه قبلی را بفرستید."
sig=m.signals_from_answer(ans)
for required in {"leaf_position","root","water","soil","prior_program","analysis"}:
    assert required in sig,(required,sig)

top=m.topic_from_text("درختام زرد شدن و هنوز علائم کمبود روی برگ‌های جوان دیده میشه")
assert "plant_diagnosis" in top,top

p={"id":1,"name":"کود کامل نمونه","status":"publish","categories":[],"tags":[],"attributes":[],"description":"","short_description":"","reviews_allowed":True}
m._MEMORY_BY_PRODUCT[1]={"answered":1,"topics":{"plant_diagnosis"},"signals":sig,"question_ids":[10]}
cands=m.candidates_v9(p,"fertilizer","conversational",random.Random(11))
follow=[x for x in cands if x.get("intent")=="answer_memory_followup"]
assert follow, "answer-memory followup missing"
assert any(str(x.get("key") or "").startswith("followup:plant_diagnosis") for x in follow),follow
assert all(m.candidate_topic(x)!="plant_diagnosis" or x.get("intent")=="answer_memory_followup" for x in cands)

cfg={"watchdog_enabled":True,"watchdog_max_pending":60,"watchdog_max_consecutive_failures":3,"comment_status":"hold"}
state={"watchdog":{"consecutive_failures":0}}
assert m.watchdog_reason(cfg,state,{"pending_generated":59,"unexpected_types":[]},True) is None
assert m.watchdog_reason(cfg,state,{"pending_generated":60,"unexpected_types":[]},True)=="pending-queue-limit"
assert m.watchdog_reason(cfg,{"watchdog":{"consecutive_failures":3}},{"pending_generated":0,"unexpected_types":[]},True)=="consecutive-failures"
assert m.watchdog_reason(cfg,state,{"pending_generated":0,"unexpected_types":["review"]},True)=="unexpected-comment-type"

ok,reason=q.consistency_guard(p,{"intent":"answer_memory_followup","key":"bad"},"برای ادامه بررسی چه اطلاعاتی لازمه؟")
assert not ok and "followup" in reason,(ok,reason)
print("PASS v9")
