#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
OUT=Path(sys.argv[1]); OUT.parent.mkdir(parents=True,exist_ok=True)

s=requests.Session()
s.auth=(USER,PASS)
s.headers.update({"Accept":"application/json","User-Agent":"k20-phase18-news-cli-lifecycle/1.0","Cache-Control":"no-cache"})

def cli(command:str):
    r=s.post(
        BASE+"/wp-json/wpvibe/v1/cli/run",
        json={"command":command,"confirm_write":False},
        timeout=90,
    )
    data=r.json() if r.headers.get("content-type","").lower().startswith("application/json") else {}
    if not r.ok:
        raise RuntimeError(f"CLI HTTP {r.status_code}")
    if int(data.get("exit_code",1)) != 0:
        raise RuntimeError(f"CLI exit {data.get('exit_code')}: {str(data.get('stderr') or '')[:300]}")
    return data

created_id=None
cleanup_verified=False
steps=[]
try:
    created=cli('post create --post_title="K20 Phase18 Temporary Lifecycle 20260921" --post_status=draft --post_type=news --porcelain')
    raw=str(created.get("stdout") or "").strip()
    m=re.search(r"\b(\d+)\b",raw)
    if not m:
        raise RuntimeError("Could not parse temporary news ID")
    created_id=int(m.group(1))
    steps.append({"step":"create_draft","ok":True,"id":created_id})

    read=cli(f"post get {created_id} --fields=ID,post_title,post_status,post_type")
    rb=str(read.get("stdout") or "")
    if '"post_status":"draft"' not in rb.replace(" ","") or '"post_type":"news"' not in rb.replace(" ",""):
        raise RuntimeError("Draft readback did not confirm news/draft")
    steps.append({"step":"readback_draft","ok":True})

    deleted=cli(f"post delete {created_id}")
    steps.append({"step":"trash","ok":True})

    final=cli(f"post get {created_id} --fields=ID,post_status,post_type")
    fb=str(final.get("stdout") or "").replace(" ","")
    if '"post_status":"trash"' not in fb or '"post_type":"news"' not in fb:
        raise RuntimeError("Final readback did not confirm trash/news")
    cleanup_verified=True
    steps.append({"step":"verify_trash","ok":True})
    result={"ok":True,"temporary_news_id":created_id,"steps":steps,"cleanup_verified":True,"permanent_delete":False}
except Exception as exc:
    if created_id and not cleanup_verified:
        try:
            cli(f"post delete {created_id}")
            final=cli(f"post get {created_id} --fields=ID,post_status,post_type")
            cleanup_verified='"post_status":"trash"' in str(final.get("stdout") or "").replace(" ","")
            steps.append({"step":"failure_cleanup_to_trash","ok":cleanup_verified})
        except Exception as cleanup_exc:
            steps.append({"step":"failure_cleanup_to_trash","ok":False,"error":type(cleanup_exc).__name__})
    result={
        "ok":False,
        "temporary_news_id":created_id,
        "steps":steps,
        "cleanup_verified":cleanup_verified,
        "permanent_delete":False,
        "error":f"{type(exc).__name__}: {exc}",
    }

OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE18_NEWS_CLI_LIFECYCLE",json.dumps(result,ensure_ascii=False))
if not result["ok"] or not result["cleanup_verified"]:
    raise SystemExit(2)
