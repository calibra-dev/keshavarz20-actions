#!/usr/bin/env python3
import argparse, base64, datetime as dt, hashlib, html, json, os, random, re, sys, time
from urllib import parse, request, error

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
UA = "Keshavarz20-Customer-Question-Engine/1.0"

KNOWLEDGE_PATH = os.path.join(ROOT, "knowledge.json")
try:
    _KB = json.load(open(KNOWLEDGE_PATH, encoding="utf-8"))
except Exception:
    _KB = {}

def _flat_groups(names):
    groups = _KB.get("plant_groups") or {}
    out=[]
    for name in names:
        out.extend(groups.get(name) or [])
    return out

POLITE_OPENERS = [
    "سلام وقت بخیر، ", "سلام روزتون بخیر، ", "سلام خسته نباشید، ", "وقت بخیر، ",
    "سلام، یه سوال داشتم؛ ", "سلام، ممنون میشم راهنمایی کنید؛ "
]
POLITE_CLOSERS = [
    " ممنون میشم راهنمایی کنید.", " ممنون از راهنماییتون.", " اگر امکانش هست راهنمایی کنید.",
    " پیشاپیش ممنون.", " ممنون میشم نظرتون رو بگین.", " سپاسگزارم."
]
CITIES = _KB.get("cities") or ["مشهد", "تبریز", "کرمان", "اصفهان", "اهواز", "شیراز"]
CROPS = _flat_groups(["field_crops","vegetables_fruiting","cucurbits","leafy_vegetables","root_and_bulb","legumes"]) or ["گوجه فرنگی","خیار","ذرت","گندم"]
ORCHARDS = _flat_groups(["temperate_orchards","warm_orchards","vineyards"]) or ["سیب","گردو","پسته","انار"]
INDOOR = _flat_groups(["indoor_foliage","indoor_flowering","succulents_cacti","home_fruit_trees"]) or ["فیکوس","پتوس","سانسوریا"]
SOILS = _KB.get("soil_types") or ["خاک رسی و سنگین","خاک شنی","خاک لومی","خاک آهکی","خاک شور"]
WATER_ISSUES = [f"{x} داریم" for x in (_KB.get("water_conditions") or ["آب شور","آب دارای شن","آب سخت"])]
GROWTH = _KB.get("growth_stages_annual") or ["اوایل رشد","قبل گلدهی","زمان گلدهی","بعد تشکیل میوه"]

FAMILY_KEYWORDS = {
    "fertilizer": ["کود", "هیومیک", "آهن", "پتاس", "فسفر", "npk", "کلسیم", "ریز مغذ", "میکرو", "فیکس", "پلی اس", "اسید آمینه"],
    "pesticide": ["سم", "حشره", "قارچ کش", "علف کش", "اتفون", "کنه کش", "نماتد"],
    "drip_tape": ["نوار تیپ", "نوارتیپ", "تیپ"],
    "pipe": ["لوله", "لی فلت", "لی‌فلت", "نخدار", "پلی اتیلن", "پلی‌اتیلن", "بارانی"],
    "valve": ["شیر توپی", "شیر پروانه", "شیر فلکه", "شیر تک ضرب", "شیر تیپ", "شیر لی فلت", "شیر لی‌فلت"],
    "filter": ["فیلتر", "هیدروسیکلون"],
    "fertigation": ["تانک کود", "تزریق کود", "ونتوری"],
    "sprinkler": ["آبپاش", "بارانی", "مه پاش", "مه‌پاش"],
    "fitting": ["رابط", "زانو", "سه راه", "سه‌راه", "تبدیل", "کمربند", "بست", "سرشلنگ", "فلنج", "واشر", "سوپاپ", "درپوش"]
}

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def iso(z):
    return z.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def parse_dt(s):
    if not s:
        return None
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(dt.timezone.utc)

