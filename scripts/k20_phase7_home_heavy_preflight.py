#!/usr/bin/env python3
import base64,json,os,re,urllib.parse,urllib.request,urllib.error
from pathlib import Path
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=base64.b64encode(f'{os.environ["WP_USERNAME"]}:{os.environ["WP_APP_PASSWORD"]}'.encode()).decode()
def api(path):
    req=urllib.request.Request(BASE+path,headers={"Authorization":"Basic "+AUTH,"Accept":"application/json","User-Agent":"K20-Phase7-Home-Preflight/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:
        return int(r.status),json.loads(r.read().decode("utf-8","replace"))
code,page=api("/wp-json/wp/v2/pages/644?context=edit&_fields=id,status,link,content")
raw=((page.get("content") or {}).get("raw") or "") if isinstance(page,dict) else ""
families={}
for stem in ("neshaa","loole"):
    urls=sorted(set(re.findall(r'https?://[^\s"\'<>)]*/wp-content/uploads/[^\s"\'<>)]*'+stem+r'[^\s"\'<>)]*\.(?:png|jpg|jpeg|webp)',raw,re.I)))
    occurrences=[]
    for u in urls:
        occurrences.append({"url":u,"count":raw.count(u)})
    families[stem]={"urls":occurrences,"total_url_occurrences":sum(x["count"] for x in occurrences),"stem_text_count":len(re.findall(stem,raw,re.I))}
out={"ok":code==200 and page.get("status")=="publish","page_id":644,"status":page.get("status"),"link":page.get("link"),"raw_length":len(raw),"families":families}
Path("phase7-results").mkdir(exist_ok=True)
Path("phase7-results/home-heavy-preflight.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False))
if not out["ok"]: raise SystemExit(2)
