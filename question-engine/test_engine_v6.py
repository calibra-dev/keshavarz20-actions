import importlib.util, os, random
p=os.path.join(os.path.dirname(__file__),"engine_v6.py")
s=importlib.util.spec_from_file_location("qe6",p); q=importlib.util.module_from_spec(s); s.loader.exec_module(q)

def prod(name): return {"id":1,"name":name,"status":"publish","reviews_allowed":True,"permalink":"https://example.test/p","categories":[],"tags":[],"attributes":[],"description":"","short_description":""}

def main():
    rng=random.Random(11)
    for style in ["colloquial","conversational","experienced","technical"]:
        for _ in range(100):
            text=q.wrap_v6("این محصول برای شرایط من مناسبه؟",True,style,rng)
            assert text.count("راهنمایی")<=1,text
            assert "؟" in text
    tee=prod("سه راه ماده مساوی 90 میلیمتر پلی اتیلن")
    cs=q.candidates_v6(tee,"fitting","conversational",rng)
    c=[x for x in cs if x.get("key")=="tee:three-branches"][0]
    assert "دو سر پلی‌اتیلن" in c["core"] and "رزوه ماده" in c["core"]
    print("PASS v6")
if __name__=="__main__":main()