def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def norm(s):
    s = (s or "").replace("ي", "ی").replace("ك", "ک").lower()
    s = re.sub(r"[^\w\u0600-\u06ff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def tokens(s):
    return {x for x in norm(s).split() if len(x) > 1 and x not in {"این", "برای", "سلام", "ممنون", "میشه", "می‌شود", "محصول", "مدل"}}

def jaccard(a, b):
    aa, bb = tokens(a), tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)

def stable_jitter(seed, lo, hi):
    h = hashlib.sha256(str(seed).encode("utf-8")).digest()
    n = int.from_bytes(h[:8], "big")
    return lo + (n % (hi - lo + 1))

def add_months(d, months):
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    import calendar
    day = min(d.day, calendar.monthrange(y, m)[1])
    return d.replace(year=y, month=m, day=day)

class WP:
    def __init__(self):
        self.base = os.environ["WP_BASE_URL"].rstrip("/")
        u = os.environ["WP_USERNAME"]
        p = os.environ["WP_APP_PASSWORD"]
        self.auth = "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()

    def _call(self, method, path, body=None, auth=True):
        headers = {"Accept":"application/json", "User-Agent":UA}
        if auth:
            headers["Authorization"] = self.auth
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=180) as r:
                raw = r.read().decode("utf-8", "replace")
                return int(r.status), (json.loads(raw) if raw else None), dict(r.headers)
        except error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try: payload = json.loads(raw)
            except Exception: payload = {"raw": raw[:1000]}
            raise RuntimeError(f"HTTP {e.code} {path}: {payload}") from e

    def products(self, cfg):
        out = []
        statuses = cfg.get("allow_product_statuses") or ["publish"]
        for status in statuses:
            for page in range(1, int(cfg.get("max_product_pages", 20)) + 1):
                params = parse.urlencode({
                    "per_page": int(cfg.get("products_per_page",100)), "page":page, "status":status,
                    "orderby":"id", "order":"asc",
                    "_fields":"id,name,slug,status,permalink,categories,tags,attributes,short_description,description,reviews_allowed"
                })
                try:
                    code, rows, hdr = self._call("GET", "/wp-json/wc/v3/products?" + params)
                except RuntimeError as exc:
                    if "HTTP 400" in str(exc) and page > 1: break
                    raise
                if not rows: break
                out.extend(rows)
                total_pages = int(hdr.get("X-WP-TotalPages") or hdr.get("x-wp-totalpages") or 0)
                if (total_pages and page >= total_pages) or len(rows) < int(cfg.get("products_per_page",100)):
                    break
        return out

    def comments(self, pages=10, per_page=100, post=None):
        out = []
        for page in range(1, pages+1):
            q = {"context":"edit","per_page":per_page,"page":page,"orderby":"date_gmt","order":"desc"}
            if post: q["post"] = int(post)
            try:
                _, rows, hdr = self._call("GET", "/wp-json/wp/v2/comments?" + parse.urlencode(q))
            except RuntimeError as exc:
                if "HTTP 400" in str(exc) and page > 1: break
                raise
            if not rows: break
            out.extend(rows)
            total_pages = int(hdr.get("X-WP-TotalPages") or hdr.get("x-wp-totalpages") or 0)
            if (total_pages and page >= total_pages) or len(rows) < per_page: break
        return out

    def submit_comment(self, product_id, text, cfg):
        body = {
            "post": int(product_id),
            "content": text,
            "author": 0,
            "author_name": cfg["author_name"],
            "author_email": cfg["author_email"],
            "author_url": self.base,
            "status": cfg.get("comment_status", "hold")
        }
        _, obj, _ = self._call("POST", "/wp-json/wp/v2/comments", body)
        return obj

    def comment(self, cid):
        _, obj, _ = self._call("GET", f"/wp-json/wp/v2/comments/{int(cid)}?context=edit")
        return obj

def iran_season(d=None):
    d=(d or now_utc()).date()
    md=(d.month,d.day)
    if (3,21) <= md <= (6,20): return "بهار"
    if (6,21) <= md <= (9,22): return "تابستان"
    if (9,23) <= md <= (12,20): return "پاییز"
    return "زمستان"

