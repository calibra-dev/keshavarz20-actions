#!/usr/bin/env python3
import json,os,requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime,timezone
from urllib.parse import urljoin
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(path):
 with open(os.path.join(ROOT,path),encoding='utf-8') as f:return json.load(f)
sc=load('growthos-phase10-input/searchconsole-snapshot-20260926.json')
bing=load('growthos-phase10-input/bing-status-20260926.json')
ga=load('growthos-phase10-input/ga4-ai-funnel-20260926.json')
tool_metrics=load('growthos-phase10-input/tool-page-metrics-20260926.json')
try:p9=load('growthos-phase9-results/summary.json')
except Exception:p9=load('growthos-phase9-results/independent-readback.json')
if not p9.get('ok'):raise SystemExit('Phase 9 verified readback is required before Phase 10.')
BASE=os.environ.get('WP_BASE_URL','').rstrip('/');AUTH=(os.environ.get('WP_USERNAME',''),os.environ.get('WP_APP_PASSWORD',''))
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-growthos-phase10/1.0'})
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.5,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(['GET']))
S.mount('https://',HTTPAdapter(max_retries=retry));S.mount('http://',HTTPAdapter(max_retries=retry))
def get(path,params=None):
 r=S.get(urljoin(BASE+'/',path.lstrip('/')),params=params,timeout=45);r.raise_for_status();return r.json()
targets=[('post',143698,'drip_calculator'),('page',144236,'layflat_calculator'),('page',144238,'filter_selector'),('page',144239,'compatibility_checker'),('page',144266,'pipe_size_selector'),('page',145233,'basket_builder'),('page',145234,'product_comparator'),('page',145286,'smart_proforma')]
instrument=[]
for kind,pid,key in targets:
 typ='posts' if kind=='post' else 'pages';o=get(f'wp-json/wp/v2/{typ}/{pid}',{'context':'edit'});raw=((o.get('content') or {}).get('raw') or '')
 instrument.append({'key':key,'id':pid,'flow_event':'growthos_flow_step' in raw,'tool_result_event':'growthos_tool_result' in raw,'tool_step_event':'growthos_tool_step' in raw,'phase9_marker':raw.count('K20-GROWTHOS-PHASE9-FLOW-START'),'verified':o.get('status')=='publish' and raw.count('K20-GROWTHOS-PHASE9-FLOW-START')==1 and 'growthos_flow_step' in raw})
