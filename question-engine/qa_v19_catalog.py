#!/usr/bin/env python3
import importlib.util
import json
import os
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ROOT)
spec = importlib.util.spec_from_file_location("qe19", os.path.join(ROOT, "engine_v19.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
q = m.q


def main():
    cfg = q.b.load_cfg()
    wp = q.b.WP()
    products = wp.products(cfg)
    if not products:
        raise SystemExit("No catalog products")
    rng = random.Random(190027)
    generated = []
    history = []
    blockers = []
    per_product = {}

    for p in products:
        fam = q.fam_of(p)
        per_product.setdefault(str(p["id"]), {"family": fam, "count": 0, "intents": set(), "scenario_keys": set()})
        for seed in range(6):
            local = random.Random((int(p["id"]) * 1009) + seed)
            style = ("colloquial", "experienced", "technical")[seed % 3]
            candidates = list(q.guarded_candidates(p, fam, style, local) or [])
            local.shuffle(candidates)
            for item in candidates:
                question = q.b.wrap(str(item.get("core") or ""), False, style, local)
                ok, reason = q.consistency_guard(p, item, question)
                if not ok:
                    blockers.append({"product_id": int(p["id"]), "key": item.get("key"), "reason": reason})
                    continue
                score, reason = q.question_quality(p, question, item, fam, history[-200:])
                if score < 97:
                    continue
                pub = q.public_plan({
                    "product": p, "family": fam, "candidate": item, "question": question,
                    "style": style, "polite": False, "score": score, "catalog_size": len(products),
                })
                generated.append(pub)
                history.append(pub["question"])
                row = per_product[str(p["id"])]
                row["count"] += 1
                row["intents"].add(pub["intent_v19"])
                row["scenario_keys"].update((pub.get("scenario_dimensions") or {}).keys())
                if per_product[str(p["id"])]["count"] >= 3:
                    break
            if per_product[str(p["id"])]["count"] >= 3:
                break

    uncovered=[int(pid) for pid,row in per_product.items() if int(row["count"]) < 1]

    duplicate_pairs = 0
    comparisons = 0
    tail = generated[-200:]
    for i in range(len(tail)):
        for j in range(i):
            comparisons += 1
            if q.b.jaccard(tail[i]["question"], tail[j]["question"]) >= 0.82:
                duplicate_pairs += 1
    duplicate_rate = duplicate_pairs / comparisons if comparisons else 0.0

    ledger = []
    for pid, row in sorted(per_product.items(), key=lambda kv: int(kv[0])):
        ledger.append({
            "product_id": int(pid),
            "family": row["family"],
            "intent_count": len(row["intents"]),
            "scenario_dimensions_seen": sorted(row["scenario_keys"]),
            "approved_candidate_count": row["count"],
        })

    report = {
        "ok": len(generated) >= 1000 and not uncovered,
        "engine_version": 19,
        "catalog_products": len(products),
        "approved_candidates": len(generated),
        "semantic_duplicate_rate_last_200": round(duplicate_rate, 6),
        "blocker_count": len(blockers),
        "blocker_sample": blockers[:50],
        "products_covered": sum(1 for row in per_product.values() if int(row["count"]) >= 1),
        "uncovered_product_ids": uncovered,
        "uncovered_count": len(uncovered),
        "coverage_ledger": ledger,
        "products_covered": sum(1 for row in per_product.values() if int(row["count"]) >= 1),
        "acceptance": {
            "approved_candidates_gte_1000": len(generated) >= 1000,
            "all_catalog_products_covered": all(int(row["count"]) >= 1 for row in per_product.values()),
            "semantic_duplicate_rate_below_0_10": duplicate_rate < 0.10,
            "synthetic_evidence_label_preserved": all(x.get("evidence_classification") == "synthetic_editorial_question_generator_not_customer_evidence" for x in generated),
        },
    }
    out_dir = os.path.join(REPO_ROOT, "question-engine-results")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "v19-catalog-qa.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in ("ok", "engine_version", "catalog_products", "products_covered", "uncovered_count", "approved_candidates", "semantic_duplicate_rate_last_200", "blocker_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
