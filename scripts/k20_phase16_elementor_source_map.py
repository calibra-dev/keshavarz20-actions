#!/usr/bin/env python3
import os,json,requests,re
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
r=requests.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit","_fields":"id,meta"},auth=AUTH,timeout=90)
r.raise_for_status(); p=r.json()
raw=(p.get("meta") or {}).get("_elementor_data") or ""
data=json.loads(raw) if isinstance(raw,str) and raw.strip() else raw
terms=["نظر کارشناسی","جمع‌بندی","اگر چند ردیف","۱۵ سؤال"]
hits=[]
def walk(node,path="root"):
    if isinstance(node,dict):
        settings=node.get("settings") if isinstance(node.get("settings"),dict) else {}
        for k,v in settings.items():
            if isinstance(v,str) and any(t in v for t in terms):
                hits.append({
                  "path":path,"element_id":node.get("id"),"elType":node.get("elType"),
                  "widgetType":node.get("widgetType"),"setting_key":k,"value_len":len(v),
                  "matched_terms":[t for t in terms if t in v],
                  "snippet":re.sub(r"\s+"," ",v)[:1800]
                })
        for k,v in node.items():
            if k!="settings": walk(v,f"{path}.{k}")
    elif isinstance(node,list):
        for i,v in enumerate(node): walk(v,f"{path}[{i}]")
walk(data)
print(json.dumps({"id":PID,"elementor_data_type":type(data).__name__,"hits":hits,"hit_count":len(hits)},ensure_ascii=False))
