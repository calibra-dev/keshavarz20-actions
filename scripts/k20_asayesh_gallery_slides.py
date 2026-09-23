#!/usr/bin/env python3
from __future__ import annotations

import base64, io, json, math, os, textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "gallery-slide-results"
W, H = 1080, 1920
PRODUCT_ID = 140014
SITE = os.environ.get("WP_BASE_URL","https://keshavarz20.com").rstrip("/")
USER = os.environ["WP_USERNAME"]
PASS = os.environ["WP_APP_PASSWORD"]
AUTH = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
HEADERS = {"Authorization": f"Basic {AUTH}", "Accept": "application/json"}

DARK=(2,37,50); TEAL=(4,76,72); GREEN=(111,221,61); LIME=(181,245,83); GOLD=(246,206,70); WHITE=(255,255,255); MUTED=(211,230,229)

def rtl(s:str)->str:
    return get_display(arabic_reshaper.reshape(s))

def font(size:int,bold=False):
    candidates=[
      "/usr/share/fonts/truetype/noto/NotoSansArabic-Black.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def text_center(d, text, y, f, fill=WHITE, maxw=940, gap=10):
    # wrap conservatively for Persian
    lines=textwrap.wrap(text,width=27,break_long_words=False)
    for line in lines:
        shaped=rtl(line)
        b=d.textbbox((0,0),shaped,font=f)
        d.text(((W-(b[2]-b[0]))/2,y),shaped,font=f,fill=fill)
        y += (b[3]-b[1])+gap
    return y

def card(c, box, title, body, accent=GREEN, icon=None):
    x0,y0,x1,y1=box
    shadow=Image.new("RGBA",(W,H),(0,0,0,0)); sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x0+10,y0+14,x1+10,y1+14),radius=38,fill=(0,0,0,70))
    shadow=shadow.filter(ImageFilter.GaussianBlur(14)); c.alpha_composite(shadow)
    d=ImageDraw.Draw(c)
    d.rounded_rectangle(box,radius=38,fill=(2,53,54,232),outline=accent,width=3)
    if icon:
        d.ellipse((x0+28,y0+28,x0+108,y0+108),fill=(7,93,71,255),outline=accent,width=3)
        ff=font(42,True); b=d.textbbox((0,0),icon,font=ff); d.text((x0+68-(b[2]-b[0])/2,y0+42),icon,font=ff,fill=GOLD)
    tf=font(42,True); bf=font(28,False)
    shaped=rtl(title); b=d.textbbox((0,0),shaped,font=tf)
    d.text((x1-40-(b[2]-b[0]),y0+30),shaped,font=tf,fill=GOLD)
    yy=y0+105
    for line in textwrap.wrap(body,width=26,break_long_words=False):
        s=rtl(line); bb=d.textbbox((0,0),s,font=bf)
        d.text((x1-40-(bb[2]-bb[0]),yy),s,font=bf,fill=WHITE); yy+=45

def background():
    c=Image.new("RGBA",(W,H),DARK+(255,))
    p=c.load()
    for y in range(H):
        t=y/H
        col=(int(DARK[0]*(1-t)+TEAL[0]*t),int(DARK[1]*(1-t)+TEAL[1]*t),int(DARK[2]*(1-t)+TEAL[2]*t),255)
        for x in range(W): p[x,y]=col
    # glow
    g=Image.new("RGBA",(W,H),(0,0,0,0)); gd=ImageDraw.Draw(g)
    gd.ellipse((160,310,920,1160),fill=(80,210,115,45))
    gd.ellipse((-250,1150,520,2050),fill=(5,145,155,55))
    g=g.filter(ImageFilter.GaussianBlur(80)); c.alpha_composite(g)
    d=ImageDraw.Draw(c)
    # stylized water/mist arcs
    for off in (0,130,260):
        d.arc((-150-off,430,540-off,1200),210,350,fill=(220,245,255,110),width=5)
        d.arc((540+off,430,1230+off,1200),190,330,fill=(220,245,255,110),width=5)
    # accent top/bottom
    d.rectangle((0,0,W,18),fill=GREEN)
    d.rectangle((0,H-18,W,H),fill=GREEN)
    return c

