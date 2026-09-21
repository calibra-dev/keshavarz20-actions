#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys, xmlrpc.client
from pathlib import Path
import requests

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
OUT=Path(sys.argv[1]); OUT.parent.mkdir(parents=True,exist_ok=True)

session=requests.Session()
session.auth=(USER,PASS)
session.headers.update({"Accept":"application/json","User-Agent":"k20-phase18-news-read-probe/3.0","Cache-Control":"no-cache"})
attempts=[]

def record(name,r,data=None,**extra):
    row={
        "name":name,
        "http":r.status_code,
        "content_type":r.headers.get("content-type"),
        "json_list":isinstance(data,list),
        "json_count":len(data) if isinstance(data,list) else None,
    }
    row.update(extra)
    attempts.append(row)

def get_json(path,params=None):
    r=session.get(BASE+"/"+path.lstrip("/"),params=params,timeout=90)
    try: data=r.json()
    except Exception: data=None
    return r,data

def post_json(path,body):
    r=session.post(BASE+"/"+path.lstrip("/"),json=body,timeout=90)
    try: data=r.json()
    except Exception: data=None
    return r,data

titles=[]
method=None
news_type=None
try:
    # 1) Native WP REST collection, when the CPT is exposed.
    rt,types=get_json("wp-json/wp/v2/types")
    record("types",rt,types)
    news_type=types.get("news") if rt.ok and isinstance(types,dict) else None
    if isinstance(news_type,dict) and news_type.get("rest_base"):
        rest_base=str(news_type["rest_base"]).strip("/")
        rr,rows=get_json(f"wp-json/wp/v2/{rest_base}",{
            "context":"edit","per_page":5,"orderby":"date","order":"desc",
            "_fields":"id,title,status,type",
        })
        record("news_collection",rr,rows)
        if rr.ok and isinstance(rows,list):
            for row in rows:
                title=row.get("title") or {}
                value=(title.get("raw") or title.get("rendered") or "").strip() if isinstance(title,dict) else str(title or "").strip()
                if value: titles.append(value)
            method="rest_collection"

    # 2) Native search, if the custom subtype is exposed there.
    if not method:
        rs,rows=get_json("wp-json/wp/v2/search",{
            "per_page":100,"type":"post","subtype":"news",
            "_fields":"id,title,url,type,subtype",
        })
        record("search_subtype_news",rs,rows)
        if rs.ok and isinstance(rows,list):
            vals=[]
            for row in rows:
                if str(row.get("subtype") or "")!="news": continue
                title=str(row.get("title") or "").strip()
                if title: vals.append(title)
                if len(vals)>=5: break
            if vals:
                titles=vals
                method="rest_search"

    # 3) WPVibe's authenticated WP-native CLI emulator. Read-only command only.
    #    This route exists on the connected site and does not require exposing the
    #    custom CPT through wp/v2.
    if not method:
        command="post list --post_type=news --post_status=any --posts_per_page=5 --fields=ID,post_title,post_status --format=json"
        rc,data=post_json("wp-json/wpvibe/v1/cli/run",{"command":command,"confirm_write":False})
        blob=json.dumps(data,ensure_ascii=False,default=str) if data is not None else (rc.text or "")
        row_count=blob.count("post_title")
        response_keys=sorted(data.keys())[:20] if isinstance(data,dict) else []
        record("wpvibe_cli_read_news",rc,data,row_count=row_count,response_keys=response_keys)
        if rc.ok and row_count>0:
            method="wpvibe_cli_readonly"
            # Count only. Do not persist titles or IDs in the public repository.
            titles=["redacted"]*min(row_count,5)

    # 4) Legacy XML-RPC fallback kept for compatibility only.
    if not method:
        try:
            xml_pass="".join(str(PASS).split())
            server=xmlrpc.client.ServerProxy(f"{BASE}/xmlrpc.php",allow_none=True)
            methods=set(server.system.listMethods())
            if "wp.getPosts" not in methods:
                attempts.append({"name":"xmlrpc_methods","ok":False,"reason":"wp.getPosts_missing"})
            else:
                rows=server.wp.getPosts(
                    0,USER,xml_pass,
                    {"post_type":"news","post_status":"publish","number":5,"orderby":"post_date","order":"DESC"},
                    ["post_title"],
                )
                vals=[str((row or {}).get("post_title") or "").strip() for row in (rows or [])]
                vals=[x for x in vals if x]
                attempts.append({"name":"xmlrpc_normalized_app_password","ok":True,"row_count":len(vals)})
                if vals:
                    titles=vals
                    method="xmlrpc_normalized_app_password"
        except Exception as exc:
            attempts.append({"name":"xmlrpc_normalized_app_password","ok":False,"error":str(exc)})

    result={
        "ok":bool(method),
        "read_only":True,
        "post_type":"news",
        "probe_method":method,
        "sample_title_count":len(titles),
        "writes_performed":0,
        "attempts":attempts,
        "news_type_exposed":isinstance(news_type,dict),
        "news_rest_base":news_type.get("rest_base") if isinstance(news_type,dict) else None,
    }
    if not method:
        result["error"]="No authenticated read path could inspect the live news CPT."
except Exception as exc:
    result={
        "ok":False,"read_only":True,"post_type":"news","sample_title_count":0,
        "writes_performed":0,"attempts":attempts,"error":f"{type(exc).__name__}: {exc}",
    }

OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE18_NEWS_READ_PROBE",json.dumps({
    "ok":result["ok"],"probe_method":result.get("probe_method"),
    "sample_title_count":result.get("sample_title_count"),"writes_performed":0,
},ensure_ascii=False))
if not result["ok"]: raise SystemExit(2)
