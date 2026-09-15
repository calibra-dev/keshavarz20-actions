#!/usr/bin/env python3
import json, os, random, re, time
from urllib import parse, request
import importlib.util

ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe_base", os.path.join(ROOT,"engine.py"))
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

STATE_HEADER="این Issue فقط State عملیاتی عمومی موتور پرسش کشاورز بیست را نگه می‌دارد. هیچ اطلاعات مشتری، سفارش، رمز، توکن یا داده خصوصی نباید اینجا ثبت شود."
STATE_FOOTER="> Machine-managed. Do not edit while the engine is enabled."

class FastWP(b.WP):
    def products(self,cfg):
        out=[]; statuses=cfg.get("allow_product_statuses") or ["publish"]
        per=int(cfg.get("products_per_page",100))
        for status in statuses:
            for page in range(1,int(cfg.get("max_product_pages",20))+1):
                params=parse.urlencode({"per_page":per,"page":page,"status":status,"orderby":"id","order":"asc","_fields":"id,name,slug,status,permalink,categories,tags,reviews_allowed"})
                try: _,rows,hdr=self._call("GET","/wp-json/wc/v3/products?"+params)
                except RuntimeError as exc:
                    if "HTTP 400" in str(exc) and page>1: break
                    raise
                if not rows: break
                out.extend(rows)
                total=int(hdr.get("X-WP-TotalPages") or hdr.get("x-wp-totalpages") or 0)
                if (total and page>=total) or len(rows)<per: break
        return out

    def product(self,pid):
        fields="id,name,slug,status,permalink,categories,tags,attributes,short_description,description,reviews_allowed"
        _,obj,_=self._call("GET",f"/wp-json/wc/v3/products/{int(pid)}?_fields={fields}")
        return obj

    def comments(self,pages=5,per_page=100,post=None):
        out=[]
        for page in range(1,pages+1):
            q={"context":"edit","per_page":per_page,"page":page,"orderby":"date_gmt","order":"desc","_fields":"id,post,date,date_gmt,author_name,author_email,content,status,type"}
            if post: q["post"]=int(post)
            try: _,rows,hdr=self._call("GET","/wp-json/wp/v2/comments?"+parse.urlencode(q))
            except RuntimeError as exc:
                if "HTTP 400" in str(exc) and page>1: break
                raise
            if not rows: break
            out.extend(rows)
            total=int(hdr.get("X-WP-TotalPages") or hdr.get("x-wp-totalpages") or 0)
            if (total and page>=total) or len(rows)<per_page: break
        return out

def gh_call(method,path,body=None):
    token=os.environ.get("GH_TOKEN","").strip(); repo=os.environ.get("GITHUB_REPOSITORY","").strip()
    if not token or not repo: raise RuntimeError("Missing GH_TOKEN or GITHUB_REPOSITORY for engine state")
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"K20-Question-State/1.0"}
    data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False).encode("utf-8"); headers["Content-Type"]="application/json; charset=utf-8"
    req=request.Request(f"https://api.github.com/repos/{repo}{path}",data=data,headers=headers,method=method)
    with request.urlopen(req,timeout=60) as r:
        raw=r.read().decode("utf-8","replace"); return json.loads(raw) if raw else None

def default_state():
    return {"version":1,"sequence":0,"product_counts":{},"recent_product_ids":[],"total":0,"colloquial":0,"polite":0,"last_success_utc":None,"last_comment_id":None}

def read_state(cfg):
    issue=int(cfg.get("state_issue_number") or 0)
    if issue<=0: return default_state()
    obj=gh_call("GET",f"/issues/{issue}")
    body=str(obj.get("body") or "")
    m=re.search(r"```json\s*(\{.*?\})\s*```",body,re.S)
    if not m: raise RuntimeError("State issue does not contain a JSON state block")
    state=json.loads(m.group(1)); base=default_state(); base.update(state)
    base["product_counts"]={str(k):int(v) for k,v in (base.get("product_counts") or {}).items()}
    base["recent_product_ids"]=[int(x) for x in (base.get("recent_product_ids") or [])[:30]]
    return base

