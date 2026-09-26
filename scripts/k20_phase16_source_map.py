#!/usr/bin/env python3
import os,json,requests,re
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
IDS=[142587,145235,145237,145238,145251,145253,145259,145263,145281,145330,145775]
S=requests.Session(); S.auth=AUTH
rows=[]
def walk(node,terms,hits,path="root"):
    if isinstance(node,dict):
        settings=node.get("settings") if isinstance(node.get("settings"),dict) else {}
        for key,val in settings.items():
            if isinstance(val,str) and any(t in val for t in terms):
                hits.append({"path":path,"id":node.get("id"),"elType":node.get("elType"),"widgetType":node.get("widgetType"),"setting":key,"length":len(val),"terms":[t for t in terms if t in val]})
        for key,val in node.items():
            if key!="settings": walk(val,terms,hits,path+"."+str(key))
    elif isinstance(node,list):
        for i,val in enumerate(node): walk(val,terms,hits,path+"["+str(i)+"]")
for pid in IDS:
    r=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit","_fields":"id,slug,link,content,meta,modified_gmt"},timeout=90)
    r.raise_for_status(); p=r.json()
    meta=p.get("meta") if isinstance(p.get("meta"),dict) else {}
    eraw=meta.get("_elementor_data") or ""
    try: edata=json.loads(eraw) if isinstance(eraw,str) and eraw.strip() else eraw
    except Exception: edata=None
    rendered=((p.get("content") or {}).get("rendered") or "")
    terms=["نظر کارشناسی کشاورز بیست","جمع‌بندی","منابع"]
    hits=[]; walk(edata,terms,hits)
    rows.append({
      "id":pid,"slug":p.get("slug"),"modified_gmt":p.get("modified_gmt"),
      "elementor_data_len":len(eraw) if isinstance(eraw,str) else 0,
      "elementor_edit_mode":meta.get("_elementor_edit_mode"),
      "rendered_has_editorial":"نظر کارشناسی کشاورز بیست" in rendered,
      "rendered_has_review":"روش تهیه و بازبینی" in rendered,
      "rendered_has_policy":"/editorial-policy/" in rendered,
      "hits":hits
    })
print(json.dumps({"count":len(rows),"rows":rows},ensure_ascii=False))