def product_layer(im, maxw=780,maxh=780):
    layer=Image.new("RGBA",(W,H),(0,0,0,0))
    x=im.convert("RGBA"); x.thumbnail((maxw,maxh),Image.Resampling.LANCZOS)
    px=(W-x.width)//2; py=0
    sh=Image.new("RGBA",(W,H),(0,0,0,0)); sd=ImageDraw.Draw(sh)
    sd.ellipse((px+40,py+x.height-55,px+x.width-40,py+x.height+45),fill=(0,0,0,90))
    sh=sh.filter(ImageFilter.GaussianBlur(22)); layer.alpha_composite(sh)
    layer.alpha_composite(x,(px,py))
    return layer

def download(url):
    r=requests.get(url,timeout=60,headers={"User-Agent":"K20-gallery-slides/1.0"}); r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")

def upload(path:Path,title:str,alt:str):
    mime="image/webp"
    h={**HEADERS,"Content-Type":mime,"Content-Disposition":f'attachment; filename="{path.name}"'}
    r=requests.post(f"{SITE}/wp-json/wp/v2/media",headers=h,data=path.read_bytes(),timeout=180); r.raise_for_status()
    item=r.json(); mid=int(item["id"])
    p=requests.post(f"{SITE}/wp-json/wp/v2/media/{mid}",headers=HEADERS,json={"title":title,"alt_text":alt},timeout=90); p.raise_for_status()
    j=p.json(); return {"id":mid,"url":j.get("source_url"),"title":title}

def save_webp(c,path):
    c.convert("RGB").save(path,"WEBP",quality=86,method=6)

def build(product_img:Image.Image):
    OUT.mkdir(exist_ok=True)
    files=[]

    # Slide 1
    c=background(); d=ImageDraw.Draw(c)
    text_center(d,"معرفی محصول",75,font(44,True),MUTED)
    text_center(d,"لوله بارانی مه‌پاش ۲ اینچ",155,font(68,True),WHITE)
    text_center(d,"آسایش آذربایجان",245,font(68,True),LIME)
    d.rounded_rectangle((290,355,790,445),radius=35,fill=GOLD)
    text_center(d,"رول ۱۰۰ متری",370,font(42,True),(10,43,53))
    pl=product_layer(product_img,820,790); c.alpha_composite(pl,(0,500))
    d.rounded_rectangle((100,1370,980,1535),radius=45,fill=(1,48,48,235),outline=GREEN,width=3)
    text_center(d,"قطر داخلی: ۵۰ میلی‌متر",1400,font(42,True),GOLD)
    text_center(d,"سایز خارجی: ۲ اینچ",1460,font(36,True),WHITE)
    text_center(d,"مناسب برای بررسی پروژه‌های مه‌پاش و آبیاری",1610,font(34,False),WHITE)
    text_center(d,"keshavarz20.com",1780,font(32,True),MUTED)
    p=OUT/"k20-p140014-slide-01.webp"; save_webp(c,p); files.append(p)

    # Slide 2
    c=background(); d=ImageDraw.Draw(c)
    text_center(d,"ویژگی‌های مهم",75,font(44,True),MUTED)
    text_center(d,"چرا این محصول مهم است؟",165,font(66,True),WHITE)
    pl=product_layer(product_img,700,650); c.alpha_composite(pl,(0,390))
    card(c,(55,1100,515,1435),"قطر داخلی","۵۰ میلی‌متر\nسایز خارجی: ۲ اینچ",GREEN,"↔")
    card(c,(565,1100,1025,1435),"رول ۱۰۰ متری","نمایش محصول واقعی با بسته‌بندی اصلی",GREEN,"◎")
    d.rounded_rectangle((90,1500,990,1695),radius=45,fill=(3,54,51,235),outline=GOLD,width=3)
    text_center(d,"قبل از خرید، شرایط اجرای پروژه را دقیق بررسی کنید",1540,font(34,True),WHITE)
    text_center(d,"keshavarz20.com",1780,font(32,True),MUTED)
    p=OUT/"k20-p140014-slide-02.webp"; save_webp(c,p); files.append(p)

    # Slide 3
    c=background(); d=ImageDraw.Draw(c)
    text_center(d,"قبل از خرید",80,font(46,True),MUTED)
    text_center(d,"این ۳ مورد را چک کن",170,font(68,True),LIME)
    card(c,(70,400,1010,720),"۱ — فشار سیستم","توان کاری سیستم را با نیاز واقعی پروژه تطبیق بده",GREEN,"●")
    card(c,(70,790,1010,1110),"۲ — طول مسیر","متراژ و مسیر اجرا را قبل از انتخاب بررسی کن",GOLD,"↔")
    card(c,(70,1180,1010,1500),"۳ — نوع اتصالات","سازگاری اجزای اتصال، انتخاب دقیق‌تری می‌دهد",GREEN,"□")
    text_center(d,"این ۳ بررسی، انتخاب دقیق‌تری به شما می‌دهد",1610,font(36,True),GOLD)
    text_center(d,"کشاورز بیست | keshavarz20.com",1780,font(31,True),MUTED)
    p=OUT/"k20-p140014-slide-03.webp"; save_webp(c,p); files.append(p)

    # Slide 4
    c=background(); d=ImageDraw.Draw(c)
    text_center(d,"جمع‌بندی",80,font(44,True),MUTED)
    text_center(d,"لوله بارانی مه‌پاش ۲ اینچ",170,font(66,True),WHITE)
    text_center(d,"آسایش آذربایجان",255,font(66,True),LIME)
    pl=product_layer(product_img,820,810); c.alpha_composite(pl,(0,500))
    d.rounded_rectangle((120,1380,960,1570),radius=48,fill=(6,116,65,245),outline=LIME,width=4)
    text_center(d,"قطر داخلی ۵۰ میلی‌متر | سایز خارجی ۲ اینچ",1420,font(34,True),WHITE)
    d.rounded_rectangle((170,1625,910,1745),radius=40,fill=GOLD)
    text_center(d,"مشاهده جزئیات محصول در سایت",1648,font(36,True),(8,42,50))
    text_center(d,"keshavarz20.com",1805,font(34,True),WHITE)
    p=OUT/"k20-p140014-slide-04.webp"; save_webp(c,p); files.append(p)
    return files

