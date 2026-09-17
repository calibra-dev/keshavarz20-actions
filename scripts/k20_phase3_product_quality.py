#!/usr/bin/env python3
import json
from pathlib import Path

pim=json.load(open("phase3-results/top30-pim.json",encoding="utf-8"))
p2=json.load(open("phase2-results/product-quality-score.json",encoding="utf-8"))
parity=json.load(open("phase3-results/page-schema-feed-parity.json",encoding="utf-8"))
evidence=json.load(open("phase3-results/evidence-gate.json",encoding="utf-8"))

base={int(x["id"]):x for x in p2.get("products",[]) if x.get("id")}
par={int(x["product_id"]):x for x in parity.get("products",[])}
ev={int(x["product_id"]):x for x in evidence.get("products",[])}
rows=[]
for x in pim.get("products",[]):
    pid=int(x["product_id"]); b=base.get(pid,{})
    score=int(b.get("score") or 0)
    feed_points=3 if par.get(pid,{}).get("pass") else 0
    adjusted=min(100,score+feed_points)
    external=ev.get(pid,{}).get("required_external_evidence",[])
    rows.append({
      "rank":x["rank"],"product_id":pid,"name":x["name"],
      "phase2_base_score":score,"phase3_feed_points":feed_points,"phase3_score":adjusted,
      "promote_ready_85_plus":adjusted>=85,
      "pim_completeness_score":x.get("pim_completeness_score"),
      "external_evidence_blockers":external,
      "base_gaps":b.get("gaps",[])
    })
summary={
 "products":len(rows),
 "average_phase2_base":round(sum(x["phase2_base_score"] for x in rows)/len(rows),2) if rows else 0,
 "average_phase3_score":round(sum(x["phase3_score"] for x in rows)/len(rows),2) if rows else 0,
 "feed_points_awarded":sum(x["phase3_feed_points"] for x in rows),
 "products_with_feed_points":sum(1 for x in rows if x["phase3_feed_points"]==3),
 "ready_85_plus":sum(1 for x in rows if x["phase3_score"]>=85),
 "below_85":sum(1 for x in rows if x["phase3_score"]<85)
}
Path("phase3-results").mkdir(exist_ok=True)
json.dump({"ok":True,"version":"phase3-top30-product-quality-v1",
           "rule":"Phase 2 score reserved 3/10 Schema+Feed points for Phase 3. Award those 3 points only when live page/schema/feed parity passes.",
           "summary":summary,"products":rows},
          open("phase3-results/top30-product-quality-score.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("PHASE3_PRODUCT_QUALITY_OK",summary)
