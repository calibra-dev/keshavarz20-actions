#!/usr/bin/env python3
import json, os, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()

def load(rel):
    with open(ROOT/rel, encoding="utf-8") as f:
        return json.load(f)

pim=load("phase3-results/top30-pim.json")
feed=load("phase19-results/product-discovery-readiness-feed-persisted.json")
discovery=load("geo-aeo-results/k21-openai-discovery-feed-draft.json")
parity=load("phase3-results/page-schema-feed-parity.json")
indexability=load("phase3-results/top30-indexability.json")

feed_by={int(x["wp_product_id"]):x for x in feed.get("products",[]) if x.get("wp_product_id")}
# Prefer the current validated discovery draft for products that have a valid live row.
for x in discovery.get("valid_rows",[]):
    if not x.get("wp_product_id"): continue
    pid=int(x["wp_product_id"])
    feed_by[pid]={
      **feed_by.get(pid,{}),
      **x,
      "image_url":x.get("image_url"),
      "brand":x.get("brand"),
      "openai_discovery_missing_or_unresolved_fields":[],
      "source":"k21-openai-discovery-feed-draft.valid_rows"
    }
parity_by={int(x["product_id"]):x for x in parity.get("products",[]) if x.get("product_id")}
idx_by={int(x["product_id"]):x for x in indexability.get("products",[]) if x.get("product_id")}

def points(cond, pts):
    return pts if cond else 0

rows=[]
for p in pim.get("products",[]):
    pid=int(p["product_id"])
    f=feed_by.get(pid,{})
    pr=parity_by.get(pid,{})
    ix=idx_by.get(pid,{})
    ids=p.get("stable_identifiers") or {}
    fields=p.get("pim_fields") or {}
    content=p.get("content") or {}
    missing_compat=p.get("compatibility_missing_fields") or []
    unresolved=f.get("openai_discovery_missing_or_unresolved_fields") or []

    # 1) Product truth / completeness. Never reward fabricated identifiers.
    product_truth=0
    product_truth += points(bool((ids.get("sku") or {}).get("value")),15)
    product_truth += points(bool((fields.get("brand") or {}).get("value")),15)
    product_truth += points(bool((ids.get("gtin") or {}).get("value")) or bool((ids.get("mpn") or {}).get("value") if isinstance(ids.get("mpn"),dict) else ids.get("mpn")),10)
    product_truth += min(35, sum(1 for k,v in fields.items() if v)*5)
    product_truth += points(content.get("description_words",0)>=120,10)
    product_truth += points(content.get("short_words",0)>=20,5)
    product_truth += points(content.get("image_count",0)>=1 and content.get("all_image_alt_present") is True,10)

    # 2) Answer readiness.
    answer=0
    answer += points(content.get("short_words",0)>=20,20)
    answer += points(content.get("description_words",0)>=300,25)
    answer += points(p.get("decision_links_present") is True,20)
    gaps=set(p.get("product_quality_gaps") or [])
    answer += points("مناسب/نامناسب و محدودیت" not in gaps,15)
    answer += points("Verified Review/Q&A" not in gaps,10)
    answer += points("ارسال/مرجوعی/ضمانت نزدیک تصمیم خرید" not in gaps,10)

    # 3) Citation readiness: stable, indexable, evidence-rich, answerable.
    citation=0
    citation += points(ix.get("technical_indexable") is True,25)
    citation += points(ix.get("self_canonical") is True,15)
    citation += points(ix.get("in_product_sitemap") is True,10)
    citation += points(content.get("description_words",0)>=300,15)
    citation += points(p.get("decision_links_present") is True,10)
    citation += points(len(missing_compat)==0,15)
    citation += points(content.get("image_count",0)>=4,10)

    # 4) Merchant discovery readiness. External submission itself is NOT scored as achieved.
    merchant=0
    checks=pr.get("checks") or {}
    merchant += points(checks.get("product_schema_present") is True,15)
    merchant += points(checks.get("offer_present") is True,15)
    merchant += points(checks.get("sku_match") is True,10)
    merchant += points(checks.get("availability_match") is not False,10)
    merchant += points(checks.get("price_parity")=="pass",15)
    merchant += points(bool(f.get("image_url")),10)
    merchant += points(bool(f.get("brand")),10)
    merchant += points("description" not in unresolved,10)
    merchant += points("price_iso4217_mapping" not in unresolved,5)

    # 5) Compatibility readiness.
    required=p.get("compatibility_required_fields") or []
    if required:
        compatibility=round(100*(len(required)-len(missing_compat))/len(required))
    else:
        compatibility=0

    # 6) Evidence readiness: conservative, based only on persisted observable evidence.
    evidence_non_video=0
    evidence_non_video += points(bool(f.get("brand")),15)
    evidence_non_video += points(content.get("all_image_alt_present") is True,10)
    evidence_non_video += points(content.get("image_count",0)>=4,15)
    evidence_non_video += points(len(missing_compat)==0,25)
    evidence_non_video += points(p.get("decision_links_present") is True,15)
    evidence_non_video += points("Verified Review/Q&A" not in gaps,10)

    # Keep the legacy composite for backwards compatibility, but expose a strict
    # non-video score so remediation can be evaluated without relying on video.
    evidence=evidence_non_video + points("ویدئو" not in gaps,10)

    scores={
      "ai_product_completeness":min(100,product_truth),
      "answer_readiness":min(100,answer),
      "citation_readiness":min(100,citation),
      "merchant_discovery_readiness":min(100,merchant),
      "compatibility_readiness":min(100,compatibility),
      "evidence_readiness":min(100,evidence)
    }
    overall=round(sum(scores.values())/len(scores),1)
    # In a video-excluded profile, renormalize the remaining evidence signals
    # (90 available points) back to a 0..100 scale instead of imposing an automatic
    # 10-point ceiling penalty for a workstream intentionally out of scope.
    evidence_non_video_normalized=round(100*evidence_non_video/90) if evidence_non_video else 0
    non_video_scores={**scores,"evidence_readiness":min(100,evidence_non_video_normalized)}
    overall_non_video=round(sum(non_video_scores.values())/len(non_video_scores),1)
    blockers=[]
    if not f.get("brand"): blockers.append("verified_brand_missing")
    if missing_compat: blockers.append("compatibility_fields_incomplete")
    if "description" in unresolved: blockers.append("feed_description_unresolved")
    if "price_iso4217_mapping" in unresolved: blockers.append("feed_currency_mapping_unresolved")
    if content.get("image_count",0)<4: blockers.append("real_media_set_incomplete")
    if "Verified Review/Q&A" in gaps: blockers.append("verified_review_qa_missing")
    if "ویدئو" in gaps: blockers.append("real_video_missing")
    if not ((ids.get("gtin") or {}).get("value")) and not ((ids.get("mpn") or {}).get("value") if isinstance(ids.get("mpn"),dict) else ids.get("mpn")):
        blockers.append("gtin_mpn_unknown_do_not_invent")
    rows.append({
      "rank":p.get("rank"),"product_id":pid,"name":p.get("name"),"url":p.get("permalink"),
      "scores":scores,"overall":overall,"ai_ready_85_plus":overall>=85,
      "non_video_scores":non_video_scores,"overall_non_video":overall_non_video,
      "non_video_ready_85_plus":overall_non_video>=85,
      "blockers":blockers,
      "policy":"Unknown product identifiers/specifications remain unknown until an authoritative source is available."
    })

