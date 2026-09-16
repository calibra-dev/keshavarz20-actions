#!/usr/bin/env python3
import importlib.util, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe11",os.path.join(ROOT,"engine_v11.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def p(name,desc="",categories=None,tags=None,attributes=None):
    return {"id":1,"name":name,"status":"publish","categories":categories or [],"tags":tags or [],"attributes":attributes or [],"description":desc,"short_description":"","reviews_allowed":True}

cases={
    "بوشن رزوه ای پليمري 3/4 ویسپار (پايا) u-pvc":"fitting",
    "مغزی پلی اتیلن 2 اینچ":"fitting",
    "مهره ماسوره پلیمری 3 اینچ":"fitting",
    "سه راه نر پلیمری 2 اینچ":"fitting",
    "شیر توپی پلیمری 2 اینچ":"valve",
    "فیلتر دیسکی 3 اینچ":"filter",
    "تانک کود 100 لیتری":"fertigation",
    "نوار تیپ 20 سانت":"drip_tape",
    "لوله نخدار 3 اینچ":"pipe",
    "آبپاش پلیمری 1 اینچ":"sprinkler",
    "کود آهن نمونه":"fertilizer",
}
for name,expected in cases.items():
    got=m.family_v11(p(name,"مناسب اتصال به لوله پلی اتیلن"))
    assert got==expected,(name,got,expected)

# Free-form copy must never turn a seedling/product into fertilizer.
chay=p(
    "چای ترش",
    "برای رشد بهتر می‌توان درباره کود آهن، پتاس، NPK، کلسیم و هیومیک مطالعه کرد",
    categories=[{"id":724,"name":"محصولات کشاورزی"},{"id":793,"name":"نشاء"}],
)
assert m.family_v11(chay)=="generic",m.family_v11(chay)

# Structured taxonomy can still classify an otherwise ambiguous product.
structured_fertilizer=p("محصول نمونه",categories=[{"id":1,"name":"کود و تغذیه گیاه"}])
assert m.family_v11(structured_fertilizer)=="fertilizer",m.family_v11(structured_fertilizer)

# If description says fertilizer but structured taxonomy says nothing relevant, fail safe to generic.
desc_only=p("محصول نمونه","کود آهن پتاس فسفر NPK کلسیم ریز مغذی")
assert m.family_v11(desc_only)=="generic",m.family_v11(desc_only)

assert m.fitting_subtype_v11(p("بوشن رزوه ای 3/4"))=="bushing"
assert m.fitting_subtype_v11(p("مغزی 2 اینچ"))=="nipple"
assert m.fitting_subtype_v11(p("مهره ماسوره 2 اینچ"))=="union"
assert m.q.b.family(p("بوشن رزوه ای پليمري 3/4 ویسپار u-pvc","برای اتصال لوله"))=="fitting"
assert m.q.b.family(chay)=="generic"
assert m.q.recent_generated_comments is m.recent_generated_comments_v11
print("PASS v11")
