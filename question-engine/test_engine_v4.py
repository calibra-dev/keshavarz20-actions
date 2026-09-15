import importlib.util, os, random
p=os.path.join(os.path.dirname(__file__),"engine_v4.py")
s=importlib.util.spec_from_file_location("qe4",p); q=importlib.util.module_from_spec(s); s.loader.exec_module(q)

def product(i): return {"id":i,"name":f"محصول {i}","status":"publish","reviews_allowed":True}

def main():
    rng=random.Random(3); ps=[product(i) for i in range(1,6)]
    state=q.q.default_state(); state["product_counts"]={"1":0,"2":1,"3":1,"4":1,"5":1}; state["recent_product_ids"]=[1]
    picked=q.choose_product_v4(ps,state,rng)
    assert picked["id"]!=1, "recent under-count product must not repeat immediately"
    state["recent_product_ids"]=[]; picked=q.choose_product_v4(ps,state,rng); assert picked["id"]==1
    assert q._is_polite("سلام وقت بخیر، ممنون میشم راهنمایی کنید")
    assert q._is_colloquial("سلام یه سوال داشتم این جواب میده؟")
    print("PASS v4")
if __name__=="__main__":main()
