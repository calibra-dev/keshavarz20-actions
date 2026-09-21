#!/usr/bin/env python3
import json, os, sys, time, shutil
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urljoin
import requests
from playwright.sync_api import sync_playwright

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
REQ=sys.argv[1]
OUT=sys.argv[2]
S=requests.Session(); S.auth=AUTH
S.headers.update({"Accept":"application/json","User-Agent":"k20-checkout-gateway-e2e/1.0","Cache-Control":"no-cache"})

def wc(method,path,params=None,body=None):
    r=S.request(method,urljoin(BASE+"/",path.lstrip("/")),params=params,json=body,timeout=120)
    data=None
    try:data=r.json()
    except Exception:pass
    if not r.ok:
        raise RuntimeError(f"{method} {path} HTTP {r.status_code}: {str(data)[:500]}")
    return data

def fill_any(page, selectors, value):
    for sel in selectors:
        loc=page.locator(sel)
        if loc.count():
            try:
                loc.first.fill(value, timeout=3000)
                return sel
            except Exception:
                pass
    return None

def select_text_any(page, selectors, text):
    for sel in selectors:
        loc=page.locator(sel)
        if loc.count():
            try:
                opts=loc.first.locator("option").all()
                for o in opts:
                    label=(o.inner_text() or "").strip()
                    if text in label:
                        val=o.get_attribute("value")
                        loc.first.select_option(val, timeout=5000)
                        return {"selector":sel,"value":val,"label":label}
            except Exception:
                pass
    return None

def text_any(page, selectors):
    out=[]
    for sel in selectors:
        loc=page.locator(sel)
        if loc.count():
            try:
                txt=loc.first.inner_text(timeout=3000).strip()
                if txt: out.append(txt)
            except Exception:
                pass
    return "\n".join(out)

with open(REQ,"r",encoding="utf-8-sig") as f:
    cfg=json.load(f)

stamp=datetime.now(timezone.utc)
email=f"k20-checkout-test-{int(time.time())}@example.com"
result={
  "ok":False,
  "started_at_utc":stamp.isoformat(),
  "test_identity":"synthetic_noncustomer",
  "real_payment_attempted":False,
  "card_data_entered":False,
  "external_payment_page_loaded":False,
  "test_order_cleanup":{"found":False,"deleted":False,"verified_404":False},
}

