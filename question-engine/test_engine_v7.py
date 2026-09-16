import importlib.util, os, random
p=os.path.join(os.path.dirname(__file__),"engine_v7.py")
s=importlib.util.spec_from_file_location("qe7",p); q=importlib.util.module_from_spec(s); s.loader.exec_module(q)

def prod(name): return {"id":1,"name":name,"status":"publish","reviews_allowed":True,"permalink":"https://example.test/p","categories":[],"tags":[],"attributes":[],"description":"","short_description":""}

def bykey(items,prefix):
    return [x for x in items if str(x.get("key") or "").startswith(prefix)]

def main():
    rng=random.Random(19)
    fert=prod("کود کامل مایع")
    fc=q.candidates_v7(fert,"fertilizer","experienced",rng)
    rich=bykey(fc,"postuse:prior-program")
    assert rich and "قبل از تکرار مصرف" in rich[0]["core"] and "وضعیت ریشه" in rich[0]["core"]
    assert not [x for x in fc if x.get("key")=="postuse:no-result"]
    assert not [x for x in fc if x.get("key")=="plant:symptom:yellowing"]
    tape=prod("نوار تیپ 20 سانت")
    tc=q.candidates_v7(tape,"drip_tape","conversational",rng)
    assert bykey(tc,"driptape:scenario:")
    pipe=prod("لوله نخدار 3 اینچ")
    pc=q.candidates_v7(pipe,"pipe","conversational",rng)
    assert bykey(pc,"pipe:scenario:")
    fitting=prod("کمربند پلی اتیلن 63")
    xc=q.candidates_v7(fitting,"fitting","conversational",rng)
    assert bykey(xc,"installer:existing-line:fitting:")
    print("PASS v7")
if __name__=="__main__":main()