def write_state(cfg,state):
    issue=int(cfg.get("state_issue_number") or 0)
    if issue<=0: return
    safe={k:state.get(k) for k in ["version","sequence","product_counts","recent_product_ids","total","colloquial","polite","last_success_utc","last_comment_id"]}
    body=STATE_HEADER+"\n\n```json\n"+json.dumps(safe,ensure_ascii=False,separators=(",",":"))+"\n```\n\n"+STATE_FOOTER
    gh_call("PATCH",f"/issues/{issue}",{"body":body})

def due_from_state(state,cfg):
    last=b.parse_dt(state.get("last_success_utc"))
    if last:
        seed=f"comment:{state.get('last_comment_id')}:{state.get('sequence')}"
    else:
        last=b.parse_dt(cfg.get("campaign_start_utc")); seed=f"start:{cfg.get('campaign_start_utc')}"
    if not last: return None
    jitter=b.stable_jitter(seed,int(cfg["min_interval_seconds"]),int(cfg["max_interval_seconds"]))
    return last+b.dt.timedelta(seconds=jitter),jitter

def choose_product(products,state,rng):
    eligible=[p for p in products if p.get("status")=="publish" and p.get("reviews_allowed",True)]
    if not eligible: raise RuntimeError("No eligible published products with comments/reviews enabled")
    counts=state.get("product_counts") or {}; recent=set((state.get("recent_product_ids") or [])[:12])
    min_count=min(int(counts.get(str(p["id"]),0)) for p in eligible)
    pool=[p for p in eligible if int(counts.get(str(p["id"]),0))==min_count]
    fresh=[p for p in pool if int(p["id"]) not in recent]
    if fresh: pool=fresh
    return rng.choice(pool)

def style_from_state(state,cfg,rng):
    total=int(state.get("total") or 0); col=int(state.get("colloquial") or 0); target=float(cfg.get("colloquial_target",.15))
    if col < round(target*(total+1)): return "colloquial"
    r=rng.random()
    if r<.47:return "conversational"
    if r<.82:return "experienced"
    return "technical"

def polite_from_state(state,cfg,rng):
    total=int(state.get("total") or 0); count=int(state.get("polite") or 0); target=float(cfg.get("politeness_target",.70)); desired=round(target*(total+1))
    if count<desired:return True
    if count>desired:return False
    return rng.random()<target

def fitting_subtype(p):
    n=b.norm(str(p.get("name") or ""))
    if "کمربند" in n:return "saddle"
    if "تیپ" in n and ("لی فلت" in n or "لی‌فلت" in n):return "tape_to_layflat"
    if "زانو" in n:return "elbow"
    if "سه راه" in n or "سه‌راه" in n:return "tee"
    if "تبدیل" in n:return "reducer"
    if "فلنج" in n:return "flange"
    if "سرشلنگ" in n:return "hose_tail"
    if "درپوش" in n or "انتهای خط" in n:return "endcap"
    if "سوپاپ" in n:return "check_valve"
    if "رابط" in n:return "coupling"
    return "generic_fitting"

def valve_subtype(p):
    n=b.norm(str(p.get("name") or ""))
    if "تیپ" in n:return "tape_valve"
    if "لی فلت" in n or "لی‌فلت" in n:return "layflat_valve"
    if "پروانه" in n:return "butterfly"
    if "توپی" in n or "فلکه" in n:return "ball"
    return "generic_valve"

