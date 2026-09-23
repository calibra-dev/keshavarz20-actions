#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]
ENGINE=ROOT/"engine-gallery-product-creator"
SITE=os.environ.get("WP_BASE_URL","https://keshavarz20.com").rstrip("/")
USER=os.environ["WP_USERNAME"]
PASSWORD=os.environ["WP_APP_PASSWORD"]


def sha256(p:Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()


def wp(method,path,**kwargs):
    r=requests.request(method,SITE+"/wp-json"+path,auth=(USER,PASSWORD),timeout=180,**kwargs)
    r.raise_for_status()
    return r.json()


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("approval"); a=ap.parse_args()
    approval_path=Path(a.approval)
    approval=json.loads(approval_path.read_text(encoding="utf-8"))

    if approval.get("engine")!="engine-gallery-product-creator":
        raise SystemExit("wrong engine")
    if approval.get("approved") is not True:
        raise SystemExit("approval rejected: approved must be true")
    if approval.get("approved_by")!="user_chat_confirmation":
        raise SystemExit("approval rejected: approved_by mismatch")
    if approval.get("approval_phrase")!="APPROVED_FOR_GALLERY":
        raise SystemExit("approval rejected: approval phrase mismatch")

    batch_id=approval["batch_id"]
    product_id=int(approval["product_id"])
    preview=ENGINE/"previews"/batch_id
    manifest=json.loads((preview/"manifest.json").read_text(encoding="utf-8"))

    if manifest["batch_id"]!=batch_id or int(manifest["product_id"])!=product_id:
        raise SystemExit("approval/manifest identity mismatch")
    if manifest.get("preview_only") is not True or manifest.get("approval_required") is not True:
        raise SystemExit("manifest safety flags invalid")
    if len(manifest.get("assets") or [])!=5:
        raise SystemExit("manifest must contain exactly five assets")

    expected=list(approval.get("asset_sha256") or [])
    actual=[]
    for asset in manifest["assets"]:
        p=preview/asset["file"]
        digest=sha256(p)
        if digest!=asset["sha256"]:
            raise SystemExit(f"preview changed after generation: {p.name}")
        actual.append(digest)
    if expected!=actual:
        raise SystemExit("approval hash list does not exactly match preview manifest")

    result_dir=ENGINE/"publish-results"
    result_dir.mkdir(parents=True,exist_ok=True)
    evidence=result_dir/f"{batch_id}.json"
    if evidence.exists():
        prior=json.loads(evidence.read_text(encoding="utf-8"))
        if prior.get("ok") is True and prior.get("verified") is True:
            print(json.dumps({"ok":True,"noop":True,"reason":"already published and verified","batch_id":batch_id},ensure_ascii=False))
            return

    before=wp("GET",f"/wc/v3/products/{product_id}")
    before_ids=[int(x["id"]) for x in (before.get("images") or [])]
    if int(before.get("id"))!=product_id:
        raise RuntimeError("product readback mismatch before publish")

    uploaded=[]
    try:
        for idx, asset in enumerate(manifest["assets"],1):
            p=preview/asset["file"]
            headers={
                "Content-Type":"image/webp",
                "Content-Disposition":f'attachment; filename="{batch_id}-{idx:02d}.webp"'
            }
            media=wp("POST","/wp/v2/media",headers=headers,data=p.read_bytes())
            mid=int(media["id"])
            alt=f"{manifest['product_name']} – اینفوگرافیک {idx} از 5"
            wp("POST",f"/wp/v2/media/{mid}",json={"title":alt,"alt_text":alt})
            uploaded.append({"id":mid,"url":media.get("source_url"),"sha256":asset["sha256"]})

        merged=[{"id":i} for i in before_ids+[x["id"] for x in uploaded]]
        write_result=wp("PUT",f"/wc/v3/products/{product_id}",json={"images":merged})
        write_ids=[int(x["id"]) for x in (write_result.get("images") or [])]
        write_confirmed=all(x["id"] in write_ids for x in uploaded) and all(i in write_ids for i in before_ids)
        if not write_confirmed:
            wp("PUT",f"/wc/v3/products/{product_id}",json={"images":[{"id":i} for i in before_ids]})
            raise RuntimeError("gallery PUT response missing expected image IDs; previous gallery IDs restored")

        verified=False
        final_ids=[]
        for attempt in range(12):
            time.sleep(5)
            final=wp("GET",f"/wc/v3/products/{product_id}?context=edit&_cb={int(time.time())}-{attempt}")
            final_ids=[int(x["id"]) for x in (final.get("images") or [])]
            if all(x["id"] in final_ids for x in uploaded) and all(i in final_ids for i in before_ids):
                verified=True
                break
        if not verified:
            raise RuntimeError("gallery write confirmed by PUT response but cache-busted readback did not converge; gallery was NOT rolled back")

        result={
            "ok":True,
            "verified":True,
            "engine":"engine-gallery-product-creator",
            "batch_id":batch_id,
            "product_id":product_id,
            "before_image_ids":before_ids,
            "uploaded":uploaded,
            "final_image_ids":final_ids,
            "append_only":True,
            "approval_verified":True,
            "published_at_epoch":int(time.time())
        }
        evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception:
        raise


if __name__=="__main__": main()
