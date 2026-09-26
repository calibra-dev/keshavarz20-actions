#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
ENGINE=ROOT/"engine-gallery-product-creator"

def sha256(p:Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("batch_id"); a=ap.parse_args()
    d=ENGINE/"previews"/a.batch_id
    m=json.loads((d/"manifest.json").read_text(encoding="utf-8"))
    assert m["preview_only"] is True
    assert m["approval_required"] is True
    assert m["publish_ready"] is False
    assert m["gallery_write_performed"] is False
    expected_count = int(m["asset_count"])
    assert expected_count in (5, 8)
    assert len(m["assets"]) == expected_count
    hashes=[]
    for i, asset in enumerate(m["assets"],1):
        p=d/asset["file"]
        assert p.exists(), p
        with Image.open(p) as im:
            assert im.format=="WEBP", (p,im.format)
            assert im.size==(1000,1000), (p,im.size)
        digest=sha256(p)
        assert digest==asset["sha256"], (p,digest,asset["sha256"])
        hashes.append(digest)
    assert len(set(hashes))==expected_count, "duplicate slide binaries detected"
    print(json.dumps({"ok":True,"batch_id":a.batch_id,"product_id":m["product_id"],"asset_count":expected_count,"gallery_write_performed":False},ensure_ascii=False))
if __name__=="__main__": main()
