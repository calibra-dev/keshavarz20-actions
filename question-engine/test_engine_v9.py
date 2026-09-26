#!/usr/bin/env python3
import datetime as dt
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


# The pending watchdog is rolling-window based so a historical moderation
# backlog cannot permanently stop a healthy continuous campaign.
_orig_recent=q.recent_generated_comments
_orig_now=q.b.now_utc
try:
    fixed=dt.datetime(2026,9,26,6,0,0,tzinfo=dt.timezone.utc)
    q.b.now_utc=lambda: fixed
    q.recent_generated_comments=lambda cfg,limit=100: [
        {"status":"hold","type":"comment","date_gmt":"2026-09-26T05:00:00Z"},
        {"status":"hold","type":"comment","date_gmt":"2026-09-24T05:00:00Z"},
    ]
    snap=m.watchdog_snapshot({"watchdog_enabled":True,"watchdog_pending_window_hours":24,"watchdog_max_pending":90})
    assert snap["pending_generated"]==1,snap
    assert snap["pending_window_hours"]==24,snap
finally:
    q.recent_generated_comments=_orig_recent
    q.b.now_utc=_orig_now

ok,reason=q.consistency_guard(p,{"intent":"answer_memory_followup","key":"bad"},"برای ادامه بررسی چه اطلاعاتی لازمه؟")
assert not ok and "followup" in reason,(ok,reason)
print("PASS v9")
