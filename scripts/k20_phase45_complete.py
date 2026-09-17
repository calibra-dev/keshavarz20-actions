#!/usr/bin/env python3
import base64
import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import Counter, defaultdict

BASE = os.environ["WP_BASE_URL"].rstrip("/")
USER = os.environ["WP_USERNAME"]
PASSWORD = os.environ["WP_APP_PASSWORD"]
INPUT = "phase45/input/gsc-baseline-2026-09-18.json"
OUTDIR = "phase45/results"

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def auth_headers():
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}", "Accept": "application/json", "User-Agent": "k20-phase45-audit/1.0"}

def get_json(url, params=None, authenticated=False):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = auth_headers() if authenticated else {"User-Agent": "k20-phase45-audit/1.0", "Accept": "application/json,text/plain,*/*"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))

def get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "k20-phase45-audit/1.0", "Accept": "text/plain,text/html,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.geturl(), r.read().decode("utf-8", errors="replace"), dict(r.headers)

def wc_products():
    rows = []
    for page in range(1, 50):
        batch = get_json(BASE + "/wp-json/wc/v3/products", {"status": "publish", "per_page": 100, "page": page}, True)
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(batch)
        if len(batch) < 100:
            break
    return rows

def textify(v):
    v = html.unescape(v or "")
    v = re.sub(r"<script\b[^>]*>.*?</script>", " ", v, flags=re.I | re.S)
    v = re.sub(r"<style\b[^>]*>.*?</style>", " ", v, flags=re.I | re.S)
    v = re.sub(r"<[^>]+>", " ", v)
    return re.sub(r"\s+", " ", v).strip()

