#!/usr/bin/env python3
import os,json,re,html,requests
from datetime import datetime,timezone
BASE=os.environ['WP_BASE_URL'].rstrip('/')
AUTH=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
S=requests.Session();S.auth=AUTH;S.headers.update({'Accept':'application/json','User-Agent':'k20-seogod1-phase56/1.0'})
with open('phase3-results/top30-pim.json',encoding='utf-8') as f: top=json.load(f)
rows=[]
for x in top.get('products',[])[:20]:
    pid=int(x['product_id']); r=S.get(f'{BASE}/wp-json/wc/v3/products/{pid}',timeout=120); r.raise_for_status(); p=r.json()
    desc=p.get('description') or ''; short=p.get('short_description') or ''
    text=lambda v: re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(v or ''))).strip()
    corpus=(text(short)+' '+text(desc)).lower()
    pub={}
    try:
        pr=requests.get(p.get('permalink'),timeout=45,headers={'User-Agent':'k20-seogod1-phase56/1.0','Cache-Control':'no-cache'})
        body=pr.text[:1200000]
        pub={'http':pr.status_code,'bytes':len(pr.content),'product_schema':bool(re.search(r'"@type"\s*:\s*"Product"',body,re.I)),'offer_schema':bool(re.search(r'"@type"\s*:\s*"Offer"',body,re.I)),'faq_schema':bool(re.search(r'"@type"\s*:\s*"FAQPage"',body,re.I))}
    except Exception as e: pub={'error':type(e).__name__}
    brands=p.get('brands') or []
    row={
      'rank':x['rank'],'id':pid,'name':p.get('name'),'permalink':p.get('permalink'),'sku':p.get('sku'),
      'family':x.get('family'),'gsc':x.get('gsc'),'stock_status':p.get('stock_status'),'stock_quantity':p.get('stock_quantity'),
      'price':p.get('price'),'regular_price':p.get('regular_price'),'sale_price':p.get('sale_price'),
      'brand_names':[b.get('name') for b in brands if b.get('name')],
      'categories':p.get('categories') or [],'attributes':p.get('attributes') or [],'image_count':len(p.get('images') or []),
      'short_words':len(text(short).split()),'description_words':len(text(desc).split()),
      'decision_signals':{
        'suitable':any(k in corpus for k in ['مناسب','کاربرد','انتخاب']),
        'unsuitable':any(k in corpus for k in ['نامناسب','مناسب نیست','نخرید','محدودیت','قبل از خرید']),
        'shipping':any(k in corpus for k in ['ارسال','باربری','تحویل']),
        'returns':any(k in corpus for k in ['مرجوع','بازگشت','مغایرت','ضمانت']),
        'compatibility':any(k in corpus for k in ['سازگار','اتصال','سایز','واشر','مته','بست']),
        'alternatives':any(k in corpus for k in ['جایگزین','محصولات مرتبط','مکمل','همراه']),
        'qa':any(k in corpus for k in ['پرسش','سوالات رایج','سؤالات رایج','faq'])
      },'public_probe':pub,'modified_gmt':p.get('date_modified_gmt')
    }
    rows.append(row)
summary={
 'selected':len(rows),'in_stock':sum(1 for r in rows if r['stock_status']=='instock'),'out_of_stock':sum(1 for r in rows if r['stock_status']=='outofstock'),
 'priced':sum(1 for r in rows if str(r['price']).strip()),'one_image_only':sum(1 for r in rows if r['image_count']<=1),
 'shipping_signal':sum(1 for r in rows if r['decision_signals']['shipping']),'returns_signal':sum(1 for r in rows if r['decision_signals']['returns']),
 'unsuitable_signal':sum(1 for r in rows if r['decision_signals']['unsuitable']),'compatibility_signal':sum(1 for r in rows if r['decision_signals']['compatibility']),
 'product_schema':sum(1 for r in rows if r.get('public_probe',{}).get('product_schema')),
 'offer_schema':sum(1 for r in rows if r.get('public_probe',{}).get('offer_schema'))
}
os.makedirs('seo-god1-results',exist_ok=True)
out={'program':'SEO God1','phases':[5,6],'generated_at_utc':datetime.now(timezone.utc).isoformat(),'mode':'read-only','selection':'Top20 of current GSC/Woo commercial-priority cohort','summary':summary,'products':rows}
with open('seo-god1-results/phase05-06-top20-live-audit.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print('PHASE56_AUDIT_OK',json.dumps(summary,ensure_ascii=False))
