from __future__ import annotations
import sys
from pathlib import Path

def add_product_engine_path() -> None:
    p=Path(__file__).resolve().parent / "product-engine"
    s=str(p)
    if s not in sys.path:
        sys.path.insert(0,s)
