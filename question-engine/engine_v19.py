#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ROOT)

spec = importlib.util.spec_from_file_location("qe18", os.path.join(ROOT, "engine_v18.py"))
v18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v18)
q = v18.q

orig_candidates = q.guarded_candidates
orig_guard = q.consistency_guard
orig_quality = q.question_quality
orig_public_plan = q.public_plan
orig_run = q.run
orig_family = q.b.family
orig_ref_name = q.b.ref_name

INTENT_ALIASES = {
    "water_efficiency": "selection",
    "risk_check": "safety/risk",
    "design_scenario": "field_context",
    "installer_scenario": "installation",
    "post_install": "post_purchase",
    "postuse": "post_purchase",
    "many_outlets": "complete_basket",
    "quantity": "calculation_inputs",
    "area": "calculation_inputs",
    "amount": "calculation_inputs",
    "shipping": "logistics",
    "bulk": "wholesale",
    "price_freshness": "total_cost",
    "discount": "total_cost",
    "complement": "complete_basket",
    "crop_fit": "suitability",
    "crop_choice": "suitability",
    "use_case": "selection",
    "connection": "compatibility",
    "pressure_flow": "selection",
    "flow": "selection",
    "problem": "troubleshooting",
    "post_use": "post_purchase",
}

ARTICLE_INTENTS = {
    "selection", "suitability", "troubleshooting", "maintenance",
    "total_cost", "field_context", "calculation_inputs", "safety/risk",
}
COMPATIBILITY_INTENTS = {"compatibility", "complete_basket", "installation", "replacement", "alternative"}

BLOCKED_EXPERIENCE_PHRASES = (
    "از شما خریدم", "از سایت شما خریدم", "سفارش قبلیم", "مشتری شما هستم",
    "هفته پیش از شما گرفتم", "قبلا از شما خریدم", "قبلاً از شما خریدم",
)

SCENARIO_MARKERS = {
    "area": ("یک هکتار", "۲ هکتار", "2 هکتار", "۵ هکتار", "5 هکتار", "۱۰ هکتار", "10 هکتار", "مساحت"),
    "water": ("آب چاه", "آب شور", "آب سخت", "شن", "رسوب", "کیفیت آب", "ec", "شوری"),
    "pressure": ("فشار", "بار"),
    "flow": ("دبی", "آبدهی"),
    "elevation": ("اختلاف ارتفاع", "شیب", "نقطه بلند"),
    "installation_state": ("نصب", "نصاب", "اتصال فعلی", "محل نصب"),
    "maintenance": ("سرویس", "شست", "نگهداری", "تعمیر"),
    "failure_mode": ("نشتی", "گرفتگی", "کم آبی", "کم‌آبی", "افت فشار", "برگشت آب"),
    "logistics": ("ارسال", "باربری", "عمده", "پیش فاکتور", "پیش‌فاکتور"),
}


def _norm(value):
    return q.b.norm(str(value or ""))


def _canonical_intent(intent, semantic_key):
    normalized = INTENT_ALIASES.get(str(intent or ""), str(intent or "") or "selection")
    digest = hashlib.sha256(f"{normalized}|{semantic_key}".encode("utf-8")).hexdigest()[:16]
    return normalized, f"question-intent-{digest}"


def _extract_scenario(question):
    text = _norm(question)
    out = {}
    for key, markers in SCENARIO_MARKERS.items():
        if any(_norm(marker) in text for marker in markers):
            out[key] = True
    for crop in list(getattr(q.b, "CROPS", []) or []) + list(getattr(q.b, "ORCHARDS", []) or []):
        if _norm(crop) and _norm(crop) in text:
            out["crop"] = crop
            break
    for city in list(getattr(q.b, "CITIES", []) or []):
        if _norm(city) and _norm(city) in text:
            out["province_or_climate"] = city
            break
    return out


def _family_v19(p):
    name = _norm(p.get("name"))
    categories = {_norm(x.get("name")) for x in (p.get("categories") or [])}
    if "پرلیت" in name or "بستر کشت" in categories:
        return "growing_media"
    return orig_family(p)


