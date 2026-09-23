#!/usr/bin/env python3
from __future__ import annotations
import base64, json, os, re
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
CLEANUP = ROOT / "k21-top30-results" / "generated-media-cleanup-plan.json"
BATCH = ROOT / "k21-top30-results" / "top30-media-batch.json"
OUT = ROOT / "k21-top30-results" / "permanent-generated-media-delete-result.json"

VIDEO_IDS = [145348,145349,145350,145351,145352,145353,145354,145355,145356,145357,145358,145359,145360,145361,145385,145387,145391,145393,145397,145399,145403,145405,145410,145412,145421,145423,145427,145429,145433,145435,145439,145441,145445,145447,145451,145453,145566,145567,145568,145570,145573,145574,145577,145579,145581,145583]
CUSTOM_IMAGE_IDS = {145715,145716,145717,145718}

def auth_headers():
    token = base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Accept":"application/json"}

def main():
    cleanup=json.loads(CLEANUP.read_text(encoding="utf-8"))
    batch=json.loads(BATCH.read_text(encoding="utf-8"))
    image_ids=set()
    for p in cleanup["products"]:
        image_ids.update(int(x) for x in p.get("removed_generated_image_ids",[]))
    for p in batch.get("products",[]):
        for m in p.get("new_media",[]):
            image_ids.add(int(m["id"]))
    targets=sorted(image_ids | set(VIDEO_IDS))
    base=os.environ["WP_BASE_URL"].rstrip("/")
    headers=auth_headers()
    verified=[]
    missing=[]
    for mid in targets:
        r=requests.get(f"{base}/wp-json/wp/v2/media/{mid}",headers=headers,timeout=60)
        if r.status_code==404:
            missing.append(mid); continue
        r.raise_for_status()
        item=r.json()
        url=str(item.get("source_url") or "")
        ok = (mid in VIDEO_IDS and re.search(r"/2026/09/(?:video(?:-\d+)?\.mp4|thumbnail(?:-\d+)?\.jpg)$",url,re.I)) or              (mid in CUSTOM_IMAGE_IDS) or              (mid in image_ids and ("/k21-p" in url or re.search(r"/k21-\d+-decision-",url,re.I)))
        if not ok:
            raise RuntimeError(f"Refusing delete for {mid}: unexpected source_url {url}")
        verified.append({"id":mid,"source_url":url})
    deleted=[]
    for item in verified:
        mid=item["id"]
        r=requests.delete(f"{base}/wp-json/wp/v2/media/{mid}",headers=headers,params={"force":"true"},timeout=90)
        if r.status_code==404:
            missing.append(mid); continue
        r.raise_for_status()
        deleted.append(mid)
    remaining=[]
    for mid in deleted:
        r=requests.get(f"{base}/wp-json/wp/v2/media/{mid}",headers=headers,timeout=60)
        if r.status_code != 404:
            remaining.append({"id":mid,"http_code":r.status_code})
    result={
        "ok": not remaining,
        "target_count":len(targets),
        "verified_count":len(verified),
        "deleted_count":len(deleted),
        "missing_count":len(set(missing)),
        "verified_absent_count":len(deleted)-len(remaining),
        "remaining_after_delete":remaining,
        "deleted_ids":deleted,
        "missing_ids":sorted(set(missing)),
        "guardrail":"Only exact K21-generated image/video/thumbnail IDs derived from repository evidence were eligible."
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("deleted_ids","missing_ids","remaining_after_delete")},ensure_ascii=False))
    if remaining:
        raise RuntimeError(f"{len(remaining)} media attachments still resolve after permanent deletion")
if __name__=="__main__":
    main()
