#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Comment, Tag

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
WP_BASE = os.environ["WP_BASE_URL"].rstrip("/")
WP_USER = os.environ["WP_USERNAME"]
WP_PASS = os.environ["WP_APP_PASSWORD"]
WM_SCRIPTS = Path(os.environ["K20_WATERMARK_SCRIPTS"])
OUT = ROOT / "output"
BACKUPS = OUT / "backups-structural-v2"
OUT.mkdir(parents=True, exist_ok=True)
BACKUPS.mkdir(parents=True, exist_ok=True)

CALC_URL = "https://keshavarz20.com/drip-tape-length-fittings-calculator/"

QUICK = {
146227: "اگر آب چاه شن حمل می‌کند، تصمیم را با نام فیلتر شروع نکنید. ابتدا نوع و شدت ذرات، دبی سیستم و نیاز فیلتراسیون قطره‌چکان را مشخص کنید؛ در بار شن بالا، جداکننده شن می‌تواند پیش از فیلتر نهایی قرار گیرد، اما جای فیلتر نهایی را نمی‌گیرد.",
145899: "فشارشکن زمانی مفید است که فشار ورودی از نیاز پایین‌دست بیشتر باشد و بخواهید فشار یک زون را کنترل کنید. اگر فشار منبع از ابتدا کم است، فشارشکن راه‌حل نیست؛ اول افت مسیر، گرفتگی، پمپ و قطر لوله را بررسی کنید.",
145775: "برای فهمیدن یکنواختی آبیاری، حدس‌زدن کافی نیست. دبی چند قطره‌چکان نماینده و فشار نقاط کلیدی را در شرایط پایدار اندازه بگیرید، سپس DU را محاسبه کنید تا مشخص شود مشکل بیشتر به افت فشار، گرفتگی یا طراحی شبکه مربوط است.",
145236: "افت فشار بعد از فیلتر فقط وقتی به خود فیلتر نسبت داده می‌شود که فشار قبل و بعد آن را در دبی واقعی مقایسه کنید. اگر افت پس از شست‌وشو سریع برمی‌گردد، نوع آلودگی، ظرفیت فیلتر و شرایط آب باید دوباره بررسی شود.",
145344: "پمپ آبیاری را با اسب‌بخار انتخاب نکنید. انتخاب درست از دبی زون فعال و هد کل دینامیکی شروع می‌شود و باید نقطه کار واقعی روی منحنی پمپ با فشار و دبی موردنیاز شبکه هم‌خوان باشد.",
145330: "قطره‌چکان PC همیشه انتخاب بهتر نیست. وقتی شیب، طول خط یا اختلاف فشار معنی‌دار دارید، PC می‌تواند تغییر دبی را در محدوده کاری خودش کمتر کند؛ اما جای طراحی درست، فشارشکن، فیلتراسیون یا کنترل گرفتگی را نمی‌گیرد.",
145281: "فرتیگیشن را از مقدار کود شروع نکنید؛ اول کیفیت آب، فشار، دبی، روش تزریق و سازگاری کودها را بررسی کنید. تزریق باید در شرایط پایدار شبکه انجام شود و شست‌وشوی کافی پس از آن بخشی از فرایند است.",
145253: "آزمایش خاک فقط وقتی برای تصمیم کوددهی ارزش دارد که نمونه واقعاً نماینده زمین باشد. ناحیه‌های متفاوت را جدا کنید، عمق و زمان نمونه‌برداری را با هدف آزمایش هماهنگ کنید و از نقاط غیرعادی برای نمونه مرکب عمومی استفاده نکنید.",
145237: "برد کم آبپاش فقط به معنی فشار کم نیست. فشار خارج از محدوده طراحی، نازل گرفته یا فرسوده، دبی ناکافی، باد و فاصله‌گذاری نامناسب هم می‌توانند پاشش را خراب کنند؛ بنابراین فشار و وضعیت نازل را قبل از خرید قطعه جدید اندازه بگیرید.",
145259: "ضربه قوچ با فشار زیاد دائمی فرق دارد و معمولاً هم‌زمان با تغییر سریع جریان رخ می‌دهد. زمان بسته‌شدن شیر، رفتار پمپ، سرعت جریان، هوا و آرایش خط را بررسی کنید؛ یک شیر هوا یا فشارشکن به‌تنهایی راه‌حل عمومی همه شبکه‌ها نیست.",
}

