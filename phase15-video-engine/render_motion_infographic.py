#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "phase15-video-engine"
OUT = ENGINE / "out"

spec = importlib.util.spec_from_file_location("k20_video_engine", ENGINE / "k20_video_engine.py")
engine = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

W, H = 1080, 1920
BG = (247, 250, 252)
BLUE = (16, 107, 170)
DARK = (12, 50, 80)
GREEN = (24, 145, 78)
SOFT_BLUE = (231, 244, 252)
SOFT_GREEN = (235, 248, 239)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def font(size: int, bold: bool = False):
    win = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates = [
        win / ("tahomabd.ttf" if bold else "tahoma.ttf"),
        win / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def rtl(text: str) -> str:
    return engine.rtl(text)


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, f, fill, max_width=960, line_gap=14):
    lines = textwrap.wrap(text, width=28, break_long_words=False)
    for line in lines:
        shaped = rtl(line)
        box = draw.textbbox((0,0), shaped, font=f)
        tw = box[2]-box[0]
        draw.text(((W-tw)//2, y), shaped, font=f, fill=fill)
        y += (box[3]-box[1]) + line_gap
    return y


def add_card(canvas: Image.Image, xy, title: str, body: str, accent):
    x0,y0,x1,y1 = xy
    shadow = Image.new("RGBA", canvas.size, (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x0+10,y0+14,x1+10,y1+14), radius=34, fill=(0,0,0,36))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    canvas.alpha_composite(shadow)
    d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((x0,y0,x1,y1), radius=34, fill=(255,255,255,245), outline=accent, width=3)
    d.rounded_rectangle((x0+22,y0+22,x0+92,y0+92), radius=20, fill=accent)
    centered_x=(x0+x1)//2
    tf=font(40,True); bf=font(31,False)
    t=rtl(title)
    tb=d.textbbox((0,0),t,font=tf)
    d.text((centered_x-(tb[2]-tb[0])//2,y0+116),t,font=tf,fill=DARK)
    lines=textwrap.wrap(body,width=25,break_long_words=False)
    yy=y0+180
    for line in lines:
        s=rtl(line); bb=d.textbbox((0,0),s,font=bf)
        d.text((centered_x-(bb[2]-bb[0])//2,yy),s,font=bf,fill=(55,70,85))
        yy+=46


def product_layer(product_img: Image.Image, box=(120,420,960,1180)):
    x0,y0,x1,y1=box
    layer=Image.new("RGBA",(W,H),(0,0,0,0))
    img=product_img.copy().convert("RGBA")
    img.thumbnail((x1-x0, y1-y0))
    x=(W-img.width)//2
    y=y0+(y1-y0-img.height)//2
    shadow=Image.new("RGBA",(W,H),(0,0,0,0))
    sd=ImageDraw.Draw(shadow)
    sd.ellipse((x+40,y+img.height-30,x+img.width-40,y+img.height+55), fill=(0,0,0,45))
    shadow=shadow.filter(ImageFilter.GaussianBlur(18))
    layer.alpha_composite(shadow)
    layer.alpha_composite(img,(x,y))
    return layer


def scene_base():
    c=Image.new("RGBA",(W,H),BG+(255,))
    d=ImageDraw.Draw(c)
    d.rectangle((0,0,W,22),fill=BLUE)
    d.rectangle((0,H-22,W,H),fill=GREEN)
    return c


def make_scenes(product_img: Image.Image, outdir: Path):
    scenes=[]
    # Scene 1
    c=scene_base(); d=ImageDraw.Draw(c)
    centered(d,"معرفی محصول",80,font(46,True),BLUE)
    centered(d,"لوله بارانی مه‌پاش ۲ اینچ آسایش آذربایجان",160,font(60,True),DARK)
    c.alpha_composite(product_layer(product_img,(120,430,960,1220)))
    d.rounded_rectangle((330,1290,750,1390), radius=36, fill=BLUE)
    centered(d,"رول ۱۰۰ متری",1310,font(44,True),(255,255,255))
    centered(d,"سایز ۲ اینچ",1450,font(48,True),GREEN)
    centered(d,"keshavarz20.com",1740,font(34,False),(80,95,110))
    p=outdir/"scene-01.png"; c.convert("RGB").save(p,quality=95); scenes.append(p)

    # Scene 2
    c=scene_base(); d=ImageDraw.Draw(c)
    centered(d,"برای چه کاری؟",90,font(58,True),DARK)
    c.alpha_composite(product_layer(product_img,(220,260,860,900)))
    add_card(c,(100,980,980,1370),"کاربرد","مناسب برای سیستم‌های مه‌پاش و آبیاری؛ انتخاب نهایی باید با شرایط واقعی پروژه هماهنگ شود.",GREEN)
    centered(d,"محصول واقعی کشاورز بیست",1530,font(42,True),BLUE)
    centered(d,"بدون ادعای فنی ساختگی",1610,font(34,False),(80,95,110))
    p=outdir/"scene-02.png"; c.convert("RGB").save(p,quality=95); scenes.append(p)

    # Scene 3
    c=scene_base(); d=ImageDraw.Draw(c)
    centered(d,"قبل از خرید بررسی کنید",100,font(58,True),DARK)
    add_card(c,(90,330,990,720),"۱","فشار سیستم و شرایط کاری",BLUE)
    add_card(c,(90,790,990,1180),"۲","طول مسیر و نحوه اجرای خط",GREEN)
    add_card(c,(90,1250,990,1640),"۳","نوع اتصالات و سازگاری اجزا",BLUE)
    p=outdir/"scene-03.png"; c.convert("RGB").save(p,quality=95); scenes.append(p)

    # Scene 4
    c=scene_base(); d=ImageDraw.Draw(c)
    centered(d,"انتخاب مطمئن‌تر با بررسی درست",100,font(54,True),DARK)
    c.alpha_composite(product_layer(product_img,(160,350,920,1100)))
    d.rounded_rectangle((125,1260,955,1455),radius=48,fill=GREEN)
    centered(d,"مشاهده جزئیات محصول",1305,font(48,True),(255,255,255))
    centered(d,"keshavarz20.com",1370,font(42,True),(255,255,255))
    centered(d,"لوله مه‌پاش ۲ اینچ آسایش آذربایجان",1600,font(37,True),BLUE)
    p=outdir/"scene-04.png"; c.convert("RGB").save(p,quality=95); scenes.append(p)
    return scenes


def render_segments(scenes: list[Path], outdir: Path, seconds_each=3.75):
    segs=[]
    frames=int(round(seconds_each*30))
    for i,p in enumerate(scenes,1):
        seg=outdir/f"seg-{i:02d}.mp4"
        zoom="min(zoom+0.0005,1.045)" if i%2 else "min(zoom+0.00035,1.035)"
        run([
            "ffmpeg","-y","-loop","1","-i",str(p),
            "-vf",f"zoompan=z='{zoom}':d={frames}:s={W}x{H}:fps=30,fade=t=in:st=0:d=0.25,fade=t=out:st={seconds_each-0.25:.2f}:d=0.25,format=yuv420p",
            "-t",f"{seconds_each:.3f}","-an","-c:v","libx264","-preset","medium","-crf","19",str(seg)
        ])
        segs.append(seg)
    concat=outdir/"segments.txt"
    concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in segs),encoding="utf-8")
    return segs,concat


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("request")
    a=ap.parse_args()
    req=json.loads((ROOT/a.request).read_text(encoding="utf-8"))
    pid=int(req["product_id"])
    duration=float(req.get("duration_seconds",15))
    if abs(duration-15)>0.01:
        raise SystemExit("This renderer is locked to 15 seconds for this request")

    image_url, product_url, resolved=engine.choose_real_product_image("", product_id=pid)
    if resolved != pid:
        raise RuntimeError("Resolved product mismatch")

    outdir=OUT/f"motion-infographic-{pid}-15s"
    outdir.mkdir(parents=True,exist_ok=True)
    source=outdir/"source-product.jpg"
    engine.download(image_url,source)
    product_img=Image.open(source).convert("RGB")
    scenes=make_scenes(product_img,outdir)

    narration=req["narration"]
    raw_audio=outdir/"narration-raw.mp3"
    audio=outdir/"narration.mp3"
    engine.synthesize_audio(narration,raw_audio,voice=req.get("voice","fa-IR-FaridNeural"))
    engine.fit_audio_duration(raw_audio,audio,15.0)

    segs,concat=render_segments(scenes,outdir,3.75)
    silent=outdir/"silent.mp4"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(silent)])
    video=outdir/"video.mp4"
    run([
        "ffmpeg","-y","-i",str(silent),"-i",str(audio),"-t","15.000",
        "-c:v","copy","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(video)
    ])
    result={
        "ok":True,
        "mode":"motion-infographic",
        "product_id":pid,
        "product_url":product_url,
        "source_image_url":image_url,
        "duration_seconds":round(engine.media_duration(video),3),
        "video_file":str(video.relative_to(ROOT)),
        "scenes":[str(p.relative_to(ROOT)) for p in scenes],
        "narration":narration,
    }
    (outdir/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
