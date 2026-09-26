#!/usr/bin/env python3
import os,re,json,requests,subprocess,tempfile
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
PID=145235
MARK="k20-phase16-gutenberg-test-v1"
def get():
 r=requests.get(f"{BASE}/wp-json/wp/v2/posts/{PID}",params={"context":"edit","_fields":"id,link,content"},auth=AUTH,timeout=90); r.raise_for_status(); return r.json()
def update(content):
 with tempfile.TemporaryDirectory() as td:
  req=Path(td)/"q.json"; out=Path(td)/"r.json"
  req.write_text(json.dumps({"action":"post.update","id":PID,"payload":{"content":content}},ensure_ascii=False),encoding="utf-8")
  cp=subprocess.run(["pwsh","-NoLogo","-NoProfile","-File","scripts/Invoke-K20SiteGateway.ps1","-RequestPath",str(req),"-OutputPath",str(out)],text=True,capture_output=True,timeout=300)
  if cp.returncode: raise SystemExit((cp.stderr or cp.stdout)[-1000:])
  data=json.loads(out.read_text(encoding="utf-8-sig"))
  if data.get("ok") is not True: raise SystemExit("gateway not ok")
p=get(); raw=p["content"]["raw"]
raw=re.sub(r"<!-- k20-phase16-gutenberg-test-v1 -->[\s\S]*?<!-- /k20-phase16-gutenberg-test-v1 -->","",raw)
raw=re.sub(r"<!-- wp:html -->\s*<!-- k20-phase16-gutenberg-test-v1 -->[\s\S]*?<!-- /k20-phase16-gutenberg-test-v1 -->\s*<!-- /wp:html -->","",raw)
frag=f"""<!-- wp:html -->
<!-- {MARK} -->
<section dir="rtl">
<h2>روش تهیه و بازبینی</h2>
<p>این نوشته با منابع فنی معتبر بازبینی شده است. جزئیات در <a href="https://keshavarz20.com/editorial-policy/">سیاست تحریریه، منابع و بازبینی محتوای کشاورز بیست</a> آمده است.</p>
</section>
<!-- /{MARK} -->
<!-- /wp:html -->"""
update(raw.rstrip()+"\n\n"+frag+"\n")
p2=get(); rendered=p2["content"]["rendered"]
pub=requests.get(p2["link"],headers={"Cache-Control":"no-cache, no-store","Pragma":"no-cache","User-Agent":"k20-p16-gutenberg-test/1.0"},timeout=90)
checks={"rendered_marker":MARK in rendered,"rendered_review":"روش تهیه و بازبینی" in rendered,"rendered_policy":"/editorial-policy/" in rendered,"public_http":pub.status_code,"public_marker":MARK in pub.text,"public_review":"روش تهیه و بازبینی" in pub.text,"public_policy":"/editorial-policy/" in pub.text}
print(json.dumps(checks,ensure_ascii=False))
if not all(v is True or v==200 for v in checks.values()): raise SystemExit(2)
