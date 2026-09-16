#!/usr/bin/env python3
import importlib.util
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe17", os.path.join(ROOT, "engine_v17.py"))
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


# 1) A nitrogen fertilizer must get concrete compatibility questions, not
#    the old generic 'with other fertilizers' wording.
nitrogen = product("کود نیتروژن ۳۰ درصد مخصوص کودآبیاری")
assert q.fam_of(nitrogen) == "fertilizer", q.fam_of(nitrogen)
assert m.fertilizer_profile(nitrogen) == "nitrogen", m.fertilizer_profile(nitrogen)

candidates = q.guarded_candidates(nitrogen, "fertilizer", "experienced", random.Random(17))
mix = [x for x in candidates if x.get("intent") == "mix"]
assert len(mix) >= 4, len(mix)
texts = [m.canon(x.get("core")) for x in mix]
assert any("10 52 10" in x for x in texts), texts
assert any("سولفات پتاسیم" in x for x in texts), texts
assert all("کودهای دیگه" not in x and "کودهای دیگر" not in x for x in texts), texts
for candidate in mix:
    ok, reason = q.consistency_guard(nitrogen, candidate, candidate["core"])
    assert ok, (candidate, reason)

# 2) A 10-52-10 product should not select 10-52-10 again as the second fertilizer.
#    The product name itself naturally remains in the question, so inspect the semantic key.
phosphate = product("کود NPK 10-52-10 فسفر بالا")
assert m.fertilizer_profile(phosphate) == "phosphorus", m.fertilizer_profile(phosphate)
ph_mix = [x for x in q.guarded_candidates(phosphate, "fertilizer", "experienced", random.Random(3)) if x.get("intent") == "mix"]
assert ph_mix, "no specific mix candidates for 10-52-10"
assert all(":کود-10-52-10:" not in str(x.get("key") or "") for x in ph_mix), ph_mix
assert any(":اوره:" in str(x.get("key") or "") for x in ph_mix), ph_mix
assert any("سولفات پتاسیم" in m.canon(x["core"]) for x in ph_mix), ph_mix

# 3) The exact live PE end-cap pattern must never inherit a random PVC/lay-flat line.
endcap = product("درپوش انتهایی پیچی آبلوله 63میلیمتر پلی اتیلن")
assert q.fam_of(endcap) == "fitting", q.fam_of(endcap)
assert q.fitting_subtype(endcap) == "endcap", q.fitting_subtype(endcap)
line = m.fitting_line_context(endcap)
assert line == "لوله پلی‌اتیلن 63 میلی‌متر", line
fit = q.guarded_candidates(endcap, "fitting", "experienced", random.Random(9))
keys = [str(x.get("key") or "") for x in fit]
assert not any(x.startswith("installer:existing-line:fitting:") for x in keys), keys
assert not any(x.startswith("postinstall:leak:fitting:") for x in keys), keys
matched = [x for x in fit if str(x.get("key") or "").startswith("postinstall:matched-line:fitting:")]
assert matched, keys
for candidate in matched:
    text = m.canon(candidate["core"])
    assert "لوله پلی اتیلن 63 میلی متر" in text, text
    assert "پولیکا" not in text and "لی فلت" not in text and "u pvc" not in text, text
    ok, reason = q.consistency_guard(endcap, candidate, candidate["core"])
    assert ok, (candidate, reason)

print("PASS v17")