def product_text(p):
    bits = [p.get("name", ""), strip_html(p.get("short_description","")), strip_html(p.get("description",""))]
    bits += [x.get("name","") for x in p.get("categories") or []]
    bits += [x.get("name","") for x in p.get("tags") or []]
    for a in p.get("attributes") or []:
        bits.append(str(a.get("name", "")))
        bits.extend(map(str, a.get("options") or []))
    return " ".join(bits)

def family(p):
    name = norm(str(p.get("name") or ""))
    ordered_name_rules = [
        ("drip_tape", ["نوار تیپ", "نوارتیپ"]),
        ("fertigation", ["تانک کود", "تزریق کود", "ونتوری"]),
        ("filter", ["فیلتر", "هیدروسیکلون"]),
        ("valve", ["شیر توپی", "شیر پروانه", "شیر فلکه", "شیر تک ضرب", "شیر تیپ", "شیر لی فلت", "شیر لی‌فلت"]),
        ("fitting", ["کمربند", "رابط", "زانو", "سه راه", "سه‌راه", "تبدیل", "بست", "سرشلنگ", "فلنج", "واشر", "سوپاپ", "درپوش"]),
        ("pipe", ["لوله", "لی فلت", "لی‌فلت", "نخدار", "پلی اتیلن", "پلی‌اتیلن"]),
        ("sprinkler", ["آبپاش", "مه پاش", "مه‌پاش"]),
        ("pesticide", ["سم", "حشره", "قارچ کش", "علف کش", "اتفون", "کنه کش", "نماتد"]),
        ("fertilizer", ["کود", "هیومیک", "آهن", "پتاس", "فسفر", "npk", "کلسیم", "ریز مغذ", "میکرو", "فیکس", "پلی اس", "اسید آمینه"]),
    ]
    for fam, words in ordered_name_rules:
        if any(norm(w) in name for w in words):
            return fam
    t = norm(product_text(p))
    scores = {}
    for k, vals in FAMILY_KEYWORDS.items():
        score = 0
        for x in vals:
            nx = norm(x)
            if nx and nx in t:
                score += max(1, len(nx.split()))
                if len(nx) >= 7:
                    score += 1
        scores[k] = score
    best = max(scores, key=scores.get)
    return best if scores[best] else "generic"

def ref_name(p):
    name = str(p.get("name") or "این محصول").strip()
    short = re.sub(r"\s+", " ", name)
    return short if len(short) <= 52 else "این محصول"

def detect_pressure_claim(p):
    t = product_text(p)
    m = re.search(r"(?<!\d)(\d+(?:[\.,]\d+)?)\s*(?:بار|bar)(?!\w)", t, re.I)
    return m.group(1).replace(",", ".") if m else None

def style_from_history(hist, cfg, rng):
    recent = hist[:100]
    colloq = sum(1 for h in recent if any(x in norm(h) for x in ["به نظرتون", "جواب میده", "چی بگیرم", "یه سوال", "میخوام", "می‌خوام"]))
    target = float(cfg.get("colloquial_target", .15))
    desired = round(target * (len(recent)+1))
    if colloq < desired: return "colloquial"
    r = rng.random()
    if r < .47: return "conversational"
    if r < .82: return "experienced"
    return "technical"

def polite_from_history(hist, cfg, rng):
    recent = hist[:100]
    def is_polite(q): return any(x in q for x in ["سلام", "وقت بخیر", "ممنون", "سپاس", "راهنمایی کنید", "راهنمایی کنین"])
    count = sum(is_polite(h) for h in recent)
    target = float(cfg.get("politeness_target", .70))
    desired = round(target * (len(recent)+1))
    if count < desired: return True
    if count > desired + 1: return False
    return rng.random() < target

