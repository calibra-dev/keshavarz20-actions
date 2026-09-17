#!/usr/bin/env python3
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ROOT)
POLICY_PATH = os.path.join(REPO_ROOT, "automation-policy", "seo-god-2026.json")

spec = importlib.util.spec_from_file_location("qe17", os.path.join(ROOT, "engine_v17.py"))
v17 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v17)
q = v17.q

with open(POLICY_PATH, "r", encoding="utf-8") as fh:
    POLICY = json.load(fh)

orig_candidates = q.guarded_candidates
orig_guard = q.consistency_guard


def add(out, intent, key, core):
    out.append({"intent": intent, "key": key, "core": core})


def _family_decision_candidates(p, fam, rng):
    name = q.b.ref_name(p)
    out = []

    if fam == "drip_tape":
        crop = rng.choice(q.b.CROPS)
        add(out, "suitability", "seogod:drip-tape:suitability",
            f"برای اینکه قبل از خرید {name} بفهمم واقعاً برای {crop} و زمین من مناسبه، مساحت، فاصله ردیف‌ها، طول هر ردیف، فشار و منبع آب رو باید بگم؟")
        add(out, "water_efficiency", "seogod:drip-tape:water-risk",
            f"برای انتخاب {name} از نظر یکنواختی آبیاری و ریسک گرفتگی، کیفیت آب، نوع فیلتر، فشار ابتدای خط و طول ردیف‌ها چقدر در تصمیم اثر دارن؟")
        add(out, "total_cost", "seogod:drip-tape:complete-basket",
            f"اگر بخوام برای {name} سبد خرید ناقص نباشه، علاوه بر متراژ نوار چه اطلاعاتی لازمه تا تعداد شیر، رابط، بست انتهایی، مته و فیلتراسیون مورد نیاز درست محاسبه بشه؟")

    elif fam == "pipe":
        add(out, "selection", "seogod:pipe:hydraulic-context",
            f"برای انتخاب {name} فقط سایز اسمی کافیه یا باید دبی، طول مسیر، اختلاف ارتفاع، فشار، سایز خروجی پمپ و تعداد انشعاب‌ها هم مشخص باشه؟")
        add(out, "compatibility", "seogod:pipe:connection-system",
            f"قبل از خرید {name} برای اینکه اتصالات اشتباه نگیرم، قطر واقعی یا سایز اسمی، جنس لوله و نوع اتصال ابتدا و انتهای خط رو دقیقاً از کجا باید چک کنم؟")
        add(out, "total_cost", "seogod:pipe:system-cost",
            f"برای مقایسه اقتصادی {name} با گزینه‌های دیگه، غیر از قیمت خود لوله چه مواردی مثل اتصال، نصب، حمل، تعمیر و افت فشار باید در هزینه کل سیستم حساب بشه؟")

    elif fam == "fitting":
        add(out, "compatibility", "seogod:fitting:wrong-purchase",
            f"برای اینکه {name} رو اشتباه سفارش ندم، کدوم اندازه‌های قطعه و لوله، نوع رزوه، جنس خط و شکل اتصال فعلی رو باید قبل از خرید تطبیق بدم؟")
        add(out, "installation", "seogod:fitting:installation-risk",
            f"برای نصب {name} چه اطلاعاتی از محل نصب، فشار خط، آب‌بندی و ابزار لازم باید بدونم تا بعد از نصب نشتی یا خرابی از انتخاب اشتباه نباشه؟")

    elif fam in {"valve", "automatic_valve", "air_valve"}:
        add(out, "compatibility", f"seogod:{fam}:system-fit",
            f"برای اینکه {name} با خط من سازگار باشه، سایز و جنس لوله، نوع اتصال، جهت جریان، فشار کاری و نقشی که شیر باید در سیستم داشته باشه رو باید اعلام کنم؟")
        add(out, "maintenance", f"seogod:{fam}:service",
            f"قبل از خرید {name} چه نکاتی درباره دسترسی برای سرویس، رسوب یا ذرات آب و قطعاتی که ممکنه نیاز به بازبینی دوره‌ای داشته باشن باید بررسی کنم؟")

    elif fam == "filter":
        add(out, "selection", "seogod:filter:water-source",
            f"برای انتخاب {name} منبع آب، نوع ذرات یا رسوب، دبی سیستم، سایز ورودی و خروجی و کیفیت آب رو باید چطور مشخص کنم تا فیلتر کم‌ظرفیت یا نامتناسب نگیرم؟")
        add(out, "maintenance", "seogod:filter:maintenance",
            f"برای مقایسه {name} با گزینه‌های دیگه، دفعات شست‌وشو، افت فشار، دسترسی به قطعات و شرایط سرویس چه نقشی در هزینه و دردسر واقعی استفاده دارن؟")

    elif fam == "pump":
        add(out, "selection", "seogod:pump:design-inputs",
            f"برای اینکه {name} رو فقط از روی توان یا دهانه انتخاب نکنم، عمق یا ارتفاع مکش، ارتفاع پمپاژ، طول مسیر، دبی مورد نیاز، قطر لوله و اختلاف ارتفاع رو باید بگم؟")
        add(out, "risk_check", "seogod:pump:operating-risk",
            f"قبل از خرید {name} چه اطلاعاتی از منبع برق یا سوخت، مدت کار پیوسته، کیفیت آب و شرایط نصب لازمه تا انتخاب روی کاغذ خوب ولی در مزرعه نامناسب نشه؟")

    elif fam in {"sprinkler", "dripper", "bubbler", "riser"}:
        add(out, "design_scenario", f"seogod:{fam}:field-context",
            f"برای اینکه {name} برای مزرعه یا باغ من درست انتخاب بشه، فشار و دبی واقعی خط، نوع کشت، فاصله‌ها، خاک یا باد و تعداد نقاط مصرف رو باید چطور در نظر بگیرم؟")
        add(out, "compatibility", f"seogod:{fam}:connection",
            f"قبل از سفارش {name} چه سایز اتصال، رزوه، لوله و قطعات مکملی رو باید تطبیق بدم تا موقع نصب چیزی از سبد جا نمونه؟")

    elif fam in {"fertilizer", "fertigation", "adjuvant"}:
        add(out, "suitability", f"seogod:{fam}:context-first",
            f"برای اینکه درباره مناسب بودن {name} تصمیم درستی بگیرم، نوع کشت و مرحله رشد، مساحت، روش مصرف، کیفیت آب و برنامه قبلی تغذیه رو باید اعلام کنم؟")
        add(out, "risk_check", f"seogod:{fam}:evidence-limit",
            f"قبل از استفاده از {name} چه اطلاعاتی از برچسب یا آنالیز محصول، آب و خاک و مواد دیگری که هم‌زمان مصرف میشن لازمه بررسی بشه تا توصیه بر پایه حدس نباشه؟")

    elif fam == "pesticide":
        add(out, "suitability", "seogod:pesticide:diagnosis-first",
            f"قبل از اینکه درباره {name} تصمیم بگیرم، برای تشخیص درست باید عکس یا نشانه‌های آفت یا بیماری، شدت درگیری، مرحله رشد محصول، سم قبلی و شرایط هوا رو اعلام کنم؟")
        add(out, "risk_check", "seogod:pesticide:label-safety",
            f"برای بررسی {name} چه اطلاعاتی از برچسب ثبت‌شده، محصول هدف، دوره کارنس، شرایط آب‌وهوا و مواد هم‌زمان باید از منبع معتبر کنترل بشه تا دوز یا کاربرد حدسی گفته نشه؟")

    elif fam in {"seed", "seedling"}:
        add(out, "suitability", f"seogod:{fam}:season-region",
            f"برای اینکه بفهمم {name} برای کشت من مناسبه، منطقه، فصل، فضای باز یا گلخانه، خاک، آب و هدف برداشت رو باید مشخص کنم؟")
        add(out, "risk_check", f"seogod:{fam}:purchase-risk",
            f"قبل از خرید {name} چه اطلاعاتی درباره منبع و بسته‌بندی، شرایط نگهداری و محدودیت‌های اقلیمی یا کشت باید بررسی بشه تا فقط از روی اسم محصول تصمیم نگیرم؟")

    else:
        add(out, "suitability", f"seogod:{fam}:decision-context",
            f"برای اینکه بفهمم {name} واقعاً برای کار من مناسبه، چه اطلاعاتی از کاربرد، اندازه‌ها، شرایط نصب و محدودیت‌های سیستم باید قبل از خرید مشخص کنم؟")
        add(out, "risk_check", f"seogod:{fam}:wrong-purchase-risk",
            f"رایج‌ترین چیزهایی که باید قبل از سفارش {name} از روی محصول و سیستم خودم تطبیق بدم چیه تا به خاطر سایز، اتصال یا کاربرد اشتباه مجبور به تعویض نشم؟")

    return out