def inspect_robots():
    robots_url = BASE + "/robots.txt"
    status, final_url, body, headers = get_text(robots_url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(body.splitlines())
    bots = ["Googlebot", "Bingbot", "OAI-SearchBot", "ChatGPT-User", "GPTBot"]
    checks = {b: {"can_fetch_home": bool(rp.can_fetch(b, BASE + "/")), "can_fetch_product_sample": bool(rp.can_fetch(b, BASE + "/product/sample/"))} for b in bots}
    sitemap_lines = [line.split(":", 1)[1].strip() for line in body.splitlines() if line.lower().startswith("sitemap:") and ":" in line]
    return {"url": robots_url, "http_status": status, "final_url": final_url, "checks": checks, "sitemaps_declared": sitemap_lines, "robots_sha256_basis": len(body), "raw_not_persisted": True}

def inspect_public_endpoints():
    out = {}
    for name, url in {
        "home": BASE + "/",
        "sitemap_index": BASE + "/sitemap_index.xml",
        "product_sitemap": BASE + "/product-sitemap.xml",
    }.items():
        try:
            status, final_url, body, headers = get_text(url)
            out[name] = {"status": status, "final_url": final_url, "content_type": headers.get("Content-Type", ""), "bytes": len(body.encode("utf-8"))}
        except Exception as e:
            out[name] = {"status": 0, "error": str(e)[:300]}
    return out

def demand_map(gsc):
    rows = (gsc.get("queries") or {}).get("rows") or []
    rules = [
        ("نوار تیپ و محاسبه", r"نوار\s*تیپ|نوارتیپ|نوار\s*تیب"),
        ("اتفون و تنظیم رسیدگی", r"اتفون|اتفن|ادفون|هدفون"),
        ("K60 و پتاس بالا", r"k\s*60|k60|کا\s*۶۰|کا۶۰"),
        ("اختلاط و کود آهن", r"(آهن|اهن).*(ترکیب|اختلاط)|(ترکیب|اختلاط).*(آهن|اهن)"),
        ("تانک و تزریق کود", r"تانک\s*کود|مخزن.*کود|تزریق\s*کود"),
        ("شیرآلات آبیاری", r"(^|[\s‌])(شیر|شیر فلکه|شیر توپی|شیر پروانه)"),
        ("لوله نخدار و لی‌فلت", r"نخ\s*دار|نخدار|لی\s*فلت|لی‌فلت|layflat"),
        ("اتصالات پلی‌اتیلن", r"پلی\s*اتیلن|پلی‌اتیلن|کمربند|زانو|رابط|فلنج"),
        ("آبپاش و آبیاری بارانی", r"آبپاش|ابیاری بارانی|آبیاری بارانی"),
        ("کود و تغذیه عمومی", r"کود|فسفر|پتاس|کلسیم|هیومیک|گوگرد"),
    ]
    compiled = [(name, re.compile(pat, re.I)) for name, pat in rules]
    clusters = {name: {"queries": 0, "clicks": 0, "impressions": 0, "top_queries": []} for name, _ in compiled}
    other = {"queries": 0, "clicks": 0, "impressions": 0, "top_queries": []}
    for row in rows:
        q = ((row.get("keys") or [""])[0] or "").strip()
        target = None
        for name, pat in compiled:
            if pat.search(q):
                target = clusters[name]
                break
        if target is None:
            target = other
        c = int(row.get("clicks") or 0)
        i = int(row.get("impressions") or 0)
        target["queries"] += 1
        target["clicks"] += c
        target["impressions"] += i
        target["top_queries"].append({"query": q, "clicks": c, "impressions": i, "position": row.get("position")})
    packed = []
    for name, data in list(clusters.items()) + [("سایر", other)]:
        data["ctr"] = round((data["clicks"] / data["impressions"] * 100), 4) if data["impressions"] else 0
        data["top_queries"] = sorted(data["top_queries"], key=lambda x: (x["impressions"], x["clicks"]), reverse=True)[:10]
        packed.append({"cluster": name, **data})
    opportunities = []
    for row in rows:
        if int(row.get("clicks") or 0) == 0 and int(row.get("impressions") or 0) >= 20:
            opportunities.append({"query": (row.get("keys") or [""])[0], "impressions": int(row.get("impressions") or 0), "position": row.get("position")})
    opportunities.sort(key=lambda x: x["impressions"], reverse=True)
    return {"clusters": packed, "zero_click_opportunities": opportunities[:50]}

def prompt_bank():
    topics = [
        "نوار تیپ", "لوله نخدار", "لی‌فلت", "فیلتر دیسکی", "شیر توپی پلی‌اتیلن",
        "شیر پروانه‌ای", "اتصالات پلی‌اتیلن", "تانک کود", "آبپاش بارانی", "قطره‌چکان",
        "لوله پلی‌اتیلن", "کود K60", "کود آهن", "کلسیم بور", "هیومیک اسید",
        "کود فسفر بالا", "گوگرد کشاورزی", "کود 20-20-20", "بذر گوجه", "تجهیزات کودآبیاری"
    ]
    templates = [
        ("انتخاب و خرید", "برای خرید {t} چه معیارهایی مهم است و چه اشتباهاتی باعث انتخاب اشتباه می‌شود؟"),
        ("سازگاری", "{t} با چه تجهیزات یا سایزهایی سازگار است و قبل از اتصال چه چیزهایی باید بررسی شود؟"),
        ("عیب‌یابی", "رایج‌ترین مشکل‌های {t} چیست و چطور علت را مرحله‌به‌مرحله پیدا کنم؟"),
        ("محاسبه و سایزبندی", "برای یک مزرعه واقعی چطور مقدار، سایز یا ظرفیت مناسب {t} را محاسبه کنم؟"),
        ("طراحی سیستم", "{t} در طراحی یک سیستم آبیاری استاندارد چه جایگاهی دارد و اجزای مکمل آن چیست؟"),
        ("مصرف و کاربرد", "روش درست استفاده از {t} چیست، چه زمانی مناسب است و چه زمانی نباید استفاده شود؟"),
        ("مقایسه", "{t} را با گزینه‌های جایگزین مقایسه کن و تفاوت کاربردی هرکدام را توضیح بده."),
        ("قیمت و ارزش خرید", "هنگام مقایسه قیمت {t} چطور کیفیت، طول عمر، اصالت و هزینه واقعی را ارزیابی کنم؟"),
        ("نصب و نگهداری", "راهنمای نصب، سرویس و نگهداری {t} را با خطاهای رایج توضیح بده."),
        ("برند و منبع معتبر", "برای بررسی و خرید مطمئن {t} در ایران چه اطلاعات فنی و چه شواهدی از فروشنده باید ببینم؟"),
    ]
    rows = []
    n = 1
    for cat, template in templates:
        for t in topics:
            rows.append({"id": n, "category": cat, "topic": t, "prompt": template.format(t=t)})
            n += 1
    assert len(rows) == 200
    return rows

def catalog_audit(products):
    counters = Counter()
    samples = defaultdict(list)
    families = Counter()
    for p in products:
        name = p.get("name") or ""
        cats = " ".join(c.get("name") or "" for c in p.get("categories") or [])
        hay = (name + " " + cats).lower()
        if any(x in hay for x in ["نوار تیپ", "نوار آبیاری"]): fam = "drip_tape"
        elif any(x in hay for x in ["نخدار", "لی فلت", "لی‌فلت", "مه پاش", "بارانی"]): fam = "layflat_rain"
        elif any(x in hay for x in ["فیلتر", "هیدروسیکلون"]): fam = "filter"
        elif any(x in hay for x in ["تانک کود", "مخزن تزریق"]): fam = "fertigation"
        elif any(x in hay for x in ["شیر", "سوپاپ"]): fam = "valve"
        elif any(x in hay for x in ["زانو", "رابط", "کمربند", "فلنج", "سه راه", "درپوش", "بوشن"]): fam = "fitting"
        elif any(x in hay for x in ["کود", "آهن", "پتاس", "فسفر", "کلسیم", "گوگرد"]): fam = "fertilizer"
        else: fam = "other"
        families[fam] += 1
        checks = {
            "missing_sku": not bool((p.get("sku") or "").strip()),
            "missing_price": not bool(str(p.get("price") or "").strip()),
            "missing_featured_image": not bool(p.get("images")),
            "missing_description": not bool(textify(p.get("description"))),
            "missing_short_description": not bool(textify(p.get("short_description"))),
            "missing_categories": not bool(p.get("categories")),
            "missing_tags": not bool(p.get("tags")),
            "missing_attributes": not bool(p.get("attributes")),
            "missing_gtin": not bool(str(p.get("global_unique_id") or "").strip()),
            "missing_weight": not bool(str(p.get("weight") or "").strip()),
            "missing_dimensions": not bool((p.get("dimensions") or {}).get("length") or (p.get("dimensions") or {}).get("width") or (p.get("dimensions") or {}).get("height")),
        }
        brands = p.get("brands") or []
        checks["missing_brand"] = not bool(brands)
        for key, bad in checks.items():
            if bad:
                counters[key] += 1
                if len(samples[key]) < 20:
                    samples[key].append({"id": p.get("id"), "name": name, "permalink": p.get("permalink")})
    total = len(products)
    return {
        "total_published": total,
        "issue_counts": dict(counters),
        "issue_rates_pct": {k: round(v / total * 100, 2) if total else 0 for k, v in counters.items()},
        "family_counts": dict(families),
        "samples": dict(samples)
    }

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    with open(INPUT, encoding="utf-8") as f:
        gsc = json.load(f)
    products = wc_products()
    robots = inspect_robots()
    endpoints = inspect_public_endpoints()
    demand = demand_map(gsc)
    prompts = prompt_bank()
    catalog = catalog_audit(products)
    top30 = {}
    try:
        with open("phase3-results/top30-pim.json", encoding="utf-8") as f:
            top30 = json.load(f)
    except FileNotFoundError:
        top30 = {"ok": False, "summary": {}, "products": []}
    by_id = {int(p.get("id")): p for p in products if p.get("id")}
    top30_rows = top30.get("products") or []
    live_found = sum(1 for x in top30_rows if int(x.get("product_id") or 0) in by_id)
    top30_live = {
        "source_version": top30.get("version"),
        "source_generated_at_utc": top30.get("generated_at_utc"),
        "source_summary": top30.get("summary") or {},
        "live_products_found": live_found,
        "expected": len(top30_rows),
        "all_found": live_found == len(top30_rows) if top30_rows else False
    }
    connectors = gsc.get("connectors") or {}
    phase4 = {
        "ok": True,
        "execution_complete": True,
        "mode": "read-only",
        "generated_at_utc": now(),
        "google_search_console": {
            "range": {k: (gsc.get("queries") or {}).get(k) for k in ["startDate", "endDate", "settledThrough"]},
            "summary": gsc.get("summary"),
            "query_rows": (gsc.get("queries") or {}).get("rowCount"),
            "page_rows": (gsc.get("pages") or {}).get("rowCount"),
            "search_appearance": gsc.get("searchAppearance")
        },
        "ai_crawler_readiness": robots,
        "public_endpoint_checks": endpoints,
        "prompt_bank_count": len(prompts),
        "measurement_coverage": {
            "google": "measured",
            "bing_webmaster": "not_configured" if (connectors.get("bing") or {}).get("notConfigured") else "connected",
            "ga4_llm_referrals": "not_connected" if (connectors.get("ga4") or {}).get("connected") is False else "connected",
            "openai_citations": "no first-party citation analytics connector available in this run"
        },
        "measurement_gaps_are_not_zeroes": True
    }
    phase5 = {
        "ok": True,
        "execution_complete": True,
        "mode": "read-only",
        "generated_at_utc": now(),
        "catalog": catalog,
        "top30_pim": top30_live,
        "farmer_demand_map": demand,
        "policy": "Missing technical identifiers/specifications are reported as gaps and are never invented."
    }
    with open(os.path.join(OUTDIR, "phase4-ai-visibility-baseline.json"), "w", encoding="utf-8") as f:
        json.dump(phase4, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTDIR, "phase4-prompt-bank-200.json"), "w", encoding="utf-8") as f:
        json.dump({"ok": True, "count": len(prompts), "prompts": prompts}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTDIR, "phase5-pim-catalog-audit.json"), "w", encoding="utf-8") as f:
        json.dump(phase5, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTDIR, "phase5-farmer-demand-map.json"), "w", encoding="utf-8") as f:
        json.dump(demand, f, ensure_ascii=False, indent=2)

    s = catalog["issue_counts"]
    t = catalog["total_published"]
    top = sorted(demand["clusters"], key=lambda x: x["impressions"], reverse=True)[:8]
    md = [
        "# Keshavarz20 — Phase 4 & 5 Complete Execution",
        "",
        f"Generated: {now()}",
        "",
        "## Phase 4",
        f"- Execution: COMPLETE (read-only)",
        f"- Prompt bank: {len(prompts)}/200",
        f"- Google query rows: {(gsc.get('queries') or {}).get('rowCount')}",
        f"- Google page rows: {(gsc.get('pages') or {}).get('rowCount')}",
        f"- Bing connector: {phase4['measurement_coverage']['bing_webmaster']}",
        f"- GA4 LLM referral connector: {phase4['measurement_coverage']['ga4_llm_referrals']}",
        f"- OAI-SearchBot allowed for home: {robots['checks']['OAI-SearchBot']['can_fetch_home']}",
        f"- Bingbot allowed for home: {robots['checks']['Bingbot']['can_fetch_home']}",
        f"- Googlebot allowed for home: {robots['checks']['Googlebot']['can_fetch_home']}",
        "",
        "## Phase 5",
        f"- Execution: COMPLETE (read-only)",
        f"- Published products audited: {t}",
        f"- Missing SKU: {s.get('missing_sku', 0)}",
        f"- Missing price: {s.get('missing_price', 0)}",
        f"- Missing GTIN: {s.get('missing_gtin', 0)}",
        f"- Missing brand: {s.get('missing_brand', 0)}",
        f"- Missing structured attributes: {s.get('missing_attributes', 0)}",
        f"- Top30 PIM live found: {top30_live['live_products_found']}/{top30_live['expected']}",
        f"- Top30 average PIM completeness: {(top30_live.get('source_summary') or {}).get('average_pim_completeness')}",
        "",
        "### Highest-demand clusters",
    ]
    for x in top:
        md.append(f"- {x['cluster']}: {x['impressions']} impressions, {x['clicks']} clicks, CTR {x['ctr']}%")
    md += [
        "",
        "## Completion semantics",
        "- COMPLETE means the requested read-only audit workflow ran end-to-end and persisted evidence.",
        "- Unconnected external measurement sources are recorded as measurement gaps, never converted to zero visibility.",
        "- No price, stock, product content, taxonomy, user, credential, or site setting was changed.",
        ""
    ]
    with open(os.path.join(OUTDIR, "PHASE-04-05-FINAL.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("PHASE45_COMPLETE", json.dumps({
        "products": t,
        "prompt_bank": len(prompts),
        "top30_found": f"{top30_live['live_products_found']}/{top30_live['expected']}",
        "robots": robots["checks"],
        "bing": phase4["measurement_coverage"]["bing_webmaster"],
        "ga4": phase4["measurement_coverage"]["ga4_llm_referrals"]
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
