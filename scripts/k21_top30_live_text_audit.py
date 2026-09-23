#!/usr/bin/env python3
from __future__ import annotations
import base64, html, json, os, re
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/"k21-top30-results"/"text-only-remediation-plan-20260923.json"
OUT_JSON=ROOT/"k21-top30-results"/"live-text-readiness-20260923.json"
OUT_MD=ROOT/"k21-top30-results"/"live-text-readiness-20260923.md"

def clean_text(s):
    s=re.sub(r"<script\b[\s\S]*?</script>"," ",s or "",flags=re.I)
    s=re.sub(r"<style\b[\s\S]*?</style>"," ",s,flags=re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    s=html.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def words(s):
    return len([x for x in clean_text(s).split(" ") if x])

def contains(s,*needles):
    t=clean_text(s)
    return all(n in t for n in needles)

def score_product(p, expected):
    desc=p.get("description") or ""
    short=p.get("short_description") or ""
    text=clean_text(desc)
    name=str(p.get("name") or "")
    sku=str(p.get("sku") or "")
    note_marker="k21-text-only-start" in desc and "k21-text-only-end" in desc
    faq_count=len(re.findall(r"<details\b",desc,flags=re.I))
    video_free=not re.search(r"<video\b|ویدئوی راهنما|راهنمای ویدئویی",desc,flags=re.I)

    checks={
      # Identity & specificity: 15
      "name_in_description": {"pts":5, "ok": bool(name and name in text)},
      "sku_in_description": {"pts":5, "ok": bool(sku and sku in text)},
      "product_specific_k21_block": {"pts":5, "ok": note_marker},
      # Depth & summary: 10
      "description_depth": {"pts":5, "ok": words(desc)>=700},
      "short_description": {"pts":5, "ok": words(short)>=35},
      # Decision readiness: 20
      "suitable": {"pts":5, "ok": "این محصول برای چه شرایطی مناسب است؟" in text},
      "unsuitable": {"pts":5, "ok": "چه زمانی انتخاب مناسبی نیست؟" in text},
      "project_inputs": {"pts":5, "ok": "چه اطلاعاتی قبل از سفارش لازم است؟" in text},
      "final_decision": {"pts":5, "ok": "راهنمای تصمیم نهایی" in text},
      # Compatibility and data honesty: 20
      "compatibility": {"pts":5, "ok": "سازگاری و قطعه مقابل" in text},
      "counterpart_logic": {"pts":5, "ok": "قطعه مقابل" in text},
      "unverified_handling": {"pts":5, "ok": "تأییدنشده" in text},
      "identifier_transparency": {"pts":5, "ok": "GTIN / MPN" in text and ("ساخته نشده" in text or "حدس" in text)},
      # Operational guidance: 15
      "installation": {"pts":5, "ok": "نصب و کنترل اولیه" in text},
      "common_errors": {"pts":5, "ok": "خطاهای رایج" in text},
      "post_install_checks": {"pts":5, "ok": "بعد از نصب چه چیزهایی بررسی شود؟" in text},
      # FAQ and commerce: 10
      "faq": {"pts":5, "ok": faq_count>=5},
      "shipping_returns": {"pts":5, "ok": "ارسال، مغایرت و مرجوعی" in text},
      # Evidence transparency: 10
      "data_transparency": {"pts":5, "ok": "شفافیت داده و منبع مشخصات" in text},
      "no_fabrication_language": {"pts":5, "ok": ("حدس" in text and ("تأیید" in text or "معتبر" in text))},
    }
    score=sum(v["pts"] for v in checks.values() if v["ok"])
    return {
      "product_id":int(p["id"]),
      "name":name,
      "sku":sku,
      "score":score,
      "passed_95":score>=95,
      "description_words":words(desc),
      "short_description_words":words(short),
      "faq_count":faq_count,
      "video_free":video_free,
      "k21_text_block_present":note_marker,
      "image_count_observed":len(p.get("images") or []),
      "checks":checks,
      "failed_checks":[k for k,v in checks.items() if not v["ok"]],
    }

def main():
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    ids=[int(x["product_id"]) for x in plan["products"]]
    expected={int(x["product_id"]):x for x in plan["products"]}
    base=os.environ["WP_BASE_URL"].rstrip("/")
    token=base64.b64encode(f"{os.environ['WP_USERNAME']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
    headers={"Authorization":f"Basic {token}","Accept":"application/json"}
    rows=[]
    for pid in ids:
        r=requests.get(f"{base}/wp-json/wc/v3/products/{pid}",headers=headers,timeout=90)
        r.raise_for_status()
        rows.append(score_product(r.json(),expected[pid]))
    rows.sort(key=lambda x: ids.index(x["product_id"]))
    result={
      "ok": all(x["passed_95"] and x["video_free"] for x in rows),
      "program":"K21 Text Readiness v1",
      "scope":"live WooCommerce description + short_description only",
      "products":len(rows),
      "products_95_plus":sum(1 for x in rows if x["passed_95"]),
      "products_below_95":sum(1 for x in rows if not x["passed_95"]),
      "average_score":round(sum(x["score"] for x in rows)/len(rows),1),
      "video_free_products":sum(1 for x in rows if x["video_free"]),
      "media_generation":False,
      "scoring_note":"This is a text-only readiness score. It does not award or require generated images/video, GTIN/MPN, verified reviews, price, stock, or external AI citations.",
      "products_detail":rows,
    }
    OUT_JSON.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# K21 Top30 Live Text Readiness","",f"- محصولات: **{result['products']}**",f"- بالای 95: **{result['products_95_plus']}**",f"- میانگین: **{result['average_score']}**",f"- بدون ویدئو: **{result['video_free_products']}/{result['products']}**","","| # | محصول | امتیاز متن | کلمات توضیح | کلمات کوتاه |","|---:|---|---:|---:|---:|"]
    for i,x in enumerate(rows,1):
        md.append(f"| {i} | {x['name']} | {x['score']}/100 | {x['description_words']} | {x['short_description_words']} |")
    OUT_MD.write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="products_detail"},ensure_ascii=False))
    if not result["ok"]:
        bad=[{"id":x["product_id"],"score":x["score"],"video_free":x["video_free"],"failed":x["failed_checks"]} for x in rows if not x["passed_95"] or not x["video_free"]]
        print(json.dumps({"bad":bad},ensure_ascii=False))
        raise SystemExit(2)

if __name__=="__main__":
    main()