def candidates_v18(p, fam, style, rng):
    out = list(orig_candidates(p, fam, style, rng) or [])
    existing_keys = {str(x.get("key") or "") for x in out}
    for candidate in _family_decision_candidates(p, fam, rng):
        if candidate["key"] not in existing_keys:
            out.append(candidate)
    return out


def guard_v18(p, candidate, question):
    ok, reason = orig_guard(p, candidate, question)
    if not ok:
        return ok, reason
    key = str(candidate.get("key") or "")
    if not key.startswith("seogod:"):
        return True, None

    text = q.b.norm(str(question or ""))
    ref = q.b.norm(q.b.ref_name(p))
    if ref and ref not in text and q.b.norm("این محصول") not in text:
        return False, "SEO God decision question lost selected product context"

    unsupported = [
        "حتما مناسب", "حتماً مناسب", "قطعا مناسب", "قطعاً مناسب", "تضمین نتیجه",
        "دوز قطعی", "بدون نیاز به بررسی", "برای همه زمین ها", "برای همه زمین‌ها",
    ]
    if any(q.b.norm(x) in text for x in unsupported):
        return False, "unsupported certainty in SEO God decision question"
    return True, None


q.guarded_candidates = candidates_v18
q.consistency_guard = guard_v18


def main():
    q.main()


if __name__ == "__main__":
    main()
