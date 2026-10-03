#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"daily-agri-articles"

spec=importlib.util.spec_from_file_location("article_v6",ART/"publish_queue_v6.py")
v6=importlib.util.module_from_spec(spec); spec.loader.exec_module(v6)
base=v6.base

out=Path(sys.argv[1]); out.parent.mkdir(parents=True,exist_ok=True)
post_id=None; media_id=None
cleanup={"post":False,"media":False}
steps=[]

def rest(method, route, **kwargs):
    kwargs.setdefault("auth",(base.WP_USER,base.WP_PASS))
    kwargs.setdefault("timeout",70)
    r=base.SESSION.request(method,f"{base.WP_BASE}/wp-json{route}",**kwargs)
    return r

def existing_category():
    r=rest("GET","/wp/v2/categories",params={"per_page":20,"hide_empty":False,"orderby":"count","order":"desc"})
    r.raise_for_status()
    rows=r.json()
    if not rows: raise RuntimeError("No existing WordPress category available for E2E")
    row=rows[0]
    return int(row["id"]),str(row["name"])

def existing_tags():
    r=rest("GET","/wp/v2/tags",params={"per_page":20,"hide_empty":False,"orderby":"count","order":"desc"})
    r.raise_for_status()
    names=[str(x.get("name") or "").strip() for x in r.json() if str(x.get("name") or "").strip()]
    if len(names)<4: raise RuntimeError("Need four existing WordPress tags for non-mutating E2E taxonomy test")
    return names[:4]

def delete_post(pid):
    r=rest("DELETE",f"/wp/v2/posts/{pid}",params={"force":"true"})
    if r.status_code not in (200,410):
        return False
    chk=rest("GET",f"/wp/v2/posts/{pid}",params={"context":"edit"})
    return chk.status_code in (404,410)

def delete_media(mid):
    r=rest("DELETE",f"/wp/v2/media/{mid}",params={"force":"true"})
    if r.status_code not in (200,410):
        return False
    chk=rest("GET",f"/wp/v2/media/{mid}",params={"context":"edit"})
    return chk.status_code in (404,410)

stamp=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
category_id,category_name=existing_category()
tags=existing_tags()

filler=(
 "این پاراگراف فقط برای آزمون فنی موقت موتور مقاله کشاورز بیست ساخته شده است. "
 "هیچ ادعای زراعی، تجاری، محصولی، قیمتی، موجودی، نتیجه میدانی یا توصیه مصرفی در آن وجود ندارد. "
 "هدف فقط عبور کنترل‌شده از اعتبارسنجی، ساخت پیش‌نویس، خواندن مجدد و حذف کامل همان داده آزمایشی است. "
)
body="<p>"+filler+"</p>"*1
body="".join(f"<p>{filler}</p>" for _ in range(38))
body+=(
 '<h2>تصمیم و محدودیت</h2><p>این متن فقط transport test است و برای استفاده عمومی یا تصمیم کشاورزی نوشته نشده است. '
 '<a href="https://keshavarz20.com/irrigation-pipe-size-selector/">انتخابگر سایز لوله کشاورز بیست</a> و '
 '<a href="https://keshavarz20.com/editorial-policy/">سیاست تحریریه کشاورز بیست</a> فقط برای کنترل لینک داخلی در payload آمده‌اند.</p>'
 '<h2>جمع‌بندی</h2><p>این پیش‌نویس موقت باید بعد از readback حذف شود و نباید منتشر شود.</p>'
 '<h2>نظر کارشناسی کشاورز بیست</h2><p>هیچ نظر کارشناسی واقعی یا نتیجه فنی از این تست استخراج نمی‌شود.</p>'
 '<h2>منابع</h2><ul>'
 '<li><a href="https://www.fao.org/">FAO</a></li>'
 '<li><a href="https://www.nrcs.usda.gov/">USDA NRCS</a></li>'
 '<li><a href="https://extension.umn.edu/">University of Minnesota Extension</a></li>'
 '</ul>'
 '<h2>روش تهیه و بازبینی</h2><p>این payload صرفاً برای E2E فنی Phase 18 ایجاد شده، draft-only است و پس از readback حذف می‌شود. '
 'هیچ انسان، تجربه میدانی، نتیجه پروژه یا منبع ساختگی به آن نسبت داده نشده است. '
 '<a href="https://keshavarz20.com/editorial-policy/">سیاست تحریریه</a>.</p>'
)

