from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
import os

from core import bridge, cache_purge

def _basename(url: str) -> str:
    try:
        return os.path.basename(urlparse(url).path)
    except Exception:
        return ""

def maybe_optimize_featured(product: dict[str,Any], baseline: dict[str,Any]) -> dict[str,Any]:
    rep=baseline.get("representative") or {}
    if int(rep.get("performance") or 0)>=96:
        return {"attempted":False,"reason":"baseline already >=96"}
    images=product.get("images") or []
    if not images:
        return {"attempted":False,"reason":"no product image"}
    featured=images[0]
    aid=int(featured.get("id") or 0)
    src=str(featured.get("src") or "")
    if not aid or not src:
        return {"attempted":False,"reason":"featured image identity unavailable"}

    top=baseline.get("top_network_requests") or []
    source_name=_basename(src)
    relevant=False
    for req in top:
        if source_name and source_name.split(".")[0] in str(req.get("url") or ""):
            relevant=True
            break
    if not relevant:
        return {"attempted":False,"reason":"featured image not a top transferred resource"}

    hashed=bridge("media.hash",dry_run=True,payload={"attachment_id":aid}).get("result") or {}
    byte_count=int(hashed.get("bytes") or 0)
    if byte_count and byte_count<280000:
        return {"attempted":False,"reason":"featured source below optimization threshold","bytes":byte_count}

    optimized=bridge("media.optimize",payload={
        "attachment_id":aid,"mime":"image/webp","quality":82,"max_dimension":1600
    }).get("result") or {}
    new_id=int(optimized.get("new_attachment_id") or 0)
    if not new_id:
        return {"attempted":False,"reason":"media.optimize produced no attachment","source_attachment_id":aid}

    bound=bridge("asset.featured.set",payload={
        "target_id":int(product["id"]),"attachment_id":new_id
    }).get("result") or {}
    cache_purge()
    return {
        "attempted":True,
        "source_attachment_id":aid,
        "new_attachment_id":new_id,
        "previous_attachment_id":int(bound.get("previous_attachment_id") or aid),
        "snapshot_id":bound.get("snapshot_id"),
        "source_bytes":byte_count or None,
        "optimized_bytes":optimized.get("bytes"),
        "optimized_mime":optimized.get("mime"),
    }

def restore_featured(product_id: int, action: dict[str,Any]) -> bool:
    if not action.get("attempted"):
        return True
    previous=int(action.get("previous_attachment_id") or action.get("source_attachment_id") or 0)
    if not previous:
        return False
    out=bridge("asset.featured.set",payload={
        "target_id":int(product_id),"attachment_id":previous
    }).get("result") or {}
    cache_purge()
    return int(out.get("featured_attachment_id") or 0)==previous
