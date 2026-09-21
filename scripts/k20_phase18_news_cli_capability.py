#!/usr/bin/env python3
from __future__ import annotations
import io, json, os, re, sys
from pathlib import Path
import requests
from PIL import Image

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
OUT=Path(sys.argv[1]); OUT.parent.mkdir(parents=True,exist_ok=True)

s=requests.Session()
s.auth=(USER,PASS)
s.headers.update({"Accept":"application/json","User-Agent":"k20-phase18-news-cli-capability/1.0","Cache-Control":"no-cache"})

def cli(command:str):
    r=s.post(BASE+"/wp-json/wpvibe/v1/cli/run",json={"command":command,"confirm_write":False},timeout=90)
    try: data=r.json()
    except Exception: data={}
    if not r.ok: raise RuntimeError(f"CLI HTTP {r.status_code}")
    if int(data.get("exit_code",1))!=0:
        raise RuntimeError(f"CLI exit {data.get('exit_code')}: {str(data.get('stderr') or '')[:400]}")
    return data

def cli_value(command:str):
    return str(cli(command).get("stdout") or "").strip()

post_id=None
media_id=None
steps=[]
cleanup={"post":False,"media":False}
try:
    # Create a tiny local WebP and upload through native WordPress media REST.
    im=Image.new("RGB",(64,36),(240,240,240))
    buf=io.BytesIO(); im.save(buf,"WEBP",quality=80); raw=buf.getvalue()
    mr=s.post(
        BASE+"/wp-json/wp/v2/media",
        data=raw,
        headers={
            "Content-Disposition":'attachment; filename="k20-phase18-temp.webp"',
            "Content-Type":"image/webp",
        },
        timeout=90,
    )
    if not mr.ok: raise RuntimeError(f"Media upload HTTP {mr.status_code}: {mr.text[:300]}")
    media=mr.json(); media_id=int(media["id"])
    steps.append({"step":"media_upload","ok":True,"media_id":media_id})

    mu=s.post(
        BASE+f"/wp-json/wp/v2/media/{media_id}",
        json={"title":"K20 Phase18 Temporary Media","alt_text":"K20 Phase18 temporary lifecycle media","caption":""},
        timeout=90,
    )
    if not mu.ok: raise RuntimeError(f"Media metadata HTTP {mu.status_code}")
    steps.append({"step":"media_metadata","ok":True})

    create=cli_value('post create --post_title="k20-phase18-temp-news-20260921" --post_status=draft --post_type=news --porcelain')
    m=re.search(r"\b(\d+)\b",create)
    if not m: raise RuntimeError("Could not parse news ID")
    post_id=int(m.group(1))
    steps.append({"step":"create_news_draft","ok":True,"post_id":post_id})

    # Verify the core type/status first.
    rb=cli_value(f"post get {post_id} --fields=ID,post_title,post_name,post_status,post_type")
    compact=rb.replace(" ","")
    if '"post_status":"draft"' not in compact or '"post_type":"news"' not in compact:
        raise RuntimeError("Core draft/type readback mismatch")
    steps.append({"step":"core_readback","ok":True})

    # Exercise the fields the scheduled news publisher requires.
    cli(f'post meta update {post_id} _thumbnail_id {media_id} --force')
    steps.append({"step":"featured_media_meta","ok":True})
    cli(f'post meta update {post_id} _yoast_wpseo_title "K20 Phase18 Temporary SEO Title" --force')
    cli(f'post meta update {post_id} _yoast_wpseo_metadesc "Temporary lifecycle metadata for Phase 18 verification only." --force')
    cli(f'post meta update {post_id} _yoast_wpseo_focuskw "phase18 temporary" --force')
    steps.append({"step":"yoast_meta","ok":True})
    cli(f"post term set {post_id} news_cat 839 --by=id")
    steps.append({"step":"news_category","ok":True})

    thumb=cli_value(f"post meta get {post_id} _thumbnail_id")
    yt=cli_value(f"post meta get {post_id} _yoast_wpseo_title")
    if str(media_id) not in thumb or "Phase18" not in yt:
        raise RuntimeError("Protected metadata readback mismatch")
    steps.append({"step":"required_meta_readback","ok":True})

    cli(f"post delete {post_id}")
    final=cli_value(f"post get {post_id} --fields=ID,post_status,post_type")
    cleanup["post"]='"post_status":"trash"' in final.replace(" ","")
    if not cleanup["post"]: raise RuntimeError("News cleanup did not reach trash")
    steps.append({"step":"trash_news","ok":True})

    cli(f"post delete {media_id}")
    media_final=cli_value(f"post get {media_id} --fields=ID,post_status,post_type")
    cleanup["media"]='"post_status":"trash"' in media_final.replace(" ","")
    if not cleanup["media"]: raise RuntimeError("Media cleanup did not reach trash")
    steps.append({"step":"trash_media","ok":True})

    result={"ok":True,"temporary_news_id":post_id,"temporary_media_id":media_id,"steps":steps,"cleanup_verified":cleanup,"permanent_delete":False}
except Exception as exc:
    if post_id and not cleanup["post"]:
        try:
            cli(f"post delete {post_id}")
            cleanup["post"]='"post_status":"trash"' in cli_value(f"post get {post_id} --fields=ID,post_status").replace(" ","")
        except Exception: pass
    if media_id and not cleanup["media"]:
        try:
            cli(f"post delete {media_id}")
            cleanup["media"]='"post_status":"trash"' in cli_value(f"post get {media_id} --fields=ID,post_status").replace(" ","")
        except Exception: pass
    result={"ok":False,"temporary_news_id":post_id,"temporary_media_id":media_id,"steps":steps,"cleanup_verified":cleanup,"permanent_delete":False,"error":f"{type(exc).__name__}: {exc}"}

OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE18_NEWS_CLI_CAPABILITY",json.dumps(result,ensure_ascii=False))
if not result["ok"] or not all(result["cleanup_verified"].values()): raise SystemExit(2)
