#!/usr/bin/env python3
import importlib.util, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe10",os.path.join(ROOT,"engine_v10.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
assert callable(m.recent_generated_comments_v10)
assert m.q.recent_generated_comments is m.recent_generated_comments_v10
cfg={"watchdog_enabled":True,"watchdog_max_pending":60,"watchdog_max_consecutive_failures":3,"comment_status":"hold"}
assert m.v9.watchdog_reason(cfg,{"watchdog":{"consecutive_failures":0}},{"pending_generated":0,"unexpected_types":[]},True) is None
print("PASS v10")
