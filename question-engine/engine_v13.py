#!/usr/bin/env python3
import importlib.util
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe12", os.path.join(ROOT, "engine_v12.py"))
v12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v12)
q = v12.q

orig_family = q.b.family
orig_candidates = q.guarded_candidates
orig_guard = q.consistency_guard


def n(value):
    return q.b.norm(str(value or ""))


def family_v13(p):
    name = n(p.get("name"))
    if n("بابلر") in name:
        return "bubbler"
    if n("شیر تخلیه هوا") in name:
        return "air_valve"
    if n("شیر خودکار") in name:
        return "automatic_valve"
    if n("مته دستی") in name:
        return "irrigation_tool"
    return orig_family(p)


def add(out, intent, key, core):
    out.append({"intent": intent, "key": key, "core": core})


def candidates_v13(p, fam, style, rng):
    out = orig_candidates(p, fam, style, rng)
    name = q.b.ref_name(p)

    if fam == "bubbler":
        orchard = rng.choice(q.b.ORCHARDS)
        add(out, "design_scenario", f"bubbler:orchard:{n(orchard)}",
            f"برای باغ {orchard} می‌خوام از {name} استفاده کنم؛ برای تعیین تعداد بابلر هر درخت چه اطلاعاتی از سن درخت، بافت خاک، نیاز آبی و فاصله کاشت لازمه بگم؟")
        add(out, "selection", "bubbler:flow-control",
            f"برای انتخاب درست {name} چه اطلاعاتی از فشار خط، دبی مورد نیاز هر نقطه و تنظیمی یا ثابت بودن آبدهی باید بررسی بشه؟")
        add(out, "filtration", "bubbler:filtration",
            f"آب من ممکنه ذرات یا رسوب داشته باشه؛ برای اینکه {name} دچار گرفتگی نشه چه اطلاعاتی از کیفیت آب و فیلتراسیون سیستم لازمه؟")
        add(out, "layout", "bubbler:wetted-area",
            f"برای اینکه بدونم {name} سطح خیس‌شدگی مناسبی دور درخت میده، نوع خاک، شیب زمین و محل قرارگیری بابلر نسبت به تنه رو باید چطور در نظر بگیرم؟")

    elif fam == "air_valve":
        add(out, "placement", "air-valve:placement",
            f"برای اینکه مشخص بشه {name} در کجای خط نصب بشه، طول مسیر، اختلاف ارتفاع، نقاط بلند خط و محل پمپ یا منبع رو باید بگم؟")
        add(out, "compatibility", "air-valve:connection",
            f"برای انتخاب {name} فقط سایز اسمی کافیه یا باید سایز اتصال، فشار کاری سیستم و نوع خط لوله هم مشخص باشه؟")
        add(out, "troubleshooting", "air-valve:air-problem",
            f"اگر داخل خط هوا جمع میشه یا جریان ناپایدار میشه، چه نشانه‌هایی رو باید بگم تا مشخص بشه {name} برای رفع مشکل مناسبه یا ایراد از بخش دیگه سیستمه؟")
        add(out, "installation", "air-valve:installation",
            f"برای نصب {name} چه اطلاعاتی از جهت و محل نصب، دسترسی برای سرویس و آرایش اتصالات اطرافش لازمه بررسی بشه؟")

    elif fam == "automatic_valve":
        add(out, "use_case", "automatic-valve:role",
            f"برای اینکه مشخص بشه {name} انتخاب درستیه، باید بگم این شیر قراره در کدام بخش سیستم چه کاری انجام بده و جهت جریان، فشار و سایز اتصال چقدره؟")
        add(out, "compatibility", "automatic-valve:connection",
            f"برای سازگاری {name} با خط فعلی، نوع اتصال دو طرف، جنس لوله و فشار کاری سیستم رو باید اعلام کنم؟")
        add(out, "installation", "automatic-valve:orientation",
            f"قبل از نصب {name} چطور باید جهت جریان و وضعیت نصب توصیه‌شده سازنده رو بررسی کنم تا عملکردش درست باشه؟")
        add(out, "troubleshooting", "automatic-valve:operation",
            f"اگر {name} بعد از نصب درست عمل نکنه، قبل از تعویض چه چیزهایی از جهت نصب، فشار، آلودگی داخل خط و اتصالات باید بررسی بشه؟")

    elif fam == "irrigation_tool":
        add(out, "compatibility", "irrigation-tool:hole-fit",
            f"برای اینکه مطمئن بشم {name} برای نصب اتصال من مناسبه، جنس لوله یا سطحی که باید سوراخ بشه و قطر ورودی قطعه‌ای که بعدش نصب میشه رو باید بگم؟")
        add(out, "use_case", "irrigation-tool:material",
            f"می‌خوام با {name} روی خط آبیاری سوراخ ایجاد کنم؛ ضخامت و جنس لوله چقدر در مناسب بودن این ابزار و کیفیت سوراخ مهمه؟")
        add(out, "installation", "irrigation-tool:clean-hole",
            f"برای اینکه سوراخ با {name} تمیز دربیاد و بعداً محل اتصال نشتی نده، قبل و بعد از سوراخ‌کاری چه نکاتی رو باید رعایت کنم؟")

    return out


def guard_v13(p, candidate, question):
    ok, reason = orig_guard(p, candidate, question)
    if not ok:
        return ok, reason
    fam = q.b.family(p)
    text = n(question)
    if fam in {"bubbler", "air_valve", "automatic_valve", "irrigation_tool"} and any(
        term in text for term in [n("مقدار مصرف کود"), n("زمان مصرف سم"), n("علائم کمبود")]
    ):
        return False, "ag-input scenario leaked onto residual irrigation family"
    return True, None


q.b.family = family_v13
q.guarded_candidates = candidates_v13
q.consistency_guard = guard_v13


def main():
    q.main()


if __name__ == "__main__":
    main()
