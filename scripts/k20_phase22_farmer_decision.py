#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List

REQUIRED_FIELDS = [
    "crop",
    "area_ha",
    "water_source",
    "pressure_bar",
    "available_flow_m3h",
    "soil_texture",
    "region",
]

HIGH_RISK_WATER_SOURCES = {"river", "canal", "surface", "رودخانه", "کانال", "آب سطحی"}
SOIL_GUIDANCE = {
    "sandy": "نفوذ آب معمولاً سریع‌تر است؛ مدت/فاصله آبیاری باید با آزمون مزرعه و نیاز واقعی گیاه تنظیم شود.",
    "loam": "خاک لومی معمولاً نقطه شروع متعادلی است، اما برنامه آبیاری همچنان به آزمون مزرعه و اقلیم وابسته است.",
    "clay": "ریسک ماندابی‌شدن و نفوذ آهسته‌تر را بررسی کنید؛ از قطعیت در زمان‌بندی آبیاری بدون آزمون خاک پرهیز شود.",
    "شنی": "نفوذ آب معمولاً سریع‌تر است؛ مدت/فاصله آبیاری باید با آزمون مزرعه و نیاز واقعی گیاه تنظیم شود.",
    "لومی": "خاک لومی معمولاً نقطه شروع متعادلی است، اما برنامه آبیاری همچنان به آزمون مزرعه و اقلیم وابسته است.",
    "رسی": "ریسک ماندابی‌شدن و نفوذ آهسته‌تر را بررسی کنید؛ از قطعیت در زمان‌بندی آبیاری بدون آزمون خاک پرهیز شود.",
}


