#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location("news_base",ROOT/"daily-agri-news"/"publish_queue.py")
news=importlib.util.module_from_spec(spec); spec.loader.exec_module(news)
out=Path(sys.argv[1]); out.parent.mkdir(parents=True,exist_ok=True)
try:
    titles=news.recent_news_titles(limit=5)
    result={"ok":True,"read_only":True,"post_type":"news","sample_title_count":len(titles),"writes_performed":0}
except Exception as exc:
    result={"ok":False,"read_only":True,"post_type":"news","sample_title_count":0,"writes_performed":0,"error":str(exc)}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE18_NEWS_READ_PROBE",json.dumps(result,ensure_ascii=False))
if not result["ok"]: raise SystemExit(2)