HUBS=[('drip_tape','نوار تیپ'),('layflat_hose','لوله نخدار / لی‌فلت'),('tape_layflat_fittings','اتصالات نوار تیپ و لوله نخدار'),('pe_pipe_fittings','لوله و اتصالات پلی‌اتیلن'),('filtration','فیلتراسیون آبیاری')]
INTENTS=[
 ('informational',['{h} چیست و چه زمانی کاربرد دارد؟','مهم‌ترین مشخصات {h} برای تصمیم خرید چیست؟','محدودیت‌های استفاده از {h} چیست؟','برای شناخت فنی {h} چه داده‌ای باید از سازنده بگیریم؟']),
 ('selection',['برای یک پروژه واقعی چطور {h} مناسب را انتخاب کنم؟','برای انتخاب {h} چه ورودی‌هایی از مزرعه لازم است؟','چه زمانی نباید هنوز {h} را قطعی انتخاب کنم؟','بین مدل‌های {h} چه معیارهایی را اولویت بدهم؟']),
 ('comparison',['دو گزینه {h} را بر چه معیارهایی مقایسه کنیم؟','تفاوت مدل‌های {h} را چطور بدون حدس بررسی کنیم؟','برای مقایسه {h} کدام داده‌ها باید هم‌واحد باشند؟','چه زمانی مقایسه ظاهری {h} گمراه‌کننده است؟']),
 ('troubleshooting',['رایج‌ترین علت انتخاب اشتباه {h} چیست؟','اگر {h} بعد از نصب درست کار نکرد از کجا عیب‌یابی کنم؟','چه نشانه‌ای می‌گوید مشکل از سازگاری {h} است؟','برای جلوگیری از دوباره‌کاری در {h} چه چک‌لیستی لازم است؟']),
 ('commercial',['قبل از خرید {h} چه چیزهایی را در پیش‌فاکتور کنترل کنم؟','چه اقلام مکملی معمولاً همراه {h} باید بررسی شوند؟','قیمت {h} به چه مشخصات تأییدشده‌ای وابسته است؟','برای سفارش پروژه‌ای {h} چه اطلاعاتی به فروشنده بدهم؟']),
 ('project',['برای مزرعه یک هکتاری {h} را چطور وارد طراحی اولیه کنم؟','برای پروژه با چند زون {h} چگونه بررسی می‌شود؟','برای مسیر طولانی چه اطلاعاتی قبل از انتخاب {h} لازم است؟','در پروژه شیب‌دار انتخاب {h} به چه داده‌هایی وابسته است؟']),
 ('calculation',['برای محاسبه مقدار یا سایز {h} چه فرمول و ورودی‌هایی لازم است؟','چطور نتیجه محاسبه {h} را به سبد خرید تبدیل کنم؟','کدام فرضیات محاسبه {h} باید کنار نتیجه ثبت شوند؟','چه خروجی محاسباتی {h} هنوز نیازمند تأیید کارشناس است؟']),
 ('installation',['قبل از نصب {h} چه سازگاری‌هایی باید کنترل شود؟','ترتیب نصب {h} و قطعات مکمل چگونه بررسی می‌شود؟','چه ابزار یا آب‌بندی برای نصب {h} ممکن است لازم باشد؟','بعد از نصب {h} چه تست اولیه‌ای انجام دهیم؟']),
 ('maintenance',['برای نگهداری {h} چه مواردی را دوره‌ای بررسی کنیم؟','چه نشانه‌هایی در {h} هشدار نیاز به سرویس است؟','چه اشتباه نگهداری عمر {h} را کم می‌کند؟','چه داده‌ای از سرویس {h} باید ثبت شود؟']),
 ('local',['برای خرید و ارسال {h} به شهرستان چه اطلاعاتی لازم است؟','برای پروژه در فارس انتخاب {h} به چه شرایط محلی وابسته است؟','برای پروژه در خوزستان انتخاب {h} با آب و اقلیم چگونه بررسی می‌شود؟','برای دریافت پیش‌فاکتور {h} در استان‌های مختلف چه داده‌ای بفرستم؟'])]
prompts=[];n=1
for key,label in HUBS:
 for intent,templates in INTENTS:
  for t in templates:
   prompts.append({'prompt_id':f'P{n:03d}','language':'fa','hub':key,'intent':intent,'prompt':t.format(h=label),'google_ai':{'status':'not_run','cited':None,'page':None},'bing_ai':{'status':'not_run','cited':None,'citation_share':None,'intent':None,'topic':None},'chatgpt_search':{'status':'not_run','cited':None,'page':None,'brand_mentioned':None},'tested_at_utc':None,'notes':None});n+=1