def guarded_candidates(p,fam,style,rng):
    base=b.core_candidates(p,fam,style,rng)
    general=[x for x in base if x.get("intent") in {"bulk","shipping","price_freshness","discount","complement","alternative","claim_challenge"}]
    name=b.ref_name(p); n=b.norm(str(p.get("name") or "")); out=list(base)
    def add(intent,key,core): out.append({"intent":intent,"key":key,"core":core})
    if fam=="fertilizer":
        crop=rng.choice(b.CROPS); orchard=rng.choice(b.ORCHARDS); area=rng.choice(["یک هکتار","۲ هکتار","۵ هکتار"])
        add("amount",f"fertilizer:amount:{b.norm(crop)}:{area}",f"{area} {crop} دارم؛ اگر این محصول برای کشت من مناسبه چه مقدار باید مصرف کنم و مقدار مصرف به روش آبیاری یا محلول‌پاشی فرق می‌کنه")
        add("orchard_method",f"fertilizer:orchard:{b.norm(orchard)}",f"باغ {orchard} دارم؛ این محصول رو اگر مناسب باغ من باشه بهتره از طریق آبیاری بدم یا محلول‌پاشی و سن درخت هم روی روش مصرف اثر داره")
    if fam=="drip_tape":
        crop=rng.choice(b.CROPS); area=rng.choice(["یک هکتار","۲ هکتار","۵ هکتار"])
        add("quantity",f"driptape:quantity:{b.norm(crop)}:{area}",f"{area} {crop} دارم؛ تقریباً چند رول نوار تیپ لازم میشه و برای حساب دقیق باید فاصله ردیف‌ها و طول هر ردیف رو هم بگم")
    if fam=="fitting":
        st=fitting_subtype(p); out=list(general)
        if st=="tape_to_layflat":
            no_washer="بدون واشر" in n
            add("comparison","tape-layflat:washer-compare",f"این مدل {'بدون واشره' if no_washer else 'واشردار هست'}؛ تفاوتش با مدل {'واشردار' if no_washer else 'بدون واشر'} از نظر نصب و آب‌بندی چیه و برای چه شرایطی کدوم بهتره")
            add("installation","tape-layflat:install",f"برای نصب درست {name} روی لی‌فلت چه نکاتی مهمه که بعداً دور محل اتصال نشتی ایجاد نشه")
            add("many_outlets","tape-layflat:many-outlets","اگر حدود ۱۰۰ ردیف نوار تیپ بخوام از خط لی‌فلت خروجی بگیرم، رابط ساده بهتره یا شیر لی‌فلت که هر ردیف رو جدا کنترل کنم")
            add("compatibility","tape-layflat:tape-compatibility",f"{name} به همه مدل‌های نوار تیپ می‌خوره یا برای انتخابش باید سایز یا نوع تیپ رو هم در نظر بگیرم")
            if no_washer:
                add("postuse","tape-layflat:leak:no-washer",f"این مدل بدون واشره؛ اگر بعد از نصب کمی نشتی داشته باشه اول کدوم بخش از نحوه نصب و جا رفتن رابط رو باید بررسی کنم")
            else:
                add("postuse","tape-layflat:leak:washer",f"اگر بعد از نصب {name} کمی نشتی داشته باشه اول جا افتادن واشر و نحوه نصب رو بررسی کنم یا عوامل دیگه‌ای هم مهمه")
        elif st=="saddle":
            out=list(general)
            add("compatibility","saddle:pipe-material",f"این کمربند روی چه جنس لوله‌هایی قابل استفاده است؛ روی پلی‌اتیلن و پولیکا روش نصب یکسانه یا نه")
            add("comparison","saddle:washer-alternative","نصاب گفته برای گرفتن خروجی از لوله با واشر کار کنم؛ از نظر دوام و احتمال نشتی چه زمانی کمربند انتخاب مطمئن‌تریه")
            add("installation","saddle:install",f"برای نصب {name} چطور بفهمم پیچ‌ها به اندازه کافی سفت شده‌اند و بیش از حد سفت کردن به لوله یا کمربند آسیب نمی‌زنه")
            add("postuse","saddle:leak",f"کمربند رو نصب کردم ولی دور خروجی کمی نشتی داره؛ قبل از سفت کردن بیشتر چه بخش‌هایی از نصب رو باید بررسی کنم")
        else:
            out=list(general)
            add("compatibility",f"{st}:compatibility",f"برای اینکه مطمئن بشم {name} به خط من می‌خوره، دقیقاً چه سایز و نوع اتصال دو طرف رو باید اعلام کنم")
            add("installation",f"{st}:install",f"برای نصب {name} چه قطعات یا آب‌بندی‌های مکملی لازمه که موقع اجرا چیزی کم نیارم")
            add("postuse",f"{st}:postuse",f"اگر بعد از نصب {name} نشتی یا لقی دیده بشه، قبل از تعویض قطعه چه مواردی از نصب باید بررسی بشه")
    if fam=="valve":
        st=valve_subtype(p); out=list(general)
        add("connection",f"valve:{st}:connection",f"برای نصب {name} روی خط هم‌سایز چه نوع رابط یا اتصال مکملی لازمه")
        add("postuse",f"valve:{st}:operation",f"اگر بعد از مدتی باز و بسته کردن {name} سفت بشه یا از محل اتصال نشتی ببینم، اول چه مواردی باید بررسی بشه")
        if st=="ball": add("nonag","valve:ball:building",f"از {name} برای خط آب ساختمان یا حیاط هم میشه استفاده کرد یا برای کار غیرکشاورزی بهتره مدل دیگه‌ای انتخاب کنم")
        if st in {"tape_valve","layflat_valve"}: add("many_outlets",f"valve:{st}:many-outlets","اگر تعداد زیادی خروجی داشته باشم، استفاده از شیر روی هر ردیف چه مزیتی نسبت به رابط ساده داره و چه زمانی ارزش هزینه بیشتر رو داره")
    return out

