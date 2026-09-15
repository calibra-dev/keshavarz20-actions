import importlib.util, os, random
p=os.path.join(os.path.dirname(__file__),"engine_v5.py")
s=importlib.util.spec_from_file_location("qe5",p); q=importlib.util.module_from_spec(s); s.loader.exec_module(q)

def prod(name): return {"id":1,"name":name,"status":"publish","reviews_allowed":True,"permalink":"https://example.test/p","categories":[],"tags":[],"attributes":[],"description":"","short_description":""}

def main():
    rng=random.Random(5)
    cases=[
      ("سوپاپ چدنی 2 اینچ","check_valve","check-valve:pump-line"),
      ("درپوش انتهای خط 3 اینچ","endcap","endcap:pipe"),
      ("فلنج 4 اینچ","flange","flange:match"),
      ("سرشلنگی 2 اینچ","hose_tail","hose-tail:both-sides"),
      ("سه راه پلی اتیلن 63","tee","tee:three-branches"),
      ("زانو پلی اتیلن 63","elbow","elbow:line"),
      ("تبدیل 90 به 63","reducer","reducer:two-sizes"),
      ("رابط مساوی 90","coupling","coupling:ends")]
    for name,st,key in cases:
        p=prod(name); assert q.q.fitting_subtype(p)==st,(name,q.q.fitting_subtype(p),st)
        cs=q.candidates_v5(p,"fitting","conversational",rng); assert any(x["key"]==key for x in cs),(name,key)
        for c in cs:
            ok,reason=q.guard_v5(p,c,c["core"]); assert ok,(name,c,reason)
    print("PASS v5")
if __name__=="__main__":main()