def wrap(core, polite, style, rng):
    core = core.strip().rstrip(" .")
    if not core.endswith("؟"): core += "؟"
    if style == "colloquial":
        core = core.replace("می‌شود", "میشه").replace("می‌توانید", "می‌تونید").replace("پیشنهاد می‌کنید", "پیشنهاد می‌دین")
    if not polite: return core
    mode = rng.choice(["open", "close", "both"])
    op = rng.choice(POLITE_OPENERS) if mode in ("open","both") else ""
    cl = rng.choice(POLITE_CLOSERS) if mode in ("close","both") else ""
    return (op + core + cl).strip()

def core_candidates(p, fam, style, rng):
    name = ref_name(p)
    city = rng.choice(CITIES); crop = rng.choice(CROPS); orchard = rng.choice(ORCHARDS); indoor = rng.choice(INDOOR)
    soil = rng.choice(SOILS); water_issue = rng.choice(WATER_ISSUES); stage = rng.choice(GROWTH)
    area = rng.choice(["یک هکتار", "۲ هکتار", "۵ هکتار", "حدود ۱۰ هکتار"])
    pressure = detect_pressure_claim(p)
    c = []
    def add(intent, key, text): c.append({"intent":intent,"key":key,"core":text})
    add("bulk", "commerce:bulk", f"اگر از {name} تعداد بالا بخوام برای خرید عمده باید از سایت ثبت کنم یا برای قیمت همکاری با پشتیبانی هماهنگ کنم")
    add("shipping", f"commerce:shipping:{city}", f"ارسال {name} برای {city} معمولاً با چه روشی انجام میشه و حدوداً چند روز تا تحویل باربری زمان می‌بره")
    add("price_freshness", "commerce:price-freshness", f"قیمت درج‌شده برای {name} به‌روز هست یا قبل از سفارش بهتره استعلام بگیرم")
    add("discount", "commerce:discount", f"اگر این محصول قبلاً تخفیف داشته باشه امکان داره دوباره روی تخفیف قرار بگیره یا زمان مشخصی نداره")
    add("complement", "purchase:complete-kit", f"برای اینکه موقع نصب یا استفاده چیزی کم نیارم، همراه {name} چه لوازم یا قطعات مکملی لازمه بگیرم")
    add("alternative", "purchase:alternative", f"اگر {name} برای شرایط من مناسب نباشه نزدیک‌ترین گزینه جایگزینش معمولاً چه مدلیه")
    if pressure:
        add("claim_challenge", f"claim:pressure:{pressure}", f"برای این محصول فشار {pressure} بار نوشته شده؛ این عدد برای کار دائم هم قابل اتکاست یا فشار حداکثری و لحظه‌ایه")
    if fam in ("fertilizer","pesticide"):
        add("crop_fit", f"crop:{crop}:fit", f"{area} {crop} دارم؛ این محصول برای {crop} هم کاربرد داره یا اول باید شرایط مزرعه و مرحله رشد بررسی بشه")
        add("timing", f"crop:{crop}:stage:{stage}", f"{crop} من الان {stage} هست؛ اگر این محصول مناسبش باشه بهترین زمان استفاده در همین مرحله است یا زمان دیگه‌ای بهتره")
        add("method", f"crop:{crop}:method", f"برای {crop} اگر این محصول قابل استفاده باشه، مصرف از طریق آبیاری منطقی‌تره یا محلول‌پاشی")
        add("orchard", f"orchard:{orchard}:use", f"باغ {orchard} دارم؛ برای تعیین مقدار و زمان مصرف این محصول چه اطلاعاتی از سن درخت، بار و آزمایش خاک لازم دارید")
        add("mix", "nutrition:calcium-iron-mix", "کود کلسیم و آهن رو میشه داخل یک برنامه نزدیک به هم استفاده کرد یا برای جلوگیری از ناسازگاری بهتره جدا داده بشن")
        add("salinity", "soil:salinity", f"{water_issue}؛ این محصول اصلاً برای چنین شرایطی کمکی می‌کنه یا موضوع شوری و کیفیت آب باید جداگانه بررسی بشه")
        add("soil", f"soil:{norm(soil)}", f"{soil} دارم؛ این موضوع روی روش و مقدار مصرف این محصول اثر می‌ذاره")
        add("diagnosis", "plant:symptom:yellowing", f"درختام زرد شدن و دقیق نمی‌دونم کمبود آهنه یا مشکل دیگه؛ برای اینکه مشخص بشه {name} به دردشون می‌خوره چه اطلاعاتی لازمه بفرستم")
        add("indoor", f"indoor:{indoor}", f"{indoor} داخل خونه دارم؛ از این محصول برای گلدان هم میشه استفاده کرد یا بیشتر برای باغ و مزرعه طراحی شده")
        add("post_use", "postuse:no-result", f"اگر این محصول رو یک نوبت استفاده کرده باشم ولی هنوز علائم کمبود دیده بشه، قبل از تکرار مصرف چه چیزهایی باید بررسی بشه")
        add("season", f"season:{iran_season()}", f"الان فصل {iran_season()} هست؛ برای استفاده از این محصول زمان فصل مهمه یا بیشتر باید مرحله رشد و شرایط گیاه رو در نظر بگیرم")
    elif fam == "drip_tape":
        add("area", f"irrigation:{crop}:{area}", f"{area} {crop} دارم؛ برای برآورد تعداد رول نوار تیپ چه اطلاعاتی مثل فاصله ردیف و طول زمین لازمه")
        add("slope", "irrigation:slope", "زمینم شیب داره؛ این مدل تیپ جواب میده یا برای یکنواختی آب باید نوع دیگه‌ای انتخاب کنم")
        add("water_quality", "irrigation:water-quality", f"{water_issue}؛ برای اینکه این نوار زود نگیره چه نوع فیلتراسیونی باید در نظر بگیرم")
        add("crop_choice", f"irrigation:crop:{crop}", f"برای کشت {crop} این مدل نوار مناسبه یا فاصله خروجی‌ها و ضخامت نوار باید بر اساس کشت انتخاب بشه")
        add("transition", "irrigation:flood-to-drip", "چند ساله زمین رو غرقابی آبیاری می‌کنم و می‌خوام قطره‌ای کنم؛ برای شروع طراحی اول دبی آب مهم‌تره یا مساحت و تعداد ردیف‌ها")
        add("postuse", "postuse:endline-lowflow", "تیپ رو پهن کردم ولی انتهای بعضی ردیف‌ها آب کمتره؛ بیشتر باید طول ردیف و فشار رو چک کنم یا احتمال گرفتگی هم هست")
    elif fam == "pipe":
        add("size", "pipe:size-from-source", "خروجی آب من ۳ اینچه؛ برای انتخاب سایز این لوله فقط سایز خروجی پمپ کافیه یا دبی، طول مسیر و افت فشار هم باید حساب بشه")
        add("slope", "pipe:slope", "زمینم شیب داره؛ برای انتقال آب با این مدل، اختلاف ارتفاع روی انتخاب سایز یا فشار کاری اثر می‌ذاره")
        add("compare", "pipe:pe-vs-layflat", "برای انتقال آب لوله پلی‌اتیلن بهتره یا لوله نخدار؛ چه زمانی هزینه و دردسر جمع‌کردن نخدار ارزشش رو داره")
        add("longrun", "pipe:long-distance", "مسیر انتقال آبم چندصد متره؛ برای اینکه آخر خط افت فشار زیادی نداشته باشم چه اطلاعاتی برای انتخاب قطر مناسب لازمه")
        add("maintenance", "pipe:seasonal-storage", "اگر این لوله یک فصل کامل زیر آفتاب استفاده بشه آخر فصل بهتره جمعش کنیم یا موندن در زمین مشکلی نداره")
        add("season", f"pipe:season:{iran_season()}", f"با توجه به اینکه الان فصل {iran_season()} هست، برای نگهداری یا جمع‌کردن این لوله نکته خاصی هست که رعایت کنم")
    elif fam in ("fitting","valve"):
        add("compatibility", "fitting:pe-size", f"برای نصب {name} روی لوله پلی‌اتیلن هم‌سایز، مستقیم بسته میشه یا رابط و تبدیل جدا هم لازم دارم")
        add("pvc", "fitting:pvc", f"از {name} روی لوله پولیکا هم میشه استفاده کرد یا ساختارش فقط برای پلی‌اتیلن طراحی شده")
        add("installer", "fitting:washer-vs-clamp", "نصاب گفته با واشر از لوله خروجی بگیرم؛ از نظر نشتی و دوام واشر بهتره یا کمربند")
        add("many_outlets", "fitting:100-outlets", "اگر حدود ۱۰۰ تا خروجی بخوام بگیرم، استفاده از رابط ساده بهتره یا شیر خروجی که هر خط رو جدا کنترل کنم")
        add("nonag", "use:building", f"از {name} برای تأسیسات ساختمون یا خط آب حیاط هم میشه استفاده کرد یا بهتره مدل مخصوص ساختمان بگیرم")
        add("market_size", "fitting:market-size", "لوله‌ای دارم که نصاب بهش سایز ۵ ساختمانی میگه؛ برای خرید اتصال یا سوپاپ چطور سایز اینچ درستش رو مشخص کنم")
        add("postuse", "postuse:leak", f"{name} رو نصب کردم ولی کمی نشتی داره؛ اول باید واشر و محل نصب رو بررسی کنم یا سفت‌کردن بیشتر ممکنه به قطعه آسیب بزنه")
    elif fam == "filter":
        add("water_quality", "filter:sand", "آب چاه من کمی شن میاره؛ برای انتخاب این فیلتر فقط دبی مهمه یا مقدار شن و نوع آبیاری هم باید مشخص باشه")
        add("flow", "filter:flow", "برای اینکه این فیلتر باعث افت فشار زیاد نشه، دبی پمپ و فشار ورودی رو چطور باید با ظرفیت فیلتر تطبیق بدم")
        add("maintenance", "filter:cleaning", "برای آب چاه معمولاً هر چند وقت یکبار باید این فیلتر رو شست‌وشو یا سرویس کرد و از کجا بفهمم زمانش رسیده")
    elif fam == "fertigation":
        add("capacity", "fertigation:capacity", "برای انتخاب حجم تانک کود، مساحت زمین و دبی سیستم مهم‌تره یا مقدار کودی که در هر نوبت تزریق می‌کنم")
        add("method", "fertigation:method", "برای تزریق کود در سیستم قطره‌ای این مدل چه تفاوتی با ونتوری داره و برای مزرعه متوسط کدوم روش کنترل بهتری میده")
    elif fam == "sprinkler":
        add("pressure", "sprinkler:pressure", "برای اینکه پاشش این آبپاش یکنواخت باشه حداقل چه اطلاعاتی از فشار و دبی پمپ باید داشته باشم")
        add("slope", "sprinkler:slope", "زمینم شیب داره؛ برای چیدمان این آبپاش‌ها باید فاصله یا زون‌بندی رو تغییر بدم")
    else:
        add("use", "generic:fit", f"برای اینکه مطمئن بشم {name} برای کار من مناسبه، قبل از خرید چه مشخصاتی از شرایط کار باید بگم")
        add("difference", "generic:compare", f"تفاوت اصلی {name} با مدل‌های مشابه ارزون‌تر چیه و برای چه شرایطی پرداخت اختلاف قیمت منطقیه")
    if style == "colloquial":
        add("simple_help", f"human:simple:{fam}", f"من خیلی فنی نیستم؛ برای اینکه بفهمم {name} به کارم میاد دقیقاً چه چیزایی رو باید اندازه بگیرم یا بگم")
    elif style == "technical":
        add("technical", f"human:technical:{fam}", f"برای انتخاب مهندسی {name} کدام پارامترهای طراحی یا شرایط بهره‌برداری باید قبل از سفارش کنترل شوند")
    return c

