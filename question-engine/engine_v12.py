#!/usr/bin/env python3
import importlib.util
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe11", os.path.join(ROOT, "engine_v11.py"))
v11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v11)
q = v11.q

orig_family = q.b.family
orig_candidates = q.guarded_candidates
orig_guard = q.consistency_guard


def n(value):
    return q.b.norm(str(value or ""))


def structured_terms(p):
    cats = [n(x.get("name")) for x in (p.get("categories") or [])]
    tags = [n(x.get("name")) for x in (p.get("tags") or [])]
    attrs = []
    for attr in p.get("attributes") or []:
        attrs.append(n(attr.get("name")))
        attrs.extend(n(x) for x in (attr.get("options") or []))
    return set(x for x in cats + tags + attrs if x)


def family_v12(p):
    # Preserve every family v11 can already identify safely.
    base = orig_family(p)
    if base != "generic":
        return base

    name = n(p.get("name"))
    terms = structured_terms(p)

    # Explicit product-name rules. These precede broad category fallbacks.
    name_rules = [
        ("seed", ["بذر"]),
        ("pump", ["پمپ آب", "پمپ کف کش", "کف کش", "کف‌کش", "لجن کش", "لجن‌کش", "پمپ بنزینی", "ست کنترل"]),
        ("power_equipment", ["موتور برق", "موتور جوش", "درایور بردی موتور", "درایور موتور"]),
        ("riser", ["رایزر"]),
        ("dripper", ["دریپر", "قطره چکان", "قطره‌چکان"]),
        ("hardware", ["پیچ و مهره"]),
        ("adjuvant", ["سورفکتانت", "ادجوانت", "خیس کننده", "خیس‌کننده"]),
        ("fitting", ["چپقی", "کپ رزوه", "کپ رزوه‌ای", "انشعاب دوشاخه"]),
    ]
    for fam, words in name_rules:
        if any(n(word) in name for word in words):
            return fam

    # Exact structured taxonomy rules observed in the live catalog audit.
    if n("بذرهای کشاورزی") in terms:
        return "seed"
    if n("نشاء") in terms:
        return "seedling"
    if n("کف کش و لجن کش") in terms or n("پمپ و ست کنترل") in terms:
        return "pump"
    if n("موتور برق و پمپ بنزینی") in terms:
        return "power_equipment"
    if n("رایزر پلیمری") in terms:
        return "riser"
    if n("قطره چکان (دریپر)") in terms:
        return "dripper"
    if n("پیچ و مهره") in terms:
        return "hardware"
    if n("اتصالات u-pvc") in terms:
        return "fitting"

    return "generic"


def add(out, intent, key, core):
    out.append({"intent": intent, "key": key, "core": core})


