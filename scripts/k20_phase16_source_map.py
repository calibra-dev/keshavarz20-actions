#!/usr/bin/env python3
import os,json,requests,re,hashlib
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
S=requests.Session(); S.auth=AUTH
def get(path,params=None,auth=True):
    r=requests.get(BASE+path,params=params,auth=AUTH if auth else None,timeout=90,headers={"Accept":"application/json","Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-source-map/1.0"})
    r.raise_for_status(); return r.json()
edit=get(f"/wp-json/wp/v2/posts/{PID}",{"context":"edit"})
view=get(f"/wp-json/wp/v2/posts/{PID}",{"context":"view"},False)
revs=get(f"/wp-json/wp/v2/posts/{PID}/revisions",{"context":"edit","per_page":5})
def h(s): return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]
def slen(v):
    if isinstance(v,str): return len(v)
    try:return len(json.dumps(v,ensure_ascii=False))
    except:return -1
content=edit.get("content") or {}
meta=edit.get("meta") if isinstance(edit.get("meta"),dict) else {}
report={
 "id":PID,
 "top_level_fields":sorted(edit.keys()),
 "template":edit.get("template"),
 "format":edit.get("format"),
 "status":edit.get("status"),
 "modified_gmt":edit.get("modified_gmt"),
 "meta_keys":sorted(meta.keys()),
 "meta_value_shapes":{k:{"type":type(v).__name__,"len":slen(v)} for k,v in meta.items()},
 "content":{
   "raw_len":len(content.get("raw") or ""),"raw_sha":h(content.get("raw") or ""),
   "rendered_len":len(content.get("rendered") or ""),"rendered_sha":h(content.get("rendered") or ""),
   "protected":content.get("protected")
 },
 "view_content":{"len":len(((view.get("content") or {}).get("rendered") or "")),"sha":h(((view.get("content") or {}).get("rendered") or ""))},
 "revisions":[{"id":x.get("id"),"modified_gmt":x.get("modified_gmt"),"raw_len":len(((x.get("content") or {}).get("raw") or "")),"raw_sha":h(((x.get("content") or {}).get("raw") or "")),"rendered_len":len(((x.get("content") or {}).get("rendered") or "")),"rendered_sha":h(((x.get("content") or {}).get("rendered") or ""))} for x in revs],
 "links_keys":sorted((edit.get("_links") or {}).keys())
}
print(json.dumps(report,ensure_ascii=False))
