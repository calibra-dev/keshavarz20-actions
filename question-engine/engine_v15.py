#!/usr/bin/env python3
import importlib.util
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe14", os.path.join(ROOT, "engine_v14.py"))
v14 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v14)
q = v14.q


def _shadow_state(state, rejected_product_ids):
    shadow = dict(state)
    counts = dict(state.get("product_counts") or {})
    for pid in rejected_product_ids:
        # Keep coverage semantics, but temporarily move a product out of the
        # minimum-count pool after it has exhausted its usable candidates.
        counts[str(int(pid))] = int(counts.get(str(int(pid)), 0)) + 1000000
    shadow["product_counts"] = counts
    shadow["recent_product_ids"] = list(state.get("recent_product_ids") or [])
    return shadow


def prepare_plan_v15(wp, cfg, state, rng):
    products = wp.products(cfg)
    if not products:
        raise RuntimeError("No products returned for quality planner")

    threshold = int(cfg.get("quality_threshold", 97))
    max_products = max(1, min(int(cfg.get("quality_retry_products", 16)), len(products)))
    max_wraps = max(1, min(int(cfg.get("quality_retry_wraps", 2)), 4))
    max_candidates = max(1, min(int(cfg.get("quality_retry_candidates", 24)), 60))

    # Keep style/politeness targets tied to the real state. A rejected candidate
    # must not silently change campaign distribution targets.
    style = q.style_from_state(state, cfg, rng)
    polite = q.polite_from_state(state, cfg, rng)

    rejected_products = set()
    diagnostics = []

    for _product_attempt in range(max_products):
        shadow = _shadow_state(state, rejected_products)
        basic = q.choose_product(products, shadow, rng)
        pid = int(basic["id"])
        if pid in rejected_products:
            # Defensive guard in case a future choose_product implementation
            # stops honoring product_counts.
            continue

        p = wp.product(pid)
        fam = q.fam_of(p)
        comments = wp.comments(pages=5, post=pid)
        existing = [q.b.comment_text(x) for x in comments if q.b.comment_text(x)]

        candidates = list(q.guarded_candidates(p, fam, style, rng) or [])
        rng.shuffle(candidates)
        candidate_attempts = 0

        for candidate in candidates:
            if candidate_attempts >= max_candidates:
                break
            core = str(candidate.get("core") or "").strip()
            if not core:
                diagnostics.append({"product_id": pid, "key": candidate.get("key"), "reason": "empty-core"})
                continue
            if any(q.b.jaccard(core, old) >= .72 for old in existing):
                diagnostics.append({"product_id": pid, "key": candidate.get("key"), "reason": "core-duplicate"})
                continue
            ok, reason = q.consistency_guard(p, candidate, core)
            if not ok:
                diagnostics.append({"product_id": pid, "key": candidate.get("key"), "reason": reason or "core-guard"})
                continue

            candidate_attempts += 1
            for _wrap_attempt in range(max_wraps):
                question = q.b.wrap(core, polite, style, rng)
                score, qreason = q.question_quality(p, question, candidate, fam, existing)
                if score >= threshold:
                    return {
                        "product": p,
                        "family": fam,
                        "candidate": candidate,
                        "question": question,
                        "style": style,
                        "polite": polite,
                        "score": score,
                        "catalog_size": len(products),
                    }
                diagnostics.append({
                    "product_id": pid,
                    "key": candidate.get("key"),
                    "score": int(score),
                    "reason": qreason or "quality-below-threshold",
                })

        rejected_products.add(pid)

    tail = diagnostics[-12:]
    raise RuntimeError(
        "No quality-approved plan after retries: "
        f"threshold={threshold} products_tried={len(rejected_products)} diagnostics={tail}"
    )


q.prepare_plan = prepare_plan_v15


def main():
    q.main()


if __name__ == "__main__":
    main()
