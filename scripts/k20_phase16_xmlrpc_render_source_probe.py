#!/usr/bin/env python3
import os, json, re, hashlib
from xmlrpc.client import ServerProxy

BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
PID=145235

server=ServerProxy(BASE+"/xmlrpc.php", allow_none=True)
post=server.wp.getPost(0, USER, PASS, PID, ["post_id","post_title","post_name","post_status","post_content","custom_fields","post_modified_gmt"])

terms=re.compile(r"(content|builder|elementor|cache|render|template|snippet|html|editor|wpb|oxygen|bricks|breakdance|kadence|block|phase16|k20)",re.I)
rows=[]
for item in post.get("custom_fields",[]) or []:
    key=str(item.get("key",""))
    val=item.get("value","")
    sval=val if isinstance(val,str) else json.dumps(val,ensure_ascii=False,default=str)
    if terms.search(key) or "نظر کارشناسی کشاورز بیست" in sval or "بازبینی عمیق فنی" in sval:
        rows.append({
          "key":key,
          "length":len(sval),
          "sha256":hashlib.sha256(sval.encode("utf-8","ignore")).hexdigest(),
          "has_editorial":"نظر کارشناسی کشاورز بیست" in sval,
          "has_deep":"بازبینی عمیق فنی" in sval,
          "snippet":sval[:1200]
        })

content=str(post.get("post_content") or "")
out={
 "ok":True,
 "post_id":PID,
 "post_title":post.get("post_title"),
 "post_status":post.get("post_status"),
 "post_modified_gmt":post.get("post_modified_gmt"),
 "post_content_len":len(content),
 "post_content_sha256":hashlib.sha256(content.encode("utf-8","ignore")).hexdigest(),
 "post_content_has_editorial":"نظر کارشناسی کشاورز بیست" in content,
 "post_content_has_deep":"بازبینی عمیق فنی" in content,
 "candidate_meta_count":len(rows),
 "candidate_meta":rows
}
print(json.dumps(out,ensure_ascii=False,default=str))
