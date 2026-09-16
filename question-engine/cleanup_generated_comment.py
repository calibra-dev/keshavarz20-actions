#!/usr/bin/env python3
import argparse, importlib.util, json, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe11",os.path.join(ROOT,"engine_v11.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
q=m.q

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--comment-id",type=int,required=True); ap.add_argument("--expected-product-id",type=int,required=True); ap.add_argument("--result",required=True); a=ap.parse_args()
    for k in ("WP_BASE_URL","WP_USERNAME","WP_APP_PASSWORD"):
        if not os.environ.get(k,"").strip():raise SystemExit(f"Missing secret {k}")
    cfg=q.b.load_cfg(); wp=q.FastWP()
    _,c,_=wp._call("GET",f"/wp-json/wp/v2/comments/{a.comment_id}?context=edit")
    if int(c.get("post") or 0)!=a.expected_product_id:raise RuntimeError("Cleanup product mismatch")
    if not m.v10.v9._is_generated(c,cfg):raise RuntimeError("Cleanup refused: comment is not engine-generated")
    if str(c.get("status") or "")!="hold":raise RuntimeError("Cleanup refused: comment is not pending/hold")
    if str(c.get("type") or "comment")!="comment":raise RuntimeError("Cleanup refused: unexpected comment type")
    _,deleted,_=wp._call("DELETE",f"/wp-json/wp/v2/comments/{a.comment_id}?force=true")
    if not isinstance(deleted,dict) or not deleted.get("deleted"):raise RuntimeError("Cleanup delete was not confirmed")
    missing=False
    try:wp._call("GET",f"/wp-json/wp/v2/comments/{a.comment_id}?context=edit")
    except RuntimeError as exc:
        missing="HTTP 404" in str(exc)
    if not missing:raise RuntimeError("Cleanup readback did not confirm 404")
    out={"ok":True,"action":"cleanup_generated_comment","comment_id":a.comment_id,"product_id":a.expected_product_id,"verified_deleted":True}
    os.makedirs(os.path.dirname(a.result),exist_ok=True)
    with open(a.result,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False))
if __name__=="__main__":main()