def main():
    product=requests.get(f"{SITE}/wp-json/wc/v3/products/{PRODUCT_ID}",headers=HEADERS,timeout=90); product.raise_for_status(); prod=product.json()
    old_images=prod.get("images") or []
    if not old_images: raise RuntimeError("Product has no source image")
    product_img=download(old_images[0]["src"])
    files=build(product_img)
    uploaded=[]
    titles=[
      "معرفی لوله بارانی مه‌پاش ۲ اینچ آسایش آذربایجان",
      "ویژگی‌ها و ابعاد لوله بارانی مه‌پاش آسایش آذربایجان",
      "چک‌لیست قبل از خرید لوله بارانی مه‌پاش",
      "جمع‌بندی لوله بارانی مه‌پاش ۲ اینچ آسایش آذربایجان",
    ]
    alts=[
      "لوله بارانی مه‌پاش ۲ اینچ آسایش آذربایجان رول ۱۰۰ متری؛ قطر داخلی ۵۰ میلی‌متر و سایز خارجی ۲ اینچ",
      "اینفوگرافیک ابعاد لوله بارانی مه‌پاش؛ قطر داخلی ۵۰ میلی‌متر و سایز خارجی ۲ اینچ",
      "چک‌لیست فشار سیستم، طول مسیر و نوع اتصالات قبل از خرید لوله بارانی مه‌پاش",
      "جمع‌بندی مشخصات لوله بارانی مه‌پاش ۲ اینچ آسایش آذربایجان و لینک کشاورز بیست",
    ]
    for p,t,a in zip(files,titles,alts): uploaded.append(upload(p,t,a))
    existing=[{"id":int(x["id"])} for x in old_images]
    newids=[x["id"] for x in uploaded]
    merged=existing+[{"id":i} for i in newids if i not in {x["id"] for x in old_images}]
    upd=requests.put(f"{SITE}/wp-json/wc/v3/products/{PRODUCT_ID}",headers=HEADERS,json={"images":merged},timeout=120); upd.raise_for_status()
    rb=requests.get(f"{SITE}/wp-json/wc/v3/products/{PRODUCT_ID}",headers=HEADERS,timeout=90); rb.raise_for_status(); final=rb.json()
    final_ids=[int(x["id"]) for x in final.get("images") or []]
    if not all(i in final_ids for i in newids): raise RuntimeError("Gallery readback missing new slides")
    result={"ok":True,"product_id":PRODUCT_ID,"product_name":final.get("name"),"previous_image_ids":[int(x["id"]) for x in old_images],"uploaded":uploaded,"final_image_ids":final_ids,"internal_diameter":"50 mm","external_size":"2 inch","preserved_existing":True}
    (OUT/"20260923-p140014-gallery-slides.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
