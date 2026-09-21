#!/usr/bin/env python3
import base64,datetime,hashlib,json,os,pathlib,urllib.request
BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]; PASS=os.environ["WP_APP_PASSWORD"]
AUTH=base64.b64encode(f"{USER}:{PASS}".encode()).decode()
PAGE_ID=644
OUT=pathlib.Path("phase7-results/home-meta-owner-scan-20260922.json")
headers={"Authorization":"Basic "+AUTH,"Accept":"application/json","User-Agent":"K20-Home-Meta-Owner/1.0"}
url=f"{BASE}/wp-json/wp/v2/pages/{PAGE_ID}?context=edit&_fields=id,slug,status,modified_gmt,meta"
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=120) as r:
    p=json.load(r)
meta=p.get("meta") or {}
patterns=["loole","neshaa","141437","141441","k20-home-loole","k20-home-neshaa"]
rows=[]
for key,val in sorted(meta.items()):
    if isinstance(val,str):
        s=val
    else:
        try: s=json.dumps(val,ensure_ascii=False,separators=(",",":"))
        except Exception: s=str(val)
    hits=[x for x in patterns if x.lower() in s.lower()]
    rows.append({
      "key":key,
      "type":type(val).__name__,
      "length":len(s),
      "sha256":hashlib.sha256(s.encode()).hexdigest(),
      "pattern_hits":hits
    })
out={
  "mode":"read-only",
  "generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "page":{"id":p.get("id"),"slug":p.get("slug"),"status":p.get("status"),"modified_gmt":p.get("modified_gmt")},
  "meta_key_count":len(rows),
  "meta":rows,
  "matched_keys":[x["key"] for x in rows if x["pattern_hits"]],
  "site_mutations":0
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"matched_keys":out["matched_keys"],"meta_key_count":out["meta_key_count"]},ensure_ascii=False))