RELATED = {
146227: [
("https://keshavarz20.com/irrigation-filter-pressure-drop-clogging-troubleshooting/","عیب‌یابی افت فشار و گرفتگی فیلتر آبیاری"),
("https://keshavarz20.com/drip-irrigation-uniformity-du-field-test-guide/","تست یکنواختی و دبی قطره‌چکان در مزرعه"),
],
145899: [
("https://keshavarz20.com/pc-vs-non-pc-drip-emitter-selection-guide/","مقایسه قطره‌چکان PC و معمولی"),
("https://keshavarz20.com/drip-irrigation-uniformity-du-field-test-guide/","تست یکنواختی آبیاری قطره‌ای و محاسبه DU"),
],
145775: [
("https://keshavarz20.com/drip-irrigation-pressure-regulator-selection-guide/","راهنمای انتخاب فشارشکن آبیاری قطره‌ای"),
("https://keshavarz20.com/irrigation-filter-pressure-drop-clogging-troubleshooting/","تشخیص افت فشار و گرفتگی فیلتر"),
],
145236: [
("https://keshavarz20.com/sandy-well-water-drip-filtration-guide/","فیلتراسیون آب چاه شنی در آبیاری قطره‌ای"),
("https://keshavarz20.com/drip-irrigation-uniformity-du-field-test-guide/","تست دبی و یکنواختی شبکه قطره‌ای"),
],
145344: [
("https://keshavarz20.com/drip-irrigation-pressure-regulator-selection-guide/","انتخاب فشارشکن بر اساس فشار و دبی واقعی"),
("https://keshavarz20.com/irrigation-water-hammer-air-valve-guide/","تشخیص ضربه قوچ و شوک فشار در شبکه"),
],
145330: [
("https://keshavarz20.com/drip-irrigation-pressure-regulator-selection-guide/","راهنمای فشارشکن آبیاری قطره‌ای"),
("https://keshavarz20.com/drip-irrigation-uniformity-du-field-test-guide/","اندازه‌گیری یکنواختی واقعی آبیاری"),
],
145281: [
("https://keshavarz20.com/sandy-well-water-drip-filtration-guide/","انتخاب فیلتراسیون برای آب چاه شنی"),
("https://keshavarz20.com/irrigation-filter-pressure-drop-clogging-troubleshooting/","عیب‌یابی گرفتگی و افت فشار فیلتر"),
],
145253: [
("https://keshavarz20.com/%da%a9%d9%88%d8%af%d9%87%d8%a7%db%8c-%da%a9%d8%b4%d8%a7%d9%88%d8%b1%d8%b2%db%8c/","دسته کودهای کشاورزی"),
("https://keshavarz20.com/category/knowledge-center/%d8%aa%d8%ba%d8%b0%db%8c%d9%87-%da%af%db%8c%d8%a7%d9%87-%d9%88-%da%a9%d9%88%d8%af-%d8%af%d9%87%db%8c/","مطالب تغذیه گیاه و کوددهی"),
],
145237: [
("https://keshavarz20.com/irrigation-pump-flow-head-selection-guide/","انتخاب پمپ آبیاری بر اساس دبی و هد"),
("https://keshavarz20.com/irrigation-water-hammer-air-valve-guide/","بررسی شوک فشار و ضربه قوچ در شبکه آبیاری"),
],
145259: [
("https://keshavarz20.com/irrigation-pump-flow-head-selection-guide/","انتخاب و بررسی نقطه کار پمپ آبیاری"),
("https://keshavarz20.com/drip-irrigation-pressure-regulator-selection-guide/","کنترل فشار با فشارشکن آبیاری"),
],
}

CALC_RELEVANT = {146227,145899,145775,145236,145330,145281}


def run(cmd:list[str], *, input_text:str|None=None) -> str:
    cp=subprocess.run(cmd,input=input_text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or f"exit {cp.returncode}")[-3000:])
    return cp.stdout


def curl_json(method:str, route:str, payload:dict|None=None, query:list[tuple[str,str]]|None=None)->Any:
    url=f"{WP_BASE}/wp-json{route}"
    cmd=["curl","-fsS","--retry","2","--connect-timeout","20","--max-time","150",
         "-u",f"{WP_USER}:{WP_PASS}"]
    if method == "GET":
        cmd += ["--get",url]
        for k,v in query or []:
            cmd += ["--data-urlencode",f"{k}={v}"]
    else:
        cmd += ["-X",method,"-H","Content-Type: application/json","--data-binary","@-",url]
    out=run(cmd,input_text=json.dumps(payload,ensure_ascii=False) if payload is not None else None)
    return json.loads(out)


