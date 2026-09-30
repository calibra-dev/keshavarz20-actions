from __future__ import annotations

import hashlib
import re
from typing import Any

from core import textify

ALLOWED_CLASSES={"FACT","MANUFACTURER_CLAIM","ESTIMATE","ENGINEERING_REQUIRED","EXPERT_INTERPRETATION"}
BANNED_VISIBLE=[
    "در این مقاله","در ادامه","روش تهیه و بازبینی","نظر کارشناسی کشاورز بیست",
    "همان‌طور که می‌دانید","در دنیای امروز","به طور کلی می‌توان گفت",
    "به‌طور کلی می‌توان گفت","محصولی کاربردی و باکیفیت","انتخابی ایده‌آل برای همه"
]

def sentence_fingerprints(raw: str) -> list[tuple[str,str]]:
    text=textify(raw).lower()
    chunks=re.split(r"[.!؟]\s+|\n+",text)
    out=[]
    for sentence in chunks:
        norm=re.sub(r"[^\w\u0600-\u06ff]+"," ",sentence)
        norm=re.sub(r"\s+"," ",norm).strip()
        if len(norm.split()) < 12:
            continue
        out.append((hashlib.sha256(norm.encode("utf-8")).hexdigest()[:20],norm[:220]))
    return out

def validate(candidate: dict[str,Any], product: dict[str,Any], source_urls: list[str], bank: dict[str,Any]) -> list[str]:
    errors=[]
    required=[
        "family","commercial_angle","short_description_html","description_html",
        "seo_title","meta_description","focus_keyphrase","related_keyphrases",
        "image_alt_suggestions","claims","source_urls","buyer_decision"
    ]
    for key in required:
        if key not in candidate:
            errors.append(f"missing key: {key}")
    short=str(candidate.get("short_description_html") or "")
    desc=str(candidate.get("description_html") or "")
    combined=short+"\n"+desc
    low=combined.lower()
    if len(textify(short)) < 90:
        errors.append("short description is too thin")
    if len(textify(desc)) < 650:
        errors.append("full description is too thin")
    for token in ("<script","<style","<iframe","application/ld+json","<h1","javascript:"):
        if token in low:
            errors.append(f"forbidden markup: {token}")
    if re.search(r"\bk20\b",combined,re.I):
        errors.append("internal K20 token leaked into visible copy")
    for phrase in BANNED_VISIBLE:
        if phrase in combined:
            errors.append(f"generic/non-commercial phrase: {phrase}")
    collisions=[]
    for h,snippet in sentence_fingerprints(combined):
        previous=bank.get(h)
        if previous and int(previous.get("product_id") or 0) != int(product.get("id") or 0):
            collisions.append(snippet[:90])
    if collisions:
        errors.append("reused long sentences from prior products: "+" | ".join(collisions[:3]))
    allow=set(source_urls)
    for claim in candidate.get("claims") or []:
        cls=str(claim.get("class") or "")
        url=str(claim.get("evidence_url") or "")
        if cls not in ALLOWED_CLASSES:
            errors.append(f"invalid claim class: {cls}")
        if cls in {"FACT","MANUFACTURER_CLAIM"} and not url:
            errors.append("FACT/MANUFACTURER_CLAIM without source")
        if url and url not in allow:
            errors.append("claim source outside research allow-list")
    for url in candidate.get("source_urls") or []:
        if url not in allow:
            errors.append("candidate source outside research allow-list")
    image_ids={int(x.get("id") or 0) for x in (product.get("images") or [])}
    for item in candidate.get("image_alt_suggestions") or []:
        if int(item.get("attachment_id") or 0) not in image_ids:
            errors.append("ALT suggestion targets unrelated attachment")
    return sorted(set(errors))

def score(candidate: dict[str,Any], product: dict[str,Any], source_urls: list[str], errors: list[str]) -> tuple[int,dict[str,Any]]:
    if errors:
        return max(0,70-5*len(errors)),{"blockers":errors}
    total=0
    detail={}
    evidence=25 if len(set(source_urls))>=2 else (18 if source_urls else 5)
    total+=evidence; detail["evidence"]=evidence
    text=textify(str(candidate.get("short_description_html") or "")+" "+str(candidate.get("description_html") or ""))
    commercial_hits=sum(1 for t in ["خرید","انتخاب","سفارش","مناسب","قبل از خرید","سازگار","نصب","مصرف","پیش‌فاکتور"] if t in text)
    commercial=20 if commercial_hits>=4 else (16 if commercial_hits>=2 else 10)
    total+=commercial; detail["commercial"]=commercial
    desc=str(candidate.get("description_html") or "")
    structure=20
    if len(textify(desc))<1000: structure-=3
    if len(re.findall(r"<h[23]\b",desc,re.I))<2: structure-=3
    if not re.search(r"<(?:ul|ol|table|details)\b",desc,re.I): structure-=2
    if not any(t in text for t in ["محدودیت","مناسب نیست","قبل از خرید","بررسی کنید","سازگار"]): structure-=2
    total+=max(0,structure); detail["decision_structure"]=max(0,structure)
    seo=15
    title=textify(str(candidate.get("seo_title") or ""))
    meta=textify(str(candidate.get("meta_description") or ""))
    if not 25<=len(title)<=90: seo-=2
    if not 70<=len(meta)<=200: seo-=2
    if len(textify(str(candidate.get("focus_keyphrase") or "")))<3: seo-=3
    total+=max(0,seo); detail["seo"]=max(0,seo)
    safety=10
    if any(x in text for x in ["تضمینی","شماره یک","بهترین محصول"]): safety-=5
    total+=safety; detail["safety"]=safety
    images=product.get("images") or []
    alt_map={int(x.get("attachment_id") or 0):textify(str(x.get("alt_text") or "")) for x in (candidate.get("image_alt_suggestions") or [])}
    media=10 if not images or all(alt_map.get(int(i.get("id") or 0)) or textify(str(i.get("alt") or "")) for i in images) else 6
    total+=media; detail["media_alt"]=media
    return min(100,total),detail

def update_bank(state: dict[str,Any], product_id: int, candidate: dict[str,Any]) -> None:
    bank=state.setdefault("sentence_bank",{})
    raw=str(candidate.get("short_description_html") or "")+" "+str(candidate.get("description_html") or "")
    for h,snippet in sentence_fingerprints(raw):
        bank[h]={"product_id":product_id,"snippet":snippet}
    if len(bank)>3000:
        for key in list(bank)[:len(bank)-3000]:
            bank.pop(key,None)
