#!/usr/bin/env python3
import importlib.util, os
from urllib import parse

ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe10",os.path.join(ROOT,"engine_v10.py")); v10=importlib.util.module_from_spec(spec); spec.loader.exec_module(v10)
q=v10.q
orig_fitting_subtype=q.fitting_subtype


def structured_family_v11(p):
    parts=[]
    parts.extend(str(x.get("name") or "") for x in (p.get("categories") or []))
    parts.extend(str(x.get("name") or "") for x in (p.get("tags") or []))
    for attr in p.get("attributes") or []:
        parts.append(str(attr.get("name") or ""))
        parts.extend(str(x) for x in (attr.get("options") or []))
    text=q.b.norm(" ".join(parts))
    if not text:return "generic"
    scores={}
    for fam,words in q.b.FAMILY_KEYWORDS.items():
        score=0
        for word in words:
            nw=q.b.norm(word)
            if nw and nw in text:
                score+=max(1,len(nw.split()))
                if len(nw)>=7:score+=1
        scores[fam]=score
    top=max(scores.values()) if scores else 0
    if top<=0:return "generic"
    winners=[fam for fam,score in scores.items() if score==top]
    return winners[0] if len(winners)==1 else "generic"


def family_v11(p):
    name=q.b.norm(str(p.get("name") or ""))
    name_rules=[
        ("drip_tape",["نوار تیپ","نوارتیپ"]),
        ("fertigation",["تانک کود","تزریق کود","ونتوری","انژکتور کود"]),
        ("filter",["فیلتر","هیدروسیکلون"]),
        ("valve",["شیر توپی","شیر پروانه","شیر فلکه","شیر تک ضرب","شیر تیپ","شیر لی فلت","شیر لی‌فلت","بال ولو","گیت ولو"]),
        ("fitting",[
            "بوشن","مغزی","مهره ماسوره","مهره‌ماسوره","نیپل","کوپلینگ",
            "کمربند","رابط","زانو","سه راه","سه‌راه","چهار راه","چهارراه","تبدیل",
            "بست","سرشلنگ","سر شلنگ","فلنج","واشر","سوپاپ","درپوش","انتهای خط",
            "رابط تیپ","اتصال تیپ"
        ]),
        ("sprinkler",["آبپاش","مه پاش","مه‌پاش"]),
        ("pipe",["لوله","لی فلت","لی‌فلت","نخدار","لوله پلی اتیلن","لوله پلی‌اتیلن"]),
        ("pesticide",["سم","حشره","قارچ کش","علف کش","اتفون","کنه کش","نماتد"]),
        ("fertilizer",["کود","هیومیک","آهن","پتاس","فسفر","npk","کلسیم","ریز مغذ","میکرو","فیکس","پلی اس","اسید آمینه"]),
    ]
    for fam,words in name_rules:
        if any(q.b.norm(w) in name for w in words):return fam
    return structured_family_v11(p)


def fitting_subtype_v11(p):
    n=q.b.norm(str(p.get("name") or ""))
    if "بوشن" in n:return "bushing"
    if "مغزی" in n or "نیپل" in n:return "nipple"
    if "مهره ماسوره" in n or "مهره‌ماسوره" in n:return "union"
    if "کوپلینگ" in n:return "coupling"
    return orig_fitting_subtype(p)


def recent_generated_comments_v11(cfg,limit=100):
    wp=q.FastWP(); found={}; per=max(1,min(100,int(limit or 100)))
    for status in ("hold","approve"):
        params=parse.urlencode({
            "context":"edit","per_page":per,"page":1,"orderby":"date_gmt","order":"desc","status":status,
            "_fields":"id,post,parent,date,date_gmt,author_name,author_email,content,status,type"
        })
        # Fail closed: if the watchdog cannot inspect the queue, the caller must fail rather than assume zero pending.
        _,rows,_=wp._call("GET","/wp-json/wp/v2/comments?"+params)
        for c in rows or []:
            if v10.v9._is_generated(c,cfg):found[int(c["id"])]=c
    return sorted(found.values(),key=lambda c:str(c.get("date_gmt") or c.get("date") or ""),reverse=True)

q.b.family=family_v11
q.fitting_subtype=fitting_subtype_v11
q.recent_generated_comments=recent_generated_comments_v11


def main():q.main()
if __name__=="__main__":main()
