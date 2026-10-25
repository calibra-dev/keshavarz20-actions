#!/usr/bin/env python3
"""Safe, limited Calibra 1.8.17 source/asset verification for disposable Docker QA."""
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import urllib.parse

SITE=os.environ.get("WP_BASE_URL","").rstrip("/")
USER=os.environ.get("WP_USERNAME","")
PASS=os.environ.get("WP_APP_PASSWORD","")
if not all([SITE,USER,PASS]):
    raise SystemExit("SITE_READ_AUTH_NOT_AVAILABLE")
AUTH="Basic "+base64.b64encode((USER+":"+PASS).encode()).decode()
ENDPOINT=SITE+"/wp-json/keshavarz20-ops/v3/execute"

def bridge(action,payload,tag):
    data=json.dumps({"action":action,"request_id":"calibra1817-qa-"+tag,"payload":payload},ensure_ascii=False).encode()
    req=urllib.request.Request(ENDPOINT,data=data,headers={
        "Authorization":AUTH,"Content-Type":"application/json; charset=utf-8",
        "Accept":"application/json","User-Agent":"K20-Calibra-QA-SourceRead"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=90) as res: answer=json.load(res)
    except urllib.error.HTTPError as e:
        raise SystemExit("BRIDGE_"+action+"_HTTP_"+str(e.code))
    if not isinstance(answer,dict) or answer.get("ok") is not True:
        raise SystemExit("BRIDGE_"+action+"_FAILED_"+str(answer.get("code")))
    return answer.get("result") or {}

def sha256(data):return hashlib.sha256(data).hexdigest()

inventory=bridge("plugin.assets",{"plugin":"k20-dashboard/k20-dashboard.php"},"inventory")
assert inventory.get("version")=="1.8.17", "WRONG_INSTALLED_VERSION"
entries=inventory.get("files") or []
assert len(entries)>40 and len(entries)<125, "UNEXPECTED_PLUGIN_FILE_COUNT"
print("INSTALLED_PLUGIN_INVENTORY_OK version=1.8.17 files="+str(len(entries)))
entry_by_path={item["path"]:item for item in entries}
for path in ["k20-dashboard.php","assets/js/admin.js","assets/js/iran-cities.js"]:
    assert path in entry_by_path,"MISSING_REQUIRED_FILE_"+path
print("INSTALL_PACKAGE_REQUIRED_FILES_PRESENT")
meta=bridge("code.read",{"root":"k20-dashboard","path":"k20-dashboard.php"},"code-main")
raw=meta.get("source_text","").encode()
if not raw:
    raise SystemExit("CODE_READ_EMPTY")
source_sha=sha256(raw)
expected=entry_by_path["k20-dashboard.php"]["sha256"]
print("SOURCE_MAIN_READ_OK bytes="+str(len(raw))+" sha_match="+str(source_sha==expected))
if source_sha!=expected:
    print("MAIN_SOURCE_REDACTED_OR_MUTATED; full-file reconstruction needs verified local
if len(sys.argv)>1 and sys.argv[1]=="build":
    import pathlib
    import zipfile
    root=pathlib.Path(os.environ.get("CALIBRA_QA_DIR","/tmp/calibra1817qa"))
    root.mkdir(parents=True,exist_ok=True)
    stage=root/"k20-dashboard"
    stage.mkdir(parents=True,exist_ok=True)
    text_ext={"php","js","css","json","html","htm","txt","md","yml","yaml"}
    repaired=0
    for idx,item in enumerate(entries):
        rel=item["path"]
        if not rel or rel.startswith("/") or ".." in rel.split("/") or "\\\\" in rel:
            raise SystemExit("UNSAFE_PLUGIN_PATH")
        expected=item["sha256"]
        ext=rel.rsplit(".",1)[-1].lower()
        if ext in text_ext:
            result=bridge("code.read",{"root":"k20-dashboard","path":rel},"source-"+str(idx))
            data=result.get("source_text","").encode("utf-8")
            if sha256(data)!=expected and rel=="k20-dashboard.php":
                source=data.decode("utf-8")
                pattern=r"(define\\s*\\(\\s*['\\\"]K20D_ZHAKET_PRODUCT_TOKEN['\\\"]\\s*,\\s*)['\\\"]\\*\\*\\*['\\\"]"
                for quote in ("'","\\\""):
                    changed,count=re.subn(pattern,lambda m:m.group(1)+quote+quote,source)
                    if count==1 and sha256(changed.encode())==expected:
                        data=changed.encode()
                        repaired+=1
                        break
            if sha256(data)!=expected:
                raise SystemExit("SOURCE_HASH_MISMATCH:"+rel)
        else:
            url=SITE+"/wp-content/plugins/k20-dashboard/"+"/".join(urllib.parse.quote(part) for part in rel.split("/"))
            req=urllib.request.Request(url,headers={"User-Agent":"K20-Calibra-QA-Readonly"})
            try:
                with urllib.request.urlopen(req,timeout=60) as res: data=res.read(12000000)
            except urllib.error.HTTPError as e:
                raise SystemExit("ASSET_FETCH_HTTP_"+str(e.code)+":"+rel)
            if sha256(data)!=expected:
                raise SystemExit("ASSET_HASH_MISMATCH:"+rel)
        dest=stage/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
    target=root/"Calibra-Dashboard-1.8.17-VERIFIED-LIVE.zip"
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipout:
        for file in sorted(stage.rglob("*")):
            if file.is_file(): zipout.write(file,file.relative_to(root).as_posix())
    with zipfile.ZipFile(target) as check:
        assert len(check.namelist())==len(entries),"FILE_COUNT_MISMATCH"
        assert check.testzip() is None,"ZIP_CRC_FAILURE"
    print("CALIBRA_1817_RECONSTRUCTED_FROM_LIVE_ALL_FILES_HASH_VALID count="+str(len(entries))+" repaired_redacted_constants="+str(repaired))
    print("CALIBRA_1817_QA_ZIP_READY bytes="+str(target.stat().st_size))
 corrective logic")
print("CALIBRA_1817_SOURCE_PREFLIGHT_COMPLETE")
