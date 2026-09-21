#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'seo-god1'/'SEO-GOD1-REMAINING-MASTER-PLAN-20260921.json'
OUT=ROOT/'seo-god1-results'/'remaining-gate-latest.json'

plan=json.loads(PLAN.read_text(encoding='utf-8'))
waves=plan['waves']
result={
  'program':'SEO God1 Remaining Gate',
  'generated_at_utc':datetime.now(timezone.utc).isoformat(),
  'closed_no_repeat':plan['closed_no_repeat'],
  'release_blocker_count':len(plan['current_release_blockers']),
  'next_action':plan['immediate_next_action'],
  'waves':[{'wave':w['wave'],'name':w['name'],'priority':w['priority'],'state':w['state']} for w in waves],
  'guard':{
    'repeat_closed_audits':False,
    'fabricate_unknowns':False,
    'mass_internal_link_body_rewrite':False,
    'hidden_paid_video_generation':False,
    'unauthorized_payment_or_secret_mutation':False
  }
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('SEO_GOD1_REMAINING_GATE',json.dumps({'next_action':result['next_action'],'release_blocker_count':result['release_blocker_count']},ensure_ascii=False))
