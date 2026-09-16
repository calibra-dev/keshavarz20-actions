#!/usr/bin/env python3
import importlib.util, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe6",os.path.join(ROOT,"engine_v6.py")); v6=importlib.util.module_from_spec(spec); spec.loader.exec_module(v6)
q=v6.q
orig_candidates=q.guarded_candidates
orig_guard=q.consistency_guard

def kb(name, fallback):
    return q.b._KB.get(name) or fallback

def plant_symptoms():
    blocked={"گرفتگی قطره‌چکان","افت فشار انتهای خط"}
    return [x for x in kb("symptoms",["زردی برگ","رشد ضعیف","سوختگی حاشیه برگ"]) if x not in blocked]

def add(out,intent,key,core):
    out.append({"intent":intent,"key":key,"core":core})

def candidates_v7(p,fam,style,rng):
    out=orig_candidates(p,fam,style,rng)
    name=q.b.ref_name(p)
    if fam=="fertilizer":
        out=[x for x in out if x.get("key") not in {"plant:symptom:yellowing","postuse:no-result"}]
        crop=rng.choice(q.b.CROPS)
        symptom=rng.choice(plant_symptoms())
        stage=rng.choice(kb("growth_stages_annual",["رشد رویشی","گلدهی","تشکیل میوه"]))
        previous=rng.choice(["یک کود کامل ۲۰-۲۰-۲۰","کود آهن","هیومیک اسید","کود کلسیم","اسیدآمینه"])
        leaf=rng.choice(["برگ‌های جوان","برگ‌های پیر","هم برگ‌های بالا هم پایین"])
        soil=rng.choice(kb("soil_types",["خاک لومی","خاک آهکی","خاک شور"]))
        water=rng.choice(kb("water_conditions",["آب شور","آب سخت","آب با EC بالا"]))
        add(out,"post_use",f"postuse:prior-program:{q.b.norm(crop)}:{q.b.norm(previous)}",
            f"برای {crop} یک نوبت {previous} دادم و بعد {name} رو استفاده کردم ولی هنوز {symptom} دیده میشه؛ قبل از تکرار مصرف چه چیزهایی مثل محل بروز علائم، وضعیت ریشه، آب و مقدار مصرف رو باید بررسی کنم")
        add(out,"diagnosis",f"diagnosis:leaf-position:{q.b.norm(crop)}:{q.b.norm(leaf)}",
            f"{crop} من {symptom} داره و بیشتر روی {leaf} دیده میشه؛ برای اینکه بفهمم مشکل واقعاً تغذیه‌ایه و {name} انتخاب مناسبی هست چه اطلاعاتی از گیاه، آب و خاک لازمه بفرستم")
        add(out,"growth_stage",f"nutrition:stage-history:{q.b.norm(crop)}:{q.b.norm(stage)}",
            f"{crop} من الان در مرحله {stage} هست و قبلاً {previous} مصرف کردم؛ قبل از اضافه کردن {name} بهتره چه چیزهایی از برنامه قبلی و علائم گیاه بررسی بشه")
        add(out,"soil_water",f"nutrition:soil-water:{q.b.norm(soil)}:{q.b.norm(water)}",
            f"خاکم {soil} هست و {water} دارم؛ اگر بخوام {name} استفاده کنم این شرایط چقدر روی جذب و نتیجه مصرف اثر می‌ذاره و چه اطلاعاتی باید قبلش بررسی بشه")
        indoor=rng.choice(q.b.INDOOR)
        add(out,"indoor_postuse",f"indoor:postuse:{q.b.norm(indoor)}",
            f"{indoor} داخل خونه دارم و بعد از یک نوبت کوددهی هنوز برگ‌ها ظاهر طبیعی ندارن؛ قبل از اینکه {name} رو امتحان کنم نور، آبیاری، زهکشی و برنامه کود قبلی رو چطور باید بررسی کنم")
        orchard=rng.choice(q.b.ORCHARDS); age=rng.choice(kb("tree_ages",["درخت جوان بارده","درخت بالغ"])); tstage=rng.choice(kb("growth_stages_tree",["گلدهی","تشکیل میوه","بعد برداشت"]))
        add(out,"orchard_diagnosis",f"orchard:diagnosis:{q.b.norm(orchard)}:{q.b.norm(age)}:{q.b.norm(tstage)}",
            f"باغ {orchard} با {age} دارم و الان مرحله {tstage} هست؛ اگر علائم کمبود ببینم برای اینکه مشخص بشه {name} واقعاً مناسبه چه اطلاعاتی از برگ، بار درخت، آب، خاک و کودهای قبلی لازمه")
    elif fam=="pesticide":
        crop=rng.choice(q.b.CROPS); stage=rng.choice(kb("growth_stages_annual",["رشد رویشی","گلدهی","تشکیل میوه"]))
        add(out,"post_use",f"pesticide:prior-treatment:{q.b.norm(crop)}:{q.b.norm(stage)}",
            f"برای {crop} در مرحله {stage} قبلاً یک نوبت سم استفاده کردم ولی نتیجه کامل نگرفتم؛ قبل از استفاده از {name} چه اطلاعاتی از آفت یا بیماری، سم قبلی، فاصله مصرف و شرایط هوا لازمه بررسی بشه")
        add(out,"diagnosis",f"pesticide:identify-target:{q.b.norm(crop)}",
            f"روی {crop} یک مشکل دارم ولی مطمئن نیستم آفت، بیماری یا تنش محیطیه؛ قبل از اینکه {name} استفاده کنم چه عکس یا اطلاعاتی لازمه تا کاربردش درست بررسی بشه")
    elif fam=="drip_tape":
        crop=rng.choice(q.b.CROPS); area=rng.choice(["یک هکتار","۲ هکتار","۵ هکتار"]); terrain=rng.choice(kb("terrain_conditions",["شیب ملایم","شیب متوسط"])); source=rng.choice(kb("water_sources",["چاه","استخر"])); water=rng.choice(kb("water_conditions",["آب دارای شن","آب شور"]));
        add(out,"design_scenario",f"driptape:scenario:{q.b.norm(crop)}:{area}:{q.b.norm(terrain)}",
            f"{area} {crop} دارم، زمینم {terrain} داره و آبم از {source} میاد؛ برای اینکه بفهمم {name} مناسب هست و چند رول لازم دارم چه اطلاعاتی از فاصله ردیف، طول ردیف، فشار و دبی لازمه")
        add(out,"water_quality",f"driptape:water:{q.b.norm(water)}",
            f"آب من {water} داره و می‌خوام از {name} استفاده کنم؛ برای اینکه قطره‌چکان‌ها زود نگیرن چه مشخصاتی از آب و فیلتراسیون باید قبل خرید بررسی بشه")
    elif fam=="pipe":
        length=rng.choice(["حدود ۲۵۰ متر","حدود ۴۰۰ متر","نزدیک ۶۰۰ متر"]); terrain=rng.choice(kb("terrain_conditions",["شیب ملایم","اختلاف ارتفاع محسوس بین ابتدا و انتهای زمین"]));
        add(out,"design_scenario",f"pipe:scenario:{q.b.norm(length)}:{q.b.norm(terrain)}",
            f"خروجی پمپم ۳ اینچه، مسیر انتقال {length} هست و زمین {terrain} داره؛ برای انتخاب سایز {name} فقط خروجی پمپ کافیه یا دبی، افت فشار و اختلاف ارتفاع هم باید حساب بشه")
    elif fam=="filter":
        source=rng.choice(kb("water_sources",["چاه","استخر"])); water=rng.choice(kb("water_conditions",["آب دارای شن","آب کدر","آب دارای جلبک"]));
        add(out,"water_scenario",f"filter:scenario:{q.b.norm(source)}:{q.b.norm(water)}",
            f"منبع آبم {source} هست و {water} دارم؛ برای اینکه بفهمم {name} به‌تنهایی مناسبه یا مرحله فیلتراسیون دیگه هم لازمه چه اطلاعاتی از دبی و کیفیت آب باید بگم")
    elif fam=="sprinkler":
        crop=rng.choice(q.b.CROPS); area=rng.choice(["یک هکتار","۳ هکتار","۵ هکتار"]); climate=rng.choice(kb("climate_contexts",["منطقه بادخیز","منطقه گرم و خشک"]));
        add(out,"design_scenario",f"sprinkler:scenario:{q.b.norm(crop)}:{area}:{q.b.norm(climate)}",
            f"{area} {crop} دارم و منطقه‌مون {climate} هست؛ برای اینکه بدونم {name} جواب میده چه اطلاعاتی از فشار پمپ، دبی، فاصله آبپاش‌ها و باد لازمه")
    elif fam in {"fitting","valve"}:
        pipe=rng.choice(["لوله پلی‌اتیلن","لوله پولیکا","لوله نخدار","خط لی‌فلت"])
        add(out,"installer_scenario",f"installer:existing-line:{fam}:{q.b.norm(pipe)}",
            f"نصاب برای {pipe} یک روش اتصال پیشنهاد داده ولی می‌خوام قبل خرید مطمئن بشم؛ برای اینکه مشخص بشه {name} انتخاب درستیه چه سایز، جنس لوله و نوع اتصال فعلی رو باید بگم")
        add(out,"post_install",f"postinstall:leak:{fam}:{q.b.norm(pipe)}",
            f"روی {pipe} اتصال رو نصب کردم ولی کمی نشتی دارم؛ قبل از اینکه قطعه رو عوض کنم چه چیزهایی از سایز، آب‌بندی و نحوه نصب رو باید بررسی کنم")
    elif fam=="fertigation":
        area=rng.choice(["۲ هکتار","۵ هکتار","حدود ۱۰ هکتار"]); source=rng.choice(kb("water_sources",["چاه","استخر"]));
        add(out,"system_scenario",f"fertigation:scenario:{area}:{q.b.norm(source)}",
            f"برای {area} زمین با آب {source} می‌خوام کود رو از طریق سیستم آبیاری تزریق کنم؛ برای اینکه بفهمم {name} مناسب کارمه چه اطلاعاتی از دبی، فشار، حجم محلول و روش تزریق لازمه")
    return out

def guard_v7(p,candidate,question):
    ok,reason=orig_guard(p,candidate,question)
    if not ok:return ok,reason
    fam=q.fam_of(p); text=q.b.norm(question); key=str(candidate.get("key") or "")
    if fam not in {"fertilizer","pesticide"} and any(x in text for x in ["علائم کمبود","کود قبلی","برگ های جوان","برگ‌های جوان"]):
        return False,"plant-nutrition scenario on non-input product"
    if fam=="pesticide" and "مقدار مصرف" in text and "کاربرد" not in text:
        return False,"dose wording without verified pesticide applicability"
    if key.startswith("postuse:prior-program") and fam!="fertilizer":
        return False,"fertilizer prior-program scenario on wrong family"
    return True,None

q.guarded_candidates=candidates_v7
q.consistency_guard=guard_v7

def main():q.main()
if __name__=="__main__":main()
