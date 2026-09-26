#!/usr/bin/env python3
import os,json,requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
TERM="نظر کارشناسی کشاورز بیست"
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
r=S.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit"},timeout=90); r.raise_for_status(); data=r.json()
hits=[]
def walk(x,path="$"):
    if isinstance(x,dict):
        for k,v in x.items():
            walk(v,path+"."+str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x): walk(v,f"{path}[{i}]")
    elif isinstance(x,str):
        if TERM in x:
            hits.append({"path":path,"length":len(x),"term_count":x.count(TERM)})
walk(data)
summary={
 "top_level_keys":sorted(data.keys()),
 "has_meta":isinstance(data.get("meta"),dict),
 "meta_keys":sorted(list((data.get("meta") or {}).keys())) if isinstance(data.get("meta"),dict) else [],
 "template":data.get("template"),
 "format":data.get("format"),
 "hits":hits
}
print(json.dumps(summary,ensure_ascii=False))
