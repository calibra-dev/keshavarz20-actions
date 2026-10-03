#!/usr/bin/env python3
from __future__ import annotations
from decimal import Decimal, InvalidOperation

def normalize_commerce_price(amount, source_currency):
    cur=str(source_currency or "").strip().upper()
    try:
        value=Decimal(str(amount).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("invalid amount")
    if value < 0:
        raise ValueError("negative amount")
    if cur=="IRT":
        return {"amount": (value*Decimal("10")), "currency":"IRR", "rule":"IRT_X10_TO_IRR"}
    if len(cur)==3 and cur.isalpha() and cur!="IRT":
        return {"amount": value, "currency":cur, "rule":"IDENTITY_ISO4217_ASSUMED_UPSTREAM_VALIDATED"}
    raise ValueError("unsupported currency")

def merchant_amount_micros(amount, source_currency):
    n=normalize_commerce_price(amount,source_currency)
    micros=n["amount"]*Decimal("1000000")
    if micros != micros.to_integral_value():
        raise ValueError("amount cannot be represented exactly in micros")
    return {"amountMicros":str(int(micros)),"currencyCode":n["currency"],"rule":n["rule"]}

if __name__=="__main__":
    assert normalize_commerce_price("1","IRT")=={"amount":Decimal("10"),"currency":"IRR","rule":"IRT_X10_TO_IRR"}
    assert normalize_commerce_price("125000","IRT")["amount"]==Decimal("1250000")
    assert merchant_amount_micros("125000","IRT")=={"amountMicros":"1250000000000","currencyCode":"IRR","rule":"IRT_X10_TO_IRR"}
    print("CURRENCY_NORMALIZATION_OK")
