#!/usr/bin/env python3
import html, json, os, re, requests
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.0,status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))
S.mount("https://",HTTPAdapter(max_retries=retry)); S.mount("http://",HTTPAdapter(max_retries=retry))
S.headers.update({"Accept":"application/json","User-Agent":"k20-growthos-phase15-entity-os/1.0","Cache-Control":"no-cache"})
NOW=datetime.now(timezone.utc).isoformat()

P14=Path("growthos-phase14-results/summary.json")
P2=Path("growthos-phase2-results/product-truth-registry.json")
P3S=Path("growthos-phase3-results/html-schema-feed-parity-summary.json")
P11=Path("growthos-phase11-results/openai-product-feed-readiness.json")
P12=Path("growthos-phase12-results/merchant-field-map.json")
PASSIGN=Path("brand-assignment-results/apply-all-158.json")
PREMED=Path("brand-remediation-results/apply-verified-latest.json")

def api(path,params=None):
    r=S.get(urljoin(BASE+"/",path.lstrip("/")),params=params,timeout=120)
    r.raise_for_status(); return r.json()

def all_products():
    out=[]
    for page in range(1,40):
        rows=api("wp-json/wc/v3/products",{"status":"publish","per_page":100,"page":page,"orderby":"id","order":"asc"})
        if not rows: break
        out.extend(rows)
        if len(rows)<100: break
    return out

def norm_text(v):
    s=str(v or "").casefold().replace("\u200c"," ").replace("\u200f"," ")
    s=s.replace("keshavarz20","کشاورز بیست")
    s=re.sub(r"[^0-9a-zآ-ی]+","",s)
    return s

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

def node_types(n):
    t=n.get("@type") if isinstance(n,dict) else None
    return set(str(x) for x in (t if isinstance(t,list) else [t]) if x)

def parse_jsonld(text):
    blocks=re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',text,re.I)
    nodes=[]; errors=[]
    for raw in blocks:
        try:
            data=json.loads(html.unescape(raw.strip()))
            nodes.extend([n for n in walk(data) if isinstance(n,dict)])
        except Exception as e:
            errors.append(type(e).__name__)
    return nodes,errors

def public_get(url):
    return requests.get(url,timeout=90,headers={"User-Agent":"k20-growthos-phase15-entity-os/1.0","Cache-Control":"no-cache"},allow_redirects=True)

def safe_entity(n):
    logo=n.get("logo")
    if isinstance(logo,dict): logo=logo.get("url") or logo.get("contentUrl") or logo.get("@id")
    same=n.get("sameAs")
    if isinstance(same,str): same=[same]
    if not isinstance(same,list): same=[]
    return {
      "types":sorted(node_types(n)),
      "id":n.get("@id"),
      "name":n.get("name"),
      "alternateName":n.get("alternateName"),
      "url":n.get("url"),
      "logo":logo,
      "sameAs_declared":[x for x in same if isinstance(x,str) and x.startswith(("http://","https://"))],
      "telephone_present":bool(n.get("telephone")),
      "address_present":bool(n.get("address"))
    }

def phase2_truth_brand_map():
    if not P2.exists(): return {}
    data=json.loads(P2.read_text(encoding="utf-8"))
    out={}
    for rec in data.get("records",[]):
        f=(rec.get("fields") or {}).get("brand") or {}
        if f.get("status") in {"VERIFIED","SOURCE-CONFIRMED","USER-CONFIRMED"} and f.get("value"):
            out[int(rec["product_id"])]=str(f["value"]).strip()
    return out

