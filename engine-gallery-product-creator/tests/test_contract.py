#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RULES=ROOT/"engine-gallery-product-creator"/"config"/"category-rules.json"

def main():
    r=json.loads(RULES.read_text(encoding="utf-8"))
    assert r["output"]["slides_per_product"]==5
    assert r["output"]["width"]==1000 and r["output"]["height"]==1000
    general=r["general_pipe_fitting_size_map_mm_to_inch"]
    assert general["63"]=="2"
    assert general["50"]=="1-1/2"
    threaded=r["threaded_layflat_only_outer_inch_to_inner_mm"]
    assert threaded["2"]==50
    assert threaded["4.5"]==110
    assert threaded["8"]==200
    assert "mist-pipe" in r["categories"]
    assert "threaded-layflat" in r["categories"]
    print(json.dumps({"ok":True,"engine":"engine-gallery-product-creator","tests":"config-contract"}))
if __name__=="__main__": main()