rows.sort(key=lambda x:(x["overall"],-(x.get("rank") or 999)))
avg=lambda key: round(sum(x["scores"][key] for x in rows)/max(1,len(rows)),1)
summary={
  "products":len(rows),
  "overall_average":round(sum(x["overall"] for x in rows)/max(1,len(rows)),1),
  "ai_ready_85_plus":sum(1 for x in rows if x["ai_ready_85_plus"]),
  "below_85":sum(1 for x in rows if not x["ai_ready_85_plus"]),
  "non_video_overall_average":round(sum(x["overall_non_video"] for x in rows)/max(1,len(rows)),1),
  "non_video_ready_85_plus":sum(1 for x in rows if x["non_video_ready_85_plus"]),
  "non_video_below_85":sum(1 for x in rows if not x["non_video_ready_85_plus"]),
  "averages":{k:avg(k) for k in [
    "ai_product_completeness","answer_readiness","citation_readiness",
    "merchant_discovery_readiness","compatibility_readiness","evidence_readiness"
  ]},
  "external_product_feed_submitted":False,
  "direct_ai_citation_measurement_complete":False
}
blocker_counts={}
for x in rows:
    for b in x["blockers"]: blocker_counts[b]=blocker_counts.get(b,0)+1

out={
 "ok":True,
 "program":"K21 GEO/AEO AI Product Readiness",
 "version":"k21-ai-readiness-v4",
 "generated_at_utc":NOW,
 "mode":"read-only-scoring",
 "source_files":[
   "phase3-results/top30-pim.json",
   "phase19-results/product-discovery-readiness-feed-persisted.json",
   "geo-aeo-results/k21-openai-discovery-feed-draft.json",
   "phase3-results/page-schema-feed-parity.json",
   "phase3-results/top30-indexability.json"
 ],
 "summary":summary,
 "blocker_counts":dict(sorted(blocker_counts.items(), key=lambda kv:(-kv[1],kv[0]))),
 "products":rows,
 "guardrails":[
   "No GTIN, MPN, brand, technical specification, review, citation or recommendation is invented.",
   "A score is an internal readiness indicator, not a guarantee of ranking, citation or recommendation.",
   "External feed submission and direct AI answer-surface citations remain unearned until independently observed."
 ]
}
backlog=[]
priority_order=[
 "verified_brand_missing","compatibility_fields_incomplete","feed_description_unresolved",
 "feed_currency_mapping_unresolved","real_media_set_incomplete","verified_review_qa_missing",
 "real_video_missing","gtin_mpn_unknown_do_not_invent"
]
for b in priority_order:
    affected=[x["product_id"] for x in rows if b in x["blockers"]]
    if affected:
        backlog.append({
          "priority":"P1" if b in priority_order[:4] else "P2",
          "blocker":b,
          "affected_products":len(affected),
          "product_ids":affected,
          "acceptance":"Resolve only from verified first-party/manufacturer/catalog evidence; preserve unknown values otherwise."
        })

Path(ROOT/"geo-aeo-results").mkdir(exist_ok=True)
with open(ROOT/"geo-aeo-results/k21-ai-product-readiness.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
with open(ROOT/"geo-aeo-results/k21-ai-product-backlog.json","w",encoding="utf-8") as f:
    json.dump({"generated_at_utc":NOW,"program":out["program"],"summary":summary,"backlog":backlog},f,ensure_ascii=False,indent=2)
print("K21_AI_READINESS_OK",json.dumps(summary,ensure_ascii=False))