def clean_external(value:str)->str:
    cleaner=WM_SCRIPTS/"clean_text.py"
    if not cleaner.exists():
        raise RuntimeError("watermarks-remover clean_text.py missing")
    with tempfile.TemporaryDirectory(prefix="k20wm-") as td:
        src=Path(td)/"in.html"; dst=Path(td)/"out.html"
        src.write_text(value,encoding="utf-8")
        run([sys.executable,str(cleaner),str(src),"-o",str(dst),"--no-normalize-spaces"])
        return dst.read_text(encoding="utf-8")


def norm(s:str)->str:
    return re.sub(r"\s+"," ",BeautifulSoup(s or "","html.parser").get_text(" ",strip=True)).strip()


def remove_duplicate_heading_blocks(soup:BeautifulSoup)->int:
    seen:set[tuple[str,str]]=set()
    removed=0
    for heading in list(soup.find_all(["h2","h3"])):
        if not heading.parent:
            continue
        key=(heading.name,norm(str(heading)))
        if not key[1]:
            continue
        if key not in seen:
            seen.add(key); continue
        # Remove only known repeated editorial-review headings, never ordinary FAQ duplicates.
        if key[1] not in {"بازبینی عمیق فنی","چک‌های اجرایی قبل از تصمیم","منابع مرجع تکمیلی","روش تهیه و بازبینی"}:
            continue
        level=int(heading.name[1])
        node=heading
        while node:
            nxt=node.next_sibling
            if isinstance(nxt,Tag) and nxt.name in {"h2","h3"} and int(nxt.name[1]) <= level:
                node.decompose(); removed+=1; break
            node.decompose(); removed+=1
            node=nxt
    return removed


def trim_faq_sections(soup:BeautifulSoup, keep:int=7)->int:
    removed=0
    for h2 in list(soup.find_all("h2")):
        title=norm(str(h2))
        if "۱۵ سؤال" not in title:
            continue
        section=h2.find_parent("section")
        if not section:
            continue
        questions=list(section.find_all("h3",recursive=True))
        for q in questions[keep:]:
            node=q
            while node:
                nxt=node.next_sibling
                if isinstance(nxt,Tag) and nxt.name in {"h2","h3"}:
                    node.decompose(); removed+=1; break
                node.decompose(); removed+=1
                node=nxt
        h2.string="پرسش‌های پرتکرار و کاربردی"
    return removed


def make_quick(soup:BeautifulSoup, post_id:int)->bool:
    if any("پاسخ کوتاه" in norm(str(h)) for h in soup.find_all(["h2","h3"])):
        return False
    block=soup.new_tag("section")
    block["class"]="k20-quick-answer"
    block["dir"]="rtl"
    block["style"]="direction:rtl;text-align:right;line-height:2;background:#f4fbf6;border:1px solid #cfe5d5;border-radius:16px;padding:20px;margin:22px 0"
    h=soup.new_tag("h2"); h.string="پاسخ کوتاه"
    p=soup.new_tag("p"); p.string=QUICK[post_id]
    block.append(h); block.append(p)
    first=soup.find("section")
    if first:
        first.insert_after(block)
    else:
        soup.insert(0,block)
    return True


def make_related(soup:BeautifulSoup,post_id:int,current_html:str)->bool:
    if "مطالب مرتبط برای ادامه تصمیم" in current_html:
        return False
    items=list(RELATED.get(post_id,[]))
    if post_id in CALC_RELEVANT and CALC_URL not in current_html:
        items.insert(0,(CALC_URL,"ماشین حساب نوار تیپ؛ محاسبه متراژ، رول و اتصالات"))
    # filter already-existing links
    items=[x for x in items if x[0] not in current_html][:3]
    if not items:
        return False
    sec=soup.new_tag("section")
    sec["class"]="k20-related-decision-links"
    sec["dir"]="rtl"
    sec["style"]="direction:rtl;text-align:right;line-height:2;background:#fff;border:1px solid #dbe9df;border-radius:16px;padding:20px;margin:22px 0"
    h=soup.new_tag("h2"); h.string="مطالب مرتبط برای ادامه تصمیم"; sec.append(h)
    ul=soup.new_tag("ul")
    for url,label in items:
        li=soup.new_tag("li"); a=soup.new_tag("a",href=url); a.string=label; li.append(a); ul.append(li)
    sec.append(ul)
    # Insert before sources/method/summary when possible.
    target=None
    for h2 in soup.find_all("h2"):
        t=norm(str(h2))
        if t in {"منابع","منابع فنی","منابع و محدودیت‌های این راهنما","منابع و دامنه اعتبار این راهنما","روش تهیه و بازبینی"}:
            target=h2.find_parent("section") or h2
            break
    if target: target.insert_before(sec)
    else: soup.append(sec)
    return True