assert len(prompts)==200
vis=sc.get('visible_query_page_totals') or {};irr=sc.get('irrigation_subset') or {};overall=(ga.get('overall') or {})
def ratio(a,b):return round(a/b,6) if b else None
sessions=float(overall.get('sessions') or 0);eng=float(overall.get('engaged_sessions') or 0);cart=float(overall.get('add_to_carts') or 0);checkout=float(overall.get('checkouts') or 0);purchases=float(overall.get('purchases') or 0);ai=((overall.get('ai_referral_visible_rows') or {}));ais=float(ai.get('sessions') or 0)
dashboard={'phase':10,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'search_console':{'date_min':sc.get('observed_date_min'),'date_max':sc.get('observed_date_max'),'rows':sc.get('row_count'),'visible_clicks':vis.get('clicks'),'visible_impressions':vis.get('impressions'),'irrigation_rows':irr.get('rows'),'irrigation_clicks':irr.get('clicks'),'irrigation_impressions':irr.get('impressions'),'tool_url_metrics':tool_metrics.get('tools')},'ga4':{'sessions':sessions,'engaged_sessions':eng,'engagement_rate_calc':ratio(eng,sessions),'key_events':overall.get('key_events'),'add_to_carts':cart,'checkouts':checkout,'purchases':purchases,'purchase_revenue':overall.get('purchase_revenue'),'cart_per_session':ratio(cart,sessions),'checkout_per_cart':ratio(checkout,cart),'purchase_per_checkout':ratio(purchases,checkout),'ai_referral_sessions':ais,'ai_referral_share_sessions':ratio(ais,sessions),'ai_referral_rows':ai.get('rows')},'bing':bing,'instrumentation':instrument}
events={'version':'growthos-event-taxonomy-v1','events':[{'event':'growthos_flow_step','surface':'all eight tools + decision hubs','purpose':'stage-to-stage navigation','required_params':['step','target','source_path']},{'event':'growthos_tool_result','surface':'pipe size selector','purpose':'calculation completed','required_params':['tool','step','flow_m3h','dmin_mm','data_complete']},{'event':'growthos_tool_step','surface':'smart proforma','purpose':'draft/add row/print/whatsapp actions','required_params':['tool','step']},{'event':'add_to_cart','surface':'WooCommerce/GA4','purpose':'basket conversion','required_params':[]},{'event':'begin_checkout','surface':'WooCommerce/GA4','purpose':'checkout start','required_params':[]},{'event':'purchase','surface':'WooCommerce/GA4','purpose':'transaction completion','required_params':[]}],'delivery_note':'Custom GrowthOS events are present in page code/dataLayer. GA4 reporting of custom events requires the site tag/GTM to forward or collect them; this phase does not assume that mapping exists until observed in GA4.'}
gaps={'google_generative_ai':{'official_report_exists':True,'available_globally_since':'2026-08-31','connector_status':'not_exposed_as_separate_fields_in current Windsor/GSC Wizard tools inspected in this run','action':'export/read Google Search Console Generative AI report when connector support is available; do not infer AI Overview/AI Mode impressions from ordinary web Search rows'},'bing_ai_performance':{'official_capabilities':['citations','grounding queries','intents','topics','citation share','compare'],'current_connector_status':bing.get('status'),'error':bing.get('error'),'interpretation':'measurement gap, not zero visibility'},'chatgpt_search':{'prompt_level_citation_api':'not available in current connected tools','ga4_observed_referrals':ai,'interpretation':'referral sessions are observed outcomes, not a full citation count'},'purchases':{'observed':purchases,'interpretation':'GA4 returned zero purchases in this window; this alone does not prove zero real orders or perfect purchase tracking.'}}
os.makedirs('growthos-phase10-results',exist_ok=True)
for name,obj in [('prompt-bank-200.json',prompts),('measurement-dashboard.json',dashboard),('event-taxonomy.json',events),('measurement-gaps.json',gaps),('instrumentation-audit.json',{'targets':instrument,'verified':sum(x['verified'] for x in instrument),'total':len(instrument)})]:json.dump(obj,open('growthos-phase10-results/'+name,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
inst_ok=all(x['verified'] for x in instrument)
summary={'ok':inst_ok and len(prompts)==200 and sc.get('row_count',0)>0 and overall.get('status')=='measured','phase':10,'version':'growthos-citation-geo-aio-measurement-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_MEASUREMENT_SYSTEM_ACTIVE_WITH_EXTERNAL_ENGINE_GAPS' if inst_ok else 'FAIL','prompt_bank_count':len(prompts),'instrumentation_verified':sum(x['verified'] for x in instrument),'instrumentation_total':len(instrument),'fresh_google_search_rows':sc.get('row_count'),'bing_status':bing.get('status'),'ga4_ai_referral_sessions':ais,'external_measurement_gaps_recorded':True,'fabricated_citation_counts':0,'next_measurement_gate':'Populate prompt-bank engine result fields only from direct engine observations or first-party AI reports.'}
json.dump(summary,open('growthos-phase10-results/summary.json','w',encoding='utf-8'),ensure_ascii=False,indent=2);print('GROWTHOS_PHASE10',json.dumps(summary,ensure_ascii=False))
