from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# Persian U+200C ZWNJ is a valid half-space and is intentionally preserved.
_DROP = {
    0x200B, 0x200D, 0x2060, 0xFEFF,
    0x200E, 0x200F,
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    0x2066, 0x2067, 0x2068, 0x2069,
}
_SPACES = {0x00A0, 0x1680, 0x180E, 0x202F, 0x205F, 0x3000}
_TAG_MIN = 0xE0000
_TAG_MAX = 0xE007F

def sanitize_text(value: str) -> str:
    out = []
    for ch in str(value):
        cp = ord(ch)
        if cp in _DROP or _TAG_MIN <= cp <= _TAG_MAX:
            continue
        out.append(" " if cp in _SPACES else ch)
    return "".join(out)

def scan_text(value: str) -> dict[str, int]:
    out = {"hidden_controls": 0, "tag_characters": 0, "odd_spaces": 0}
    for ch in str(value):
        cp = ord(ch)
        if cp in _DROP:
            out["hidden_controls"] += 1
        elif _TAG_MIN <= cp <= _TAG_MAX:
            out["tag_characters"] += 1
        elif cp in _SPACES:
            out["odd_spaces"] += 1
    return out

def sanitize_obj(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_obj(v) for v in value]
    if isinstance(value, tuple):
        return tuple(sanitize_obj(v) for v in value)
    if isinstance(value, dict):
        return {k: sanitize_obj(v) for k, v in value.items()}
    return value

def scan_obj(value: Any) -> dict[str, int]:
    total = {"hidden_controls": 0, "tag_characters": 0, "odd_spaces": 0}
    def walk(v: Any) -> None:
        if isinstance(v, str):
            cur = scan_text(v)
            for k in total:
                total[k] += cur[k]
        elif isinstance(v, list):
            for x in v: walk(x)
        elif isinstance(v, dict):
            for x in v.values(): walk(x)
    walk(value)
    return total

def assert_clean(value: Any) -> None:
    residual = scan_obj(value)
    if any(residual.values()):
        raise ValueError(f"K20 sanitizer verification failed: {residual}")

def sanitize_payload_inplace(value: Any) -> dict[str, int]:
    before = scan_obj(value)
    def walk(v: Any) -> Any:
        if isinstance(v, str):
            return sanitize_text(v)
        if isinstance(v, list):
            for i, x in enumerate(v): v[i] = walk(x)
            return v
        if isinstance(v, dict):
            for k in list(v): v[k] = walk(v[k])
            return v
        return v
    walk(value)
    assert_clean(value)
    return before

def sanitize_json_file(path: str | Path, output: str | Path | None = None) -> dict[str, Any]:
    src = Path(path)
    payload = json.loads(src.read_text(encoding="utf-8"))
    removed = sanitize_payload_inplace(payload)
    dst = Path(output) if output else src
    dst.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"input": str(src), "output": str(dst), "removed": removed, "clean": True}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="json_path")
    ap.add_argument("--output")
    ap.add_argument("--check", dest="check_path")
    args = ap.parse_args()
    if args.json_path:
        print(json.dumps(sanitize_json_file(args.json_path, args.output), ensure_ascii=False))
        return 0
    if args.check_path:
        payload = json.loads(Path(args.check_path).read_text(encoding="utf-8"))
        residual = scan_obj(payload)
        clean = not any(residual.values())
        print(json.dumps({"input": args.check_path, "clean": clean, "residual": residual}, ensure_ascii=False))
        return 0 if clean else 2
    ap.error("Provide --json or --check")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
