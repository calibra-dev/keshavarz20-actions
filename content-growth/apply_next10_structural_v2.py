#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup, Comment, Tag

ROOT=Path(__file__).resolve().parent
WP_BASE=os.environ["WP_BASE_URL"].rstrip("/")
WP_USER=os.environ["WP_USERNAME"]
WP_PASS=os.environ["WP_APP_PASSWORD"]
WM_SCRIPTS=Path(os.environ["K20_WATERMARK_SCRIPTS"])
OUT=ROOT/"output"
BACKUPS=OUT/"backups-next10-v2"
OUT.mkdir(parents=True,exist_ok=True); BACKUPS.mkdir(parents=True,exist_ok=True)

QUICK={
145238:"اگر شیر آبیاری نشتی دارد یا کامل بسته نمی‌شود، اول محل دقیق نشتی و نوع خرابی را مشخص کنید. نشتی رزوه، نشتی از محور، عبور آب از داخل شیر و سفتی مکانیزم علت‌های یکسانی ندارند؛ فشار، وجود ذرات و وضعیت آب‌بندی را قبل از تعویض کامل شیر بررسی کنید.",
145235:"اگر یک زون آبیاری یکنواخت آب نمی‌دهد، قبل از افزایش فشار یا تعویض قطعه، فشار و دبی را در ابتدا، میانه و انتهای زون مقایسه کنید. الگوی اختلاف‌ها معمولاً نشان می‌دهد مشکل بیشتر از افت فشار، گرفتگی، شیب، طول خط یا طراحی زون است.",
145263:"متراژ نوار تیپ از عرض قابل کشت، فاصله ردیف‌ها و طول واقعی ردیف‌ها به دست می‌آید؛ تعداد اتصالات هم به تعداد خطوط و آرایش اتصال وابسته است. محاسبه اولیه برای برآورد خرید مفید است، اما طول مجاز خط، فشار، دبی و اختلاف ارتفاع باید جداگانه کنترل شوند.",
145251:"برای خواندن آزمایش آب آبیاری، EC، SAR، pH، بی‌کربنات، سختی و کیفیت ذرات را جدا از هم نبینید. هیچ عددی به‌تنهایی نسخه خرید فیلتر یا اصلاح آب نیست؛ تفسیر باید با خاک، گیاه، روش آبیاری و خطر گرفتگی یا رسوب کنار هم انجام شود.",
144232:"انتخاب آبپاش از روی سایز رزوه یا برد تبلیغاتی کافی نیست. فشار کاری واقعی، دبی هر آبپاش، تعداد آبپاش‌های هم‌زمان، فاصله‌گذاری، باد، شدت پاشش و نرخ نفوذ خاک باید با هم بررسی شوند تا یکنواختی قابل قبول حاصل شود.",
143916:"در دوره نوسان قیمت کود، کم‌ریسک‌ترین مسیر این است که خرید را از نیاز واقعی گیاه و نتیجه آزمون خاک و آب شروع کنید، نه از یک فرمول ثابت NPK. زمان، روش مصرف، تقسیم نوبت‌ها و سازگاری با مرحله رشد می‌تواند به اندازه مقدار کود روی کارایی اثر بگذارد.",
143913:"در موج گرما و خشکسالی، افزایش کورکورانه زمان آبیاری همیشه پاسخ درست نیست. ابتدا فشار و یکنواختی شبکه، گرفتگی، شیب، ظرفیت منبع و رطوبت واقعی خاک را بررسی کنید و بعد دفعات یا مدت آبیاری را متناسب با مزرعه تنظیم کنید.",
143871:"افت فشار، نشتی و ترکیدن لوله پلی‌اتیلن سه مسئله متفاوت‌اند و باید جداگانه عیب‌یابی شوند. فشار ورودی و خروجی، دبی، قطر داخلی، طول، شیب، وضعیت اتصالات و رخدادهای گذرای فشار را اندازه بگیرید؛ تعویض پمپ یا لوله بدون تشخیص محل افت می‌تواند مسئله را حل نکند.",
143870:"PN، SDR و گرید ماده مثل PE80 یا PE100 هرکدام معنی جداگانه دارند و نباید به‌جای هم استفاده شوند. رده فشار فقط با دیدن یک عدد انتخاب نمی‌شود؛ جنس ماده، SDR، دما، شرایط کار، استاندارد ساخت و فشار واقعی شبکه باید با هم کنترل شوند.",
143869:"سایز لوله پلی‌اتیلن را از روی قطر اسمی یا تجربه یک پروژه دیگر انتخاب نکنید. دبی طراحی، طول مسیر، افت فشار مجاز، اختلاف ارتفاع، قطر داخلی و رده لوله باید هم‌زمان بررسی شوند تا فشار کافی در نقطه مصرف باقی بماند.",
}

