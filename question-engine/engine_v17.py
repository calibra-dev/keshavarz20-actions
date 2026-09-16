#!/usr/bin/env python3
import importlib.util
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe16", os.path.join(ROOT, "engine_v16.py"))
v16 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v16)
q = v16.q

orig_candidates = q.guarded_candidates
orig_guard = q.consistency_guard
orig_family = q.b.family
orig_fitting_subtype = q.fitting_subtype

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def canon(value):
    text = str(value or "").translate(_DIGITS)
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    return q.b.norm(text)


def product_blob(p):
    try:
        return canon(q.b.product_text(p))
    except Exception:
        return canon(p.get("name"))


def family_v17(p):
    name = canon(p.get("name"))
    if "اتصال نر" in name or "اتصال ماده" in name:
        return "fitting"
    return orig_family(p)


def fitting_subtype_v17(p):
    name = canon(p.get("name"))
    if "اتصال نر" in name:
        return "male_adapter"
    if "اتصال ماده" in name:
        return "female_adapter"
    return orig_fitting_subtype(p)


def fertilizer_profile(p):
    text = product_blob(p)
    # These labels choose a question context only; they never claim compatibility.
    if any(x in text for x in ["کلسیم", "کلسیم نیترات", "نیترات کلسیم"]):
        return "calcium"
    if any(x in text for x in ["آهن", "کلات آهن", "fe eddha", "fe edta"]):
        return "iron"
    if any(x in text for x in ["هیومیک", "فولویک"]):
        return "humic"
    if any(x in text for x in ["اسید آمینه", "آمینو اسید", "امینو اسید"]):
        return "amino"
    if any(x in text for x in ["پتاسیم", "پتاس", "k60", "سولفات پتاسیم", "نیترات پتاسیم"]):
        return "potassium"
    if any(x in text for x in ["فسفر", "فسفات", "فسفیت"]):
        return "phosphorus"
    if any(x in text for x in ["نیتروژن", "ازت", "اوره", "سولفات آمونیوم", "نیترات آمونیوم"]):
        return "nitrogen"
    # canon()/norm() turns separators such as '-' into spaces.
    if re.search(r"(?<!\d)10\s+52\s+10(?!\d)", text):
        return "phosphorus"
    if re.search(r"(?<!\d)\d{1,2}\s+\d{1,2}\s+\d{1,2}(?!\d)", text) or "npk" in text:
        return "npk"
    return "generic"


PARTNERS = {
    "nitrogen": ["کود ۱۰-۵۲-۱۰", "سولفات پتاسیم", "هیومیک اسید"],
    "phosphorus": ["اوره", "سولفات پتاسیم", "هیومیک اسید"],
    "potassium": ["کود ۱۰-۵۲-۱۰", "اوره", "هیومیک اسید"],
    "calcium": ["کود ۱۰-۵۲-۱۰", "سولفات پتاسیم", "کود آهن"],
    "iron": ["کود کلسیم", "کود ۲۰-۲۰-۲۰", "هیومیک اسید"],
    "humic": ["کود ۱۰-۵۲-۱۰", "اوره", "سولفات پتاسیم"],
    "amino": ["کود ۲۰-۲۰-۲۰", "کود ۱۰-۵۲-۱۰", "سولفات پتاسیم"],
    "npk": ["اوره", "سولفات پتاسیم", "هیومیک اسید"],
    "generic": ["کود ۱۰-۵۲-۱۰", "سولفات پتاسیم", "اوره"],
}


def same_as_product(p, partner):
    text = product_blob(p)
    pt = canon(partner)
    if pt and pt in text:
        return True
    if "10 52 10" in pt and re.search(r"(?<!\d)10\s+52\s+10(?!\d)", text):
        return True
    if "20 20 20" in pt and re.search(r"(?<!\d)20\s+20\s+20(?!\d)", text):
        return True
    return False


def _size_mm(p):
    text = canon(p.get("name"))
    m = re.search(r"(?<!\d)(\d{2,3})\s*(?:میلی\s*متر|میلیمتر|mm)(?!\w)", text)
    return m.group(1) if m else None


def fitting_line_context(p):
    # Use the product title for material identity. Descriptions/categories may
    # mention related materials and must not silently change the scenario.
    text = canon(p.get("name"))
    size = _size_mm(p)
    suffix = f" {size} میلی‌متر" if size else ""
    if any(x in text for x in ["لی فلت", "لی‌فلت"]):
        return "خط لی‌فلت"
    if any(x in text for x in ["u pvc", "upvc", "pvc", "پولیکا"]):
        return "لوله U-PVC" + suffix
    if any(x in text for x in ["پلی اتیلن", "پلی‌اتیلن", "آبلوله"]):
        return "لوله پلی‌اتیلن" + suffix
    if "نوار تیپ" in text or "نوارتیپ" in text:
        return "نوار تیپ"
    return None


