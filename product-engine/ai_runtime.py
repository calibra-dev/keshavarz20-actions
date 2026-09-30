from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
import k20_sanitizer

MASTER = Path(__file__).resolve().parent / "MASTER_PROMPT_V1.md"
API_KEY = os.environ.get("OPENAI_API_KEY","").strip()
MODEL = os.environ.get("OPENAI_PRODUCT_MODEL") or os.environ.get("OPENAI_TEXT_MODEL") or "gpt-5.6"

class ModelAccessError(RuntimeError):
    pass

def _collect_urls(value: Any, urls: set[str]) -> None:
    if isinstance(value,dict):
        url=value.get("url")
        if isinstance(url,str) and url.startswith("http"):
            urls.add(url)
        for v in value.values():
            _collect_urls(v,urls)
    elif isinstance(value,list):
        for v in value:
            _collect_urls(v,urls)

def _client() -> OpenAI:
    if not API_KEY:
        raise ModelAccessError("OPENAI_API_KEY is not configured for product-engine")
    return OpenAI(api_key=API_KEY)

def research(product: dict[str,Any]) -> tuple[str,list[str]]:
    prompt=f"""Deep-research this exact Keshavarz20 WooCommerce product for commercial page remediation.

Requirements:
- Search the live web.
- Exact model/product evidence only; do not transfer specs from a similar item.
- Prefer manufacturer, label, official datasheet, regulator/standard, then independent technical sources.
- Identify buyer intent, commercial objections, selection risk, compatibility limits, installation/use issues and evidence gaps.
- Do not write the final page.
- Do not invent a fact if exact evidence is absent.

LIVE PRODUCT DATA:
{json.dumps(product,ensure_ascii=False)}
"""
    response=_client().responses.create(
        model=MODEL,
        reasoning={"effort":"high"},
        tools=[{"type":"web_search"}],
        input=prompt,
    )
    urls:set[str]=set()
    try:
        _collect_urls(response.model_dump(),urls)
    except Exception:
        pass
    return response.output_text,sorted(urls)

def _parse_json(raw: str) -> dict[str,Any]:
    value=(raw or "").strip()
    fence=chr(96)*3
    if value.startswith(fence):
        value=value.split("\n",1)[1] if "\n" in value else value[len(fence):]
    if value.endswith(fence):
        value=value[:-len(fence)].rstrip()
    try:
        obj=json.loads(value)
    except json.JSONDecodeError:
        match=re.search(r"(\{.*\})",value,flags=re.S)
        if not match:
            raise
        obj=json.loads(match.group(1))
    if not isinstance(obj,dict):
        raise ValueError("Product model output must be a JSON object")
    return obj

def compose(product: dict[str,Any], research_report: str, source_urls: list[str], feedback: str="") -> dict[str,Any]:
    master=MASTER.read_text(encoding="utf-8")
    prompt=f"""{master}

LIVE PRODUCT DATA:
{json.dumps(product,ensure_ascii=False)}

LIVE RESEARCH REPORT:
{research_report}

RESEARCH SOURCE URL ALLOW-LIST:
{json.dumps(source_urls,ensure_ascii=False)}

PREVIOUS VALIDATION FEEDBACK:
{feedback or "none"}

Return the exact JSON contract only.
Any claim evidence_url must be from RESEARCH SOURCE URL ALLOW-LIST.
Do not make the structure or sentences imitate another product.
"""
    response=_client().responses.create(
        model=MODEL,
        reasoning={"effort":"high"},
        input=prompt,
    )
    obj=_parse_json(response.output_text)
    k20_sanitizer.sanitize_payload_inplace(obj)
    k20_sanitizer.assert_clean(obj)
    return obj