RELATED={
145238:[
("https://keshavarz20.com/irrigation-valves-buying-guide/","راهنمای خرید و انتخاب شیرآلات آبیاری"),
("https://keshavarz20.com/irrigation-water-hammer-air-valve-guide/","تشخیص ضربه قوچ و شوک فشار"),
],
145235:[
("https://keshavarz20.com/drip-irrigation-uniformity-du-field-test-guide/","تست یکنواختی آبیاری و محاسبه DU"),
("https://keshavarz20.com/drip-irrigation-pressure-regulator-selection-guide/","انتخاب فشارشکن آبیاری قطره‌ای"),
("https://keshavarz20.com/irrigation-filter-pressure-drop-clogging-troubleshooting/","عیب‌یابی افت فشار و گرفتگی فیلتر"),
],
145263:[
("https://keshavarz20.com/drip-tape-length-fittings-calculator/","ماشین حساب اصلی نوار تیپ؛ متراژ، رول و اتصالات"),
("https://keshavarz20.com/drip-irrigation-zone-uneven-flow-troubleshooting/","عیب‌یابی افت دبی و فشار در زون قطره‌ای"),
],
145251:[
("https://keshavarz20.com/sandy-well-water-drip-filtration-guide/","راهنمای فیلتراسیون آب چاه شنی"),
("https://keshavarz20.com/drip-irrigation-fertigation-injection-guide/","راهنمای تزریق کود در آبیاری قطره‌ای"),
],
144232:[
("https://keshavarz20.com/sprinkler-low-radius-uneven-irrigation-troubleshooting/","عیب‌یابی برد کم و پاشش نامنظم آبپاش"),
("https://keshavarz20.com/irrigation-pump-flow-head-selection-guide/","انتخاب پمپ بر اساس دبی و هد"),
],
143916:[
("https://keshavarz20.com/soil-sampling-before-fertilizing-guide/","نمونه‌برداری خاک قبل از کوددهی"),
("https://keshavarz20.com/drip-irrigation-fertigation-injection-guide/","فرتیگیشن و تزریق کود در آبیاری"),
],
143913:[
("https://keshavarz20.com/drip-irrigation-uniformity-du-field-test-guide/","اندازه‌گیری یکنواختی واقعی آبیاری قطره‌ای"),
("https://keshavarz20.com/drip-tape-sloped-field-design-guide/","طراحی نوار تیپ در زمین شیب‌دار"),
],
143871:[
("https://keshavarz20.com/irrigation-water-hammer-air-valve-guide/","ضربه قوچ، شیر هوا و شوک فشار"),
("https://keshavarz20.com/polyethylene-pipe-size-flow-pressure-guide/","انتخاب سایز لوله پلی‌اتیلن بر اساس دبی و افت فشار"),
],
143870:[
("https://keshavarz20.com/polyethylene-pipe-size-flow-pressure-guide/","انتخاب سایز لوله پلی‌اتیلن"),
("https://keshavarz20.com/polyethylene-pipe-pressure-loss-leak-burst-troubleshooting/","عیب‌یابی افت فشار، نشتی و ترکیدگی"),
],
143869:[
("https://keshavarz20.com/polyethylene-pipe-pn-sdr-pe80-pe100-guide/","راهنمای PN، SDR، PE80 و PE100"),
("https://keshavarz20.com/polyethylene-pipe-pressure-loss-leak-burst-troubleshooting/","عیب‌یابی افت فشار و نشتی لوله پلی‌اتیلن"),
],
}

