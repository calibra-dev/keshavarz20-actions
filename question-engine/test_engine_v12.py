#!/usr/bin/env python3
import importlib.util
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe12", os.path.join(ROOT, "engine_v12.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


def p(name, categories=None, tags=None, desc=""):
    return {
        "id": 1,
        "name": name,
        "status": "publish",
        "categories": [{"name": x} for x in (categories or [])],
        "tags": [{"name": x} for x in (tags or [])],
        "attributes": [],
        "description": desc,
        "short_description": "",
        "reviews_allowed": True,
    }


cases = [
    (p("بذر گوجه افرا تایلند", ["بذرهای کشاورزی", "نهاده های کشاورزی"], ["بذر"]), "seed"),
    (p("چای ترش", ["محصولات کشاورزی", "نشاء"], [], "کود آهن و پتاس در متن توضیحات آمده"), "seedling"),
    (p("پمپ کف کش 16 متری 2 اینچ", ["ابزارآلات و تجهیزات صنعتی", "کف کش و لجن کش"]), "pump"),
    (p("ست کنترل اتوماتیک پمپ آب", ["ابزارآلات و تجهیزات صنعتی", "پمپ و ست کنترل"]), "pump"),
    (p("موتور برق 3 کیلو وات", ["ابزارآلات و تجهیزات صنعتی", "موتور برق و پمپ بنزینی"]), "power_equipment"),
    (p("موتور جوش نمونه", ["ابزارآلات و تجهیزات صنعتی", "موتور برق و پمپ بنزینی"]), "power_equipment"),
    (p("رایزر آلمینیومی 1 متری 2 اینچ", ["تجهیزات و لوازم کشاورزی", "رایزر پلیمری"]), "riser"),
    (p("دریپر خود شوینده ۸ لیتری", ["آبیاری قطره‌ای", "قطره چکان (دریپر)"]), "dripper"),
    (p("پیچ و مهره 80*14", ["پیچ و مهره", "لوازم جانبی"]), "hardware"),
    (p("سورفکتانت غیر یونی و خیس‌کننده فیت ایکس گرین", ["ایکس گرین (XGreen)", "كودهای کشاورزی", "نهاده های کشاورزی"]), "adjuvant"),
    (p("چپقی رزوه ای ویسپار 1 اینچ u-pvc", ["اتصالات u-pvc"]), "fitting"),
    (p("کپ رزوه ای u-pvc ویسپار 2 اینچ", ["اتصالات u-pvc"]), "fitting"),
    (p("انشعاب دوشاخه ۱۶×۱/۲", ["آبیاری قطره‌ای", "انشعابات و بست ها"]), "fitting"),
]

for product, expected in cases:
    got = q.b.family(product)
    assert got == expected, (product["name"], got, expected)

# Existing v11 families must keep precedence over broad structured categories.
assert q.b.family(p("سم اتفون نمونه", ["بذرهای کشاورزی", "نهاده های کشاورزی"])) == "pesticide"
assert q.b.family(p("کود آهن نمونه", ["كودهای کشاورزی"])) == "fertilizer"
assert q.b.family(p("شیر توپی پلیمری 2 اینچ", ["اتصالات u-pvc"])) == "valve"

rng = random.Random(12)
for fam, product, prefix in [
    ("seed", p("بذر گوجه نمونه", ["بذرهای کشاورزی"]), "seed:"),
    ("seedling", p("چای ترش", ["نشاء"]), "seedling:"),
    ("pump", p("پمپ کف کش 16 متری", ["کف کش و لجن کش"]), "pump:"),
    ("power_equipment", p("موتور برق نمونه", ["موتور برق و پمپ بنزینی"]), "power:"),
    ("riser", p("رایزر آلمینیومی 2 اینچ", ["رایزر پلیمری"]), "riser:"),
    ("dripper", p("دریپر ۸ لیتری", ["قطره چکان (دریپر)"]), "dripper:"),
    ("hardware", p("پیچ و مهره 80*14", ["پیچ و مهره"]), "hardware:"),
    ("adjuvant", p("سورفکتانت غیر یونی", ["كودهای کشاورزی"]), "adjuvant:"),
]:
    cands = q.guarded_candidates(product, fam, "conversational", rng)
    specific = [c for c in cands if str(c.get("key") or "").startswith(prefix)]
    assert specific, (fam, prefix)
    for c in specific:
        ok, reason = q.consistency_guard(product, c, c["core"])
        assert ok, (fam, c, reason)

# Regression: free description text must still never change an otherwise unknown product into fertilizer.
unknown = p("محصول ناشناخته", ["محصولات کشاورزی"], [], "کود آهن، پتاس، فسفر و هیومیک")
assert q.b.family(unknown) == "generic"

print("PASS v12")
