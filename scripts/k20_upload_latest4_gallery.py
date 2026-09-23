#!/usr/bin/env python3
from __future__ import annotations

import base64, json, os, time
from pathlib import Path

import requests
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
PRODUCT_ID=140014
SITE=os.environ.get("WP_BASE_URL","https://keshavarz20.com").rstrip("/")
USER=os.environ["WP_USERNAME"]
PASS=os.environ["WP_APP_PASSWORD"]
AUTH=(USER,PASS)

PAYLOAD=ROOT/"gallery-slide-payloads"/"20260923-asayesh-latest4"
OUT=ROOT/"gallery-slide-results"
OUT.mkdir(parents=True,exist_ok=True)

TITLES=[
 "معرفی لوله بارانی مه‌پاش ۲ اینچ آسایش آذربایجان",
 "آبدهی و نحوه پاشش لوله بارانی مه‌پاش آسایش آذربایجان",
 "مشخصات و ابعاد لوله بارانی مه‌پاش آسایش آذربایجان",
 "نمونه اجرا و چک‌لیست انتخاب لوله بارانی مه‌پاش",
]
ALTS=[
 "معرفی لوله بارانی مه‌پاش ۲ اینچ آسایش آذربایجان؛ قطر داخلی ۵۰ میلی‌متر، سایز خارجی ۲ اینچ و رول ۱۰۰ متری",
 "اینفوگرافیک نحوه پاشش و آبدهی لوله بارانی مه‌پاش آسایش آذربایجان در مزرعه",
 "مشخصات لوله بارانی مه‌پاش آسایش آذربایجان؛ قطر داخلی ۵۰ میلی‌متر، سایز خارجی ۲ اینچ و رول ۱۰۰ متری",
 "نمونه اجرای لوله بارانی مه‌پاش و چک‌لیست فشار سیستم، طول مسیر، نوع اتصالات و نیاز واقعی پروژه",
]

def wp(method,path,**kwargs):
    r=requests.request(method,SITE+"/wp-json"+path,auth=AUTH,timeout=180,**kwargs)
    r.raise_for_status()
    return r.json()

def rebuild(index:int)->Path:
    parts=sorted(PAYLOAD.glob(f"slide{index}-part*.txt"))
    if not parts:
        raise RuntimeError(f"missing payload chunks for slide {index}")
    data="".join(p.read_text(encoding="ascii").strip() for p in parts)
    raw=base64.b64decode(data)
    tmp=OUT/f"source-{index}.webp"
    tmp.write_bytes(raw)
    with Image.open(tmp).convert("RGB") as im:
        im=im.resize((800,800),Image.Resampling.LANCZOS)
        final=OUT/f"k20-p140014-premium-gallery-{index:02d}.webp"
        im.save(final,"WEBP",quality=82,method=6)
    return final

def upload(path:Path,title,alt):
    headers={
      "Content-Type":"image/webp",
      "Content-Disposition":f'attachment; filename="{path.name}"'
    }
    media=wp("POST","/wp/v2/media",headers=headers,data=path.read_bytes())
    mid=int(media["id"])
    wp("POST",f"/wp/v2/media/{mid}",json={"title":title,"alt_text":alt})
    return {"id":mid,"url":media.get("source_url"),"file":path.name}

def main():
    before=wp("GET",f"/wc/v3/products/{PRODUCT_ID}")
    before_ids=[int(x["id"]) for x in before.get("images",[])]
    built=[rebuild(i) for i in range(1,5)]
    uploaded=[upload(p,t,a) for p,t,a in zip(built,TITLES,ALTS)]
    new_ids=[x["id"] for x in uploaded]
    merged=[{"id":i} for i in before_ids+new_ids if i not in []]
    wp("PUT",f"/wc/v3/products/{PRODUCT_ID}",json={"images":merged})
    final=None
    for _ in range(8):
        time.sleep(3)
        final=wp("GET",f"/wc/v3/products/{PRODUCT_ID}")
        final_ids=[int(x["id"]) for x in final.get("images",[])]
        if all(i in final_ids for i in new_ids):
            break
    final_ids=[int(x["id"]) for x in final.get("images",[])]
    if not all(i in final_ids for i in new_ids):
        raise RuntimeError(f"gallery readback missing new ids: {new_ids}; final={final_ids}")
    result={
      "ok":True,
      "product_id":PRODUCT_ID,
      "product_name":final.get("name"),
      "preserved_existing":True,
      "before_image_ids":before_ids,
      "uploaded":uploaded,
      "final_image_ids":final_ids,
      "dimensions":"800x800",
      "format":"webp",
      "verified":True,
    }
    (OUT/"20260923-p140014-latest4-gallery.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
