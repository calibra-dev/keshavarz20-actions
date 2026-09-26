#!/usr/bin/env python3
import os,re,json,requests,time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry))
r=S.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit","_fields":"id,link,content"},timeout=90); r.raise_for_status(); p=r.json()
raw=p["content"]["raw"]; rendered=p["content"]["rendered"]
term="نظر کارشناسی کشاورز بیست"
raw_idx=[m.start() for m in re.finditer(re.escape(term),raw)]
ren_idx=[m.start() for m in re.finditer(re.escape(term),rendered)]
def snip(s,i,n=900): return s[max(0,i-n):min(len(s),i+n)]
rows=[]
for i in raw_idx:
    frag=snip(raw,i,500)
    # Find longest exact suffix/prefix context chunks from raw around each occurrence that exist in rendered.
    candidates=[]
    for span in [80,120,180,240,320,420]:
        a=max(0,i-span); b=min(len(raw),i+span)
        chunk=raw[a:b]
        candidates.append({"span":span,"in_rendered":chunk in rendered})
    rows.append({"index":i,"snippet":snip(raw,i,700),"candidates":candidates})
out={"raw_indices":raw_idx,"rendered_indices":ren_idx,"raw_occurrences":rows,"rendered_snippets":[snip(rendered,i,900) for i in ren_idx],"raw_len":len(raw),"rendered_len":len(rendered)}
print(json.dumps(out,ensure_ascii=False))
