#!/usr/bin/env python3
import argparse
import collections
import datetime as dt
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
CLASSIFIER_VERSION = "v13"

spec = importlib.util.spec_from_file_location("qe13", os.path.join(ROOT, "engine_v13.py"))
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
q = engine.q


def names(rows):
    return [str(x.get("name") or "").strip() for x in (rows or []) if str(x.get("name") or "").strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    args = ap.parse_args()

    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    wp = q.FastWP()
    products = wp.products(cfg)
    family_counts = collections.Counter()
    category_counts = collections.Counter()
    generic_category_counts = collections.Counter()
    family_category_counts = collections.defaultdict(collections.Counter)
    generic_products = []

    for p in products:
        fam = q.b.family(p)
        family_counts[fam] += 1
        cats = names(p.get("categories"))
        tags = names(p.get("tags"))
        for cat in cats:
            category_counts[cat] += 1
            family_category_counts[fam][cat] += 1
        if fam == "generic":
            for cat in cats:
                generic_category_counts[cat] += 1
            generic_products.append({
                "id": int(p.get("id") or 0),
                "name": str(p.get("name") or ""),
                "categories": cats,
                "tags": tags,
            })

    generic_products.sort(key=lambda x: (x["categories"], x["name"], x["id"]))
    out = {
        "ok": True,
        "classifier_version": CLASSIFIER_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "catalog_size": len(products),
        "family_counts": dict(sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "generic_count": family_counts.get("generic", 0),
        "category_counts": dict(category_counts.most_common()),
        "generic_category_counts": dict(generic_category_counts.most_common()),
        "family_category_counts": {
            fam: dict(counter.most_common()) for fam, counter in sorted(family_category_counts.items())
        },
        "generic_products": generic_products,
    }

    os.makedirs(os.path.dirname(args.result) or ".", exist_ok=True)
    with open(args.result, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        "ok": True,
        "classifier_version": CLASSIFIER_VERSION,
        "catalog_size": out["catalog_size"],
        "generic_count": out["generic_count"],
        "family_counts": out["family_counts"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
