#!/usr/bin/env python3
from __future__ import annotations
import base64, gzip, importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENC=ROOT/"phase24"/"import"/"20260927-direct-observations.json.gz.b64"
DEST=ROOT/"phase24"/"direct-observations-v2.json"
REPORT=ROOT/"phase24-results"/"direct-observation-ingest-2026-09-27.json"

spec=importlib.util.spec_from_file_location("p24",ROOT/"phase24"/"measurement_v2.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def main():
    raw=gzip.decompress(base64.b64decode(ENC.read_text(encoding="utf-8").strip()))
    incoming=json.loads(raw.decode("utf-8"))
    bank=json.loads((ROOT/"phase24"/"prompt-bank-200-fa.json").read_text(encoding="utf-8"))
    prompt_ids={x["prompt_id"] for x in bank["records"]}
    rows=incoming.get("observations") or []
    if len(rows)!=70:
        raise RuntimeError(f"expected 70 imported observations, got {len(rows)}")
    if len({x.get("observation_id") for x in rows})!=len(rows):
        raise RuntimeError("duplicate observation_id in import")
    if len({x.get("prompt_id") for x in rows})!=len(rows):
        raise RuntimeError("duplicate prompt_id in import")
    for obs in rows:
        m.validate_observation(obs,prompt_ids)
        if obs.get("readback_verified") is not True:
            raise RuntimeError(f"{obs.get('observation_id')}: readback_verified must be true")
    current=json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {"observations":[]}
    merged={x["observation_id"]:x for x in current.get("observations") or []}
    conflicts=[]
    for obs in rows:
        old=merged.get(obs["observation_id"])
        if old is not None and old!=obs:
            conflicts.append(obs["observation_id"])
        merged[obs["observation_id"]]=obs
    if conflicts:
        raise RuntimeError("conflicting existing observation ids: "+",".join(conflicts))
    ordered=sorted(merged.values(),key=lambda x:(x.get("prompt_id",""),x.get("surface","")))
    out={
      "schema_version":"2",
      "generated_at_utc":"2026-09-27T13:25:00Z",
      "accepted_evidence_type":"DIRECT_SURFACE_CAPTURE",
      "surfaces":list(m.PLATFORMS),
      "observations":ordered,
      "note":"Contains only validated direct answer-surface observations. Referral telemetry and ordinary web search remain excluded."
    }
    DEST.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    k=m.compute_direct_kpis(bank,out)
    report={
      "ok":True,
      "imported_observations":len(rows),
      "canonical_observations":len(ordered),
      "direct_surface_kpis":k,
      "surface_counts":{p:sum(1 for x in ordered if x["surface"]==p) for p in m.PLATFORMS},
      "readback_verified_count":sum(x.get("readback_verified") is True for x in ordered),
      "conflicts":conflicts
    }
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__": main()
