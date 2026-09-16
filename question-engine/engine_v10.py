#!/usr/bin/env python3
import importlib.util, os
from urllib import parse

ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe9",os.path.join(ROOT,"engine_v9.py")); v9=importlib.util.module_from_spec(spec); spec.loader.exec_module(v9)
q=v9.q


def recent_generated_comments_v10(cfg,limit=100):
    wp=q.FastWP(); found={}; per=max(1,min(100,int(limit or 100)))
    for status in ("hold","approve"):
        params=parse.urlencode({
            "context":"edit","per_page":per,"page":1,"orderby":"date_gmt","order":"desc","status":status,
            "search":cfg["author_name"],
            "_fields":"id,post,parent,date,date_gmt,author_name,author_email,content,status,type"
        })
        try:
            _,rows,_=wp._call("GET","/wp-json/wp/v2/comments?"+params)
        except Exception:
            rows=[]
        for c in rows or []:
            if v9._is_generated(c,cfg):
                found[int(c["id"])]=c
    return sorted(found.values(),key=lambda c:str(c.get("date_gmt") or c.get("date") or ""),reverse=True)

q.recent_generated_comments=recent_generated_comments_v10


def main():q.main()
if __name__=="__main__":main()