order_ids=[]
browser=None
try:
    # Read enabled gateways without persisting sensitive settings.
    gateways=wc("GET","wp-json/wc/v3/payment_gateways")
    enabled=[{"id":g.get("id"),"title":g.get("title"),"enabled":g.get("enabled")} for g in gateways if g.get("enabled")]
    result["enabled_gateways"]=enabled
    external=[g for g in enabled if "bitpay" in str(g.get("id","")).lower()]
    if not external:
        raise RuntimeError(f"No enabled BitPay external gateway found; enabled={enabled}")
    gateway=external[0]
    result["selected_gateway"]=gateway

    # Choose a cheap, public, in-stock, physical, simple product.
    products=wc("GET","wp-json/wc/v3/products",params={"status":"publish","stock_status":"instock","per_page":100,"orderby":"date","order":"desc"})
    candidates=[]
    for p in products:
        try: price=float(p.get("price") or 0)
        except Exception: price=0
        if p.get("type")=="simple" and price>0 and not p.get("virtual",False) and p.get("purchasable",True):
            candidates.append((price,p))
    if not candidates:
        raise RuntimeError("No in-stock purchasable physical simple product found")
    candidates.sort(key=lambda x:x[0])
    product=candidates[0][1]
    result["product"]={"id":product.get("id"),"name":product.get("name"),"sku":product.get("sku"),"price_present":bool(product.get("price"))}

    chrome=shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        raise RuntimeError("No system Chromium/Chrome binary found on runner")

    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=chrome,args=["--no-sandbox","--disable-dev-shm-usage"])
        context=browser.new_context(locale="fa-IR",timezone_id="Asia/Tehran")
        page=context.new_page()
        external_redirect={"url":None}
        capture=False

        def route_handler(route, request):
            nonlocal_capture = capture
            try:
                host=urlparse(request.url).hostname or ""
                site_host=urlparse(BASE).hostname or ""
                if nonlocal_capture and request.is_navigation_request() and host and host != site_host:
                    external_redirect["url"]=request.url
                    route.abort()
                    return
            except Exception:
                pass
            route.continue_()

        context.route("**/*", route_handler)

        add_url=f"{BASE}/?add-to-cart={product['id']}&quantity=1"
        page.goto(add_url,wait_until="domcontentloaded",timeout=90000)
        page.goto(f"{BASE}/checkout/",wait_until="domcontentloaded",timeout=90000)
        page.wait_for_timeout(4000)
        result["checkout_url"]=page.url
        result["checkout_http_reached"]=("/checkout" in page.url)

        # Classic + Blocks-compatible selector set.
        fill_any(page,["#billing_first_name","input[name='billing_first_name']","input[name='billing-first_name']"],"تست")
        fill_any(page,["#billing_last_name","input[name='billing_last_name']","input[name='billing-last_name']"],"کشاورز بیست")
        fill_any(page,["#billing_address_1","input[name='billing_address_1']","input[name='billing-address_1']"],"آدرس تست سیستمی - سفارش واقعی نیست")
        fill_any(page,["#billing_city","input[name='billing_city']","input[name='billing-city']"],"تهران")
        fill_any(page,["#billing_postcode","input[name='billing_postcode']","input[name='billing-postcode']"],"1111111111")
        fill_any(page,["#billing_phone","input[name='billing_phone']","input[name='billing-phone']"],"09120000000")
        fill_any(page,["#billing_email","input[name='billing_email']","input[name='email']"],email)

        # Country/state.
        country=select_text_any(page,["#billing_country","select[name='billing_country']","select[name='billing-country']"],"ایران")
        state=select_text_any(page,["#billing_state","select[name='billing_state']","select[name='billing-state']"],"تهران")
        result["address_selection"]={"country":country,"state":state,"city":"تهران","synthetic":True}

        # Trigger checkout updates.
        try: page.locator("body").click(position={"x":20,"y":20})
        except Exception: pass
        page.wait_for_timeout(5000)

        shipping=text_any(page,[
          ".woocommerce-shipping-methods",
          "#shipping_method",
          ".woocommerce-checkout-review-order-table",
          ".wc-block-components-totals-shipping",
          ".wc-block-components-shipping-rates-control"
        ])
        result["shipping_text"]=shipping[:1800]
        result["shipping_countrywide_visible"]=("باربری" in shipping or "تیپاکس" in shipping)
        result["local_pickup_visible"]=("تحویل محلی" in shipping)
        result["free_shipping_visible"]=("حمل و نقل رایگان" in shipping)
        if not result["shipping_countrywide_visible"]:
            raise RuntimeError(f"Countrywide shipping method not visible in checkout. Shipping text={shipping[:1000]}")
        if result["local_pickup_visible"]:
            raise RuntimeError("Local pickup is still visible in checkout")

        # Pick BitPay radio by value/id/title signal.
        radios=page.locator("input[type='radio']")
        radio_info=[]
        chosen=None
        for i in range(radios.count()):
            rr=radios.nth(i)
            try:
                val=rr.get_attribute("value") or ""
                rid=rr.get_attribute("id") or ""
                name=rr.get_attribute("name") or ""
                radio_info.append({"value":val,"id":rid,"name":name})
                blob=(val+" "+rid+" "+name).lower()
                if "bitpay" in blob and chosen is None:
                    chosen=rr
            except Exception: pass
        result["payment_radio_signals"]=radio_info[:30]
        if chosen is None:
            # Fallback via label text.
            labels=page.locator("label")
            for i in range(labels.count()):
                lab=labels.nth(i)
                try:
                    txt=(lab.inner_text() or "").strip()
                    if "بیت" in txt or "bitpay" in txt.lower():
                        target=lab.get_attribute("for")
                        if target and page.locator(f"#{target}").count():
                            chosen=page.locator(f"#{target}")
                            break
                except Exception: pass
        if chosen is None:
            raise RuntimeError("Enabled BitPay gateway is not selectable on checkout UI")
        chosen.check(force=True)
        page.wait_for_timeout(1500)
        result["payment_gateway_selectable"]=True

        place=None
        for sel in ["#place_order","button[name='woocommerce_checkout_place_order']",".wc-block-components-checkout-place-order-button"]:
            loc=page.locator(sel)
            if loc.count():
                place=loc.first
                break
        if place is None:
            raise RuntimeError("Place order button not found")
        result["place_order_button_reached"]=True

        capture=True
        try:
            place.click(timeout=10000)
        except Exception:
            # navigation may be aborted intentionally; continue to observe state
            pass

        # Give checkout + gateway processing enough time to create a redirect/order.
        for _ in range(24):
            page.wait_for_timeout(1000)
            if external_redirect["url"]:
                break
            err=text_any(page,[".woocommerce-error",".wc-block-components-notice-banner.is-error",".wc-block-components-notices__snackbar"])
            if err:
                result["checkout_error"]=err[:2000]
                break

        if external_redirect["url"]:
            u=urlparse(external_redirect["url"])
            result["payment_redirect_captured"]=True
            result["payment_redirect_host"]=u.hostname
            result["payment_redirect_path"]=u.path
            result["external_payment_page_loaded"]=False
        else:
            result["payment_redirect_captured"]=False
            result["current_url_after_place_order"]=page.url

        browser.close(); browser=None

    # Find and cleanup exact synthetic order(s).
    after=(stamp-timedelta(minutes=2)).isoformat().replace("+00:00","Z")
    orders=wc("GET","wp-json/wc/v3/orders",params={"after":after,"per_page":50,"orderby":"date","order":"desc","status":"any"})
    matches=[]
    for o in orders:
        billing=o.get("billing") or {}
        if str(billing.get("email") or "").lower()==email.lower():
            matches.append(o)
    result["test_order_cleanup"]["found"]=bool(matches)
    result["created_order_count"]=len(matches)
    if matches:
        order_ids=[int(o["id"]) for o in matches]
        result["test_order_statuses_before_cleanup"]=[{"id":o.get("id"),"status":o.get("status"),"payment_method":o.get("payment_method"),"shipping_lines":[{"method_id":x.get("method_id"),"method_title":x.get("method_title"),"total":x.get("total")} for x in (o.get("shipping_lines") or [])]} for o in matches]
        all_deleted=True; all_404=True
        for oid in order_ids:
            wc("DELETE",f"wp-json/wc/v3/orders/{oid}",params={"force":"true"})
            try:
                wc("GET",f"wp-json/wc/v3/orders/{oid}")
                all_404=False
            except RuntimeError as e:
                if "HTTP 404" not in str(e):
                    all_404=False
        result["test_order_cleanup"]["deleted"]=all_deleted
        result["test_order_cleanup"]["verified_404"]=all_404

    result["ok"]=bool(
      result.get("shipping_countrywide_visible") and
      not result.get("local_pickup_visible") and
      result.get("payment_gateway_selectable") and
      result.get("place_order_button_reached") and
      result.get("payment_redirect_captured") and
      result["test_order_cleanup"].get("found") and
      result["test_order_cleanup"].get("deleted") and
      result["test_order_cleanup"].get("verified_404")
    )