def choose_candidate(p, fam, existing_texts, used_keys, style, rng):
    cand = core_candidates(p, fam, style, rng)
    rng.shuffle(cand)
    for x in cand:
        if x["key"] in used_keys: continue
        if any(jaccard(x["core"], q) >= .72 for q in existing_texts): continue
        return x
    for x in cand:
        if not any(jaccard(x["core"], q) >= .82 for q in existing_texts):
            x = dict(x); x["key"] += ":v" + str(len(existing_texts)+1); return x
    return None

def generated_comments(all_comments, cfg):
    name = cfg["author_name"].strip()
    email = cfg["author_email"].strip().lower()
    out=[]
    for c in all_comments:
        if str(c.get("author_name") or "").strip() == name or str(c.get("author_email") or "").strip().lower() == email:
            out.append(c)
    return out

def comment_text(c):
    content = c.get("content") or {}
    if isinstance(content, dict): return strip_html(content.get("raw") or content.get("rendered") or "")
    return strip_html(str(content))

def due_from_history(hist, cfg):
    if hist:
        c = hist[0]
        d = parse_dt(c.get("date_gmt") or c.get("date"))
        seed = f"comment:{c.get('id')}:{c.get('post')}"
    else:
        d = parse_dt(cfg.get("campaign_start_utc"))
        seed = f"start:{cfg.get('campaign_start_utc')}"
    if not d: return None
    jitter = stable_jitter(seed, int(cfg["min_interval_seconds"]), int(cfg["max_interval_seconds"]))
    return d + dt.timedelta(seconds=jitter), jitter