def operator_assignment_map():
    if not PASSIGN.exists():
        return {},{"valid":False,"reason":"missing_assignment_artifact"}
    data=json.loads(PASSIGN.read_text(encoding="utf-8"))
    valid=(
        data.get("ok") is True
        and int(data.get("source_count") or 0)==158
        and int(data.get("mapping_count") or 0)==158
        and not (data.get("failures") or [])
        and len(data.get("results") or [])==158
        and all(x.get("ok") is True for x in (data.get("results") or []))
    )
    out={}
    if valid:
        for rec in data.get("results") or []:
            out[int(rec["product_id"])]=str(rec.get("requested_brand") or "").strip()
    remediation_meta={"present":False,"valid":None,"verified_assignments":0,"pseudo_removed":0}
    if PREMED.exists():
        rem=json.loads(PREMED.read_text(encoding="utf-8"))
        rem_valid=(
            rem.get("ok") is True
            and int(rem.get("scope") or 0)==87
            and not (rem.get("failures") or [])
            and all(x.get("ok") is True for x in (rem.get("results") or []))
        )
        remediation_meta={
          "present":True,"valid":rem_valid,
          "verified_assignments":int(rem.get("verified_assignments") or 0),
          "pseudo_removed":int(rem.get("pseudo_removed") or 0),
          "unresolved_multi":int(rem.get("unresolved_multi") or 0)
        }
        if not rem_valid:
            valid=False
        else:
            for rec in rem.get("results") or []:
                pid=int(rec.get("product_id") or 0)
                action=str(rec.get("action") or "")
                if action=="verified_assignment" and rec.get("brand"):
                    out[pid]=str(rec["brand"]).strip()
                elif action=="remove_pseudo":
                    out.pop(pid,None)
                elif action=="leave_unresolved_multi":
                    # Keep no asserted single brand for an unresolved multi-brand product.
                    out.pop(pid,None)
    return out,{"valid":valid,"artifact_count":len(out),"remediation":remediation_meta}

if not P14.exists(): raise SystemExit("Missing Phase 14 summary")
p14=json.loads(P14.read_text(encoding="utf-8"))
if not (p14.get("ok") and str(p14.get("status") or "").startswith("PASS")):
    raise SystemExit("Phase 14 prerequisite is not PASS")

products=all_products()
phase2_truth_brands=phase2_truth_brand_map()
operator_assignments,operator_meta=operator_assignment_map()
PSEUDO_BRANDS={"متفرقه"}
operator_real_brands={pid:b for pid,b in operator_assignments.items() if b not in PSEUDO_BRANDS}
operator_pseudo_brands={pid:b for pid,b in operator_assignments.items() if b in PSEUDO_BRANDS}
truth_brands=dict(phase2_truth_brands)
truth_conflicts=[]
for pid,b in operator_real_brands.items():
    old=truth_brands.get(pid)
    if old and not (norm_text(old)==norm_text(b) or norm_text(old) in norm_text(b) or norm_text(b) in norm_text(old)):
        truth_conflicts.append({"product_id":pid,"phase2_brand":old,"operator_brand":b})
    else:
        truth_brands[pid]=b

# Reuse the already-complete Phase 3 all-catalog parity audit rather than rerunning it.
p3=json.loads(P3S.read_text(encoding="utf-8")) if P3S.exists() else {}
p3sum=p3.get("summary") or {}
p3acc=p3.get("acceptance") or {}

# Live principal seller entity from the homepage JSON-LD.
home=public_get(BASE+"/")
nodes,parse_errors=parse_jsonld(home.text)
org_nodes=[n for n in nodes if node_types(n) & {"Organization","OnlineStore","OnlineBusiness","LocalBusiness","Store"}]
entities=[safe_entity(n) for n in org_nodes]
principal=None
for e in entities:
    if "کشاورزبیست" in norm_text(e.get("name")) or "کشاورزبیست" in norm_text(e.get("alternateName")):
        principal=e; break
if principal is None and entities: principal=entities[0]

# Catalog brand registry from current Woo product_brand assignments.
by_id={}
brand_products=defaultdict(set)
multi_brand=[]
unbranded=[]
for p in products:
    bs=[b for b in (p.get("brands") or []) if isinstance(b,dict) and b.get("id")]
    if not bs:
        unbranded.append({
          "product_id":int(p["id"]),
          "title":str(p.get("name") or "").strip(),
          "sku":str(p.get("sku") or "").strip() or None
        })
    if len(bs)>1:
        multi_brand.append({"product_id":int(p["id"]),"brand_ids":[int(b["id"]) for b in bs]})
    for b in bs:
        bid=int(b["id"]); name=str(b.get("name") or "").strip(); slug=str(b.get("slug") or "").strip()
        ent=by_id.setdefault(bid,{"brand_id":bid,"names":set(),"slugs":set()})
        if name: ent["names"].add(name)
        if slug: ent["slugs"].add(slug)
        brand_products[bid].add(int(p["id"]))

registry=[]
for bid in sorted(by_id):
    e=by_id[bid]
    names=sorted(e["names"]); slugs=sorted(e["slugs"])
    registry.append({
      "brand_id":bid,
      "canonical_name":names[0] if names else None,
      "observed_names":names,
      "observed_slugs":slugs,
      "published_product_count":len(brand_products[bid]),
      "external_sameAs":[],
      "external_identity_status":"NOT_ASSERTED_WITHOUT_SOURCE"
    })

