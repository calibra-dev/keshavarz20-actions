#!/usr/bin/env python3
import importlib.util, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe4",os.path.join(ROOT,"engine_v4.py")); v4=importlib.util.module_from_spec(spec); spec.loader.exec_module(v4)
q=v4.q
orig_candidates=q.guarded_candidates
orig_guard=q.consistency_guard

def candidates_v5(p,fam,style,rng):
    out=orig_candidates(p,fam,style,rng)
    if fam!="fitting": return out
    st=q.fitting_subtype(p); name=q.b.ref_name(p)
    if st in {"saddle","tape_to_layflat"}: return out
    general=[x for x in out if x.get("intent") in {"bulk","shipping","price_freshness","discount","complement","alternative","claim_challenge"}]
    out=list(general)
    def add(intent,key,core):out.append({"intent":intent,"key":key,"core":core})
    if st=="check_valve":
        add("selection","check-valve:pump-line",f"برای اینکه مطمئن بشم {name} برای خط من مناسبه، چه مشخصاتی از پمپ، سایز لوله و نوع اتصال باید بگم")
        add("market_size","check-valve:market-size","نصاب گفته لوله‌ای که دارم سایز ۵ ساختمانیه؛ برای اینکه سوپاپ درست بگیرم چطور باید سایزش رو به اینچ یا میلی‌متر مشخص کنم")
        add("problem","check-valve:backflow",f"اگر بعد از خاموش شدن پمپ آب خط برگرده، برای اینکه بفهمم {name} انتخاب مناسبیه چه چیزهایی از مسیر مکش و نصب باید بررسی بشه")
        add("installation","check-valve:install",f"برای نصب {name} چه اطلاعاتی از جهت جریان، محل نصب و اتصال لوله لازمه تا مدل اشتباه انتخاب نکنم")
        add("postuse","check-valve:postuse",f"اگر {name} نصب شده باشه ولی پمپ بعد از خاموش شدن دوباره نیاز به هواگیری یا پر کردن داشته باشه، قبل از تعویض سوپاپ چه مواردی باید بررسی بشه")
    elif st=="endcap":
        add("compatibility","endcap:pipe",f"برای انتخاب {name} فقط سایز اسمی لوله کافیه یا نوع لوله و قطر واقعی هم باید مشخص باشه")
        add("installation","endcap:install",f"برای بستن انتهای خط با {name} چه روش نصبی باعث میشه نشتی و باز شدن انتهای خط کمتر بشه")
        add("alternative","endcap:alternative",f"برای انتهای خط استفاده از {name} بهتره یا روش تا زدن و بست؛ انتخاب بین این دو به چه شرایطی بستگی داره")
    elif st=="flange":
        add("compatibility","flange:match",f"برای اینکه {name} به فلنج مقابل بخوره چه مشخصاتی مثل سایز، نوع اتصال و سوراخ‌کاری رو باید تطبیق بدم")
        add("installation","flange:seal",f"برای نصب {name} چه واشر یا آب‌بندی و چه اطلاعاتی از فلنج مقابل لازمه که نشتی ایجاد نشه")
    elif st=="hose_tail":
        add("compatibility","hose-tail:both-sides",f"برای انتخاب {name} باید قطر شلنگ یا لوله از یک طرف و نوع اتصال سمت شیر یا خط اصلی از طرف دیگه رو اعلام کنم")
        add("installation","hose-tail:clamp",f"برای بستن شلنگ روی {name} چه نوع بستی مناسبه و از کجا بفهمم اتصال به اندازه کافی محکم شده")
    elif st=="tee":
        add("compatibility","tee:three-branches",f"برای انتخاب {name} باید سایز هر سه شاخه رو جدا مشخص کنم یا اگر اسم قطعه مساوی باشه هر سه خروجی یک سایزن")
        add("design","tee:branch-flow",f"اگر از {name} برای گرفتن انشعاب استفاده کنم، دبی شاخه فرعی هم روی انتخاب سایز سه‌راهی اثر داره")
    elif st=="elbow":
        add("compatibility","elbow:line",f"برای انتخاب {name} نوع لوله و سایز اتصال دو سمت رو باید چطور تطبیق بدم")
        add("installation","elbow:turn",f"برای تغییر مسیر خط با {name} در محل زانو چه نکات نصبی مهمه که اتصال تحت فشار یا تنش قرار نگیره")
    elif st=="reducer":
        add("compatibility","reducer:two-sizes",f"برای انتخاب {name} باید سایز ورودی و خروجی رو دقیق بگم؛ اگر فقط سایز لوله اصلی رو بدونم چطور سایز سمت دوم رو مشخص کنم")
        add("design","reducer:hydraulic",f"تبدیل کردن خط با {name} می‌تونه روی فشار و دبی اثر بذاره؛ برای انتخاب درست چه اطلاعاتی از سیستم لازمه")
    elif st=="coupling":
        add("compatibility","coupling:ends",f"برای اینکه {name} به خط من بخوره، جنس و سایز هر دو لوله‌ای که می‌خوام به هم وصل کنم رو باید اعلام کنم")
        add("postuse","coupling:leak",f"اگر بعد از نصب {name} از محل اتصال کمی نشتی دیده بشه، قبل از سفت کردن بیشتر چه قسمت‌هایی از نصب و آب‌بندی باید بررسی بشه")
    else:
        add("selection","fitting:generic-selection",f"برای اینکه مطمئن بشم {name} قطعه درست برای کار منه، چه مشخصاتی از لوله، محل نصب و نوع اتصال باید بگم")
        add("installation","fitting:generic-install",f"برای نصب {name} چه لوازم مکمل و چه نکاتی باید از قبل مشخص باشه که موقع اجرا قطعه کم نیاد")
    return out

def guard_v5(p,candidate,question):
    ok,reason=orig_guard(p,candidate,question)
    if not ok:return ok,reason
    st=q.fitting_subtype(p); text=q.b.norm(question)
    if st in {"check_valve","endcap"} and "نوع اتصال دو طرف" in text:return False,"two-sided wording invalid for one-end fitting"
    if st=="tee" and "دو طرف" in text:return False,"tee requires three-branch wording"
    return True,None

q.guarded_candidates=candidates_v5
q.consistency_guard=guard_v5

def main():q.main()
if __name__=="__main__":main()
