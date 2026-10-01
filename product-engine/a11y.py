from __future__ import annotations

from typing import Any

SHARED_RENDERER_AUDITS={
    "button-name",
    "link-name",
    "meta-viewport",
    "target-size",
    "image-aspect-ratio",
    "image-size-responsive",
}


def analyze(result: dict[str,Any]) -> dict[str,Any]:
    diagnostics=result.get("diagnostics") or {}
    failures=diagnostics.get("failing_audits") or []
    accessibility=[x for x in failures if x.get("category")=="accessibility"]
    shared=[]
    mixed=[]
    product=[]
    for item in accessibility:
        aid=str(item.get("id") or "")
        selectors=[str(x.get("selector") or "") for x in (item.get("items") or [])]
        if aid in SHARED_RENDERER_AUDITS:
            shared.append(aid)
        elif any("product-" in s or "short-description" in s or "product_meta" in s for s in selectors):
            product.append(aid)
        else:
            mixed.append(aid)
    scores=[int(x.get("accessibility") or 0) for x in (result.get("samples") or []) if not x.get("error")]
    return {
        "scores":scores,
        "shared_renderer_audits":sorted(set(shared)),
        "product_scoped_audits":sorted(set(product)),
        "mixed_or_unknown_audits":sorted(set(mixed)),
        "failing_audit_ids":sorted(set(str(x.get("id") or "") for x in accessibility)),
    }