def consistency_guard(p,candidate,question):
    n=b.norm(str(p.get("name") or "")); q=b.norm(question); key=str(candidate.get("key") or "")
    if "بدون واشر" in n and any(x in q for x in ["واشر رو بررسی","واشر را بررسی","جا افتادن واشر"]):
        return False,"washer contradiction on no-washer product"
    if fitting_subtype(p)=="tape_to_layflat" and key in {"fitting:pvc","fitting:washer-vs-clamp","fitting:market-size","fitting:pe-size"}:
        return False,"irrelevant generic fitting intent"
    if fam_of(p)=="fertilizer" and "فشار کاری" in q:
        return False,"pressure intent on fertilizer"
    return True,None

def fam_of(p): return b.family(p)

def choose_candidate_v2(p,fam,existing,style,rng):
    candidates=guarded_candidates(p,fam,style,rng); rng.shuffle(candidates)
    seen=[]
    for x in candidates:
        core=x["core"]
        if any(b.jaccard(core,q)>=.72 for q in existing): continue
        ok,_=consistency_guard(p,x,core)
        if ok:return x
        seen.append(x.get("key"))
    raise RuntimeError(f"No consistent non-duplicate candidate for product {p.get('id')}; rejected={seen[:10]}")

def question_quality(p,q,candidate,fam,existing):
    score=b.quality(q,candidate,fam,existing)
    ok,reason=consistency_guard(p,candidate,q)
    return (score if ok else 0),reason

def prepare_plan(wp,cfg,state,rng):
    products=wp.products(cfg); basic=choose_product(products,state,rng); p=wp.product(int(basic["id"])); fam=fam_of(p)
    comments=wp.comments(pages=5,post=int(p["id"])); existing=[b.comment_text(x) for x in comments if b.comment_text(x)]
    style=style_from_state(state,cfg,rng); polite=polite_from_state(state,cfg,rng)
    candidate=choose_candidate_v2(p,fam,existing,style,rng); q=b.wrap(candidate["core"],polite,style,rng)
    score,reason=question_quality(p,q,candidate,fam,existing); threshold=int(cfg.get("quality_threshold",97))
    if score<threshold: raise RuntimeError(f"Quality/consistency gate failed: score={score} threshold={threshold} reason={reason}")
    return {"product":p,"family":fam,"candidate":candidate,"question":q,"style":style,"polite":polite,"score":score,"catalog_size":len(products)}

def public_plan(plan):
    p=plan["product"]
    return {"product_id":int(p["id"]),"product_name":p.get("name"),"product_url":p.get("permalink"),"family":plan["family"],"intent":plan["candidate"]["intent"],"semantic_key":plan["candidate"]["key"],"style":plan["style"],"polite":plan["polite"],"question":plan["question"],"quality_score":plan["score"],"catalog_size":plan["catalog_size"]}