def candidates_v12(p, fam, style, rng):
    out = orig_candidates(p, fam, style, rng)
    name = q.b.ref_name(p)

    if fam == "seed":
        add(out, "cultivation_fit", "seed:cultivation-fit",
            f"برای اینکه مشخص بشه {name} برای شرایط کشت من مناسبه، چه اطلاعاتی از منطقه، فصل کشت، فضای باز یا گلخانه و بازار هدف باید بگم؟")
        add(out, "nursery_setup", "seed:nursery-setup",
            f"اگر بخوام از {name} نشا تولید کنم، قبل از کاشت چه اطلاعاتی از بستر، دما، رطوبت و زمان انتقال نشا باید مشخص باشه؟")
        add(out, "quantity_plan", "seed:quantity-plan",
            f"برای برآورد مقدار بذر مورد نیاز از {name}، مساحت کشت، فاصله بوته‌ها و روش مستقیم یا نشاکاری رو چطور باید اعلام کنم تا تعداد بسته درست حساب بشه؟")
        add(out, "compare", "seed:official-traits",
            f"اگر بین {name} و یک رقم مشابه مردد باشم، برای مقایسه درست چه مشخصات رسمی مثل تیپ کشت، دوره رشد و ویژگی‌های رقم رو باید کنار هم ببینم؟")

    elif fam == "seedling":
        add(out, "transplant_fit", "seedling:transplant-fit",
            f"برای اینکه بدونم {name} برای انتقال به زمین من مناسبه، منطقه، فصل کشت، فضای باز یا گلخانه و زمان تقریبی نشاکاری رو باید بگم؟")
        add(out, "quality_check", "seedling:quality-check",
            f"موقع تحویل {name} برای بررسی سلامت نشا چه چیزهایی مثل ریشه، ساقه، برگ‌ها و یکنواختی بوته‌ها رو باید چک کنم؟")
        add(out, "establishment", "seedling:establishment",
            f"بعد از انتقال {name} به زمین، برای اینکه شوک جابه‌جایی کمتر بشه چه اطلاعاتی از آب، خاک، دما و شرایط مزرعه لازمه تا روش استقرار درست انتخاب بشه؟")
        city = rng.choice(q.b.CITIES)
        add(out, "shipping", f"seedling:shipping:{n(city)}",
            f"برای ارسال {name} به {city}، نشا با چه نوع بسته‌بندی و روشی فرستاده میشه که در مسیر کمتر آسیب ببینه و قبل سفارش چه محدودیتی رو باید بدونم؟")

    elif fam == "pump":
        lname = n(p.get("name"))
        if any(x in lname for x in [n("کف کش"), n("کف‌کش"), n("لجن کش"), n("لجن‌کش")]):
            add(out, "pump_sizing", "pump:submersible-sizing",
                f"برای اینکه مشخص بشه {name} برای کار من مناسبه، عمق منبع آب، ارتفاع تا محل تخلیه، طول مسیر، قطر لوله و تمیزی یا ذرات داخل آب رو باید بگم؟")
            add(out, "pump_protection", "pump:submersible-protection",
                f"برای استفاده مطمئن از {name} چه اطلاعاتی از سطح آب، دفعات روشن و خاموش شدن و شرایط برق لازمه تا خطر خشک‌کار کردن یا انتخاب اشتباه بررسی بشه؟")
        elif "ست کنترل" in lname:
            add(out, "compatibility", "pump:controller-compatibility",
                f"برای اینکه بفهمم {name} با پمپ فعلی من سازگاره، توان پمپ، برق ورودی، فشار مورد نیاز و سایز اتصال ورودی و خروجی رو باید اعلام کنم؟")
            add(out, "use_case", "pump:controller-use",
                f"مصرف من برای آبیاری و چند خروجی مختلفه؛ برای انتخاب درست {name} چه اطلاعاتی از فشار قطع و وصل، دبی و نوع پمپ لازمه؟")
        else:
            add(out, "pump_sizing", "pump:surface-sizing",
                f"برای انتخاب {name} فقط توان موتور کافی نیست؛ چه اطلاعاتی از منبع آب، دبی مورد نیاز، ارتفاع پمپاژ، طول مسیر و قطر لوله باید بگم؟")
            add(out, "irrigation_zone", "pump:irrigation-zone",
                f"می‌خوام {name} برای آبیاری یک زون استفاده کنم؛ برای اینکه مشخص بشه جواب میده تعداد خروجی‌ها، فشار لازم و دبی کل سیستم رو چطور باید حساب یا اعلام کنم؟")

    elif fam == "power_equipment":
        lname = n(p.get("name"))
        if n("موتور برق") in lname:
            add(out, "load_sizing", "power:generator-load",
                f"برای اینکه بفهمم {name} برای وسایل من کافیه، توان مصرفی دائم، جریان راه‌اندازی موتورهای برقی و تک‌فاز یا سه‌فاز بودن مصرف‌کننده‌ها رو باید بگم؟")
            add(out, "field_use", "power:generator-field",
                f"برای کار مزرعه می‌خوام از {name} استفاده کنم؛ قبل خرید چه اطلاعاتی از مدت کار پیوسته، نوع بار و حساس بودن تجهیزات برقی باید بررسی بشه؟")
        elif n("موتور جوش") in lname:
            add(out, "workload", "power:welder-workload",
                f"برای اینکه مشخص بشه {name} مناسب کارمه، نوع جوشکاری، ضخامت قطعه، الکترود مورد استفاده و مدت کار پیوسته رو باید بگم؟")
        else:
            add(out, "electrical_compatibility", "power:driver-compatibility",
                f"برای اینکه سازگاری {name} با موتور فعلی مشخص بشه، ولتاژ موتور، جریان نامی و راه‌اندازی و نوع کنترل سرعت و جهت رو باید اعلام کنم؟")
            add(out, "electrical_load", "power:driver-load",
                f"موتورم زیر بار سنگین کار می‌کنه؛ برای انتخاب درست {name} چه اطلاعاتی از جریان واقعی موتور و شرایط بار لازمه بررسی بشه؟")

    elif fam == "riser":
        add(out, "compatibility", "riser:sprinkler-compatibility",
            f"برای اینکه مشخص بشه {name} به آبپاش و خط من می‌خوره، سایز و نوع رزوه دو طرف، ارتفاع مورد نیاز و نوع اتصال خط اصلی رو باید بگم؟")
        add(out, "layout", "riser:layout",
            f"برای چیدمان آبپاش‌ها با {name}، فشار و دبی هر آبپاش، فاصله آبپاش‌ها و نحوه مهار رایزر چقدر در انتخاب مدل مناسب مهمه؟")
        add(out, "post_install", "riser:stability",
            f"اگر رایزر بعد از نصب لرزش یا کجی داشته باشه، قبل از تعویض {name} چه چیزهایی از مهار، رزوه، آبپاش و فشار سیستم باید بررسی بشه؟")

    elif fam == "dripper":
        orchard = rng.choice(q.b.ORCHARDS)
        add(out, "design_scenario", f"dripper:orchard:{n(orchard)}",
            f"برای باغ {orchard} می‌خوام از {name} استفاده کنم؛ برای تعیین تعداد دریپر هر درخت چه اطلاعاتی از سن درخت، بافت خاک، دبی مورد نیاز و فاصله کاشت لازمه؟")
        add(out, "pressure_flow", "dripper:pressure-flow",
            f"برای اینکه آبدهی {name} در طول خط یکنواخت بمونه، چه اطلاعاتی از فشار ورودی، طول لوله فرعی و تعداد دریپرهای هر خط باید بررسی بشه؟")
        add(out, "filtration", "dripper:filtration",
            f"آب من ممکنه رسوب یا ذرات داشته باشه؛ برای جلوگیری از گرفتگی {name} چه اطلاعاتی از کیفیت آب و نوع فیلتر لازمه قبل خرید مشخص کنم؟")
        add(out, "post_use", "dripper:low-flow",
            f"اگر بعد از مدتی آبدهی بعضی از {name}ها کمتر بشه، از کجا تشخیص بدم مشکل از فشار خط، گرفتگی یا کیفیت آب هست؟")

    elif fam == "hardware":
        add(out, "compatibility", "hardware:bolt-fit",
            f"برای اینکه مطمئن بشم {name} به اتصال یا فلنج من می‌خوره، قطر پیچ، طول لازم، گام رزوه و ضخامت قطعاتی که به هم بسته میشن رو باید بگم؟")
        add(out, "material", "hardware:material",
            f"این پیچ و مهره قراره در فضای باز و نزدیک آب استفاده بشه؛ برای انتخاب درست چه اطلاعاتی از جنس، پوشش و شرایط محیطی لازمه بررسی بشه؟")
        add(out, "installation", "hardware:tightening",
            f"برای نصب {name} چطور مشخص کنم چه واشر و روش بستن مناسبه تا اتصال خوب محکم بشه ولی به قطعه آسیب نرسه؟")

    elif fam == "adjuvant":
        crop = rng.choice(q.b.CROPS)
        add(out, "tank_mix_context", f"adjuvant:mix:{n(crop)}",
            f"برای {crop} می‌خوام {name} رو همراه محلول سمپاشی استفاده کنم؛ قبل از ترکیب چه اطلاعاتی از نام دقیق محصولات، برچسب مصرف، حجم آب و کیفیت آب باید بررسی بشه؟")
        add(out, "water_quality", "adjuvant:water-quality",
            f"آب سمپاشی من سختی یا املاح داره؛ برای اینکه مشخص بشه {name} در این شرایط کاربرد مناسبی داره چه مشخصاتی از آب و محلول باید بگم؟")
        add(out, "application_fit", "adjuvant:application-fit",
            f"برای اینکه بدونم {name} در برنامه سمپاشی من لازم هست یا نه، نوع محصول اصلی، هدف سمپاشی، محصول زراعی و روش محلول‌پاشی رو باید اعلام کنم؟")

    return out


def guard_v12(p, candidate, question):
    ok, reason = orig_guard(p, candidate, question)
    if not ok:
        return ok, reason
    fam = q.b.family(p)
    text = n(question)

    non_input = {"seed", "seedling", "pump", "power_equipment", "riser", "dripper", "hardware", "fitting", "valve", "pipe", "filter", "sprinkler"}
    if fam in non_input and any(term in text for term in [n("علائم کمبود"), n("کود قبلی"), n("سم قبلی"), n("مقدار مصرف کود")]):
        return False, "ag-input scenario leaked onto non-input family"
    if fam == "adjuvant" and any(term in text for term in [n("حتماً اثر"), n("تضمین اثر"), n("دوز قطعی")]):
        return False, "unsupported adjuvant efficacy or dose claim"
    if candidate.get("intent") in {"cultivation_fit", "nursery_setup", "transplant_fit"} and fam not in {"seed", "seedling"}:
        return False, "seed/seedling scenario on wrong family"
    return True, None


q.b.family = family_v12
q.guarded_candidates = candidates_v12
q.consistency_guard = guard_v12


def main():
    q.main()


if __name__ == "__main__":
    main()
