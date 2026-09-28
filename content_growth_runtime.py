from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
MASTER_PROMPT_PATH = REPO_ROOT / "content-growth" / "K20_CONTENT_GROWTH_MASTER_PROMPT_V2.md"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import k20_sanitizer


def load_master_prompt() -> str:
    return MASTER_PROMPT_PATH.read_text(encoding="utf-8")


def safe_json_from_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        import re
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r"(\{.*\})", raw, flags=re.S)
        if not m:
            raise
        value = json.loads(m.group(1))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object from the content-growth model")
    return value


def _external_clean_text(value: str) -> str:
    scripts = os.environ.get("K20_WATERMARK_SCRIPTS", "").strip()
    if not scripts:
        return k20_sanitizer.sanitize_text(value)
    cleaner = Path(scripts) / "clean_text.py"
    if not cleaner.exists():
        return k20_sanitizer.sanitize_text(value)
    with tempfile.TemporaryDirectory(prefix="k20-wm-") as td:
        src = Path(td) / "input.txt"
        dst = Path(td) / "output.txt"
        src.write_text(value, encoding="utf-8")
        cmd = [
            sys.executable, str(cleaner), str(src), "-o", str(dst),
            "--no-normalize-spaces",
        ]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        if cp.returncode != 0 or not dst.exists():
            raise RuntimeError(
                "watermarks-remover clean_text failed: "
                + (cp.stderr or cp.stdout or f"exit={cp.returncode}")[-1200:]
            )
        cleaned = dst.read_text(encoding="utf-8")
    return k20_sanitizer.sanitize_text(cleaned)


def clean_user_facing_fields(payload: dict[str, Any], fields: list[str]) -> dict[str, int]:
    cleaned_count = 0
    for field in fields:
        if field not in payload:
            continue
        value = payload[field]
        if isinstance(value, str):
            payload[field] = _external_clean_text(value)
            cleaned_count += 1
        elif isinstance(value, list):
            out = []
            for item in value:
                if isinstance(item, str):
                    out.append(_external_clean_text(item))
                elif isinstance(item, dict):
                    row = {}
                    for k, v in item.items():
                        row[k] = _external_clean_text(v) if isinstance(v, str) else v
                    out.append(row)
                else:
                    out.append(item)
            payload[field] = out
            cleaned_count += 1
    k20_sanitizer.sanitize_payload_inplace(payload)
    k20_sanitizer.assert_clean(payload)
    return {"fields_cleaned": cleaned_count}


def assert_safe_content_html(value: str) -> None:
    low = (value or "").lower()
    forbidden = ("<script", "<style", "application/ld+json", "<iframe", "javascript:")
    found = [x for x in forbidden if x in low]
    if found:
        raise ValueError("Unsafe/heavy markup in content_html: " + ", ".join(found))
