import importlib.util, os, random
p=os.path.join(os.path.dirname(__file__),"engine_v3.py")
s=importlib.util.spec_from_file_location("qe3",p); q=importlib.util.module_from_spec(s); s.loader.exec_module(q)

def prod(name):
    return {"id":1,"name":name,"status":"publish","reviews_allowed":True,"permalink":"https://example.test/p","categories":[],"tags":[],"attributes":[],"description":"","short_description":""}

def main():
    rng=random.Random(8)
    sulfur=prod("گوگرد پودری و گوگرد بنتونیت دار Room کیسه 25 کیلو گرمی")
    cs=q.candidates_v3(sulfur,"fertilizer","conversational",rng)
    assert not any(x.get("key")=="nutrition:calcium-iron-mix" for x in cs)
    mixes=[x for x in cs if x.get("intent")=="mix"]
    assert mixes and all("گوگرد" in x["core"] or "این محصول" in x["core"] for x in mixes)
    calcium=prod("کود کلسیم مایع")
    cs=q.candidates_v3(calcium,"fertilizer","conversational",rng)
    assert any(x.get("key")=="nutrition:this-calcium-with-iron" for x in cs)
    pipe=prod("لوله نخدار 3 اینچ")
    cs=q.candidates_v3(pipe,"pipe","experienced",rng)
    assert any(x.get("intent")=="terrain" for x in cs)
    assert any(x.get("intent")=="transition" for x in cs)
    print("PASS v3")
if __name__=="__main__":main()