def sanitize_comments(soup:BeautifulSoup)->int:
    n=0
    for c in list(soup.find_all(string=lambda x:isinstance(x,Comment))):
        txt=str(c)
        if "k20-phase16-deep-review-v1" in txt:
            # Repeated phase markers are internal implementation noise.
            c.extract(); n+=1
    return n


def main()->None:
    posts=curl_json("GET","/wp/v2/posts",query=[
        ("per_page","10"),("status","publish"),("orderby","date"),("order","desc"),("context","edit")
    ])
    expected=set(QUICK)
    got={int(p["id"]) for p in posts}
    if got != expected:
        raise RuntimeError(f"Latest-10 identity changed; refusing live write. expected={sorted(expected)} got={sorted(got)}")

    report=[]
    for p in posts:
        pid=int(p["id"])
        def val(x):
            if isinstance(x,dict):
                return str(x.get("raw") if x.get("raw") is not None else x.get("rendered",""))
            return str(x or "")
        old_html=val(p.get("content"))
        backup={
            "id":pid,"slug":p.get("slug"),"status":p.get("status"),"title":val(p.get("title")),
            "excerpt":val(p.get("excerpt")),"content":old_html,"featured_media":p.get("featured_media"),
            "categories":p.get("categories"),"tags":p.get("tags"),"author":p.get("author"),"meta":p.get("meta") or {},
        }
        (BACKUPS/f"{pid}.json").write_text(json.dumps(backup,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

        soup=BeautifulSoup(old_html,"html.parser")
        dedup=remove_duplicate_heading_blocks(soup)
        faq_removed=trim_faq_sections(soup,keep=7)
        quick=make_quick(soup,pid)
        related=make_related(soup,pid,old_html)
        comments=sanitize_comments(soup)
        new_html=str(soup)
        new_html=clean_external(new_html)

        # Guardrails: sources, trust, summary and visible depth must remain.
        new_text=BeautifulSoup(new_html,"html.parser").get_text(" ",strip=True)
        old_text=BeautifulSoup(old_html,"html.parser").get_text(" ",strip=True)
        if len(new_text) < min(3500,int(len(old_text)*0.62)):
            raise RuntimeError(f"{pid}: content depth dropped too much")
        for must in ("جمع‌بندی","نظر کارشناسی کشاورز بیست","روش تهیه و بازبینی"):
            if must not in new_text:
                raise RuntimeError(f"{pid}: required trust section missing: {must}")
        old_external=set(re.findall(r'href=["\'](https?://(?![^"\']*keshavarz20\.com)[^"\']+)["\']',old_html,re.I))
        new_external=set(re.findall(r'href=["\'](https?://(?![^"\']*keshavarz20\.com)[^"\']+)["\']',new_html,re.I))
        if not old_external.issubset(new_external):
            raise RuntimeError(f"{pid}: external source link was lost")

        payload={"content":new_html}
        curl_json("POST",f"/wp/v2/posts/{pid}",payload=payload)
        rb=curl_json("GET",f"/wp/v2/posts/{pid}",query=[("context","edit")])
        rb_html=val(rb.get("content"))
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
            # immediate rollback of content only; immutable guards should never have changed.
            curl_json("POST",f"/wp/v2/posts/{pid}",payload={"content":old_html})
            raise RuntimeError(f"{pid}: readback guard failed and content was rolled back: {guards}")

        report.append({
            "id":pid,"url":rb.get("link"),"status":"updated",
            "deduplicated_nodes":dedup,"faq_nodes_removed":faq_removed,
            "quick_answer_added":quick,"related_links_added":related,
            "phase_comments_removed":comments,
            "before_chars":len(old_text),"after_chars":len(new_text),
            "before_sha256":hashlib.sha256(old_html.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(new_html.encode()).hexdigest(),
            "guards":guards,
        })
        print(json.dumps(report[-1],ensure_ascii=False))

    out={"ok":True,"engine":"K20 structural content growth v2","count":len(report),
         "watermark_filter":"guillaumemeyer/watermarks-remover v0.7.0 clean_text --no-normalize-spaces",
         "posts":report}
    (ROOT/"latest10-structural-v2-report.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"latest10-structural-v2-report.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
