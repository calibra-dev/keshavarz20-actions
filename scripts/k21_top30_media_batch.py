#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path

import arabic_reshaper
import requests
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"k21-top30-results"
BASE=os.environ["WP_BASE_URL"].rstrip("/")
USER=os.environ["WP_USERNAME"]
PASSWORD=os.environ["WP_APP_PASSWORD"]
AUTH=base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
HEAD={"Authorization":f"Basic {AUTH}","Accept":"application/json"}

def rtl(text:str)->str:
    return get_display(arabic_reshaper.reshape(str(text)))

def font(size:int):
    paths=[
      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
      "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in paths:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def wrap(draw,text,f,maxw):
    words=str(text).split()
    lines=[]; cur=""
    for w in words:
        test=(cur+" "+w).strip()
        if draw.textbbox((0,0),rtl(test),font=f)[2] <= maxw:
            cur=test
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines

def extract_size(name:str)->str:
    parts=[]
    for m in re.findall(r'(\d+(?:\s*[و/]\s*\d+/\d+|(?:[./]\d+)?)\s*(?:اینچ|میلی\s*متر|میلیمتر))',name):
        if m not in parts: parts.append(m)
    if not parts:
        mm=re.findall(r'(\d+\s*میلی(?:\s*متر|متر))',name)
        parts.extend(mm[:2])
    return " / ".join(parts[:2]) or "طبق عنوان و مشخصات همین محصول"

def product(pid:int)->dict:
    r=requests.get(f"{BASE}/wp-json/wc/v3/products/{pid}",headers=HEAD,timeout=120)
    r.raise_for_status(); return r.json()

def patch_media(mid:int,title:str,alt:str):
    r=requests.post(f"{BASE}/wp-json/wp/v2/media/{mid}",headers=HEAD,json={"title":title,"alt_text":alt},timeout=120)
    r.raise_for_status()

def upload_bytes(data:bytes,filename:str,title:str,alt:str)->dict:
    h={**HEAD,"Content-Disposition":f'attachment; filename="{filename}"',"Content-Type":"image/webp"}
    r=requests.post(f"{BASE}/wp-json/wp/v2/media",headers=h,data=data,timeout=180)
    r.raise_for_status(); item=r.json()
    patch_media(int(item["id"]),title,alt)
    return {"id":int(item["id"]),"src":item.get("source_url"),"alt":alt}

def render_card(main:Image.Image,name:str,sku:str,role:str,bullets:list[str])->bytes:
    canvas=Image.new("RGB",(1200,1200),"white")
    draw=ImageDraw.Draw(canvas)
    photo=ImageOps.contain(main.convert("RGB"),(1040,560))
    x=(1200-photo.width)//2
    canvas.paste(photo,(x,40))
    titlef=font(42); subf=font(29); bodyf=font(27)
    y=635
    role_text=rtl(role)
    draw.text((1080,y),role_text,font=titlef,fill="black",anchor="ra"); y+=65
    for line in wrap(draw,name,subf,1010)[:3]:
        draw.text((1080,y),rtl(line),font=subf,fill="black",anchor="ra"); y+=42
    draw.text((1080,y),rtl(f"SKU: {sku or 'ثبت نشده'}"),font=bodyf,fill="black",anchor="ra"); y+=52
    for bullet in bullets:
        for idx,line in enumerate(wrap(draw,bullet,bodyf,970)[:3]):
            prefix="• " if idx==0 else "  "
            draw.text((1080,y),rtl(prefix+line),font=bodyf,fill="black",anchor="ra"); y+=39
        y+=8
    out=io.BytesIO(); canvas.save(out,format="WEBP",quality=88,method=6)
    return out.getvalue()

def bullets_for(name:str,role:str)->list[str]:
    size=extract_size(name)
    if role=="قبل از خرید":
        return [
          f"سایز ثبت‌شده: {size}",
          "سایز نامی به‌تنهایی سازگاری را ثابت نمی‌کند؛ قطعه مقابل و نوع اتصال را هم کنترل کنید.",
          "قیمت و موجودی را از همین صفحه و در زمان سفارش بررسی کنید.",
        ]
    if role=="سازگاری":
        return [
          "نوع اتصال دو سمت، رزوه/فلنج/بست و جهت مونتاژ را با تجهیز واقعی پروژه تطبیق دهید.",
          "فشار کاری فقط وقتی قطعی است که روی همین مدل، بسته‌بندی یا دیتاشیت معتبر تأیید شده باشد.",
          "اگر یک مشخصه روی صفحه تأیید نشده است، پیش از خرید از پشتیبانی استعلام بگیرید.",
        ]
    return [
      "نصب را بدون کجی، کشش و بار مکانیکی اضافی روی قطعه انجام دهید.",
      "آب‌بندی و مهار را متناسب با نوع اتصال واقعی اجرا کنید.",
      "پس از نصب، شبکه را مرحله‌ای آبگیری و محل اتصال را از نظر نشتی کنترل کنید.",
    ]

def main()->int:
    pim=json.loads((ROOT/"phase3-results/top30-pim.json").read_text(encoding="utf-8"))
    result={"ok":True,"products":[]}
    for row in pim.get("products",[]):
        pid=int(row["product_id"])
        p=product(pid)
        imgs=p.get("images") or []
        if not imgs:
            result["products"].append({"product_id":pid,"ok":False,"reason":"no_source_image"}); continue
        main_img=requests.get(imgs[0]["src"],timeout=120)
        main_img.raise_for_status()
        image=Image.open(io.BytesIO(main_img.content)).convert("RGB")
        name=p.get("name") or row.get("name") or str(pid)
        sku=p.get("sku") or ""
        # Normalize existing media metadata first.
        for idx,img in enumerate(imgs):
            mid=int(img["id"])
            alt=(img.get("alt") or "").strip() or (name if idx==0 else f"{name} - تصویر {idx+1}")
            patch_media(mid,name if idx==0 else f"{name} - تصویر {idx+1}",alt)
        new=[]
        for idx,role in enumerate(["قبل از خرید","سازگاری","نصب و کنترل نهایی"],1):
            data=render_card(image,name,sku,role,bullets_for(name,role))
            safe=f"k21-{pid}-decision-{idx}.webp"
            new.append(upload_bytes(data,safe,f"{name} - {role}",f"{name} - راهنمای {role}"))
        ids=[{"id":int(x["id"])} for x in imgs]
        existing_ids={x["id"] for x in ids}
        for x in new:
            if x["id"] not in existing_ids: ids.append({"id":x["id"]})
        # Keep the original gallery and append decision-support cards only.
        u=requests.put(f"{BASE}/wp-json/wc/v3/products/{pid}",headers=HEAD,json={"images":ids},timeout=180)
        u.raise_for_status()
        updated=u.json()
        result["products"].append({
          "product_id":pid,"name":name,"ok":True,
          "source_image_id":int(imgs[0]["id"]),
          "new_media":new,
          "final_image_count":len(updated.get("images") or []),
          "all_alt_present":all(bool((x.get("alt") or "").strip()) for x in updated.get("images") or [])
        })
    RESULTS.mkdir(exist_ok=True)
    out=RESULTS/"top30-media-batch.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"ok":result["ok"],"products":len(result["products"]),"success":sum(1 for x in result["products"] if x.get("ok"))},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
