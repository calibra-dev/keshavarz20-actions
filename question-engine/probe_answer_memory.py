#!/usr/bin/env python3
import argparse, importlib.util, json, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe11",os.path.join(ROOT,"engine_v11.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--product-id",type=int,required=True); ap.add_argument("--result",required=True); a=ap.parse_args()
    for k in ("WP_BASE_URL","WP_USERNAME","WP_APP_PASSWORD"):
        if not os.environ.get(k,"").strip(): raise SystemExit(f"Missing secret {k}")
    cfg=m.q.b.load_cfg(); mem=m.v10.v9.read_answer_memory(a.product_id,cfg)
    out={
        "ok":True,"action":"answer_memory_probe","product_id":a.product_id,
        "answered":int(mem.get("answered") or 0),
        "topics":sorted(mem.get("topics") or []),
        "signals":sorted(mem.get("signals") or []),
        "question_ids":[int(x) for x in (mem.get("question_ids") or [])]
    }
    os.makedirs(os.path.dirname(a.result),exist_ok=True)
    with open(a.result,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False))
if __name__=="__main__":main()
