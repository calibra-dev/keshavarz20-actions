#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NEWS=ROOT/"daily-agri-news"

spec=importlib.util.spec_from_file_location("news_v2",NEWS/"publish_queue_v2.py")
v2=importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)
base=v2.base

out=Path(sys.argv[1]); out.parent.mkdir(parents=True,exist_ok=True)
post_id=None; media_id=None
cleanup={"post":False,"media":False}
steps=[]

body=(
    "<p>این نوشته فقط برای آزمون چرخه انتشار پیش‌نویس موتور خبر کشاورز بیست ساخته شده است و هیچ ادعای خبری واقعی ندارد. "
    "هدف، بررسی مسیر فنی ساخت پیش‌نویس، تصویر، متادیتا، دسته‌بندی و خواندن مجدد است.</p>"*10
    +"<h2>جمع‌بندی</h2><p>این یک تست فنی موقت است و پس از readback به زباله‌دان منتقل می‌شود.</p>"
    +"<h2>نظر کارشناسی کشاورز بیست</h2><p>هیچ نتیجه تجاری یا فنی از این تست استخراج نمی‌شود.</p>"
    +'<h2>منابع</h2><p><a href="https://example.org/a">منبع آزمایشی اول</a> و <a href="https://example.edu/b">منبع آزمایشی دوم</a></p>'
)
p={
    "content_type":"news",
    "generated_at":"2026-09-21T07:50:00Z",
    "title":"آزمون موقت چرخه کامل موتور خبر کشاورز بیست — حذف خودکار",
    "slug":"k20-phase18-news-publisher-lifecycle",
    "excerpt":"آزمون موقت فنی برای بررسی چرخه کامل Publisher خبر؛ این پیش‌نویس پس از readback به زباله‌دان منتقل می‌شود.",
    "content_html":body,
    "focus_keyphrase":"آزمون موتور خبر کشاورز بیست",
    "related_keyphrases":["آزمون انتشار خبر","کنترل کیفیت خبر","پیش‌نویس خبر"],
    "seo_title":"آزمون موقت چرخه کامل موتور خبر کشاورز بیست",
    "meta_description":"این صفحه فقط پیش‌نویس موقت برای آزمون فنی چرخه موتور خبر کشاورز بیست است و پس از بررسی readback به زباله‌دان منتقل می‌شود.",
    "tags":["کشاورزی","آبیاری","آموزش"],
    "source_urls":["https://example.org/a","https://example.edu/b"],
    "source_names":["Example Org","Example EDU"],
    "image_search_query":"agriculture farm",
    "image_title":"آزمون موقت موتور خبر",
    "alt_text":"تصویر آزمایشی کشاورزی برای تست موتور خبر",
    "selection_reason":"این payload فقط برای آزمون end-to-end مسیر فنی Publisher است و هیچ انتخاب خبری واقعی یا ادعای انتشار عمومی ندارد.",
    "fact_check_notes":"هیچ ادعای خبری واقعی در این payload وجود ندارد؛ تنها مسیر فنی ساخت و readback بررسی می‌شود."
}

try:
    v2.validate_payload_v2(p); steps.append({"step":"validate_payload","ok":True})
    source=base.commons_search(p["image_search_query"]); steps.append({"step":"commons_search","ok":True})
    image_path=base.make_editorial_image(source); steps.append({"step":"render_webp","ok":image_path.exists()})
    media_id=base.upload_wp_image(None,image_path,p,source); steps.append({"step":"upload_media","ok":True,"media_id":media_id})
    post_id=base.create_draft(None,p,media_id,source); steps.append({"step":"create_draft","ok":True,"post_id":post_id})
    verified=base.verify(None,post_id)
    steps.append({
        "step":"verify",
        "ok":True,
        "status":verified.get("post_status"),
        "type":verified.get("post_type"),
        "target_slug":verified.get("target_slug")==p["slug"],
        "slug_state":verified.get("slug_state"),
        "featured_media":verified.get("post_thumbnail")==media_id,
    })
    if verified.get("target_slug")!=p["slug"]:
        raise RuntimeError("ASCII target slug readback mismatch")
    if verified.get("post_name") not in ("", p["slug"]):
        raise RuntimeError("Draft post_name conflicts with validated target slug")
    if verified.get("post_thumbnail")!=media_id:
        raise RuntimeError("Featured media readback mismatch")

    base.trash_wp_post(post_id)
    pfinal=base.wpvibe_cli_json(f"post get {post_id} --fields=ID,post_status,post_type")
    cleanup["post"]=isinstance(pfinal,dict) and pfinal.get("post_status")=="trash"
    base.trash_wp_post(media_id)
    mfinal=base.wpvibe_cli_json(f"post get {media_id} --fields=ID,post_status,post_type")
    cleanup["media"]=isinstance(mfinal,dict) and mfinal.get("post_status")=="trash"
    steps.append({"step":"cleanup","ok":all(cleanup.values()),"post_trash":cleanup["post"],"media_trash":cleanup["media"]})
    result={"ok":all(cleanup.values()),"temporary_news_id":post_id,"temporary_media_id":media_id,"steps":steps,"cleanup_verified":cleanup}
except Exception as exc:
    if post_id and not cleanup["post"]:
        try:
            base.trash_wp_post(post_id)
            pfinal=base.wpvibe_cli_json(f"post get {post_id} --fields=ID,post_status")
            cleanup["post"]=isinstance(pfinal,dict) and pfinal.get("post_status")=="trash"
        except Exception: pass
    if media_id and not cleanup["media"]:
        try:
            base.trash_wp_post(media_id)
            mfinal=base.wpvibe_cli_json(f"post get {media_id} --fields=ID,post_status")
            cleanup["media"]=isinstance(mfinal,dict) and mfinal.get("post_status")=="trash"
        except Exception: pass
    result={"ok":False,"temporary_news_id":post_id,"temporary_media_id":media_id,"steps":steps,"cleanup_verified":cleanup,"error":f"{type(exc).__name__}: {exc}"}

out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE18_NEWS_PUBLISHER_E2E",json.dumps(result,ensure_ascii=False))
if not result["ok"]: raise SystemExit(2)