def choose_product(products, hist, rng):
    eligible = [p for p in products if p.get("status") == "publish" and p.get("reviews_allowed", True)]
    if not eligible: raise RuntimeError("No eligible published products with comments/reviews enabled")
    counts = {int(p["id"]):0 for p in eligible}
    recent_ids=[]
    for c in hist:
        pid = int(c.get("post") or 0)
        if pid in counts:
            counts[pid]+=1; recent_ids.append(pid)
    min_count = min(counts.values())
    pool = [p for p in eligible if counts[int(p["id"])] == min_count]
    recent_block = set(recent_ids[:12])
    pool2 = [p for p in pool if int(p["id"]) not in recent_block]
    if pool2: pool = pool2
    return rng.choice(pool)

def quality(question, candidate, fam, existing):
    score=100
    if len(question) < 20: score-=10
    if len(question) > 350: score-=5
    if "؟" not in question: score-=10
    if any(w in norm(question) for w in ["قطعا", "حتما جواب", "تضمینی"]): score-=20
    if any(jaccard(question, q) >= .72 for q in existing): score-=20
    if fam == "pesticide" and re.search(r"\b\d+(?:[\.,]\d+)?\s*(?:لیتر|کیلو|گرم|سی سی|cc)\b", question, re.I): score-=30
    if not candidate.get("key"): score-=10
    return max(0,score)

