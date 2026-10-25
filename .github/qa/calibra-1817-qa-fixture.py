#!/usr/bin/env python3
"""Deliberately synthetic old-header ZIP to test WordPress upgrade mechanics only."""
from pathlib import Path
import zipfile
root=Path("/tmp/calibra1817qa")
source=root/"Calibra-Dashboard-1.8.17-VERIFIED-LIVE.zip"
target=root/"Calibra-Dashboard-1.8.16-VERSION-ONLY-FIXTURE.zip"
with zipfile.ZipFile(source) as input_zip, zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as out:
    for name in input_zip.namelist():
        original=input_zip.read(name)
        if name=="k20-dashboard/k20-dashboard.php":
            text=original.decode("utf-8")
            if text.count("Version: 1.8.17")!=1:
                raise SystemExit("UNEXPECTED_MAIN_PLUGIN_HEADER")
            if text.count("define('K20D_VERSION', '1.8.17')")!=1:
                raise SystemExit("UNEXPECTED_MAIN_PLUGIN_CONSTANT")
            text=text.replace("Version: 1.8.17","Version: 1.8.16")
            text=text.replace("define('K20D_VERSION', '1.8.17')","define('K20D_VERSION', '1.8.16')")
            original=text.encode()
        out.writestr(name,original)
with zipfile.ZipFile(target) as check:
    assert check.testzip() is None
print("SYNTHETIC_1816_VERSION_ONLY_FIXTURE_CREATED")