def _ref_name_v19(p):
    name = re.sub(r"\s+", " ", str(p.get("name") or "")).strip()
    if not name:
        return orig_ref_name(p)
    if len(name) <= 80:
        return name
    return name[:58].rstrip() + "…" + name[-18:].lstrip()


def _v19_candidates(p, fam, style, rng):
    out = list(orig_candidates(p, fam, style, rng) or [])
    name = q.b.ref_name(p)
    existing = {str(x.get("key") or "") for x in out}

    def add(intent, key, core):
        if key not in existing:
            out.append({"intent": intent, "key": key, "core": core})
            existing.add(key)

    if fam == "drip_tape":
        crop = rng.choice(q.b.CROPS)
        city = rng.choice(q.b.CITIES)
        add(
            "field_context",
            "v19:drip-tape:crop-region-inputs",
            f"اگر برای یک هکتار {crop} در حوالی {city} بخوام {name} رو بررسی کنم، قبل از خرید باید فاصله و طول ردیف‌ها، فشار، دبی و کیفیت آب رو دقیق مشخص کنم؟",
        )
    elif fam == "filter":
        add(
            "troubleshooting",
            "v19:filter:pressure-drop-diagnosis",
            f"اگر روی خطی که {name} نصب شده بعد از شست‌وشو هنوز افت فشار دارم، قبل از تعویض فیلتر باید دبی، فشار قبل و بعد، نوع ذرات آب و وضعیت المان رو اندازه بگیرم؟",
        )
    elif fam == "pipe":
        add(
            "calculation_inputs",
            "v19:pipe:sizing-inputs",
            f"برای سایزبندی {name} قبل از سفارش، دبی طراحی، طول مسیر، اختلاف ارتفاع، فشار قابل‌قبول و تعداد انشعاب‌ها رو باید کنار هم داشته باشم؟",
        )
    elif fam == "fitting":
        subtype = q.fitting_subtype(p)
        if subtype == "tee":
            add(
                "compatibility",
                "v19:fitting:interface-photo:tee",
                f"برای اینکه {name} اشتباه سفارش داده نشه، عکس اتصال فعلی، قطر واقعی یا سایز اسمی، جنس خط و اندازه و نوع اتصال هر سه شاخه رو باید تطبیق بدم؟",
            )
        else:
            add(
                "compatibility",
                "v19:fitting:interface-photo",
                f"برای اینکه {name} اشتباه سفارش داده نشه، عکس اتصال فعلی، قطر واقعی یا سایز اسمی، جنس خط و نوع رزوه یا رابط سمت‌های درگیر رو باید تطبیق بدم؟",
            )
    elif fam in {"valve", "automatic_valve", "air_valve"}:
        add(
            "compatibility",
            f"v19:{fam}:pressure-interface",
            f"برای انتخاب {name} علاوه بر سایز، نوع اتصال، جهت جریان، فشار واقعی خط و نقشی که شیر در سیستم داره باید مشخص باشه؟",
        )
    elif fam in {"fertilizer", "fertigation", "adjuvant"}:
        add(
            "safety/risk",
            f"v19:{fam}:label-water-soil",
            f"قبل از تصمیم درباره {name} باید برچسب یا آنالیز معتبر، نوع کشت و مرحله رشد، روش مصرف و اطلاعات آب و خاک رو داشته باشم تا توصیه حدسی نشه؟",
        )
    elif fam == "pesticide":
        add(
            "safety/risk",
            "v19:pesticide:diagnosis-label",
            f"قبل از تصمیم درباره {name} باید آفت یا بیماری دقیق، مرحله رشد، شرایط هوا و برچسب ثبت‌شده بررسی بشه تا کاربرد یا دوز از روی حدس گفته نشه؟",
        )
    elif fam == "growing_media":
        crop = rng.choice(q.b.INDOOR if getattr(q.b, "INDOOR", None) else q.b.CROPS)
        add(
            "suitability",
            "v19:growing-media:crop-rootzone-context",
            f"اگر بخوام {name} رو برای {crop} یا بستر گلخانه‌ای بررسی کنم، قبل از انتخاب باید هدف اختلاط، نسبت زهکشی و نگهداشت آب، روش آبیاری و کیفیت آب رو مشخص کنم؟",
        )
        add(
            "safety/risk",
            "v19:growing-media:label-origin-sterility",
            f"برای ارزیابی {name} چه اطلاعاتی از دانه‌بندی، منبع یا برند، وضعیت شست‌وشو یا استریل بودن و شرایط نگهداری باید از برچسب یا منبع معتبر بررسی بشه؟",
        )
    return out


