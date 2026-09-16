#!/usr/bin/env python3
import importlib.util
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe13", os.path.join(ROOT, "engine_v13.py"))
v13 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v13)
q = v13.q

orig_candidates = q.guarded_candidates
orig_guard = q.consistency_guard


def n(value):
    return q.b.norm(str(value or ""))


def novice_core(p, fam, rng):
    name = q.b.ref_name(p)
    crop = rng.choice(q.b.CROPS)
    orchard = rng.choice(q.b.ORCHARDS)
    mapping = {
        "fertilizer": f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} برای {crop} به کارم میاد، مرحله رشد، مساحت، روش مصرف، وضعیت آب و خاک و کودهایی که قبلاً دادم رو باید بگم؟",
        "pesticide": f"من خیلی فنی نیستم؛ قبل از اینکه بفهمم {name} برای مشکل {crop} مناسبه، چه عکس یا اطلاعاتی از آفت یا بیماری، شدت مشکل، سم قبلی و شرایط هوا باید بفرستم؟",
        "adjuvant": f"من خیلی فنی نیستم؛ برای اینکه مشخص بشه {name} توی برنامه سمپاشی من لازمه، اسم محصول اصلی، محصول زراعی، حجم آب و کیفیت آب رو باید بگم؟",
        "seed": f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} برای کشت من مناسبه، منطقه، فصل کاشت، گلخانه یا فضای باز بودن و مساحت کشت رو باید بگم؟",
        "seedling": f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} برای زمین من مناسبه، منطقه، فصل انتقال، گلخانه یا فضای باز بودن و شرایط آب و خاک رو باید بگم؟",
        "drip_tape": f"من خیلی فنی نیستم؛ برای انتخاب {name} مساحت زمین، محصول، فاصله ردیف‌ها، طول ردیف، فشار و منبع آب رو باید بگم؟",
        "pipe": f"من خیلی فنی نیستم؛ برای انتخاب {name} دبی آب، طول مسیر، اختلاف ارتفاع، سایز خروجی پمپ و نوع اتصال ابتدا و انتهای خط رو باید بگم؟",
        "fitting": f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} به خطم می‌خوره، عکس اتصال فعلی، جنس لوله، قطر واقعی یا سایز اسمی و نوع رزوه یا اتصال رو باید بفرستم؟",
        "valve": f"من خیلی فنی نیستم؛ برای انتخاب {name} سایز و جنس لوله، نوع اتصال، کاری که شیر باید انجام بده و فشار تقریبی سیستم رو باید بگم؟",
        "automatic_valve": f"من خیلی فنی نیستم؛ برای اینکه مشخص بشه {name} مناسب خط منه، کاربرد مورد نظر، جهت جریان، سایز اتصال و فشار سیستم رو باید بگم؟",
        "air_valve": f"من خیلی فنی نیستم؛ برای انتخاب {name} طول مسیر، نقاط بلند خط، اختلاف ارتفاع، سایز لوله و فشار سیستم رو باید بگم؟",
        "pump": f"من خیلی فنی نیستم؛ برای انتخاب {name} عمق منبع آب، ارتفاع پمپاژ، طول مسیر، قطر لوله و دبی مورد نیاز رو باید بگم؟",
        "power_equipment": f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} جواب کارم رو میده، نوع وسیله‌ای که می‌خوام راه بندازم، توان مصرفی، جریان راه‌اندازی و مدت کار پیوسته رو باید بگم؟",
        "filter": f"من خیلی فنی نیستم؛ برای انتخاب {name} منبع آب، نوع آلودگی یا رسوب، دبی سیستم و سایز ورودی و خروجی رو باید بگم؟",
        "sprinkler": f"من خیلی فنی نیستم؛ برای انتخاب {name} مساحت و محصول، فشار و دبی پمپ، فاصله آبپاش‌ها و باد منطقه رو باید بگم؟",
        "dripper": f"من خیلی فنی نیستم؛ برای باغ {orchard} اگر بخوام {name} انتخاب کنم، سن درخت، نوع خاک، فاصله کاشت، فشار خط و تعداد دریپر هر درخت رو باید بگم؟",
        "bubbler": f"من خیلی فنی نیستم؛ برای باغ {orchard} اگر بخوام {name} انتخاب کنم، سن درخت، بافت خاک، فشار خط و سطحی که باید دور هر درخت خیس بشه رو باید بگم؟",
        "riser": f"من خیلی فنی نیستم؛ برای انتخاب {name} سایز آبپاش، نوع رزوه، ارتفاع مورد نیاز و فشار و دبی خط رو باید بگم؟",
        "fertigation": f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} مناسب سیستم کوددهی منه، مساحت، دبی و فشار آبیاری، حجم محلول و روش تزریق رو باید بگم؟",
        "hardware": f"من خیلی فنی نیستم؛ برای انتخاب {name} قطر و طول پیچ، گام رزوه، ضخامت قطعات و شرایط محیطی محل نصب رو باید بگم؟",
        "irrigation_tool": f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} برای کارم مناسبه، جنس و ضخامت لوله و قطر اتصال یا سوراخ مورد نیاز رو باید بگم؟",
    }
    return mapping.get(fam, f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} به کارم میاد، کاربرد دقیق و شرایطی که قراره استفاده بشه رو باید چطور توضیح بدم؟")


def candidates_v14(p, fam, style, rng):
    out = orig_candidates(p, fam, style, rng)
    # Replace the one-size-fits-all novice prompt with a family-specific version.
    out = [c for c in out if str(c.get("key") or "") != f"human:simple:{fam}"]
    if style == "colloquial":
        out.append({
            "intent": "simple_help",
            "key": f"human:simple:v14:{fam}",
            "core": novice_core(p, fam, rng),
        })
    return out


def guard_v14(p, candidate, question):
    ok, reason = orig_guard(p, candidate, question)
    if not ok:
        return ok, reason
    fam = q.b.family(p)
    key = str(candidate.get("key") or "")
    text = n(question)
    if key.startswith("human:simple:v14:"):
        if q.b.ref_name(p) not in question and n(q.b.ref_name(p)) not in text:
            return False, "novice prompt must reference selected product"
        forbidden = {
            "fertilizer": ["قطعی درمان", "تضمین نتیجه"],
            "pesticide": ["حتما بزن", "حتماً بزن", "دوز قطعی"],
        }
        if any(n(x) in text for x in forbidden.get(fam, [])):
            return False, "unsupported novice recommendation claim"
    return True, None


q.guarded_candidates = candidates_v14
q.consistency_guard = guard_v14


def main():
    q.main()


if __name__ == "__main__":
    main()
