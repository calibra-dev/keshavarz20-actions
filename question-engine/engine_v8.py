#!/usr/bin/env python3
import importlib.util, os
ROOT=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("qe7",os.path.join(ROOT,"engine_v7.py")); v7=importlib.util.module_from_spec(spec); spec.loader.exec_module(v7)
q=v7.q
orig_candidates=q.guarded_candidates
orig_guard=q.consistency_guard

FAKE_TESTIMONIAL_PHRASES=[
    "من استفاده کردم عالی بود",
    "من استفاده کردم خیلی خوب بود",
    "من استفاده کردم راضی بودم",
    "خیلی راضی بودم",
    "کاملا راضی بودم",
    "کاملاً راضی بودم",
    "عالی بود و پیشنهاد",
    "حتما پیشنهاد می کنم",
    "حتماً پیشنهاد می کنم",
    "پیشنهادش می کنم",
    "پیشنهادش می‌کنم",
]

def kb(name, fallback):
    return q.b._KB.get(name) or fallback

def add(out,intent,key,core):
    out.append({"intent":intent,"key":key,"core":core})

def candidates_v8(p,fam,style,rng):
    out=orig_candidates(p,fam,style,rng)
    name=q.b.ref_name(p)
    if fam=="fertilizer":
        crop=rng.choice(q.b.CROPS)
        stage=rng.choice(kb("growth_stages_annual",["رشد رویشی","گلدهی","تشکیل میوه"]))
        add(out,"experience_request",f"experience:fertilizer:{q.b.norm(crop)}:{q.b.norm(stage)}",
            f"کسی تجربه واقعی استفاده از {name} برای {crop} در مرحله {stage} رو داره؟ روش مصرف و نتیجه‌ای که دیده رو میشه بگه")
        add(out,"experience_request","experience:fertilizer:conditions",
            f"اگر کسی {name} رو در شرایط آب یا خاک سخت‌تر استفاده کرده، ممنون میشم تجربه واقعی‌اش از نحوه مصرف و نتیجه رو بگه")
    elif fam=="pesticide":
        crop=rng.choice(q.b.CROPS)
        add(out,"experience_request",f"experience:pesticide:{q.b.norm(crop)}",
            f"کسی تجربه واقعی استفاده از {name} روی {crop} داره؟ برای چه آفت یا بیماری و تحت چه شرایطی استفاده کرده و نتیجه چطور بوده")
        add(out,"experience_request","experience:pesticide:conditions",
            f"اگر کسی قبلاً از {name} استفاده کرده، ممنون میشم بگه شرایط هوا، زمان مصرف و شدت آلودگی روی نتیجه چقدر اثر داشته")
    elif fam=="drip_tape":
        terrain=rng.choice(kb("terrain_conditions",["شیب ملایم","شیب متوسط"])); crop=rng.choice(q.b.CROPS)
        add(out,"experience_request",f"experience:driptape:{q.b.norm(terrain)}",
            f"کسی این مدل نوار تیپ رو یک فصل روی زمین با {terrain} استفاده کرده؟ یکنواختی آبدهی و دوامش در عمل چطور بوده")
        add(out,"experience_request",f"experience:driptape:{q.b.norm(crop)}",
            f"اگر کسی برای کشت {crop} از این مدل تیپ استفاده کرده، تجربه واقعی‌اش از فاصله خروجی‌ها، گرفتگی و طول ردیف چطور بوده")
    elif fam=="pipe":
        add(out,"experience_request","experience:pipe:long-run",
            f"کسی از {name} برای مسیر انتقال چندصد متری استفاده کرده؟ در عمل از نظر افت فشار، جمع‌کردن و دوام چه تجربه‌ای داشته")
        add(out,"experience_request","experience:pipe:season",
            f"اگر کسی یک فصل کامل از {name} زیر آفتاب و فضای باز استفاده کرده، ممنون میشم تجربه‌اش از دوام و نگهداری رو بگه")
    elif fam=="fitting":
        add(out,"experience_request","experience:fitting:durability",
            f"کسی مدتی از {name} استفاده کرده؟ از نظر نشتی، لقی، آب‌بندی و دوام اتصال در استفاده واقعی چه تجربه‌ای داشته")
        add(out,"experience_request","experience:fitting:install",
            f"اگر کسی {name} رو خودش یا با نصاب نصب کرده، کدوم نکته نصب بیشترین تاثیر رو روی آب‌بندی و محکم موندن اتصال داشته")
    elif fam=="valve":
        add(out,"experience_request","experience:valve:durability",
            f"کسی مدتی از {name} استفاده کرده؟ از نظر نشتی، روان بودن باز و بسته شدن و دوام اتصال در استفاده واقعی چه تجربه‌ای داشته")
        add(out,"experience_request","experience:valve:install",
            f"اگر کسی {name} رو خودش یا با نصاب نصب کرده، کدوم نکته نصب بیشترین تاثیر رو روی آب‌بندی و عملکرد شیر داشته")
    elif fam=="filter":
        add(out,"experience_request","experience:filter:well-water",
            f"کسی {name} رو روی آب چاه دارای شن یا رسوب استفاده کرده؟ فاصله شست‌وشو و افت فشارش در عمل چطور بوده")
        add(out,"experience_request","experience:filter:maintenance",
            f"اگر کسی مدت طولانی از {name} استفاده کرده، ممنون میشم تجربه‌اش از سرویس، تمیزکاری و گرفتگی رو بگه")
    elif fam=="fertigation":
        add(out,"experience_request","experience:fertigation:field",
            f"کسی از {name} برای تزریق کود در سیستم قطره‌ای استفاده کرده؟ کنترل تزریق و کار باهاش در مزرعه چطور بوده")
    elif fam=="sprinkler":
        add(out,"experience_request","experience:sprinkler:wind",
            f"کسی از {name} در زمین بادخیز یا با فشار متغیر استفاده کرده؟ یکنواختی پاشش در عمل چطور بوده")
    else:
        add(out,"experience_request",f"experience:generic:{fam}",
            f"کسی تجربه واقعی استفاده از {name} رو داره؟ بیشتر از چه نظر راضی یا ناراضی بوده و چه نکته‌ای قبل خرید باید بدونم")
    return out

def guard_v8(p,candidate,question):
    ok,reason=orig_guard(p,candidate,question)
    if not ok:return ok,reason
    text=q.b.norm(question)
    for phrase in FAKE_TESTIMONIAL_PHRASES:
        if q.b.norm(phrase) in text:
            return False,"generated testimonial claim is not allowed"
    if candidate.get("intent")=="experience_request" and not any(x in text for x in ["کسی","اگر کسی","تجربه واقعی","تجربه اش","تجربه‌اش"]):
        return False,"experience prompt must request real user experience"
    return True,None

q.guarded_candidates=candidates_v8
q.consistency_guard=guard_v8

def main():q.main()
if __name__=="__main__":main()