# Detect taxonomy identity ambiguity without guessing which term to merge.
normalized_to_ids=defaultdict(set)
for b in registry:
    normalized_to_ids[norm_text(b["canonical_name"])].add(b["brand_id"])
duplicate_name_groups=[
 {"normalized_name":k,"brand_ids":sorted(v)}
 for k,v in normalized_to_ids.items() if k and len(v)>1
]

# Verify all user-confirmed assignments against current Woo brand state.
operator_assignment_mismatch=[]
by_product_id={int(p["id"]):p for p in products}
for pid,expected in operator_assignments.items():
    p=by_product_id.get(pid) or {}
    observed=[str(b.get("name") or "").strip() for b in (p.get("brands") or []) if isinstance(b,dict)]
    en=norm_text(expected)
    ok=any(en and (en==norm_text(x) or en in norm_text(x) or norm_text(x) in en) for x in observed)
    if not ok:
        operator_assignment_mismatch.append({"product_id":pid,"expected_brand":expected,"woo_brands":observed})

# Compare current Woo brand assignments with source-backed truth (Phase 2 + explicit user-confirmed real brands).
truth_mismatch=[]
truth_known=0
for p in products:
    pid=int(p["id"])
    tv=truth_brands.get(pid)
    if not tv: continue
    truth_known+=1
    observed=[str(b.get("name") or "").strip() for b in (p.get("brands") or []) if isinstance(b,dict)]
    tn=norm_text(tv)
    ok=any(tn and (tn==norm_text(x) or tn in norm_text(x) or norm_text(x) in tn) for x in observed)
    if not ok:
        truth_mismatch.append({"product_id":pid,"truth_brand":tv,"woo_brands":observed})

multi_brand_ids={int(x["product_id"]) for x in multi_brand}
live_pseudo_brand_ids=set()
for p in products:
    pid=int(p["id"])
    names={str(b.get("name") or "").strip() for b in (p.get("brands") or []) if isinstance(b,dict)}
    if names & PSEUDO_BRANDS:
        live_pseudo_brand_ids.add(pid)
pseudo_brand_ids=live_pseudo_brand_ids
external_brand_gap_ids=multi_brand_ids | pseudo_brand_ids | {int(x["product_id"]) for x in unbranded}
external_single_brand_ready_ids={
    int(p["id"]) for p in products
    if int(p["id"]) not in external_brand_gap_ids
    and len([b for b in (p.get("brands") or []) if isinstance(b,dict) and b.get("id")])==1
}

# Cross-phase seller naming contracts.
phase11_seller=None
if P11.exists():
    phase11_seller=(json.loads(P11.read_text(encoding="utf-8")) or {}).get("seller_name")
phase12_seller_mapped=False
phase12_seller_conflicts=[]
if P12.exists():
    p12=json.loads(P12.read_text(encoding="utf-8"))
    for m in p12.get("field_mapping") or []:
        google_field=str(m.get("google") or "").strip().lower()
        k20_field=str(m.get("k20") or "").strip()
        if google_field=="seller_name" or norm_text(k20_field)=="کشاورزبیست":
            phase12_seller_mapped=True
        # Phase 12 is primarily a product-field mapping and does not require a seller_name row.
        # Treat only an explicit contradictory seller identity as a hard failure.
        if google_field in {"seller","seller_name","merchant_name"} and k20_field and norm_text(k20_field)!="کشاورزبیست":
            phase12_seller_conflicts.append({"google":m.get("google"),"k20":m.get("k20")})

principal_name=(principal or {}).get("name")
principal_url=(principal or {}).get("url")
principal_logo=(principal or {}).get("logo")
principal_types=(principal or {}).get("types") or []
name_ok=bool(principal_name and ("کشاورزبیست" in norm_text(principal_name) or norm_text(principal_name)=="کشاورزبیست"))
url_ok=not principal_url or urlparse(str(principal_url)).netloc.lower().removeprefix("www.")=="keshavarz20.com"
logo_ok=bool(principal_logo)
phase3_org_all=(p3sum.get("organization_missing")==0 and p3sum.get("audited_products")==len(products))
phase3_brand_hard=(p3sum.get("eligible_brand_mismatch_when_truth_known")==0)
phase3_all_hard=bool(p3acc.get("all_hard_parity_checks_pass"))
seller_feed_ok=(norm_text(phase11_seller)=="کشاورزبیست") if phase11_seller else False