def _present(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate(case: Dict[str, Any]) -> Dict[str, Any]:
    missing = [name for name in REQUIRED_FIELDS if not _present(case.get(name))]
    invalid: List[str] = []
    area = _num(case.get("area_ha"))
    pressure = _num(case.get("pressure_bar"))
    flow = _num(case.get("available_flow_m3h"))
    if area is not None and area <= 0:
        invalid.append("area_ha")
    if pressure is not None and pressure <= 0:
        invalid.append("pressure_bar")
    if flow is not None and flow <= 0:
        invalid.append("available_flow_m3h")

    hard_stop = bool(missing or invalid)
    water_source = str(case.get("water_source") or "").strip().lower()
    water_quality = str(case.get("water_quality") or "unknown").strip().lower()
    soil = str(case.get("soil_texture") or "").strip().lower()

    warnings: List[str] = []
    explanations: List[Dict[str, str]] = []
    next_steps: List[Dict[str, str]] = []

    if hard_stop:
        warnings.append("ورودی‌های فنی برای توصیه ایمن کامل نیستند؛ انتخاب تجهیز یا سایز نهایی متوقف می‌شود.")
    else:
        capacity = round(flow / area, 2) if area and flow else None
        explanations.append({
            "signal": "available_flow_per_hectare",
            "value": f"{capacity} m3/h/ha" if capacity is not None else "unknown",
            "meaning": "این فقط نسبت ظرفیت آب در دسترس به سطح است و نیاز آبی گیاه یا دبی طراحی را جایگزین نمی‌کند.",
        })
        if pressure is not None:
            explanations.append({
                "signal": "measured_pressure",
                "value": f"{pressure:g} bar",
                "meaning": "فشار ثبت‌شده باید در محل مصرف و زیر بار واقعی تأیید شود؛ از این مقدار به‌تنهایی برای سایزینگ استفاده نمی‌شود.",
            })
        if soil in SOIL_GUIDANCE:
            explanations.append({"signal": "soil_texture", "value": str(case.get("soil_texture")), "meaning": SOIL_GUIDANCE[soil]})

        next_steps.extend([
            {
                "tool": "pipe_size_flow_pressure_guide",
                "url": "https://keshavarz20.com/polyethylene-pipe-size-flow-pressure-guide/",
                "reason": "برای بررسی دبی، فشار، طول مسیر و افت فشار قبل از انتخاب سایز لوله.",
            },
            {
                "tool": "irrigation_filter_selector",
                "url": "https://keshavarz20.com/irrigation-filter-selector/",
                "reason": "برای تعیین کلاس فیلتراسیون بر اساس منبع آب و کیفیت واقعی آب.",
            },
            {
                "tool": "fittings_compatibility_selector",
                "url": "https://keshavarz20.com/irrigation-fittings-compatibility-selector/",
                "reason": "برای تطبیق اتصال‌ها پس از نهایی‌شدن قطر و استاندارد اتصال.",
            },
        ])

    elevated_water_risk = water_source in HIGH_RISK_WATER_SOURCES or any(
        token in water_quality for token in ("sediment", "turbid", "suspended", "گل", "رسوب", "کدر")
    )
    if elevated_water_risk:
        warnings.append("منبع/کیفیت آب می‌تواند ریسک گرفتگی را بالا ببرد؛ آزمایش آب و طراحی فیلتراسیون قبل از خرید توصیه می‌شود.")

    expert_escalation = hard_stop or elevated_water_risk or bool(case.get("uneven_terrain")) or bool(case.get("fertigation"))
    if expert_escalation:
        warnings.append("برای طراحی نهایی هیدرولیکی/زراعی، تأیید کارشناس یا نصاب واجد تجربه لازم است.")

    state = "NEEDS_MORE_INPUT" if hard_stop else "ADVISORY_ONLY"
    confidence = "low" if hard_stop else ("medium" if expert_escalation else "medium_high")

    return {
        "decision_model_version": "k20-farmer-decision-v1",
        "state": state,
        "confidence": confidence,
        "input_completeness": {
            "required_fields": REQUIRED_FIELDS,
            "missing_fields": missing,
            "invalid_fields": invalid,
            "complete": not hard_stop,
        },
        "scope": {
            "specific_product_recommendation": False,
            "hydraulic_design_claimed": False,
            "agronomic_prescription_claimed": False,
            "price_or_commercial_decision": False,
        },
        "explanations": explanations,
        "warnings": warnings,
        "next_steps": next_steps if not hard_stop else [],
        "expert_escalation": expert_escalation,
        "guardrails": [
            "Unknown values remain unknown; no value is guessed.",
            "Outcomes are advisory and explainable, not a certified irrigation design.",
            "No SKU/product is recommended until compatibility and measured field constraints are verified.",
        ],
    }


def run_cases(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = []
    for case in cases:
        result = evaluate(case)
        results.append({"case_id": case.get("case_id"), "input": case, "result": result})
    checks = {
        "all_cases_return_guardrails": all(x["result"].get("guardrails") for x in results),
        "missing_inputs_stop_specific_recommendation": all(
            not x["result"]["scope"]["specific_product_recommendation"]
            for x in results
            if x["result"]["input_completeness"]["missing_fields"] or x["result"]["input_completeness"]["invalid_fields"]
        ),
        "expert_escalation_present_when_needed": all(
            x["result"]["expert_escalation"]
            for x in results
            if x["result"]["state"] == "NEEDS_MORE_INPUT"
        ),
        "no_hydraulic_or_agronomic_certainty": all(
            not x["result"]["scope"]["hydraulic_design_claimed"] and not x["result"]["scope"]["agronomic_prescription_claimed"]
            for x in results
        ),
    }
    return {
        "phase": 22,
        "title": "Farmer Decision Personalization",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "model_version": "k20-farmer-decision-v1",
        "status": "PASS_MODEL_VALIDATION" if all(checks.values()) else "FAIL_MODEL_VALIDATION",
        "checks": checks,
        "cases": results,
        "site_mutations": 0,
        "commerce_mutations": 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise SystemExit("cases must be a JSON array")
    out = run_cases(cases)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"phase": 22, "status": out["status"], "cases": len(out["cases"]), "checks": out["checks"]}, ensure_ascii=False))
    if out["status"] != "PASS_MODEL_VALIDATION":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
