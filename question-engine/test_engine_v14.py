#!/usr/bin/env python3
import importlib.util
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe14", os.path.join(ROOT, "engine_v14.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


def p(name, categories=None):
    return {
        "id": 1,
        "name": name,
        "status": "publish",
        "categories": [{"name": x} for x in (categories or [])],
        "tags": [],
        "attributes": [],
        "description": "",
        "short_description": "",
        "reviews_allowed": True,
    }


cases = [
    (p("کود کامل نمونه"), "fertilizer", ["مرحله رشد", "مساحت", "آب", "خاک"]),
    (p("سم نمونه"), "pesticide", ["آفت", "بیماری", "شرایط هوا"]),
    (p("بذر گوجه نمونه", ["بذرهای کشاورزی"]), "seed", ["منطقه", "فصل کاشت", "مساحت"]),
    (p("چای ترش", ["نشاء"]), "seedling", ["فصل انتقال", "آب", "خاک"]),
    (p("نوار تیپ نمونه"), "drip_tape", ["فاصله ردیف", "طول ردیف", "فشار"]),
    (p("لوله نخدار 3 اینچ"), "pipe", ["دبی", "طول مسیر", "اختلاف ارتفاع"]),
    (p("رابط پلی اتیلن 2 اینچ"), "fitting", ["جنس لوله", "قطر", "رزوه"]),
    (p("شیر توپی 2 اینچ"), "valve", ["جنس لوله", "نوع اتصال", "فشار"]),
    (p("پمپ کف کش نمونه", ["کف کش و لجن کش"]), "pump", ["عمق", "ارتفاع", "دبی"]),
    (p("فیلتر دیسکی نمونه"), "filter", ["منبع آب", "دبی", "ورودی"]),
    (p("آبپاش نمونه"), "sprinkler", ["فشار", "دبی", "باد"]),
    (p("دریپر نمونه", ["قطره چکان (دریپر)"]), "dripper", ["نوع خاک", "فشار", "تعداد دریپر"]),
    (p("بابلر تنظیمی زلال رود"), "bubbler", ["بافت خاک", "فشار", "خیس"]),
    (p("شیر تخلیه هوا 1 اینچ"), "air_valve", ["نقاط بلند", "اختلاف ارتفاع", "فشار"]),
    (p("شیر خودکار پلیمری ویسپار 1 اینچ"), "automatic_valve", ["جهت جریان", "سایز اتصال", "فشار"]),
    (p("موتور برق نمونه", ["موتور برق و پمپ بنزینی"]), "power_equipment", ["توان مصرفی", "جریان راه اندازی", "کار پیوسته"]),
    (p("رایزر آلمینیومی 2 اینچ"), "riser", ["سایز آبپاش", "رزوه", "دبی"]),
    (p("تانک کود 100 لیتری"), "fertigation", ["دبی", "فشار", "حجم محلول"]),
    (p("پیچ و مهره 80*14", ["پیچ و مهره"]), "hardware", ["قطر", "طول پیچ", "گام رزوه"]),
    (p("مته دستی قطر 18 میلیمتر"), "irrigation_tool", ["جنس", "ضخامت", "قطر اتصال"]),
    (p("سورفکتانت غیر یونی"), "adjuvant", ["اسم محصول اصلی", "حجم آب", "کیفیت آب"]),
]

for idx, (product, expected_fam, required_terms) in enumerate(cases):
    fam = q.b.family(product)
    assert fam == expected_fam, (product["name"], fam, expected_fam)
    rng = random.Random(1400 + idx)
    cands = q.guarded_candidates(product, fam, "colloquial", rng)
    old = [c for c in cands if str(c.get("key") or "") == f"human:simple:{fam}"]
    assert not old, (fam, old)
    new = [c for c in cands if str(c.get("key") or "") == f"human:simple:v14:{fam}"]
    assert len(new) == 1, (fam, new)
    core = new[0]["core"]
    assert q.b.ref_name(product) in core, (fam, core)
    for term in required_terms:
        assert q.b.norm(term) in q.b.norm(core), (fam, term, core)
    ok, reason = q.consistency_guard(product, new[0], core)
    assert ok, (fam, reason, core)

# Non-colloquial styles should not inject the novice prompt.
prod = p("کود کامل نمونه")
for style in ["conversational", "experienced", "technical"]:
    cands = q.guarded_candidates(prod, "fertilizer", style, random.Random(9))
    assert not [c for c in cands if str(c.get("key") or "").startswith("human:simple:v14:")]

print("PASS v14")