EXTRA_SOURCES={
143871:[
("https://www.iso.org/standard/70102.html","ISO 8779:2020 — Polyethylene pipes for irrigation"),
("https://www.pe100plus.com/PE-Pipes/Technical-guidance/model/Design/PE-pressure-pipe/PE-pipe-design-i244.html","PE100+ Association — PE pipe design and hydraulic capacity"),
],
143870:[
("https://www.iso.org/ru/standard/72183.html","ISO 4427-1:2019 — Polyethylene pressure piping systems"),
("https://www.pe100plus.com/PE-Pipes/Technical-guidance/model/Design/SDR/pressure-rating-i1047.html","PE100+ Association — SDR and pressure rating"),
("https://www.pe100plus.com/PE-Pipes/Technical-guidance/model/Materials/mrs/What-is-the-meaning-of-the-designations-PE80-PE100-PE100-RC-i254.html","PE100+ Association — PE80, PE100 and MRS"),
],
143869:[
("https://www.iso.org/standard/70102.html","ISO 8779:2020 — Polyethylene pipes for irrigation"),
("https://www.pe100plus.com/PE-Pipes/Technical-guidance/model/Design/PE-pressure-pipe/PE-pipe-design-i244.html","PE100+ Association — Flow capacity and friction loss in PE pipe"),
],
}

