import importlib.util, os, json, random
p=os.path.join(os.path.dirname(__file__),"engine.py")
s=importlib.util.spec_from_file_location("qe",p); qe=importlib.util.module_from_spec(s); s.loader.exec_module(qe)

def product(name,cats=None,desc=""):
    return {"id":1,"name":name,"status":"publish","reviews_allowed":True,"categories":[{"name":x} for x in (cats or [])],"tags":[],"attributes":[],"description":desc,"short_description":""}

def main():
    cases={
      "کود پتاس بالا":"fertilizer","نوار تیپ 20 سانت":"drip_tape","لوله نخدار 3 اینچ":"pipe","شیر توپی 2 اینچ":"valve","فیلتر دیسکی 3 اینچ":"filter","تانک کود 200 لیتری":"fertigation","کمربند پلی اتیلن 63":"fitting","آبپاش تنظیمی":"sprinkler"
    }
    for n,want in cases.items():
        got=qe.family(product(n)); assert got==want,(n,got,want)
    cfg=json.load(open(os.path.join(os.path.dirname(__file__),"config.json"),encoding="utf-8"))
    rng=random.Random(2)
    for n,want in cases.items():
        p=product(n); c=qe.core_candidates(p,want,"conversational",rng); assert len(c)>=5,(n,len(c)); assert all(x["key"] and x["core"] for x in c)
        q=qe.wrap(c[0]["core"],True,"conversational",rng); assert "؟" in q
    assert 1080 <= qe.stable_jitter("x",1080,1559) <= 1559
    assert qe.jaccard("سلام این محصول برای ذرت خوبه", "این محصول برای ذرت خوبه") > .5
    print("PASS")
if __name__=="__main__":main()
