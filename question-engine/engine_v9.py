#!/usr/bin/env python3
import importlib.util, json, os, re
from urllib import parse

ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe8",os.path.join(ROOT,"engine_v8.py")); v8=importlib.util.module_from_spec(spec); spec.loader.exec_module(v8)
q=v8.q

orig_candidates=q.guarded_candidates
orig_guard=q.consistency_guard
orig_choose_product=q.choose_product
orig_read_state=q.read_state
orig_run=q.run

_MEMORY_BY_PRODUCT={}
_MEMORY_STATS_BY_PRODUCT={}

WATCHDOG_DEFAULT={
    "consecutive_failures":0,
    "paused_reason":None,
    "last_failure_utc":None,
    "last_health_utc":None,
    "pending_generated":0,
    "unexpected_types":[]
}


def _norm(text):
    return q.b.norm(str(text or ""))


def _comment_text(c):
    return q.b.comment_text(c)


def _is_generated(c,cfg):
    return (str(c.get("author_name") or "").strip()==str(cfg.get("author_name") or "").strip()
            or str(c.get("author_email") or "").strip().lower()==str(cfg.get("author_email") or "").strip().lower())


def _fetch_product_comments(product_id,cfg):
    wp=q.FastWP(); out=[]
    max_comments=max(20,int(cfg.get("answer_memory_max_comments_per_product",200)))
    pages=max(1,min(5,(max_comments+99)//100))
    for status in ("approve","hold"):
        for page in range(1,pages+1):
            params=parse.urlencode({
                "context":"edit","post":int(product_id),"status":status,
                "per_page":100,"page":page,"orderby":"date_gmt","order":"desc",
                "_fields":"id,post,parent,date,date_gmt,author_name,author_email,content,status,type"
            })
            try:
                _,rows,hdr=wp._call("GET","/wp-json/wp/v2/comments?"+params)
            except RuntimeError as exc:
                if "HTTP 400" in str(exc) and page>1: break
                raise
            if not rows: break
            out.extend(rows)
            total=int(hdr.get("X-WP-TotalPages") or hdr.get("x-wp-totalpages") or 0)
            if (total and page>=total) or len(rows)<100: break
    dedup={int(c.get("id") or 0):c for c in out if int(c.get("id") or 0)>0}
    return list(dedup.values())


def topic_from_text(text):
    n=_norm(text)
    topics=set()
    if any(x in n for x in ["ارسال","باربری","تحویل باربری","هزینه ارسال"]): topics.add("shipping")
    if any(x in n for x in ["قیمت","تخفیف","عمده","قیمت همکاری","پیش فاکتور","پیش‌فاکتور"]): topics.add("commerce")
    if any(x in n for x in ["زرد","علائم کمبود","برگ های جوان","برگ‌های جوان","برگ پیر","ریشه","کمبود غذایی"]): topics.add("plant_diagnosis")
    if any(x in n for x in ["اختلاط","ترکیب کنم","داخل یک تانک","با کودهای دیگه","کلسیم","کود آهن"]): topics.add("input_mix")
    if any(x in n for x in ["چند رول","تعداد رول","فاصله ردیف","طول ردیف"]): topics.add("irrigation_quantity")
    if any(x in n for x in ["دبی","افت فشار","اختلاف ارتفاع","فشار پمپ","طول مسیر","فشار ورودی"]): topics.add("hydraulic_sizing")
    if any(x in n for x in ["نصب","واشر","رزوه","کمربند","آب بندی","آب‌بندی","سایز لوله","نوع اتصال"]): topics.add("fit_install")
    if any(x in n for x in ["فیلتر","فیلتراسیون","شست وشو","شست‌وشو","گرفتگی"]): topics.add("maintenance")
    if any(x in n for x in ["تجربه واقعی","کسی تجربه","اگر کسی"]): topics.add("experience")
    if not topics: topics.add("general")
    return topics


def signals_from_answer(text):
    n=_norm(text); signals=set()
    mapping={
        "flow":["دبی"],
        "pressure":["فشار"],
        "length":["طول مسیر","طول ردیف","طول"],
        "elevation":["اختلاف ارتفاع","شیب"],
        "leaf_position":["برگ جوان","برگ های جوان","برگ‌های جوان","برگ پیر","برگ های پیر","برگ‌های پیر"],
        "root":["ریشه"],
        "water":["آب","ec","شوری آب"],
        "soil":["خاک","شوری خاک"],
        "prior_program":["کوددهی","برنامه غذایی","برنامه تغذیه","کود قبلی","سم قبلی"],
        "analysis":["آزمایش آب","آزمایش خاک","آنالیز آب","آنالیز خاک"],
        "size":["سایز","قطر"],
        "thread_connection":["رزوه","نوع اتصال"],
        "installation":["نصب","نصاب","آب بندی","آب‌بندی"],
        "shipping_method":["باربری","روش ارسال"],
        "proforma":["پیش فاکتور","پیش‌فاکتور"]
    }
    for key,terms in mapping.items():
        if any(_norm(t) in n for t in terms): signals.add(key)
    return signals


def read_answer_memory(product_id,cfg):
    if not cfg.get("answer_memory_enabled",True):
        return {"answered":0,"topics":set(),"signals":set(),"question_ids":[]}
    rows=_fetch_product_comments(product_id,cfg)
    parents={int(c["id"]):c for c in rows if int(c.get("parent") or 0)==0 and _is_generated(c,cfg)}
    topics=set(); signals=set(); answered_ids=[]
    for c in rows:
        parent=int(c.get("parent") or 0)
        if parent<=0 or parent not in parents or c.get("status")!="approved" and c.get("status")!="approve":
            continue
        if _is_generated(c,cfg):
            continue
        qtext=_comment_text(parents[parent]); atext=_comment_text(c)
        if not atext.strip():
            continue
        topics.update(topic_from_text(qtext)); signals.update(signals_from_answer(atext)); answered_ids.append(parent)
    return {"answered":len(set(answered_ids)),"topics":topics,"signals":signals,"question_ids":sorted(set(answered_ids))[-20:]}


def choose_product_v9(products,state,rng):
    p=orig_choose_product(products,state,rng)
    pid=int(p["id"]); cfg=q.b.load_cfg()
    mem=read_answer_memory(pid,cfg)
    _MEMORY_BY_PRODUCT[pid]=mem
    _MEMORY_STATS_BY_PRODUCT[pid]={"answered":mem["answered"],"topics":sorted(mem["topics"]),"signals":sorted(mem["signals"])}
    return p


def candidate_topic(candidate):
    key=str(candidate.get("key") or ""); intent=str(candidate.get("intent") or ""); text=str(candidate.get("core") or "")
    blob=_norm(key+" "+intent+" "+text)
    if "shipping" in key or "ارسال" in blob or "باربری" in blob:return "shipping"
    if any(x in key for x in ["price","discount","bulk"]) or intent in {"price_freshness","discount","bulk"}:return "commerce"
    if any(x in key for x in ["diagnosis","symptom","prior-program"]) or intent in {"diagnosis","orchard_diagnosis","post_use"} and any(x in blob for x in ["برگ","علائم","کمبود"]):return "plant_diagnosis"
    if "mix" in key or intent=="mix":return "input_mix"
    if any(x in key for x in ["quantity","area"]) and any(x in blob for x in ["رول","ردیف","تیپ"]):return "irrigation_quantity"
    if any(x in blob for x in ["دبی","افت فشار","اختلاف ارتفاع","فشار پمپ","طول مسیر"]):return "hydraulic_sizing"
    if intent in {"installation","compatibility","installer_scenario","post_install"} or any(x in blob for x in ["واشر","رزوه","آب بندی","آب‌بندی","نوع اتصال"]):return "fit_install"
    if any(x in blob for x in ["فیلتر","فیلتراسیون","شست","گرفتگی"]):return "maintenance"
    if intent=="experience_request":return "experience"
    return "general"


def _followups(p,fam,mem):
    name=q.b.ref_name(p); topics=set(mem.get("topics") or []); signals=set(mem.get("signals") or []); out=[]
    def add(topic,core): out.append({"intent":"answer_memory_followup","key":f"followup:{topic}:{int(mem.get('answered') or 0)}","core":core})
    if "plant_diagnosis" in topics and fam in {"fertilizer","pesticide"}:
        known=[]
        if "leaf_position" in signals: known.append("محل علائم روی برگ‌های جوان و پیر")
        if "root" in signals: known.append("وضعیت ریشه")
        if "prior_program" in signals: known.append("برنامه مصرف قبلی")
        if "water" in signals: known.append("شرایط آب")
        if "soil" in signals: known.append("شرایط خاک")
        context="، ".join(known[:4]) or "عکس برگ، وضعیت ریشه، آب و خاک"
        add("plant_diagnosis",f"برای ادامه بررسی همین مشکل، اگر {context} رو دقیق بفرستم، برای اینکه مشخص بشه {name} واقعاً انتخاب مناسبیه چه اطلاعات دیگه‌ای لازمه")
    if "hydraulic_sizing" in topics and fam in {"pipe","drip_tape","filter","sprinkler","fertigation"}:
        add("hydraulic_sizing",f"اگر دبی، فشار، طول مسیر و اختلاف ارتفاع رو داشته باشم، برای انتخاب دقیق {name} چه مشخصات دیگه‌ای از سیستم یا تعداد خروجی‌ها لازمه")
    if "fit_install" in topics and fam in {"fitting","valve"}:
        add("fit_install",f"اگر قطر واقعی لوله، نوع اتصال یا رزوه و محل نصب رو اعلام کنم، برای اینکه سازگاری {name} قطعی‌تر بررسی بشه چه مشخصه دیگه‌ای لازمه")
    if "input_mix" in topics and fam in {"fertilizer","pesticide"}:
        add("input_mix",f"اگر نام کامل محصولاتی که می‌خوام همراه {name} استفاده کنم و روش مصرف رو بفرستم، برای بررسی سازگاری ترکیب چه اطلاعات دیگه‌ای لازمه")
    if "maintenance" in topics and fam in {"filter","drip_tape","sprinkler"}:
        add("maintenance",f"برای ادامه عیب‌یابی {name} اگر دبی قبل و بعد، زمان آخرین شست‌وشو و وضعیت آب رو بگم، چه مورد دیگه‌ای لازمه بررسی بشه")
    return out


def candidates_v9(p,fam,style,rng):
    out=orig_candidates(p,fam,style,rng)
    mem=_MEMORY_BY_PRODUCT.get(int(p.get("id") or 0)) or {"answered":0,"topics":set(),"signals":set()}
    answered=set(mem.get("topics") or [])
    if not answered:return out
    filtered=[c for c in out if candidate_topic(c) not in answered]
    follow=_followups(p,fam,mem)
    return filtered+follow if filtered or follow else out


def guard_v9(p,candidate,question):
    ok,reason=orig_guard(p,candidate,question)
    if not ok:return ok,reason
    if candidate.get("intent")=="answer_memory_followup" and not str(candidate.get("key") or "").startswith("followup:"):
        return False,"answer-memory followup missing topic key"
    return True,None


def read_state_v9(cfg):
    state=orig_read_state(cfg)
    wd=dict(WATCHDOG_DEFAULT); wd.update(state.get("watchdog") or {}); state["watchdog"]=wd
    return state


def write_state_v9(cfg,state):
    issue=int(cfg.get("state_issue_number") or 0)
    if issue<=0:return
    wd=dict(WATCHDOG_DEFAULT); wd.update(state.get("watchdog") or {})
    safe={k:state.get(k) for k in ["version","sequence","product_counts","recent_product_ids","total","colloquial","polite","last_success_utc","last_comment_id"]}
    safe["watchdog"]={
        "consecutive_failures":int(wd.get("consecutive_failures") or 0),
        "paused_reason":wd.get("paused_reason"),
        "last_failure_utc":wd.get("last_failure_utc"),
        "last_health_utc":wd.get("last_health_utc"),
        "pending_generated":int(wd.get("pending_generated") or 0),
        "unexpected_types":list(wd.get("unexpected_types") or [])[:5]
    }
    body=q.STATE_HEADER+"\n\n```json\n"+json.dumps(safe,ensure_ascii=False,separators=(",",":"))+"\n```\n\n"+q.STATE_FOOTER
    q.gh_call("PATCH",f"/issues/{issue}",{"body":body})


def watchdog_snapshot(cfg):
    if not cfg.get("watchdog_enabled",True):
        return {"enabled":False,"pending_generated":0,"unexpected_types":[]}
    rows=q.recent_generated_comments(cfg,limit=100)
    pending=sum(1 for c in rows if c.get("status")=="hold")
    unexpected=sorted({str(c.get("type") or "") for c in rows if str(c.get("type") or "comment")!="comment"})
    return {"enabled":True,"pending_generated":pending,"unexpected_types":unexpected}


def watchdog_reason(cfg,state,snap,scheduled=True):
    if not cfg.get("watchdog_enabled",True):return None
    if cfg.get("comment_status","hold")!="hold":return "unsafe-comment-status"
    if snap.get("unexpected_types"):return "unexpected-comment-type"
    wd=state.get("watchdog") or {}
    if int(wd.get("consecutive_failures") or 0)>=int(cfg.get("watchdog_max_consecutive_failures",3)):
        return "consecutive-failures"
    if scheduled and int(snap.get("pending_generated") or 0)>=int(cfg.get("watchdog_max_pending",60)):
        return "pending-queue-limit"
    return None


def _update_watchdog(cfg,**changes):
    state=read_state_v9(cfg); wd=dict(WATCHDOG_DEFAULT); wd.update(state.get("watchdog") or {}); wd.update(changes); state["watchdog"]=wd; write_state_v9(cfg,state)


def run_v9(action,result_path):
    cfg=q.b.load_cfg(); state=read_state_v9(cfg); snap=watchdog_snapshot(cfg)
    reason=watchdog_reason(cfg,state,snap,scheduled=(action=="scheduled"))
    if action=="scheduled" and reason:
        wd=dict(state.get("watchdog") or {}); wd.update({"paused_reason":reason,"pending_generated":snap.get("pending_generated",0),"unexpected_types":snap.get("unexpected_types",[]),"last_health_utc":q.b.iso(q.b.now_utc())}); state["watchdog"]=wd; write_state_v9(cfg,state)
        res={"ok":True,"action":"scheduled","skipped":"watchdog-paused","watchdog_reason":reason,"pending_generated":snap.get("pending_generated",0)}; q.b.write_result(result_path,res); return res
    if action=="submit_one" and reason in {"unsafe-comment-status","unexpected-comment-type","consecutive-failures"}:
        raise RuntimeError("Watchdog blocked manual submit: "+reason)
    try:
        res=orig_run(action,result_path)
        if isinstance(res,dict):
            res["watchdog"]={"pending_generated":snap.get("pending_generated",0),"unexpected_types":snap.get("unexpected_types",[]),"consecutive_failures":int((state.get("watchdog") or {}).get("consecutive_failures") or 0)}
            pid=int(res.get("product_id") or 0)
            if pid and pid in _MEMORY_STATS_BY_PRODUCT:res["answer_memory"]=_MEMORY_STATS_BY_PRODUCT[pid]
            q.b.write_result(result_path,res)
        if isinstance(res,dict) and res.get("comment_id"):
            _update_watchdog(cfg,consecutive_failures=0,paused_reason=None,last_health_utc=q.b.iso(q.b.now_utc()),pending_generated=snap.get("pending_generated",0),unexpected_types=snap.get("unexpected_types",[]))
        return res
    except Exception:
        try:
            fresh=read_state_v9(cfg); wd=dict(WATCHDOG_DEFAULT); wd.update(fresh.get("watchdog") or {}); failures=int(wd.get("consecutive_failures") or 0)+1; wd.update({"consecutive_failures":failures,"last_failure_utc":q.b.iso(q.b.now_utc()),"pending_generated":snap.get("pending_generated",0),"unexpected_types":snap.get("unexpected_types",[])})
            if failures>=int(cfg.get("watchdog_max_consecutive_failures",3)):wd["paused_reason"]="consecutive-failures"
            fresh["watchdog"]=wd; write_state_v9(cfg,fresh)
        except Exception:
            pass
        raise


q.choose_product=choose_product_v9
q.guarded_candidates=candidates_v9
q.consistency_guard=guard_v9
q.read_state=read_state_v9
q.write_state=write_state_v9
q.run=run_v9


def main():q.main()
if __name__=="__main__":main()
