#!/usr/bin/env python3
import importlib.util, json, os, re
from urllib import parse
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe3",os.path.join(ROOT,"engine_v3.py")); v3=importlib.util.module_from_spec(spec); spec.loader.exec_module(v3)
q=v3.q

orig_read_state=q.read_state

def choose_product_v4(products,state,rng):
    eligible=[p for p in products if p.get("status")=="publish" and p.get("reviews_allowed",True)]
    if not eligible: raise RuntimeError("No eligible published products with comments/reviews enabled")
    counts=state.get("product_counts") or {}; recent=set((state.get("recent_product_ids") or [])[:12])
    levels=sorted({int(counts.get(str(p["id"]),0)) for p in eligible})
    for level in levels:
        pool=[p for p in eligible if int(counts.get(str(p["id"]),0))==level and int(p["id"]) not in recent]
        if pool:return rng.choice(pool)
    pool=[p for p in eligible if int(p["id"]) not in recent]
    return rng.choice(pool or eligible)

def _is_colloquial(text):
    n=q.b.norm(text)
    return any(x in n for x in ["به نظرتون","جواب میده","چی بگیرم","یه سوال","میخوام","می‌خوام","میشه","می‌تونید"])

def _is_polite(text):
    return any(x in text for x in ["سلام","وقت بخیر","ممنون","سپاس","راهنمایی کنید","راهنمایی کنین","خسته نباشید"])

def recent_generated_comments(cfg,limit=50):
    wp=q.FastWP(); found={}
    for status in ("hold","approve"):
        params=parse.urlencode({"context":"edit","per_page":limit,"page":1,"orderby":"date_gmt","order":"desc","status":status,"search":cfg["author_name"],"_fields":"id,post,date,date_gmt,author_name,author_email,content,status,type"})
        try: _,rows,_=wp._call("GET","/wp-json/wp/v2/comments?"+params)
        except Exception: rows=[]
        for c in rows or []:
            if str(c.get("author_name") or "").strip()==cfg["author_name"].strip() or str(c.get("author_email") or "").strip().lower()==cfg["author_email"].strip().lower():
                found[int(c["id"])]=c
    return sorted(found.values(),key=lambda c:str(c.get("date_gmt") or c.get("date") or ""))

def read_state_reconciled(cfg):
    state=orig_read_state(cfg); rows=recent_generated_comments(cfg)
    if not rows:return state
    last_state_id=int(state.get("last_comment_id") or 0); last_time=q.b.parse_dt(state.get("last_success_utc"))
    missing=[]
    seen_last=(last_state_id==0)
    for c in rows:
        cid=int(c.get("id") or 0); when=q.b.parse_dt(c.get("date_gmt") or c.get("date"))
        if cid==last_state_id: seen_last=True; continue
        if last_time and when and when<=last_time: continue
        if last_state_id and not seen_last and last_time is None: continue
        missing.append(c)
    if not missing:return state
    for c in missing:
        pid=int(c.get("post") or 0); counts=state.setdefault("product_counts",{}); counts[str(pid)]=int(counts.get(str(pid),0))+1
        recent=[pid]+[int(x) for x in state.get("recent_product_ids",[]) if int(x)!=pid]; state["recent_product_ids"]=recent[:30]
        text=q.b.comment_text(c); state["sequence"]=int(state.get("sequence") or 0)+1; state["total"]=int(state.get("total") or 0)+1
        state["colloquial"]=int(state.get("colloquial") or 0)+int(_is_colloquial(text)); state["polite"]=int(state.get("polite") or 0)+int(_is_polite(text))
        state["last_success_utc"]=str(c.get("date_gmt") or c.get("date")); state["last_comment_id"]=int(c.get("id") or 0)
    q.write_state(cfg,state)
    return state

q.choose_product=choose_product_v4
q.read_state=read_state_reconciled

def main(): q.main()
if __name__=="__main__":main()
