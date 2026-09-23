#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ready=json.loads((ROOT/"geo-aeo-results/k21-ai-product-readiness.json").read_text(encoding="utf-8"))
pq=json.loads((ROOT/"phase2-results/product-quality-score.json").read_text(encoding="utf-8"))
pq_by={int(x["id"]):x for x in pq.get("products",[]) if x.get("id")}
rows=[]
for x in sorted(ready.get("products",[]), key=lambda z:z.get("rank") or 999):
    q=pq_by.get(int(x["product_id"]),{})
    rows.append({
      "rank":x.get("rank"),"product_id":x["product_id"],"name":x["name"],
      "ai_readiness_overall":x["overall"],
      "ai_ready_85_plus":x["ai_ready_85_plus"],
      "scores":x["scores"],
      "product_quality_score":q.get("score"),
      "promote_ready":q.get("promote_ready"),
      "blockers":x.get("blockers",[]),
      "quality_gaps":q.get("gaps",[]),
    })
out={"summary":ready.get("summary"),"products":rows}
d=ROOT/"k21-top30-results"; d.mkdir(exist_ok=True)
(d/"final-top30-scores.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
lines=["# K21 Top30 Final Scores","",f"میانگین AI Readiness: **{ready.get('summary',{}).get('overall_average')}**","", "| رتبه | محصول | AI Readiness | Product Quality |", "|---:|---|---:|---:|"]
for r in rows:
    lines.append(f"| {r['rank']} | {r['name']} | {r['ai_readiness_overall']} | {r.get('product_quality_score') if r.get('product_quality_score') is not None else '-'} |")
(d/"final-top30-scores.md").write_text("\n".join(lines),encoding="utf-8")
print("K21_TOP30_REPORT_OK",len(rows),ready.get("summary",{}).get("overall_average"))
