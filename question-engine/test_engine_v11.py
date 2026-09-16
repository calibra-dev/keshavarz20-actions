#!/usr/bin/env python3
import importlib.util, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe11",os.path.join(ROOT,"engine_v11.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def p(name,desc=""):
    return {"id":1,"name":name,"status":"publish","categories":[],"tags":[],"attributes":[],"description":desc,"short_description":"","reviews_allowed":True}

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
assert m.fitting_subtype_v11(p("بوشن رزوه ای 3/4"))=="bushing"
assert m.fitting_subtype_v11(p("مغزی 2 اینچ"))=="nipple"
assert m.fitting_subtype_v11(p("مهره ماسوره 2 اینچ"))=="union"
assert m.q.b.family(p("بوشن رزوه ای پليمري 3/4 ویسپار u-pvc","برای اتصال لوله"))=="fitting"
assert m.q.recent_generated_comments is m.recent_generated_comments_v11
print("PASS v11")