def add(out, intent, key, core):
    out.append({"intent": intent, "key": key, "core": core})


def candidates_v17(p, fam, style, rng):
    out = list(orig_candidates(p, fam, style, rng) or [])
    name = q.b.ref_name(p)

    if fam == "fertilizer":
        # Remove broad/orphan mix prompts. Every v17 mix prompt names a concrete
        # second fertilizer and keeps the answer open instead of inventing a claim.
        out = [x for x in out if x.get("intent") != "mix"]
        profile = fertilizer_profile(p)
        partners = [x for x in PARTNERS.get(profile, PARTNERS["generic"]) if not same_as_product(p, x)]
        crop = rng.choice(q.b.CROPS)
        if not partners:
            partners = ["کود ۱۰-۵۲-۱۰", "سولفات پتاسیم"]

        for partner in partners[:3]:
            pkey = canon(partner).replace(" ", "-")
            add(
                out,
                "mix",
                f"nutrition:specific-mix:{profile}:{pkey}:tank",
                f"اگر بخوام {name} رو همراه {partner} داخل یک تانک کود استفاده کنم، این دو از نظر اختلاط قابل بررسی هستن یا بهتره جدا تزریق بشن؛ برای تصمیم درست pH و EC آب یا ترتیب حل‌کردن هم مهمه",
            )
            add(
                out,
                "mix",
                f"nutrition:specific-mix:{profile}:{pkey}:crop",
                f"برای {crop} می‌خوام {name} رو کنار {partner} در یک برنامه غذایی استفاده کنم؛ اگر هر دو برای این مرحله مناسب باشن، میشه در یک نوبت کودآبیاری داد یا بهتره بین مصرفشون فاصله باشه",
            )

    if fam == "fitting":
        # v7 randomized existing-line material. Keep randomness in wording/intent,
        # but never let it replace the material identity present in the product title.
        out = [
            x for x in out
            if not str(x.get("key") or "").startswith("installer:existing-line:fitting:")
            and not str(x.get("key") or "").startswith("postinstall:leak:fitting:")
        ]
        line = fitting_line_context(p)
        if line:
            lkey = canon(line).replace(" ", "-")
            add(
                out,
                "installer_scenario",
                f"installer:matched-line:fitting:{lkey}",
                f"برای نصب {name} روی {line}، قبل از خرید دقیقاً کدوم اندازه و نوع اتصال رو باید از روی لوله و قطعه فعلی چک کنم که سایز اشتباه نگیرم",
            )
            add(
                out,
                "post_install",
                f"postinstall:matched-line:fitting:{lkey}",
                f"{name} رو روی {line} نصب کردم ولی کمی نشتی دارم؛ قبل از تعویض قطعه، ترتیب بستن اجزا، محل آب‌بندی و درست بودن سایز رو از کجا باید بررسی کنم",
            )

    return out


SPECIFIC_MIX_MARKERS = [
    "10 52 10", "20 20 20", "اوره", "سولفات پتاسیم", "هیومیک اسید", "کود آهن", "کود کلسیم"
]


def guard_v17(p, candidate, question):
    ok, reason = orig_guard(p, candidate, question)
    if not ok:
        return ok, reason

    fam = q.fam_of(p)
    text = canon(question)
    key = str(candidate.get("key") or "")

    if fam == "fertilizer" and candidate.get("intent") == "mix":
        if any(x in text for x in ["کودهای دیگه", "کودهای دیگر"]):
            return False, "generic fertilizer-mix wording"
        if not any(marker in text for marker in SPECIFIC_MIX_MARKERS):
            return False, "mix question must name a concrete second fertilizer"
        ref = canon(q.b.ref_name(p))
        if ref and ref not in text and "این محصول" not in text and "این کود" not in text:
            return False, "mix question must reference selected product"

    if fam == "fitting" and key.startswith(("installer:matched-line:fitting:", "postinstall:matched-line:fitting:")):
        expected = fitting_line_context(p)
        if expected and canon(expected) not in text:
            return False, "matched fitting scenario lost its product line context"
        title = canon(p.get("name"))
        if any(x in title for x in ["پلی اتیلن", "پلی‌اتیلن", "آبلوله"]):
            if any(x in text for x in ["پولیکا", "u pvc", "upvc", "لی فلت", "لی‌فلت"]):
                return False, "PE fitting scenario mentions incompatible random line material"

    return True, None


q.b.family = family_v17
q.fitting_subtype = fitting_subtype_v17
q.guarded_candidates = candidates_v17
q.consistency_guard = guard_v17


def main():
    q.main()


if __name__ == "__main__":
    main()