def run(cmd:list[str],input_text:str|None=None)->str:
    cp=subprocess.run(cmd,input=input_text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    if cp.returncode!=0: raise RuntimeError((cp.stderr or cp.stdout or f"exit {cp.returncode}")[-3000:])
    return cp.stdout

def curl_json(method:str,route:str,payload:dict|None=None,query:list[tuple[str,str]]|None=None)->Any:
    cmd=["curl","-fsS","--retry","2","--connect-timeout","20","--max-time","150","-u",f"{WP_USER}:{WP_PASS}"]
    url=f"{WP_BASE}/wp-json{route}"
    if method=="GET":
        cmd+=["--get",url]
        for k,v in query or []: cmd+=["--data-urlencode",f"{k}={v}"]
        out=run(cmd)
    else:
        cmd+=["-X",method,"-H","Content-Type: application/json","--data-binary","@-",url]
        out=run(cmd,json.dumps(payload,ensure_ascii=False))
    return json.loads(out)

def clean_external(value:str)->str:
    cleaner=WM_SCRIPTS/"clean_text.py"
    if not cleaner.exists(): raise RuntimeError("watermarks-remover clean_text.py missing")
    with tempfile.TemporaryDirectory(prefix="k20wm-") as td:
        src=Path(td)/"in.html"; dst=Path(td)/"out.html"
        src.write_text(value,encoding="utf-8")
        run([sys.executable,str(cleaner),str(src),"-o",str(dst),"--no-normalize-spaces"])
        return dst.read_text(encoding="utf-8")

def norm(s:str)->str:
    return re.sub(r"\s+"," ",BeautifulSoup(s or "","html.parser").get_text(" ",strip=True)).strip()

def remove_duplicate_review_groups(soup:BeautifulSoup)->int:
    seen=set(); removed=0
    for heading in list(soup.find_all(["h2","h3"])):
        if not heading.parent: continue
        key=(heading.name,norm(str(heading)))
        if key[1] not in {"بازبینی عمیق فنی","چک‌های اجرایی قبل از تصمیم","منابع مرجع تکمیلی","روش تهیه و بازبینی"}:
            continue
        if key not in seen:
            seen.add(key); continue
        level=int(heading.name[1]); node=heading
        while node:
            nxt=node.next_sibling
            if isinstance(nxt,Tag) and nxt.name in {"h2","h3"} and int(nxt.name[1])<=level:
                node.decompose(); removed+=1; break
            node.decompose(); removed+=1; node=nxt
    return removed

def trim_15_faq(soup:BeautifulSoup,keep:int=7)->int:
    removed=0
    for h2 in list(soup.find_all("h2")):
        if "۱۵ سؤال" not in norm(str(h2)): continue
        section=h2.find_parent("section")
        if not section: continue
        qs=list(section.find_all("h3",recursive=True))
        for q in qs[keep:]:
            node=q
            while node:
                nxt=node.next_sibling
                if isinstance(nxt,Tag) and nxt.name in {"h2","h3"}:
                    node.decompose(); removed+=1; break
                node.decompose(); removed+=1; node=nxt
        h2.string="پرسش‌های پرتکرار و کاربردی"
    return removed

def add_quick(soup:BeautifulSoup,pid:int)->bool:
    if any("پاسخ کوتاه" in norm(str(h)) for h in soup.find_all(["h2","h3"])): return False
    sec=soup.new_tag("section"); sec["class"]="k20-quick-answer"; sec["dir"]="rtl"
    sec["style"]="direction:rtl;text-align:right;line-height:2;background:#f4fbf6;border:1px solid #cfe5d5;border-radius:16px;padding:20px;margin:22px 0"
    h=soup.new_tag("h2"); h.string="پاسخ کوتاه"
    p=soup.new_tag("p"); p.string=QUICK[pid]
    sec.append(h); sec.append(p)
    first=soup.find("section")
    if first: first.insert_after(sec)
    else: soup.insert(0,sec)
    return True

def add_related(soup:BeautifulSoup,pid:int,old_html:str)->bool:
    if "مطالب مرتبط برای ادامه تصمیم" in old_html: return False
    items=[x for x in RELATED.get(pid,[]) if x[0] not in old_html][:3]
    if not items: return False
    sec=soup.new_tag("section"); sec["class"]="k20-related-decision-links"; sec["dir"]="rtl"
    sec["style"]="direction:rtl;text-align:right;line-height:2;background:#fff;border:1px solid #dbe9df;border-radius:16px;padding:20px;margin:22px 0"
    h=soup.new_tag("h2"); h.string="مطالب مرتبط برای ادامه تصمیم"; sec.append(h)
    ul=soup.new_tag("ul")
    for url,label in items:
        li=soup.new_tag("li"); a=soup.new_tag("a",href=url); a.string=label; li.append(a); ul.append(li)
    sec.append(ul)
    target=None
    for h2 in soup.find_all("h2"):
        if norm(str(h2)) in {"منابع","منابع فنی","منابع مستقیم","منابع علمی و تاریخ بررسی","منابع و روش بررسی","روش تهیه و بازبینی"}:
            target=h2.find_parent("section") or h2; break
    if target: target.insert_before(sec)
    else: soup.append(sec)
    return True

def add_extra_sources(soup:BeautifulSoup,pid:int,old_html:str)->int:
    srcs=[x for x in EXTRA_SOURCES.get(pid,[]) if x[0] not in old_html]
    if not srcs: return 0
    sec=soup.new_tag("section"); sec["class"]="k20-authoritative-sources"; sec["dir"]="rtl"
    sec["style"]="direction:rtl;text-align:right;line-height:2;background:#fff;border:1px solid #dbe9df;border-radius:16px;padding:20px;margin:22px 0"
    h=soup.new_tag("h2"); h.string="منابع مرجع تکمیلی"; sec.append(h)
    ul=soup.new_tag("ul")
    for url,label in srcs:
        li=soup.new_tag("li"); a=soup.new_tag("a",href=url); a["rel"]="nofollow noopener"; a["target"]="_blank"; a.string=label; li.append(a); ul.append(li)
    sec.append(ul)
    target=None
    for h2 in soup.find_all("h2"):
        if norm(str(h2))=="روش تهیه و بازبینی":
            target=h2.find_parent("section") or h2; break
    if target: target.insert_before(sec)
    else: soup.append(sec)
    return len(srcs)

def strip_phase_comments(soup:BeautifulSoup)->int:
    n=0
    for c in list(soup.find_all(string=lambda x:isinstance(x,Comment))):
        if "k20-phase16-deep-review-v1" in str(c):
            c.extract(); n+=1
    return n

def external_links(html:str)->set[str]:
    return set(re.findall(r'href=["\'](https?://(?![^"\']*keshavarz20\.com)[^"\']+)["\']',html,re.I))

def main():
    posts=curl_json("GET","/wp/v2/posts",query=[("per_page","10"),("offset","10"),("status","publish"),("orderby","date"),("order","desc"),("context","edit")])
    expected=set(QUICK); got={int(p["id"]) for p in posts}
    if got!=expected: raise RuntimeError(f"Posts 11-20 identity changed; refusing write. expected={sorted(expected)} got={sorted(got)}")
    report=[]
    for p in posts:
        pid=int(p["id"])
        def val(x):
            if isinstance(x,dict): return str(x.get("raw") if x.get("raw") is not None else x.get("rendered",""))
            return str(x or "")
        old_html=val(p.get("content")); old_text=BeautifulSoup(old_html,"html.parser").get_text(" ",strip=True)
        backup={"id":pid,"slug":p.get("slug"),"status":p.get("status"),"title":val(p.get("title")),"excerpt":val(p.get("excerpt")),
                "content":old_html,"featured_media":p.get("featured_media"),"categories":p.get("categories"),"tags":p.get("tags"),
                "author":p.get("author"),"meta":p.get("meta") or {}}
        (BACKUPS/f"{pid}.json").write_text(json.dumps(backup,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        soup=BeautifulSoup(old_html,"html.parser")
        dedup=remove_duplicate_review_groups(soup)
        faq=trim_15_faq(soup,7)
        quick=add_quick(soup,pid)
        related=add_related(soup,pid,old_html)
        src_added=add_extra_sources(soup,pid,old_html)
        comments=strip_phase_comments(soup)
        new_html=clean_external(str(soup))
        new_text=BeautifulSoup(new_html,"html.parser").get_text(" ",strip=True)

        if len(new_text)<min(3200,int(len(old_text)*0.60)): raise RuntimeError(f"{pid}: content depth dropped too much")
        for must in ("جمع‌بندی","نظر کارشناسی کشاورز بیست","روش تهیه و بازبینی"):
            if must not in new_text: raise RuntimeError(f"{pid}: missing required trust marker {must}")
        if not external_links(old_html).issubset(external_links(new_html)): raise RuntimeError(f"{pid}: existing external source link lost")
        if pid in EXTRA_SOURCES and len(external_links(new_html))<2: raise RuntimeError(f"{pid}: authoritative source enrichment failed")

        curl_json("POST",f"/wp/v2/posts/{pid}",{"content":new_html})
        rb=curl_json("GET",f"/wp/v2/posts/{pid}",query=[("context","edit")]); rb_html=val(rb.get("content"))
        guards={
          "status":str(rb.get("status"))==str(backup["status"])=="publish",
          "slug":str(rb.get("slug"))==str(backup["slug"]),
          "featured_media":int(rb.get("featured_media") or 0)==int(backup["featured_media"] or 0),
          "categories":[int(x) for x in rb.get("categories") or []]==[int(x) for x in backup["categories"] or []],
          "tags":[int(x) for x in rb.get("tags") or []]==[int(x) for x in backup["tags"] or []],
          "author":int(rb.get("author") or 0)==int(backup["author"] or 0),
          "content_hash":hashlib.sha256(rb_html.encode()).hexdigest()==hashlib.sha256(new_html.encode()).hexdigest(),
        }
        if not all(guards.values()):
            curl_json("POST",f"/wp/v2/posts/{pid}",{"content":old_html})
            raise RuntimeError(f"{pid}: readback guard failed; content rolled back: {guards}")
        report.append({"id":pid,"url":rb.get("link"),"status":"updated","deduplicated_nodes":dedup,"faq_nodes_removed":faq,
                       "quick_answer_added":quick,"related_links_added":related,"authoritative_sources_added":src_added,
                       "phase_comments_removed":comments,"before_chars":len(old_text),"after_chars":len(new_text),
                       "before_sha256":hashlib.sha256(old_html.encode()).hexdigest(),
                       "after_sha256":hashlib.sha256(new_html.encode()).hexdigest(),"guards":guards})
        print(json.dumps(report[-1],ensure_ascii=False))
    out={"ok":True,"engine":"K20 structural content growth v2 - posts 11-20","count":len(report),
         "watermark_filter":"guillaumemeyer/watermarks-remover v0.7.0 clean_text --no-normalize-spaces","posts":report}
    (ROOT/"next10-structural-v2-report.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"next10-structural-v2-report.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
