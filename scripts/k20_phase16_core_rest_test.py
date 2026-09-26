#!/usr/bin/env python3
import os,json,re,requests,time
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
def get():
 r=requests.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit","_fields":"id,link,content,modified_gmt"},auth=AUTH,timeout=90); r.raise_for_status(); return r.json()
p=get(); raw=p["content"]["raw"]
# Remove temporary Gutenberg proof only; retain the researched deep block.
raw=re.sub(r"<!-- wp:html -->\s*<!-- k20-phase16-gutenberg-test-v1 -->[\s\S]*?<!-- /k20-phase16-gutenberg-test-v1 -->\s*<!-- /wp:html -->","",raw)
r=requests.post(f"{BASE}/wp-json/wp/v2/posts/{PID}",json={"content":raw},auth=AUTH,timeout=120)
r.raise_for_status()
time.sleep(3)
p2=get(); rendered=p2["content"]["rendered"]
pub=requests.get(p2["link"]+"?k20_core_refresh=1",headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-core-rest-test/1.0"},timeout=90)
checks={"modified_gmt":p2.get("modified_gmt"),"rendered_deep":"بازبینی عمیق فنی" in rendered,"rendered_review":"روش تهیه و بازبینی" in rendered,"rendered_policy":"/editorial-policy/" in rendered,"rendered_itrc":"https://itrc.org/projects/evals.htm" in rendered,"public_http":pub.status_code,"public_deep":"بازبینی عمیق فنی" in pub.text,"public_review":"روش تهیه و بازبینی" in pub.text,"public_policy":"/editorial-policy/" in pub.text}
print(json.dumps(checks,ensure_ascii=False))
if not all(v is True or v==200 or isinstance(v,str) for v in checks.values()): raise SystemExit(2)
