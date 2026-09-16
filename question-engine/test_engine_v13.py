#!/usr/bin/env python3
import importlib.util
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe13", os.path.join(ROOT, "engine_v13.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


def p(name, categories=None, tags=None):
    return {
        "id": 1,
        "name": name,
        "status": "publish",
        "categories": [{"name": x} for x in (categories or [])],
        "tags": [{"name": x} for x in (tags or [])],
        "attributes": [],
        "description": "",
        "short_description": "",
        "reviews_allowed": True,
    }


cases = [
    (p("بابلر تنظیمی زلال رود", ["آبیاری قطره‌ای", "لوازم آبیاری"]), "bubbler"),
    (p("بابلر قارچی بزرگ زلال رود", ["آبیاری قطره‌ای"]), "bubbler"),
    (p("بابلر ۷۵ لیتری زلال رود", ["آبیاری قطره‌ای"]), "bubbler"),
    (p("شیر تخلیه هوا 1 اینچ", ["لوازم جانبی"]), "air_valve"),
    (p("شیر تخلیه هوا 2 اینچ", ["لوازم جانبی"]), "air_valve"),
    (p("شیر خودکار پلیمری ویسپار 1 اینچ", ["لوازم جانبی"]), "automatic_valve"),
    (p("شیر خودکار پلیمری ویسپار 2 اینچ", ["لوازم جانبی"]), "automatic_valve"),
    (p("مته دستی قطر 18 میلیمتر", ["لوازم جانبی"]), "irrigation_tool"),
]

for product, expected in cases:
    got = q.b.family(product)
    assert got == expected, (product["name"], got, expected)

# Existing specific valve families must remain unchanged.
assert q.b.family(p("شیر توپی پلیمری 2 اینچ", ["شیرآلات پلی اتیلن"])) == "valve"
assert q.b.family(p("شیر پروانه‌ای پلیمری 3 اینچ", ["شیرآلات پلی اتیلن"])) == "valve"

rng = random.Random(13)
for fam, product, prefix in [
    ("bubbler", p("بابلر تنظیمی زلال رود"), "bubbler:"),
    ("air_valve", p("شیر تخلیه هوا 1 اینچ"), "air-valve:"),
    ("automatic_valve", p("شیر خودکار پلیمری ویسپار 1 اینچ"), "automatic-valve:"),
    ("irrigation_tool", p("مته دستی قطر 18 میلیمتر"), "irrigation-tool:"),
]:
    cands = q.guarded_candidates(product, fam, "conversational", rng)
    specific = [c for c in cands if str(c.get("key") or "").startswith(prefix)]
    assert specific, (fam, prefix)
    for c in specific:
        ok, reason = q.consistency_guard(product, c, c["core"])
        assert ok, (fam, c, reason)

print("PASS v13")
