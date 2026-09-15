import importlib.util, os, random
p=os.path.join(os.path.dirname(__file__),"engine_v2.py")
s=importlib.util.spec_from_file_location("qe2",p); q=importlib.util.module_from_spec(s); s.loader.exec_module(q)

def prod(name):
    return {"id":1,"name":name,"status":"publish","reviews_allowed":True,"permalink":"https://example.test/p","categories":[],"tags":[],"attributes":[],"description":"","short_description":""}

def main():
    rng=random.Random(12)
    p=prod("رابط تیپ به لی فلت بدون واشر آبافرین")
    assert q.fitting_subtype(p)=="tape_to_layflat"
    for _ in range(100):
        c=q.choose_candidate_v2(p,"fitting",[],"conversational",rng)
        text=q.b.wrap(c["core"],True,"conversational",rng)
        ok,reason=q.consistency_guard(p,c,text)
        assert ok,(c,text,reason)
        assert "واشر رو بررسی" not in text and "واشر را بررسی" not in text and "جا افتادن واشر" not in text
    p2=prod("کمربند پلی اتیلن 63")
    assert q.fitting_subtype(p2)=="saddle"
    cands=q.guarded_candidates(p2,"fitting","conversational",rng)
    assert any(x["key"]=="saddle:washer-alternative" for x in cands)
    p3=prod("شیر توپی 2 اینچ")
    assert q.valve_subtype(p3)=="ball"
    cands=q.guarded_candidates(p3,"valve","conversational",rng)
    assert any(x["key"]=="valve:ball:building" for x in cands)
    st=q.default_state(); cfg={"colloquial_target":.15,"politeness_target":.70}
    styles=[]; polite=[]
    for i in range(200):
        sty=q.style_from_state(st,cfg,rng); pol=q.polite_from_state(st,cfg,rng)
        styles.append(sty); polite.append(pol); st["total"]+=1; st["colloquial"]+=int(sty=="colloquial"); st["polite"]+=int(pol)
    cr=styles.count("colloquial")/200; pr=sum(polite)/200
    assert .14<=cr<=.16,cr
    assert .68<=pr<=.72,pr
    print("PASS v2",cr,pr)
if __name__=="__main__":main()
