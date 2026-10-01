#!/usr/bin/env python3
import asyncio, json, os, re
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

TOOLS = [
    {"key":"drip_tape_calculator","url":"https://keshavarz20.com/drip-tape-length-fittings-calculator/","kind":"interactive"},
    {"key":"pipe_size_selector","url":"https://keshavarz20.com/irrigation-pipe-size-selector/","kind":"selector"},
    {"key":"fittings_compatibility","url":"https://keshavarz20.com/irrigation-fittings-compatibility-selector/","kind":"selector"},
    {"key":"filter_selector","url":"https://keshavarz20.com/irrigation-filter-selector/","kind":"selector"},
    {"key":"layflat_calculator","url":"https://keshavarz20.com/layflat-length-fittings-calculator/","kind":"interactive"},
    {"key":"request_quotation","url":"https://keshavarz20.com/request-quotation/","kind":"quote"},
    {"key":"one_hectare_basket","url":"https://keshavarz20.com/one-hectare-drip-irrigation-basket/","kind":"interactive"},
    {"key":"product_comparator","url":"https://keshavarz20.com/irrigation-product-comparator/","kind":"interactive"},
    {"key":"proforma_request","url":"https://keshavarz20.com/request-proforma/","kind":"quote"},
]

INVALID_RE = re.compile(r"(مثبت|نامعتبر|وارد|الزامی|required|invalid|خطا|بزرگ.?تر از صفر)", re.I)
ACTION_RE = re.compile(r"(محاسبه|انتخاب|بررسی|جست.?وجو|مقایسه|نمایش|calculate|select|check|search|compare)", re.I)

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٬٫", "0123456789,.")

def ascii_digits(s):
    return (s or "").translate(PERSIAN_DIGITS).replace(",", "")

async def block_writes(route):
    method = route.request.method.upper()
    if method not in {"GET","HEAD","OPTIONS"}:
        await route.abort()
    else:
        await route.continue_()

async def get_action_button(page):
    buttons = page.locator("button:visible, input[type=button]:visible")
    n = await buttons.count()
    for i in range(n):
        b = buttons.nth(i)
        txt = (await b.inner_text()).strip()
        val = await b.get_attribute("value") or ""
        if ACTION_RE.search(txt + " " + val):
            return b
    return None

async def boundary_probe(page):
    result = {"tested":0,"cases":[],"pass":True}
    nums = page.locator("input[type=number]:visible")
    count = await nums.count()
    action = await get_action_button(page)
    if not action:
        result["note"] = "no safe visible action button matched"
        return result

    for i in range(count):
        el = nums.nth(i)
        min_raw = await el.get_attribute("min")
        try:
            min_v = float(min_raw) if min_raw not in (None,"") else None
        except Exception:
            min_v = None
        if min_v is None or min_v <= 0:
            continue
        original = await el.input_value()
        ident = await el.get_attribute("id") or await el.get_attribute("name") or f"number[{i}]"
        for label, value in (("zero","0"),("negative","-1"),("blank","")):
            await el.fill(value)
            native_valid = await el.evaluate("(e)=>e.checkValidity()")
            before = (await page.locator("body").inner_text())[-3000:]
            try:
                await action.click(timeout=3000)
                await page.wait_for_timeout(250)
            except Exception:
                pass
            after = (await page.locator("body").inner_text())[-5000:]
            custom_error = bool(INVALID_RE.search(after)) and (after != before or not native_valid)
            ok = (not native_valid) or custom_error
            result["cases"].append({
                "input": ident, "case": label, "native_valid": native_valid,
                "custom_error_signal": custom_error, "pass": ok
            })
            result["tested"] += 1
            result["pass"] = result["pass"] and ok
        await el.fill(original)
    return result

async def test_basket(page):
    ids = {
        "k20-area":"10000",
        "k20-row-length":"100",
        "k20-row-spacing":"1",
        "k20-roll-length":"1000",
        "k20-waste":"5",
        "k20-spare":"5",
    }
    missing = []
    for ident,val in ids.items():
        loc = page.locator(f"#{ident}")
        if await loc.count() == 0:
            missing.append(ident)
        else:
            await loc.fill(val)
    if missing:
        return {"pass":False,"missing":missing}
    await page.locator("#k20-calc").click()
    await page.wait_for_timeout(300)
    out = await page.locator("#k20-result").inner_text()
    norm = ascii_digits(out)
    formula_ok = ("10500" in norm and re.search(r"(^|\D)11(\D|$)", norm) is not None)
    await page.locator("#k20-area").fill("0")
    await page.locator("#k20-calc").click()
    await page.wait_for_timeout(150)
    invalid_txt = await page.locator("#k20-result").inner_text()
    invalid_ok = bool(INVALID_RE.search(invalid_txt))
    return {"pass": bool(formula_ok and invalid_ok), "formula_output": out[:1800], "formula_pass": bool(formula_ok), "zero_rejected": bool(invalid_ok)}