p={
 "content_type":"post",
 "generated_at":datetime.now(timezone.utc).isoformat(),
 "title":f"آزمون موقت Phase 18 موتور مقاله کشاورز بیست {stamp}",
 "slug":f"k20-phase18-article-e2e-{stamp}",
 "excerpt":"پیش‌نویس موقت و غیرقابل انتشار برای آزمون فنی Phase 18؛ این مورد پس از readback حذف می‌شود.",
 "content_html":body,
 "focus_keyphrase":"آزمون فنی موتور مقاله",
 "related_keyphrases":["کنترل مسیر مقاله","آزمون پیش‌نویس وردپرس","اعتبارسنجی فنی مقاله"],
 "seo_title":"آزمون موقت فنی موتور مقاله کشاورز بیست",
 "meta_description":"این پیش‌نویس صرفاً برای آزمون فنی کنترل‌شده موتور مقاله کشاورز بیست ایجاد می‌شود، منتشر نمی‌شود و پس از خواندن مجدد به‌طور کامل حذف خواهد شد.",
 "category_name":category_name,
 "category_id":category_id,
 "tags":tags,
 "source_urls":["https://www.fao.org/","https://www.nrcs.usda.gov/","https://extension.umn.edu/"],
 "source_names":["FAO","USDA NRCS","University of Minnesota Extension"],
 "research_summary":"این payload موضوع واقعی نیست و فقط برای آزمون deterministic مسیر اعتبارسنجی، WordPress REST draft، featured media، Yoast readback و cleanup کامل Phase 18 ساخته شده است.",
 "editorial_disclosure":"این خروجی صرفاً آزمون فنی خودکار است، draft-only باقی می‌ماند، هیچ نویسنده یا بازبین انسانی ساختگی ندارد و بلافاصله بعد از readback حذف می‌شود.",
 "review_status":"human_review_required_before_publish",
 "image_search_query":"irrigation agriculture field landscape",
 "image_title":"آزمون موقت موتور مقاله",
 "cover_title":"آزمون فنی موتور مقاله",
 "cover_subtitle":"پیش‌نویس موقت و حذف خودکار",
 "alt_text":"تصویر کشاورزی با مجوز باز برای آزمون فنی موقت موتور مقاله",
 "faq_items":[],
 "phase20_schema_version":"1",
 "canonical_intent_id":"ir-intent-phase18-e2e-technical-transport-test",
 "parent_hub":"راهنمای آبیاری و تجهیزات",
 "scenario_dimensions":{
   "crop":"",
   "province_or_climate":"",
   "season":"",
   "area":"",
   "water":"",
   "soil":"",
   "irrigation_system":"",
   "problem":"آزمون موقت فنی مسیر انتشار پیش‌نویس",
   "decision":"اعتبارسنجی کنترل‌شده publisher بدون انتشار عمومی"
 },
 "source_strength":"FIRST_PARTY_TECHNICAL_E2E",
 "question_engine_intents_covered":["آیا مسیر فنی پیش‌نویس مقاله سالم است؟"],
 "compatibility_rules_referenced":["draft_only","readback_required","cleanup_required"],
 "membership_cta_type":"none",
 "update_triggers":["تغییر نسخه publisher یا قرارداد Phase 20"],
 "topic_score":{
   "farmer_decision_value":20,
   "independent_intent":15,
   "evidence_strength":15,
   "demand_signal":15,
   "seasonal_relevance":10,
   "business_relevance":10,
   "original_value_potential":10,
   "cannibalization_safety":5,
   "total":100,
   "blockers":[]
 }
}

try:
    base.validate_payload(p); steps.append({"step":"validate_payload_v6_chain","ok":True})
    base.ensure_not_duplicate(p); steps.append({"step":"duplicate_guard","ok":True})
    cid,cname=base.resolve_category(p)
    if cid!=category_id: raise RuntimeError("Category readback mismatch")
    steps.append({"step":"existing_category","ok":True,"category_id":cid})

    source=base.commons_search(p["image_search_query"]); steps.append({"step":"commons_search","ok":True,"license":source.get("license")})
    image_path=base.make_editorial_cover(source,p)
    manifest=json.loads((base.OUT/"cover-render-manifest.json").read_text(encoding="utf-8"))
    visual_ok=(
        image_path.exists()
        and manifest.get("qa_passed") is True
        and manifest.get("ai_text_rendering") is False
        and manifest.get("fail_closed_on_missing_persian_stack") is True
        and manifest.get("fail_closed_on_copy_overflow") is True
    )
    steps.append({"step":"render_v6_cover","ok":visual_ok,"renderer":manifest.get("renderer")})
    if not visual_ok: raise RuntimeError("Article v6 visual gate did not pass")

    media_id=base.upload_wp_image(None,image_path,p,source); steps.append({"step":"upload_media_rest","ok":True,"media_id":media_id})
    post_id=base.create_draft(None,p,media_id,cid,cname,source); steps.append({"step":"create_draft_rest","ok":True,"post_id":post_id})
    verified=base.verify(None,post_id,cid)
    verify_ok=verified.get("post_status")=="draft" and verified.get("post_type")=="post" and int(verified.get("post_thumbnail") or 0)==media_id
    steps.append({"step":"verify_readback","ok":verify_ok,"status":verified.get("post_status"),"type":verified.get("post_type"),"featured_media":verify_ok})
    if not verify_ok: raise RuntimeError("Article draft readback mismatch")

    cleanup["post"]=delete_post(post_id)
    cleanup["media"]=delete_media(media_id)
    steps.append({"step":"cleanup","ok":all(cleanup.values()),"post_deleted":cleanup["post"],"media_deleted":cleanup["media"]})
    result={
      "ok":all(cleanup.values()),
      "temporary_post_id":post_id,
      "temporary_media_id":media_id,
      "publisher_version":"v6",
      "transport":"wordpress_rest",
      "steps":steps,
      "cleanup_verified":cleanup,
      "published":False,
      "commerce_mutations":0
    }
except Exception as exc:
    if post_id and not cleanup["post"]:
        try: cleanup["post"]=delete_post(post_id)
        except Exception: pass
    if media_id and not cleanup["media"]:
        try: cleanup["media"]=delete_media(media_id)
        except Exception: pass
    result={
      "ok":False,"temporary_post_id":post_id,"temporary_media_id":media_id,
      "publisher_version":"v5","transport":"wordpress_rest","steps":steps,
      "cleanup_verified":cleanup,"published":False,"commerce_mutations":0,
      "error":f"{type(exc).__name__}: {exc}"
    }

out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE18_ARTICLE_PUBLISHER_E2E",json.dumps(result,ensure_ascii=False))
if not result["ok"]: raise SystemExit(2)