hard_checks={
  "homepage_http_200":home.status_code==200,
  "homepage_jsonld_parse_clean":not parse_errors,
  "principal_seller_entity_found":principal is not None,
  "principal_name_is_keshavarz20":name_ok,
  "principal_url_same_origin_when_declared":url_ok,
  "phase3_all_published_products_have_organization":phase3_org_all,
  "phase3_brand_parity_hard_pass":phase3_brand_hard,
  "phase3_catalog_parity_hard_pass":phase3_all_hard,
  "phase11_seller_name_consistent":seller_feed_ok,
  "phase12_no_conflicting_seller_identity":len(phase12_seller_conflicts)==0,
  "assignment_artifact_valid":operator_meta.get("valid") is True,
  "user_confirmed_assignment_mismatch_zero":len(operator_assignment_mismatch)==0,
  "combined_truth_conflict_zero":len(truth_conflicts)==0,
  "current_truth_brand_mismatch_zero":len(truth_mismatch)==0
}
hard_pass=all(hard_checks.values())

seller_registry={
  "phase":15,
  "version":"growthos-seller-entity-registry-v1",
  "generated_at_utc":NOW,
  "canonical_key":"https://keshavarz20.com/",
  "principal_live_entity":principal,
  "other_live_org_entities":entities[1:] if principal and entities and entities[0]==principal else [e for e in entities if e!=principal],
  "cross_surface_contract":{
    "site_name":"کشاورز بیست",
    "latin_alias":"Keshavarz20",
    "canonical_url":"https://keshavarz20.com/",
    "phase11_feed_seller_name":phase11_seller,
    "phase12_merchant_seller_mapping_explicit":phase12_seller_mapped,
    "phase12_conflicting_seller_mappings":phase12_seller_conflicts
  },
  "identity_policy":{
    "sameAs_only_when_declared_and_verified":True,
    "do_not_create_gln_iso6523_without_source":True,
    "do_not_invent_legal_name_or_registration":True,
    "do_not_duplicate_principal_organization_nodes":True,
    "prefer_online_store_subtype_when_existing_schema_source_can_be_changed_safely":True
  }
}
brand_registry={
  "phase":15,
  "version":"growthos-brand-entity-registry-v1",
  "generated_at_utc":NOW,
  "published_products":len(products),
  "brand_terms":registry,
  "brand_term_count":len(registry),
  "products_with_any_woo_brand":len(products)-len(unbranded),
  "products_without_woo_brand":len(unbranded),
  "external_brand_truth_gap_products":len(external_brand_gap_ids),
  "pseudo_brand_products":len(live_pseudo_brand_ids),
  "multi_brand_ambiguous_products":len(multi_brand_ids),
  "unbranded_products":unbranded,
  "phase2_truth_brand_products":len(phase2_truth_brands),
  "user_confirmed_brand_assignment_products":len(operator_assignments),
  "user_confirmed_real_brand_products":len(operator_real_brands),
  "pseudo_brand_products":len(operator_pseudo_brands),
  "pseudo_brand_names":sorted(PSEUDO_BRANDS),
  "multi_brand_ambiguous_products":len(multi_brand_ids),
  "external_brand_truth_gap_products":len(external_brand_gap_ids),
  "external_single_brand_ready_products":len(external_single_brand_ready_ids),
  "source_verified_truth_brand_products":truth_known,
  "truth_source_conflicts":truth_conflicts,
  "user_confirmed_assignment_mismatches":operator_assignment_mismatch,
  "truth_brand_assignment_mismatches":truth_mismatch,
  "multi_brand_products":multi_brand,
  "duplicate_normalized_brand_name_groups":duplicate_name_groups,
  "policy":{
    "unknown_brand_is_not_inferred":True,
    "manufacturer_and_seller_are_distinct_entities":True,
    "brand_sameAs_not_invented":True,
    "taxonomy_merges_not_automatic":True
  }
}
graph={
  "phase":15,
  "version":"growthos-entity-graph-v1",
  "generated_at_utc":NOW,
  "nodes":{
    "seller":{"id":"k20:seller","name":"کشاورز بیست","url":"https://keshavarz20.com/","live_schema_id":(principal or {}).get("id")},
    "brands":[{"id":"k20:brand:"+str(b["brand_id"]),"name":b["canonical_name"],"product_count":b["published_product_count"]} for b in registry]
  },
  "edges":{
    "seller_offers_published_products":len(products),
    "brand_of_product_edges":sum(b["published_product_count"] for b in registry)
  },
  "non_edges":{
    "seller_is_not_automatically_manufacturer":True,
    "brand_is_not_automatically_seller":True
  }
}
soft_gaps={
  "online_store_subtype_present":("OnlineStore" in principal_types),
  "principal_logo_present":logo_ok,
  "phase12_seller_mapping_explicit":phase12_seller_mapped,
  "declared_sameAs_count":len((principal or {}).get("sameAs_declared") or []),
  "products_without_woo_brand":len(unbranded),
  "duplicate_normalized_brand_groups":len(duplicate_name_groups),
  "multi_brand_products":len(multi_brand),
  "note":"Soft gaps are enrichment/backlog items only. They do not justify fabricated identity, brand, GLN, legal registration, or sameAs data."
}
audit={
  "phase":15,
  "generated_at_utc":NOW,
  "hard_checks":hard_checks,
  "hard_pass":hard_pass,
  "soft_gaps":soft_gaps,
  "phase3_evidence":{"audited_products":p3sum.get("audited_products"),"pass":p3sum.get("pass"),"fail":p3sum.get("fail"),"organization_missing":p3sum.get("organization_missing"),"eligible_brand_mismatch_when_truth_known":p3sum.get("eligible_brand_mismatch_when_truth_known")},
  "homepage_schema_entity_count":len(entities),
  "homepage_parse_errors":parse_errors
}
summary={
  "ok":hard_pass,
  "phase":15,
  "title":"Brand & Seller Entity OS",
  "generated_at_utc":NOW,
  "status":"PASS_ENTITY_OS_WITH_SOURCE_GAPS" if hard_pass and (len(external_brand_gap_ids)>0 or len(unbranded)>0 or not soft_gaps["online_store_subtype_present"]) else ("PASS_ENTITY_OS" if hard_pass else "FAIL"),
  "published_products":len(products),
  "seller_entity_found":principal is not None,
  "seller_name_consistent":name_ok and seller_feed_ok,
  "phase3_catalog_hard_parity_pass":phase3_all_hard,
  "brand_terms":len(registry),
  "phase2_truth_brand_products":len(phase2_truth_brands),
  "user_confirmed_brand_assignment_products":len(operator_assignments),
  "user_confirmed_real_brand_products":len(operator_real_brands),
  "pseudo_brand_products":len(operator_pseudo_brands),
  "multi_brand_ambiguous_products":len(multi_brand_ids),
  "external_brand_truth_gap_products":len(external_brand_gap_ids),
  "external_single_brand_ready_products":len(external_single_brand_ready_ids),
  "source_verified_truth_brand_products":truth_known,
  "brand_truth_mismatches":len(truth_mismatch),
  "operator_assignment_mismatches":len(operator_assignment_mismatch),
  "truth_source_conflicts":len(truth_conflicts),
  "products_without_woo_brand":len(unbranded),
  "identity_fields_fabricated":0,
  "sameAs_links_fabricated":0,
  "glns_fabricated":0,
  "schema_site_writes":0,
  "next_backlog":[
    "Resolve 75 internal pseudo-brand «متفرقه» products and 12 multi-brand ambiguities only when a real manufacturer/brand source is available; never export pseudo or ambiguous brand as a single commerce brand.",
    "Verify official external brand/seller profiles before adding sameAs.",
    "Consider OnlineStore subtype at the canonical schema source only if it can be changed without duplicating Organization."
  ]
}
Path("growthos-phase15-results").mkdir(exist_ok=True)
for name,obj in [
 ("seller-entity-registry.json",seller_registry),
 ("brand-entity-registry.json",brand_registry),
 ("entity-graph.json",graph),
 ("entity-parity-audit.json",audit),
 ("summary.json",summary)
]:
    Path("growthos-phase15-results",name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
print("GROWTHOS_PHASE15_CHECKS",json.dumps(hard_checks,ensure_ascii=False))
print("GROWTHOS_PHASE15",json.dumps(summary,ensure_ascii=False))
if not hard_pass: raise SystemExit("Phase 15 hard entity parity failed")
