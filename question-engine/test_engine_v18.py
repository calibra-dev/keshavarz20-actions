#!/usr/bin/env python3
import importlib.util
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe18", os.path.join(ROOT, "engine_v18.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


def product(name, description=""):
    return {
        "id": 1,
        "name": name,
        "status": "publish",
        "categories": [],
        "tags": [],
        "attributes": [],
        "description": description,
        "short_description": "",
        "reviews_allowed": True,
    }

# Drip tape gets farmer-decision candidates, not generic SEO filler.
p = product("نوار تیپ آبیاری 20 سانتی")
fam = q.fam_of(p)
items = q.guarded_candidates(p, fam, "experienced", random.Random(18))
seo = [x for x in items if str(x.get("key") or "").startswith("seogod:")]
assert seo, "SEO God candidates missing"
assert any(x.get("intent") == "water_efficiency" for x in seo), seo
assert any(x.get("intent") == "total_cost" for x in seo), seo
for item in seo:
    ok, reason = q.consistency_guard(p, item, item["core"])
    assert ok, (item, reason)

# Pipe questions must ask for design context instead of claiming a size is correct.
pipe = product("لوله نخدار 4 اینچ")
items = q.guarded_candidates(pipe, q.fam_of(pipe), "experienced", random.Random(4))
seo = [x for x in items if str(x.get("key") or "").startswith("seogod:")]
blob = " ".join(x["core"] for x in seo)
assert "دبی" in blob and "اختلاف ارتفاع" in blob and "هزینه کل" in blob, blob
assert "حتماً مناسب" not in blob and "قطعا مناسب" not in blob, blob

# Pesticide intelligence must stay diagnosis/label first and never invent dose.
pest = product("حشره کش نمونه")
items = q.guarded_candidates(pest, q.fam_of(pest), "experienced", random.Random(2))
seo = [x for x in items if str(x.get("key") or "").startswith("seogod:")]
blob = " ".join(x["core"] for x in seo)
assert "برچسب" in blob or "آفت" in blob, blob
assert "دوز قطعی" not in blob, blob

assert m.POLICY["policy_version"] == "seo-god-2026.09.18"
print("PASS v18")
