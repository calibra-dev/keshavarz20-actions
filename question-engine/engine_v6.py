#!/usr/bin/env python3
import importlib.util, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe5",os.path.join(ROOT,"engine_v5.py")); v5=importlib.util.module_from_spec(spec); spec.loader.exec_module(v5)
q=v5.q
orig_candidates=q.guarded_candidates

GREET_ONLY={
 "colloquial":["سلام، ","سلام خسته نباشید، ","سلام، یه سوال داشتم؛ "],
 "conversational":["سلام وقت بخیر، ","سلام روزتون بخیر، ","وقت بخیر، ","سلام، یه سوال داشتم؛ "],
 "experienced":["سلام وقت بخیر، ","وقت بخیر، ","سلام خسته نباشید، "],
 "technical":["سلام وقت بخیر، ","وقت بخیر، ","سلام و احترام، "]}
OPEN_GUIDE={
 "colloquial":["سلام، ممنون میشم یه راهنمایی بدین؛ "],
 "conversational":["سلام، ممنون میشم راهنمایی کنید؛ "],
 "experienced":["سلام، ممنون میشم نظرتون رو بگین؛ "],
 "technical":["سلام و احترام، ممنون میشم راهنمایی بفرمایید؛ "]}
CLOSE_GUIDE={
 "colloquial":[" ممنون میشم راهنمایی کنین."," مرسی اگه راهنمایی کنین."],
 "conversational":[" ممنون میشم راهنمایی کنید."," اگر امکانش هست راهنمایی کنید."," ممنون میشم نظرتون رو بگین."],
 "experienced":[" ممنون میشم راهنمایی کنید."," ممنون میشم تجربه‌تون رو بگین."],
 "technical":[" ممنون میشم راهنمایی بفرمایید."," سپاسگزار می‌شم نظرتون رو بفرمایید."]}
CLOSE_THANK={
 "colloquial":[" ممنون."," مرسی."],
 "conversational":[" ممنون."," پیشاپیش ممنون."," سپاسگزارم."],
 "experienced":[" ممنون."," پیشاپیش ممنون."," سپاسگزارم."],
 "technical":[" سپاسگزارم."," پیشاپیش ممنون."]}

def wrap_v6(core,polite,style,rng):
    core=core.strip().rstrip(" .")
    if style=="colloquial":
        core=core.replace("می‌شود","میشه").replace("می‌توانید","می‌تونید").replace("پیشنهاد می‌کنید","پیشنهاد می‌دین").replace("می‌خواهم","می‌خوام")
    if not core.endswith("؟"):core+="؟"
    if not polite:return core
    style=style if style in GREET_ONLY else "conversational"
    mode=rng.choice(["open","close","both"])
    if mode=="open":
        if rng.random()<.25:return rng.choice(OPEN_GUIDE[style])+core
        return rng.choice(GREET_ONLY[style])+core
    if mode=="close":return core+rng.choice(CLOSE_GUIDE[style])
    if rng.random()<.5:return rng.choice(GREET_ONLY[style])+core+rng.choice(CLOSE_GUIDE[style])
    return rng.choice(OPEN_GUIDE[style])+core+rng.choice(CLOSE_THANK[style])

def candidates_v6(p,fam,style,rng):
    out=orig_candidates(p,fam,style,rng)
    if fam=="fitting" and q.fitting_subtype(p)=="tee":
        out=[x for x in out if x.get("key")!="tee:three-branches"]
        name=q.b.ref_name(p); n=q.b.norm(str(p.get("name") or ""))
        if "ماده" in n:
            core=f"اسم این قطعه {name} هست؛ برای اینکه اشتباه سفارش ندم، دو سر پلی‌اتیلن و رزوه ماده وسط هرکدوم دقیقاً چه سایزی هستن"
        else:
            core=f"برای انتخاب {name} باید سایز هر سه سر اتصال رو جدا بررسی کنم یا عبارت مساوی یعنی هر سه سر یک سایزن"
        out.append({"intent":"compatibility","key":"tee:three-branches","core":core})
    return out

q.guarded_candidates=candidates_v6
q.b.wrap=wrap_v6

def main():q.main()
if __name__=="__main__":main()
