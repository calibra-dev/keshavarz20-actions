#!/usr/bin/env python3
"""Read-only validation of the installed Calibra 1.8.17 regional REST response.
No raw order, customer, or city records are printed.
"""
import base64
import json
import math
import os
import urllib.error
import urllib.request

base = os.environ.get("WP_BASE_URL", "").rstrip("/")
user = os.environ.get("WP_USERNAME", "")
password = os.environ.get("WP_APP_PASSWORD", "")
if not all((base, user, password)):
    raise SystemExit("NO_SITE_CREDENTIALS")

token = base64.b64encode(f"{user}:{password}".encode()).decode()
request = urllib.request.Request(
    base + "/wp-json/k20-dashboard/v1/snapshot?section=regional&range=365&force=0",
    headers={"Authorization": "Basic " + token, "Accept": "application/json", "User-Agent": "Calibra-1817-ReadOnly-QA"},
)
try:
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
except urllib.error.HTTPError as err:
    raise SystemExit(f"REGIONAL_REST_HTTP_{err.code}")
if not isinstance(payload, dict) or payload.get("section") != "regional":
    raise SystemExit("REGIONAL_WRONG_RESPONSE")
if payload.get("ok") is not True:
    raise SystemExit("REGIONAL_RESPONSE_ERROR")
data = payload.get("data")
if not isinstance(data, dict) or data.get("available") is not True:
    raise SystemExit("REGIONAL_DATA_UNAVAILABLE")
provinces = data.get("provinces")
if not isinstance(provinces, list) or len(provinces) != 31:
    raise SystemExit("REGIONAL_PROVINCES_NOT_31")
codes = [p.get("code") for p in provinces]
if len(set(codes)) != 31:
    raise SystemExit("REGIONAL_PROVINCE_CODES_DUPLICATED")
province_orders = 0
province_revenue = 0.0
active_cities = 0
for p in provinces:
    items = p.get("cities")
    if not isinstance(items, list) or len(items) != p.get("city_count"):
        raise SystemExit("REGIONAL_CITY_COUNT_MISMATCH")
    orders = p.get("orders")
    if not isinstance(orders, int) or orders < 0:
        raise SystemExit("REGIONAL_BAD_PROVINCE_ORDERS")
    province_orders += orders
    revenue = float(p["revenue"])
    if not math.isfinite(revenue):
        raise SystemExit("REGIONAL_NONFINITE_PROVINCE_REVENUE")
    province_revenue += revenue
    city_orders = 0
    city_revenue = 0.0
    for city in items:
        quantity = city.get("orders")
        if not isinstance(quantity, int) or quantity <= 0:
            raise SystemExit("REGIONAL_CITY_WITH_NO_ORDERS")
        city_orders += quantity
        amount = float(city["revenue"])
        if not math.isfinite(amount):
            raise SystemExit("REGIONAL_NONFINITE_CITY_REVENUE")
        city_revenue += amount
    if city_orders > orders:
        raise SystemExit("REGIONAL_CITY_ORDERS_GREATER_THAN_PROVINCE")
    # A province may contain orders with an empty city; require equality only
    # when every province order is represented in the non-empty city rows.
    if city_orders == orders and not math.isclose(city_revenue, revenue, rel_tol=1e-12, abs_tol=0.01):
        raise SystemExit("REGIONAL_CITY_PROVINCE_REVENUE_MISMATCH")
    active_cities += len(items)
unmatched = data.get("unmatched") or {}
external = data.get("external") or {}
total_orders = data.get("total_orders")
if province_orders + int(unmatched.get("count", 0)) + int(external.get("count", 0)) != total_orders:
    raise SystemExit("REGIONAL_NATIONAL_ORDER_BALANCE_MISMATCH")
mapped_revenue = float(data["mapped_revenue"])
total_revenue = float(data["total_revenue"])
unmatched_revenue = float(unmatched["revenue"])
external_revenue = float(external["revenue"])
if not all(math.isfinite(x) for x in (mapped_revenue, total_revenue, unmatched_revenue, external_revenue)):
    raise SystemExit("REGIONAL_NONFINITE_NATIONAL_REVENUE")
if not math.isclose(province_revenue, mapped_revenue, rel_tol=1e-12, abs_tol=0.01):
    raise SystemExit("REGIONAL_MAPPED_REVENUE_MISMATCH")
if not math.isclose(province_revenue + unmatched_revenue + external_revenue, total_revenue, rel_tol=1e-12, abs_tol=0.01):
    raise SystemExit("REGIONAL_NATIONAL_REVENUE_MISMATCH")
print("LIVE_REGIONAL_REST_OK")
print("LIVE_31_PROVINCES_OK")
print("LIVE_ORDER_BALANCE_OK")
print("LIVE_REVENUE_BALANCE_OK")
print("LIVE_CITY_PROVINCE_REVENUE_BALANCE_WHEN_COMPLETE_OK")
print("LIVE_NATIONAL_REVENUE_INCLUDING_UNMATCHED_EXTERNAL_OK")
print("LIVE_SALES_ONLY_CITY_ROWS_OK")
print("REGIONAL_PROBE_METADATA=" + json.dumps({"city_rows_with_sales": active_cities, "total_orders": total_orders, "unmatched_orders": int(unmatched.get("count", 0)), "external_orders": int(external.get("count", 0)), "source": payload.get("source"), "cache_hit": payload.get("cache_hit")}, ensure_ascii=False))