def load_cfg():
    return json.load(open(CONFIG_PATH, encoding="utf-8"))

def write_result(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: json.dump(obj,f,ensure_ascii=False,indent=2)

def run(action, result_path):
    cfg=load_cfg(); wp=WP(); rng=random.SystemRandom(); now=now_utc()
    allc = wp.comments(pages=max(2, int(cfg.get("history_window",200))//100+1))
    ghist=generated_comments(allc,cfg)
    ghist.sort(key=lambda x: str(x.get("date_gmt") or x.get("date") or ""), reverse=True)
    texts=[comment_text(x) for x in ghist if comment_text(x)]
    if action == "status":
        due=due_from_history(ghist,cfg)
        res={"ok":True,"action":action,"enabled":bool(cfg.get("enabled")),"generated_comments_seen":len(ghist),"next_due_utc":iso(due[0]) if due else None,"jitter_seconds":due[1] if due else None}
        write_result(result_path,res); return res
    if action == "scheduled":
        if not cfg.get("enabled"):
            res={"ok":True,"action":action,"skipped":"disabled"}; write_result(result_path,res); return res
        end=parse_dt(cfg.get("campaign_end_utc"))
        if end and now >= end:
            res={"ok":True,"action":action,"skipped":"campaign-ended","campaign_end_utc":iso(end)}; write_result(result_path,res); return res
        due=due_from_history(ghist,cfg)
        if not due:
            raise RuntimeError("Enabled campaign has no campaign_start_utc")
        due_at,jitter=due; look=int(cfg.get("scheduler_lookahead_seconds",900))
        if due_at > now + dt.timedelta(seconds=look):
            res={"ok":True,"action":action,"skipped":"not-due-in-window","next_due_utc":iso(due_at),"jitter_seconds":jitter}; write_result(result_path,res); return res
        wait=max(0,(due_at-now_utc()).total_seconds())
        if wait: time.sleep(wait)
        action="submit_one"
    products=wp.products(cfg)
    p=choose_product(products,ghist,rng)
    pid=int(p["id"]); fam=family(p)
    pc=wp.comments(pages=5,post=pid)
    existing=[comment_text(x) for x in pc if comment_text(x)]
    used_keys=set()
    for q in existing:
        nq=norm(q)
        for key, terms in {
            "commerce:bulk":["عمده","تعداد بالا","قیمت همکاری"],
            "commerce:price-freshness":["قیمت","به روز","به‌روز"],
            "commerce:discount":["تخفیف"],
            "irrigation:slope":["شیب"],
            "plant:symptom:yellowing":["زرد"],
            "fitting:pvc":["پولیکا"],
            "fitting:washer-vs-clamp":["واشر","کمربند"]
        }.items():
            if any(norm(t) in nq for t in terms): used_keys.add(key)
    style=style_from_history(texts,cfg,rng); polite=polite_from_history(texts,cfg,rng)
    candidate=choose_candidate(p,fam,existing,used_keys,style,rng)
    if not candidate: raise RuntimeError(f"No non-duplicate candidate for product {pid}")
    question=wrap(candidate["core"],polite,style,rng)
    score=quality(question,candidate,fam,existing)
    threshold=int(cfg.get("quality_threshold",97))
    base={"product_id":pid,"product_name":p.get("name"),"product_url":p.get("permalink"),"family":fam,"intent":candidate["intent"],"semantic_key":candidate["key"],"style":style,"polite":polite,"question":question,"quality_score":score,"catalog_size":len(products)}
    if score < threshold: raise RuntimeError(f"Quality score {score} below threshold {threshold}")
    if action == "dry_run":
        res={"ok":True,"action":action,**base}; write_result(result_path,res); return res
    if action != "submit_one": raise RuntimeError(f"Unsupported action: {action}")
    created=wp.submit_comment(pid,question,cfg)
    cid=int(created.get("id") or 0)
    if not cid: raise RuntimeError("Comment create returned no id")
    rb=wp.comment(cid)
    if int(rb.get("post") or 0)!=pid or norm(comment_text(rb))!=norm(question): raise RuntimeError("Comment readback mismatch")
    res={"ok":True,"action":"submit_one","comment_id":cid,"comment_status":rb.get("status"),"comment_type":rb.get("type"),"submitted_at_utc":rb.get("date_gmt") or rb.get("date"),**base}
    write_result(result_path,res); return res

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--action",required=True,choices=["status","dry_run","submit_one","scheduled"]); ap.add_argument("--result",required=True)
    a=ap.parse_args()
    for key in ("WP_BASE_URL","WP_USERNAME","WP_APP_PASSWORD"):
        if not os.environ.get(key,"").strip(): raise SystemExit(f"Missing secret {key}")
    try:
        res=run(a.action,a.result); print(json.dumps(res,ensure_ascii=False))
    except Exception as exc:
        write_result(a.result,{"ok":False,"action":a.action,"error":str(exc)})
        raise
if __name__=="__main__": main()
