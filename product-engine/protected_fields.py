from __future__ import annotations

import hashlib
import json
from typing import Any


def _ids(rows: Any) -> list[int]:
    out=[]
    for row in rows or []:
        if isinstance(row,dict):
            value=row.get("id")
        else:
            value=row
        try:
            out.append(int(value))
        except (TypeError,ValueError):
            continue
    return out


def _attributes(rows: Any) -> list[dict[str,Any]]:
    out=[]
    for row in rows or []:
        if not isinstance(row,dict):
            continue
        out.append({
            "id":int(row.get("id") or 0),
            "name":str(row.get("name") or ""),
            "position":int(row.get("position") or 0),
            "visible":bool(row.get("visible",False)),
            "variation":bool(row.get("variation",False)),
            "options":[str(x) for x in (row.get("options") or [])],
        })
    return out


def snapshot(product: dict[str,Any]) -> dict[str,Any]:
    return {
        "status":product.get("status"),
        "type":product.get("type"),
        "slug":product.get("slug"),
        "price":product.get("price"),
        "regular_price":product.get("regular_price"),
        "sale_price":product.get("sale_price"),
        "stock_status":product.get("stock_status"),
        "stock_quantity":product.get("stock_quantity"),
        "manage_stock":product.get("manage_stock"),
        "backorders":product.get("backorders"),
        "sku":product.get("sku"),
        "gtin":product.get("gtin") or product.get("global_unique_id"),
        "mpn":product.get("mpn"),
        "categories":_ids(product.get("categories")),
        "tags":_ids(product.get("tags")),
        "brands":_ids(product.get("brands")),
        "attributes":_attributes(product.get("attributes")),
        "variations":_ids(product.get("variations")),
    }


def fingerprint(value: dict[str,Any]) -> str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compare(before: dict[str,Any], after: dict[str,Any]) -> dict[str,Any]:
    changed={}
    for key in sorted(set(before)|set(after)):
        if before.get(key)!=after.get(key):
            changed[key]={"before":before.get(key),"after":after.get(key)}
    return {
        "ok":not changed,
        "before_sha256":fingerprint(before),
        "after_sha256":fingerprint(after),
        "changed":changed,
    }