def _guard_v19(p, candidate, question):
    ok, reason = orig_guard(p, candidate, question)
    if not ok:
        return ok, reason
    text = _norm(question)
    if any(_norm(x) in text for x in BLOCKED_EXPERIENCE_PHRASES):
        return False, "fabricated customer-purchase experience"
    if not _extract_scenario(question):
        key = str(candidate.get("key") or "")
        if key.startswith("v19:"):
            return False, "v19 scenario question has no decision-changing context"
    return True, None


def _quality_v19(p, question, candidate, fam, existing):
    score, reason = orig_quality(p, question, candidate, fam, existing)
    if score <= 0:
        return score, reason
    ok, reason = _guard_v19(p, candidate, question)
    if not ok:
        return 0, reason
    scenario = _extract_scenario(question)
    intent, _ = _canonical_intent(candidate.get("intent"), candidate.get("key"))
    if not scenario:
        score -= 3
    if intent in {"compatibility", "complete_basket", "calculation_inputs", "troubleshooting", "safety/risk"}:
        score = min(100, score + 1)
    return max(0, score), reason


def _public_plan_v19(plan):
    pub = orig_public_plan(plan)
    normalized_intent, canonical_intent_id = _canonical_intent(pub.get("intent"), pub.get("semantic_key"))
    scenario = _extract_scenario(pub.get("question"))
    pub.update({
        "engine_version": 19,
        "intent_v19": normalized_intent,
        "canonical_intent_id": canonical_intent_id,
        "scenario_dimensions": scenario,
        "potential_article_gap": normalized_intent in ARTICLE_INTENTS,
        "potential_hub_gap": False,
        "compatibility_gap": normalized_intent in COMPATIBILITY_INTENTS,
        "evidence_classification": "synthetic_editorial_question_generator_not_customer_evidence",
    })
    return pub


def _write_signal(result_path, res):
    if not res.get("ok") or not res.get("product_id") or not res.get("question"):
        return None
    base = os.path.splitext(os.path.basename(result_path))[0]
    out_dir = os.path.join(REPO_ROOT, "growth-os", "backlog", "question-signals")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, base + ".json")
    payload = {
        "schema_version": "1",
        "engine_version": 19,
        "canonical_intent_id": res.get("canonical_intent_id"),
        "product_id": int(res.get("product_id")),
        "family": res.get("family"),
        "intent": res.get("intent_v19"),
        "scenario_dimensions": res.get("scenario_dimensions") or {},
        "potential_article_gap": bool(res.get("potential_article_gap")),
        "potential_hub_gap": bool(res.get("potential_hub_gap")),
        "compatibility_gap": bool(res.get("compatibility_gap")),
        "evidence_classification": "synthetic_editorial_question_generator_not_customer_evidence",
        "contains_personal_data": False,
        "source_result": os.path.basename(result_path),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def _run_v19(action, result_path):
    res = orig_run(action, result_path)
    signal_path = _write_signal(result_path, res)
    if signal_path:
        res["backlog_signal_path"] = os.path.relpath(signal_path, REPO_ROOT).replace(os.sep, "/")
        q.b.write_result(result_path, res)
    return res


q.b.family = _family_v19
q.b.ref_name = _ref_name_v19
q.guarded_candidates = _v19_candidates
q.consistency_guard = _guard_v19
q.question_quality = _quality_v19
q.public_plan = _public_plan_v19
q.run = _run_v19


def main():
    q.main()


if __name__ == "__main__":
    main()
