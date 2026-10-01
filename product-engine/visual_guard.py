from __future__ import annotations

import re
from typing import Any


def _count(html: str, marker: str) -> int:
    return (html or "").count(marker)


def compare(before_product: dict[str,Any], after_product: dict[str,Any], html_before: str, html_after: str, policy: dict[str,Any] | None=None) -> dict[str,Any]:
    policy=policy or {}
    issues=[]
    markers={}
    for marker in policy.get("critical_markers") or []:
        b=_count(html_before,marker)
        a=_count(html_after,marker)
        markers[marker]={"before":b,"after":a}
        if b>0 and a==0:
            issues.append(f"critical marker disappeared: {marker}")
    before_images=[int(x.get("id") or 0) for x in (before_product.get("images") or [])]
    after_images=[int(x.get("id") or 0) for x in (after_product.get("images") or [])]
    if len(before_images)!=len(after_images):
        issues.append("product image slot count changed")
    h1_before=len(re.findall(r"<h1\\b",html_before or "",re.I))
    h1_after=len(re.findall(r"<h1\\b",html_after or "",re.I))
    if h1_before!=h1_after:
        issues.append(f"H1 count changed {h1_before}->{h1_after}")
    for token in ("status","type"):
        if before_product.get(token)!=after_product.get(token):
            issues.append(f"product {token} changed")
    return {
        "ok":not issues,
        "issues":issues,
        "markers":markers,
        "image_slots":{"before":before_images,"after":after_images},
        "h1_count":{"before":h1_before,"after":h1_after},
    }
