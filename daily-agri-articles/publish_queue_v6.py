#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import k20_sanitizer
spec = importlib.util.spec_from_file_location("article_v5", ROOT / "publish_queue_v5.py")
v5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v5)
base = v5.base

intent_spec = importlib.util.spec_from_file_location("intent_graph", ROOT / "intent_graph.py")
intent_graph = importlib.util.module_from_spec(intent_spec)
intent_spec.loader.exec_module(intent_graph)

previous_validate = base.validate_payload
ROLLOUT_DATE = "2026-09-27"


def _is_phase20_payload(p: dict) -> bool:
    if str(p.get("phase20_schema_version") or "").strip():
        return True
    generated = str(p.get("generated_at") or "")
    return generated[:10] >= ROLLOUT_DATE if len(generated) >= 10 else False


def validate_payload_v6(p):
    k20_sanitizer.sanitize_payload_inplace(p)
    previous_validate(p)
    if not _is_phase20_payload(p):
        return
    registry_path = REPO_ROOT / "growth-os" / "intent-registry.json"
    registry = intent_graph.load_json(registry_path) if registry_path.exists() else {"intents": []}
    try:
        intent_graph.validate_phase20_metadata(p, registry=registry)
    except ValueError as exc:
        raise base.QueuePublishError(f"Phase 20 intent gate: {exc}") from exc


base.validate_payload = validate_payload_v6

if __name__ == "__main__":
    base.main()