except Exception as e:
    result["error"]=str(e)[:4000]
finally:
    try:
        if browser: browser.close()
    except Exception: pass
    # Failsafe cleanup if an exception occurred after order creation but before normal cleanup.
    try:
        after=(stamp-timedelta(minutes=2)).isoformat().replace("+00:00","Z")
        orders=wc("GET","wp-json/wc/v3/orders",params={"after":after,"per_page":50,"orderby":"date","order":"desc","status":"any"})
        matches=[o for o in orders if str((o.get("billing") or {}).get("email") or "").lower()==email.lower()]
        if matches:
            result["test_order_cleanup"]["found"]=True
            for o in matches:
                oid=int(o["id"])
                try: wc("DELETE",f"wp-json/wc/v3/orders/{oid}",params={"force":"true"})
                except Exception: pass
            deleted=True; verified=True
            for o in matches:
                try:
                    wc("GET",f"wp-json/wc/v3/orders/{int(o['id'])}")
                    verified=False
                except RuntimeError as e:
                    if "HTTP 404" not in str(e): verified=False
            result["test_order_cleanup"]["deleted"]=deleted
            result["test_order_cleanup"]["verified_404"]=verified
    except Exception as ce:
        result["cleanup_error"]=str(ce)[:2000]
    result["finished_at_utc"]=datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({"ok":result.get("ok"),"shipping":result.get("shipping_countrywide_visible"),"gateway":result.get("payment_redirect_host"),"cleanup":result.get("test_order_cleanup"),"error":result.get("error")},ensure_ascii=False))
