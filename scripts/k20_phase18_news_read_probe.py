#!/usr/bin/env python3
from __future__ import annotations
import base64, json, os, sys
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
OUT=Path(sys.argv[1]); OUT.parent.mkdir(parents=True,exist_ok=True)

session=requests.Session()
session.auth=(USER,PASS)
session.headers.update({"Accept":"application/json","User-Agent":"k20-phase18-news-read-probe/2.0","Cache-Control":"no-cache"})

attempts=[]

def record(name,r,data=None):
    attempts.append({
        "name":name,
        "http":r.status_code,
        "content_type":r.headers.get("content-type"),
        "json_list":isinstance(data,list),
        "json_count":len(data) if isinstance(data,list) else None
    })

def get_json(path,params=None):
    r=session.get(BASE+"/"+path.lstrip("/"),params=params,timeout=90)
    try:
        data=r.json()
    except Exception:
        data=None
    return r,data

titles=[]
method=None
try:
    rt,types=get_json("wp-json/wp/v2/types")
    record("types",rt,types)
    news_type=types.get("news") if rt.ok and isinstance(types,dict) else None

    if isinstance(news_type,dict) and news_type.get("rest_base"):
        rest_base=str(news_type["rest_base"]).strip("/")
        rr,rows=get_json(f"wp-json/wp/v2/{rest_base}",{
            "context":"edit","per_page":5,"orderby":"date","order":"desc",
            "_fields":"id,title,status,type"
        })
        record("news_collection",rr,rows)
        if rr.ok and isinstance(rows,list):
            for row in rows:
                title=(row.get("title") or {})
                value=(title.get("raw") or title.get("rendered") or "").strip() if isinstance(title,dict) else str(title or "").strip()
                if value:
                    titles.append(value)
            method="rest_collection"

    if not method:
        rs,rows=get_json("wp-json/wp/v2/search",{
            "per_page":100,"type":"post","subtype":"news",
            "_fields":"id,title,url,type,subtype"
        })
        record("search_subtype_news",rs,rows)
        if rs.ok and isinstance(rows,list):
            vals=[]
            for row in rows:
                if str(row.get("subtype") or "")!="news":
                    continue
                title=str(row.get("title") or "").strip()
                if title:
                    vals.append(title)
                if len(vals)>=5:
                    break
            if vals:
                titles=vals
                method="rest_search"

    result={
        "ok":bool(method),
        "read_only":True,
        "post_type":"news",
        "probe_method":method,
        "sample_title_count":len(titles),
        "writes_performed":0,
        "rest_attempts":attempts,
        "news_type_exposed":isinstance(news_type,dict),
        "news_rest_base":news_type.get("rest_base") if isinstance(news_type,dict) else None
    }
    if not method:
        result["error"]="No authenticated REST collection/search path exposed readable news items."
except Exception as exc:
    result={
        "ok":False,"read_only":True,"post_type":"news","sample_title_count":0,
        "writes_performed":0,"rest_attempts":attempts,"error":f"{type(exc).__name__}: {exc}"
    }

OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE18_NEWS_READ_PROBE",json.dumps(result,ensure_ascii=False))
if not result["ok"]:
    raise SystemExit(2)
