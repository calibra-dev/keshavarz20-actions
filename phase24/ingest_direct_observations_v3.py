#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"phase24"/"direct-observations-v3.json"
BANK=ROOT/"phase24"/"prompt-bank-200-fa.json"

spec=importlib.util.spec_from_file_location("p24v3",ROOT/"phase24"/"measurement_v3.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def load_payload(path: Path) -> dict[str, Any]:
    if path.name.endswith(".json.gz.b64"):
        raw=gzip.decompress(base64.b64decode(path.read_text(encoding="utf-8").strip()))
        return json.loads(raw.decode("utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def obs_key(x: dict[str, Any]) -> tuple[str,str]:
    return str(x.get("observation_id") or ""), str(x.get("prompt_id") or "")


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="JSON or .json.gz.b64 capture file; repeatable")
    ap.add_argument("--report", default="phase24-results/direct-observation-ingest-v3-latest.json")
    args=ap.parse_args()

    bank=json.loads(BANK.read_text(encoding="utf-8"))
    current=json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {
        "schema_version":"3","accepted_evidence_type":"DIRECT_SURFACE_CAPTURE",
        "surfaces":list(m.PLATFORMS),"observations":[]
    }
    m.validate_observations(bank,current)

    by_id={str(x["observation_id"]):x for x in current.get("observations") or []}
    by_prompt={str(x["prompt_id"]):x for x in current.get("observations") or []}
    imported=0
    ignored_identical=0
    files=[]
    for raw_path in args.input:
        path=Path(raw_path)
        payload=load_payload(path)
        rows=payload.get("observations") or []
        if not rows:
            raise RuntimeError(f"{path}: no observations")
        candidate={"observations":rows}
        m.validate_observations(bank,candidate)
        files.append(str(path))
        for obs in rows:
            oid=str(obs["observation_id"]); pid=str(obs["prompt_id"])
            old_by_id=by_id.get(oid)
            old_by_prompt=by_prompt.get(pid)
            if old_by_id is not None and old_by_id != obs:
                raise RuntimeError(f"conflicting observation_id: {oid}")
            if old_by_prompt is not None and old_by_prompt != obs:
                raise RuntimeError(f"conflicting prompt_id already observed: {pid}")
            if old_by_id is not None or old_by_prompt is not None:
                ignored_identical+=1
                continue
            by_id[oid]=obs; by_prompt[pid]=obs; imported+=1

    ordered=sorted(by_id.values(),key=lambda x:(x.get("prompt_id",""),x.get("surface","")))
    merged={
        "schema_version":"3",
        "accepted_evidence_type":"DIRECT_SURFACE_CAPTURE",
        "surfaces":list(m.PLATFORMS),
        "observations":ordered,
        "note":"Canonical v3 registry. Only guarded, readback-verified direct answer-surface captures are accepted."
    }
    m.validate_observations(bank,merged)
    REGISTRY.write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    kpis=m.compute_direct_kpis(bank,merged)
    surface_counts={p:kpis["by_surface"][p]["observations"] for p in m.PLATFORMS}
    report={
        "ok":True,
        "input_files":files,
        "imported_new_observations":imported,
        "ignored_identical":ignored_identical,
        "canonical_observations":len(ordered),
        "surface_counts":surface_counts,
        "direct_surface_kpis":kpis,
        "readback_verified_count":sum(x.get("readback_verified") is True for x in ordered),
        "fabricated_observations":0,
        "full_200_complete":len(ordered)==200 and all(v==50 for v in surface_counts.values()),
    }
    out=ROOT/args.report
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
