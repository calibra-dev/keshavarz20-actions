import json
import pathlib
from collections import Counter
from datetime import datetime, timezone

ROOT=pathlib.Path('.')
MAIN=ROOT/'media-autopilot/state.json'
RESCUE=ROOT/'media-rest-rescue/state.json'
OUT=ROOT/'media-rest-rescue/summary.json'

def load(p): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
main=load(MAIN); rescue=load(RESCUE)
terminal=main.get('terminal_skips') or {}
exhausted={k:v for k,v in terminal.items() if str((v or {}).get('reason') or '').startswith('max_attempts_exhausted:')}
quality={k:v for k,v in terminal.items() if 'no WebP candidate met quality and saving guards' in str((v or {}).get('reason') or '')}
other={k:v for k,v in terminal.items() if k not in exhausted and k not in quality}
processed=rescue.get('processed') or {}
skipped=rescue.get('skipped') or {}
unattempted=sorted(k for k in exhausted if k not in processed and k not in skipped)
skip_reasons=Counter(str((v or {}).get('reason') or '') for v in skipped.values())
summary={
  'executed_at_utc':now(),
  'main_status':main.get('status'),
  'main_successful_migrations':int(main.get('successful_migrations') or 0),
  'main_terminal_total':len(terminal),
  'main_exhausted_for_rescue':len(exhausted),
  'main_quality_terminal':len(quality),
  'main_other_terminal':len(other),
  'rescue_status':rescue.get('status'),
  'rescue_successful_migrations':int(rescue.get('successful_migrations') or 0),
  'rescue_processed_keys':len(processed),
  'rescue_skipped_keys':len(skipped),
  'rescue_unattempted_keys':len(unattempted),
  'rescue_critical_events':len(rescue.get('critical_events') or []),
  'rescue_skip_reasons':dict(skip_reasons),
  'unattempted_keys':unattempted,
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='unattempted_keys'},ensure_ascii=False))
