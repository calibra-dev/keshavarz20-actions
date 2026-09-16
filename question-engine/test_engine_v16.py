#!/usr/bin/env python3
import importlib.util
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe16", os.path.join(ROOT, "engine_v16.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


def product(name):
    return {
        "id": 1,
        "name": name,
        "status": "publish",
        "categories": [],
        "tags": [],
        "attributes": [],
        "description": "",
        "short_description": "",
        "reviews_allowed": True,
    }


cases = [
    ("اتصال فلنچدار پلی اتیلن آبلوله 2 × 63 میلیمتر", "fitting", "flange"),
    ("اتصال فلنجدار پلی اتیلن 63 میلیمتر", "fitting", "flange"),
    ("فلنچ پلی اتیلن 2 اینچ", "fitting", "flange"),
    ("فلنج پلی اتیلن 2 اینچ", "fitting", "flange"),
]

for name, expected_family, expected_subtype in cases:
    p = product(name)
    assert q.b.family(p) == expected_family, (name, q.b.family(p), expected_family)
    assert q.fam_of(p) == expected_family, (name, q.fam_of(p), expected_family)
    assert q.fitting_subtype(p) == expected_subtype, (name, q.fitting_subtype(p), expected_subtype)

# The narrow spelling fix must not steal real pipes from the pipe family.
pipe = product("لوله پلی اتیلن 63 میلیمتر 10 بار")
assert q.b.family(pipe) == "pipe", q.b.family(pipe)
assert q.fam_of(pipe) == "pipe", q.fam_of(pipe)

# Existing fitting behavior must remain intact.
existing = product("زانو پلی اتیلن پیچی 63 میلیمتر")
assert q.b.family(existing) == "fitting", q.b.family(existing)
assert q.fitting_subtype(existing) == "elbow", q.fitting_subtype(existing)

print("PASS v16")