async def test_comparator(page):
    search = page.locator("#k20-search")
    btn = page.locator("#k20-search-btn")
    if await search.count() == 0 or await btn.count() == 0:
        return {"pass":False,"reason":"search controls missing"}
    await search.fill("نوار تیپ")
    await btn.click()
    try:
        await page.wait_for_selector("#k20-search-results button[data-id]", timeout=10000)
    except Exception:
        txt = await page.locator("#k20-search-results").inner_text()
        return {"pass":False,"reason":"no product results","result_text":txt[:800]}
    rows = page.locator("#k20-search-results button[data-id]")
    n = await rows.count()
    if n < 2:
        return {"pass":False,"reason":"fewer than two product results","result_count":n}
    await rows.nth(0).click()
    await rows.nth(1).click()
    await page.wait_for_timeout(250)
    compare = await page.locator("#k20-compare").inner_text()
    table_count = await page.locator("#k20-compare table").count()
    return {"pass": bool(table_count > 0 and len(compare.strip()) > 20), "result_count":n, "table_count":table_count, "compare_text":compare[:1800]}

async def main():
    out = {
        "program":"SEO God2","phase":14,
        "title":"Browser acceptance for calculators/selectors/BOM/proforma",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "mode":"public-read-only-browser-qa",
        "network_guard":"all non-GET/HEAD/OPTIONS requests aborted",
        "tools":[]
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width":390,"height":844}, locale="fa-IR")
        await context.route("**/*", block_writes)
        for t in TOOLS:
            page = await context.new_page()
            page_errors = []
            page.on("pageerror", lambda exc, bucket=page_errors: bucket.append(str(exc)))
            row = dict(t)
            try:
                resp = await page.goto(t["url"], wait_until="domcontentloaded", timeout=90000)
                await page.wait_for_timeout(1000)
                row["http"] = resp.status if resp else 0
                row["h1_count"] = await page.locator("h1").count()
                row["controls"] = await page.locator("input:visible, select:visible, textarea:visible").count()
                row["actions"] = await page.locator("button:visible, input[type=button]:visible, input[type=submit]:visible").count()
                overflow = await page.evaluate("()=>document.documentElement.scrollWidth-document.documentElement.clientWidth")
                row["horizontal_overflow_px"] = int(overflow)
                row["page_errors"] = page_errors[:10]
                row["smoke_pass"] = bool(row["http"] == 200 and row["h1_count"] >= 1 and row["controls"] >= 1 and row["actions"] >= 1 and overflow <= 4)

                if t["kind"] in {"interactive","selector"}:
                    row["boundary"] = await boundary_probe(page)
                if t["key"] == "one_hectare_basket":
                    row["business_logic"] = await test_basket(page)
                if t["key"] == "product_comparator":
                    row["business_logic"] = await test_comparator(page)

                blocker = not row["smoke_pass"]
                if "boundary" in row and row["boundary"]["tested"] > 0 and not row["boundary"]["pass"]:
                    blocker = True
                if "business_logic" in row and not row["business_logic"]["pass"]:
                    blocker = True
                row["pass"] = not blocker
            except Exception as e:
                row["pass"] = False
                row["error"] = f"{type(e).__name__}: {e}"
            finally:
                await page.close()
            out["tools"].append(row)
        await browser.close()

    out["tools_pass"] = sum(1 for x in out["tools"] if x.get("pass"))
    out["tools_fail"] = len(out["tools"]) - out["tools_pass"]
    out["overall_pass"] = out["tools_fail"] == 0
    Path("seo-god2-results").mkdir(exist_ok=True)
    Path("seo-god2-results/phase14-browser-acceptance.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SEO_GOD2_PHASE14_BROWSER", out["overall_pass"], out["tools_pass"], "/", len(out["tools"]))
    for x in out["tools"]:
        if not x.get("pass"):
            print("FAIL", x["key"], x.get("error") or x.get("boundary") or x.get("business_logic") or x.get("smoke_pass"))

if __name__ == "__main__":
    asyncio.run(main())
