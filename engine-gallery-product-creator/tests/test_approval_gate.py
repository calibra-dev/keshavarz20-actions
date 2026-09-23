#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PUBLISH=ROOT/"engine-gallery-product-creator"/"scripts"/"publish_approved.py"

def main():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"approval.json"
        p.write_text(json.dumps({
            "engine":"engine-gallery-product-creator",
            "batch_id":"gate-test",
            "product_id":140014,
            "approved":False,
            "approved_by":"user_chat_confirmation",
            "approval_phrase":"APPROVED_FOR_GALLERY",
            "asset_sha256":[]
        }),encoding="utf-8")
        env=os.environ.copy()
        env.setdefault("WP_USERNAME","dummy")
        env.setdefault("WP_APP_PASSWORD","dummy")
        cp=subprocess.run([sys.executable,str(PUBLISH),str(p)],env=env,text=True,capture_output=True)
        combined=(cp.stdout or "")+"\n"+(cp.stderr or "")
        assert cp.returncode != 0, "publisher unexpectedly accepted approved=false"
        assert "approved must be true" in combined, combined
    print(json.dumps({"ok":True,"test":"approval-fail-closed","site_write_attempted":False}))
if __name__=="__main__": main()
