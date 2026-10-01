from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from core import bridge, cache_purge, product_read, rest, textify


def _is_webp(url: str) -> bool:
    try:
        return urlparse(url).path.lower().endswith(".webp")
    except Exception:
        return False


def _bytes(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError,ValueError):
        return 0


def _alt_map(suggestions: list[dict[str,Any]] | None) -> dict[int,str]:
    out={}
    for item in suggestions or []:
        try:
            aid=int(item.get("attachment_id") or 0)
        except (TypeError,ValueError):
            continue
        alt=textify(str(item.get("alt_text") or ""))
        if aid and alt:
            out[aid]=alt
    return out


def optimize_product_images(product: dict[str,Any], policy: dict[str,Any], alt_suggestions: list[dict[str,Any]] | None=None) -> dict[str,Any]:
    images=product.get("images") or []
    source_ids=[int(x.get("id") or 0) for x in images if int(x.get("id") or 0)>0]
    if not policy.get("enabled",True):
        return {"attempted":False,"reason":"media optimization disabled","source_ids":source_ids,"target_ids":source_ids}
    if not images:
        return {"attempted":False,"reason":"product has no images","source_ids":[],"target_ids":[],"all_webp":True}

    quality=int(policy.get("quality") or 84)
    max_dimension=int(policy.get("max_dimension") or 1600)
    minimum_saving_pct=float(policy.get("minimum_saving_pct") or 0)
    require_smaller=bool(policy.get("require_smaller",True))
    suggestions=_alt_map(alt_suggestions)
    target_ids=[]
    items=[]
    created_ids=[]

    for index,image in enumerate(images):
        aid=int(image.get("id") or 0)
        src=str(image.get("src") or "")
        role="featured" if index==0 else "gallery"
        if not aid:
            raise RuntimeError(f"{role} image has no attachment id")
        if role=="featured" and not policy.get("featured",True):
            target_ids.append(aid); items.append({"role":role,"source_attachment_id":aid,"target_attachment_id":aid,"status":"disabled"}); continue
        if role=="gallery" and not policy.get("gallery",True):
            target_ids.append(aid); items.append({"role":role,"source_attachment_id":aid,"target_attachment_id":aid,"status":"disabled"}); continue
        if policy.get("skip_existing_webp",True) and _is_webp(src):
            target_ids.append(aid)
            items.append({"role":role,"source_attachment_id":aid,"target_attachment_id":aid,"status":"already_webp","src":src})
            continue

        hashed=bridge("media.hash",dry_run=True,payload={"attachment_id":aid}).get("result") or {}
        source_bytes=_bytes(hashed.get("bytes"))
        optimized=bridge("media.optimize",payload={
            "attachment_id":aid,
            "mime":str(policy.get("output_mime") or "image/webp"),
            "quality":quality,
            "max_dimension":max_dimension,
        }).get("result") or {}
        new_id=int(optimized.get("new_attachment_id") or 0)
        optimized_bytes=_bytes(optimized.get("bytes"))
        if not new_id:
            raise RuntimeError(f"media.optimize produced no attachment for {aid}")
        created_ids.append(new_id)
        saving_pct=None
        if source_bytes>0 and optimized_bytes>0:
            saving_pct=round((source_bytes-optimized_bytes)*100/source_bytes,2)
        if require_smaller and source_bytes>0 and optimized_bytes>0 and saving_pct is not None and saving_pct<minimum_saving_pct:
            target_ids.append(aid)
            items.append({
                "role":role,"source_attachment_id":aid,"target_attachment_id":aid,
                "rejected_attachment_id":new_id,"status":"rejected_no_size_gain",
                "source_bytes":source_bytes,"optimized_bytes":optimized_bytes,"saving_pct":saving_pct,
            })
            continue

        alt=suggestions.get(aid) or textify(str(image.get("alt") or ""))
        if alt:
            bridge("media.metadata",payload={"attachment_id":new_id,"alt_text":alt})
        target_ids.append(new_id)
        items.append({
            "role":role,"source_attachment_id":aid,"target_attachment_id":new_id,
            "status":"converted","source_bytes":source_bytes or None,
            "optimized_bytes":optimized_bytes or None,"saving_pct":saving_pct,
            "optimized_mime":optimized.get("mime") or "image/webp",
        })

    changed=target_ids!=source_ids
    if changed:
        rest("PUT",f"/wc/v3/products/{int(product['id'])}",payload={"images":[{"id":x} for x in target_ids]})
        cache_purge()

    check=product_read(int(product["id"]))
    readback_ids=[int(x.get("id") or 0) for x in (check.get("images") or [])]
    if readback_ids!=target_ids:
        if changed:
            rest("PUT",f"/wc/v3/products/{int(product['id'])}",payload={"images":[{"id":x} for x in source_ids]})
            cache_purge()
        raise RuntimeError(f"media binding readback mismatch expected={target_ids} got={readback_ids}")

    all_webp=all(_is_webp(str(x.get("src") or "")) for x in (check.get("images") or []))
    return {
        "attempted":True,
        "changed":changed,
        "source_ids":source_ids,
        "target_ids":target_ids,
        "created_attachment_ids":created_ids,
        "items":items,
        "readback_ok":True,
        "all_webp":all_webp,
    }


def restore_product_images(product_id: int, action: dict[str,Any]) -> bool:
    source_ids=[int(x) for x in (action.get("source_ids") or []) if int(x)>0]
    if not action.get("changed"):
        return True
    rest("PUT",f"/wc/v3/products/{int(product_id)}",payload={"images":[{"id":x} for x in source_ids]})
    cache_purge()
    check=product_read(int(product_id))
    readback=[int(x.get("id") or 0) for x in (check.get("images") or [])]
    return readback==source_ids


def remap_alt_suggestions(suggestions: list[dict[str,Any]] | None, action: dict[str,Any]) -> list[dict[str,Any]]:
    mapping={int(x.get("source_attachment_id") or 0):int(x.get("target_attachment_id") or 0) for x in (action.get("items") or [])}
    out=[]
    for item in suggestions or []:
        old=int(item.get("attachment_id") or 0)
        new=mapping.get(old,old)
        if new:
            out.append({"attachment_id":new,"alt_text":item.get("alt_text") or ""})
    return out