def apply_state(state,plan,comment_id,submitted_at):
    pid=int(plan["product"]["id"]); counts=state.setdefault("product_counts",{}); counts[str(pid)]=int(counts.get(str(pid),0))+1
    recent=[pid]+[int(x) for x in state.get("recent_product_ids",[]) if int(x)!=pid]; state["recent_product_ids"]=recent[:30]
    state["sequence"]=int(state.get("sequence") or 0)+1; state["total"]=int(state.get("total") or 0)+1
    if plan["style"]=="colloquial":state["colloquial"]=int(state.get("colloquial") or 0)+1
    if plan["polite"]:state["polite"]=int(state.get("polite") or 0)+1
    state["last_success_utc"]=submitted_at; state["last_comment_id"]=int(comment_id)
    return state

def run(action,result_path):
    cfg=b.load_cfg(); wp=FastWP(); rng=random.SystemRandom(); state=read_state(cfg); now=b.now_utc()
    if action=="status":
        due=due_from_state(state,cfg)
        res={"ok":True,"action":action,"enabled":bool(cfg.get("enabled")),"state_sequence":state.get("sequence"),"questions_total":state.get("total"),"products_touched":len(state.get("product_counts") or {}),"colloquial":state.get("colloquial"),"polite":state.get("polite"),"next_due_utc":b.iso(due[0]) if due else None,"jitter_seconds":due[1] if due else None}
        b.write_result(result_path,res); return res
    if action=="scheduled":
        if not cfg.get("enabled"):
            res={"ok":True,"action":action,"skipped":"disabled"}; b.write_result(result_path,res); return res
        end=b.parse_dt(cfg.get("campaign_end_utc"))
        if end and now>=end:
            res={"ok":True,"action":action,"skipped":"campaign-ended","campaign_end_utc":b.iso(end)}; b.write_result(result_path,res); return res
        due=due_from_state(state,cfg)
        if not due: raise RuntimeError("Enabled campaign has no start/last-success timestamp")
        due_at,jitter=due; look=int(cfg.get("scheduler_lookahead_seconds",900))
        if due_at>now+b.dt.timedelta(seconds=look):
            res={"ok":True,"action":action,"skipped":"not-due-in-window","next_due_utc":b.iso(due_at),"jitter_seconds":jitter}; b.write_result(result_path,res); return res
        plan=prepare_plan(wp,cfg,state,rng)
        wait=max(0,(due_at-b.now_utc()).total_seconds())
        if wait: time.sleep(wait)
        action="submit_one_prepared"
    else:
        plan=prepare_plan(wp,cfg,state,rng)
    pub=public_plan(plan)
    if action=="dry_run":
        res={"ok":True,"action":action,**pub}; b.write_result(result_path,res); return res
    if action not in {"submit_one","submit_one_prepared"}: raise RuntimeError(f"Unsupported action: {action}")
    created=wp.submit_comment(pub["product_id"],pub["question"],cfg); cid=int(created.get("id") or 0)
    if cid<=0: raise RuntimeError("Comment create returned no id")
    rb=wp.comment(cid); actual=b.comment_text(rb)
    if int(rb.get("post") or 0)!=pub["product_id"] or b.norm(actual)!=b.norm(pub["question"]): raise RuntimeError("Comment readback mismatch")
    submitted=str(rb.get("date_gmt") or rb.get("date") or b.iso(b.now_utc()))
    new_state=apply_state(state,plan,cid,submitted); write_state(cfg,new_state)
    res={"ok":True,"action":"submit_one","comment_id":cid,"comment_status":rb.get("status"),"comment_type":rb.get("type"),"submitted_at_utc":submitted,**pub}
    b.write_result(result_path,res); return res

def main():
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--action",required=True,choices=["status","dry_run","submit_one","scheduled"]); ap.add_argument("--result",required=True); a=ap.parse_args()
    for k in ("WP_BASE_URL","WP_USERNAME","WP_APP_PASSWORD"):
        if not os.environ.get(k,"").strip(): raise SystemExit(f"Missing secret {k}")
    try:
        res=run(a.action,a.result); print(json.dumps(res,ensure_ascii=False))
    except Exception as exc:
        b.write_result(a.result,{"ok":False,"action":a.action,"error":str(exc)}); raise

if __name__=="__main__":main()
