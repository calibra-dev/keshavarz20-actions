#!/usr/bin/env python3
import importlib.util, json, os, random
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe2",os.path.join(ROOT,"engine_v2.py")); q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)

orig_candidates=q.guarded_candidates
orig_guard=q.consistency_guard

def kb(name, fallback):
    return q.b._KB.get(name) or fallback

def candidates_v3(p,fam,style,rng):
    out=orig_candidates(p,fam,style,rng)
    n=q.b.norm(str(p.get("name") or "")); name=q.b.ref_name(p)
    def add(intent,key,core): out.append({"intent":intent,"key":key,"core":core})
    if fam in {"fertilizer","pesticide"}:
        out=[x for x in out if x.get("key")!="nutrition:calcium-iron-mix"]
        if "کلسیم" in n:
            add("mix","nutrition:this-calcium-with-iron","این کود کلسیم رو میشه با کود آهن در یک برنامه غذایی استفاده کرد یا بهتره زمان مصرفشون از هم جدا باشه")
        elif "آهن" in n:
            add("mix","nutrition:this-iron-with-calcium","این کود آهن رو میشه نزدیک به مصرف کلسیم داد یا برای جلوگیری از ناسازگاری بهتره جدا استفاده بشن")
        else:
            add("mix","nutrition:this-product-mix",f"{name} رو میشه با کودهای دیگه داخل یک برنامه یا تانک استفاده کرد یا قبل از هر اختلاط باید سازگاری ترکیب بررسی بشه")
        climate=rng.choice(kb("climate_contexts",["منطقه گرم و خشک","منطقه سردسیر"])); system=rng.choice(kb("cultivation_systems",["فضای باز","گلخانه خاکی"])); crop=rng.choice(q.b.CROPS)
        add("climate",f"context:climate:{q.b.norm(climate)}",f"من در {climate} کشت دارم؛ این شرایط روی زمان یا روش مصرف {name} اثر می‌ذاره یا بیشتر باید مرحله رشد و آزمایش خاک و آب رو ملاک قرار بدم")
        add("cultivation",f"context:cultivation:{q.b.norm(system)}",f"کشت من {system} هست؛ برای استفاده از {name} روش مصرف با کشت فضای باز فرق می‌کنه یا باید بر اساس آنالیز و مرحله رشد تصمیم گرفت")
        add("variety",f"context:variety:{q.b.norm(crop)}",f"{crop} دارم؛ رقم گیاه هم می‌تونه روی مقدار و زمان مصرف {name} اثر داشته باشه یا مرحله رشد مهم‌تره")
        if fam=="fertilizer":
            tree=rng.choice(q.b.ORCHARDS); age=rng.choice(kb("tree_ages",["درخت جوان بارده","درخت بالغ"])); symptom=rng.choice(kb("symptoms",["زردی برگ","رشد ضعیف"])); indoor=rng.choice(q.b.INDOOR); media=rng.choice(kb("growing_media",["خاک باغچه","کوکوپیت و پرلیت"]))
            add("tree_age",f"context:tree-age:{q.b.norm(tree)}:{q.b.norm(age)}",f"باغ {tree} با {age} دارم؛ سن درخت برای تعیین مقدار مصرف {name} چقدر مهمه")
            add("symptom",f"context:symptom:{q.b.norm(symptom)}",f"گیاه‌هام {symptom} دارن؛ قبل از اینکه {name} استفاده کنم چه اطلاعات یا آزمایشی لازمه تا مطمئن بشم علت مشکل واقعاً با این محصول مرتبطه")
            add("indoor_media",f"context:indoor:{q.b.norm(indoor)}:{q.b.norm(media)}",f"{indoor} داخل خونه و در بستر {media} دارم؛ {name} برای مصرف گلدانی هم قابل بررسی هست یا فرمولش بیشتر برای مزرعه و باغه")
    if fam in {"drip_tape","pipe","filter","sprinkler"}:
        terrain=rng.choice(kb("terrain_conditions",["شیب متوسط","زمین مسطح"])); source=rng.choice(kb("water_sources",["چاه","استخر"])); climate=rng.choice(kb("climate_contexts",["منطقه گرم و خشک","منطقه سردسیر"])); transition=rng.choice(kb("irrigation_transitions",["غرقابی به قطره‌ای","بارانی به قطره‌ای"]))
        add("terrain",f"irrigation:terrain:{q.b.norm(terrain)}",f"زمین من {terrain} داره؛ برای استفاده از {name} این شرایط روی انتخاب سایز، فشار یا تقسیم‌بندی سیستم اثر می‌ذاره")
        add("water_source",f"irrigation:source:{q.b.norm(source)}",f"منبع آبم {source} هست؛ قبل از انتخاب {name} چه مشخصاتی از دبی، فشار و کیفیت آب رو باید بدونم")
        add("climate",f"irrigation:climate:{q.b.norm(climate)}",f"زمینم در {climate} هست؛ گرما، سرما یا موندن تجهیزات زیر آفتاب روی انتخاب و نگهداری {name} اثر داره")
        add("transition",f"irrigation:transition:{q.b.norm(transition)}",f"می‌خوام سیستم آبیاری رو از {transition} تغییر بدم؛ برای اینکه بفهمم {name} در طراحی جدید مناسب هست چه اطلاعاتی از زمین و آب لازم دارید")
    if fam in {"valve","fitting"}:
        add("installer_advice",f"installer:{fam}",f"نصاب برای خط من یک روش اتصال پیشنهاد داده ولی می‌خوام قبل خرید مطمئن بشم؛ برای تشخیص اینکه {name} انتخاب درستیه چه مشخصاتی از لوله و محل نصب باید بگم")
    return out

def guard_v3(p,candidate,question):
    ok,reason=orig_guard(p,candidate,question)
    if not ok:return ok,reason
    fam=q.fam_of(p); key=str(candidate.get("key") or ""); text=q.b.norm(question); n=q.b.norm(str(p.get("name") or ""))
    if fam in {"fertilizer","pesticide"} and key=="nutrition:calcium-iron-mix": return False,"orphan nutrient-mix question"
    if fam in {"fertilizer","pesticide"} and candidate.get("intent")=="mix":
        if not any(x in text for x in ["این کود","این محصول","این سم",q.b.norm(q.b.ref_name(p))]): return False,"mix question does not reference selected product"
    if "بدون واشر" in n and "جا افتادن واشر" in text:return False,"washer contradiction"
    return True,None

q.guarded_candidates=candidates_v3
q.consistency_guard=guard_v3

def main(): q.main()
if __name__=="__main__":main()
