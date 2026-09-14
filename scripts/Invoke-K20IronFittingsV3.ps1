param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
if(-not(Test-Path -LiteralPath $RequestPath)){throw "Request file not found: $RequestPath"}
. (Join-Path $PSScriptRoot 'coupling/CommonApi.ps1')

$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 50
$mode=if($req.mode){[string]$req.mode}else{'audit'}
if($mode -notin @('audit','apply_content')){Fail "Unsupported mode: $mode"}
$slug=if($req.category_slug){[string]$req.category_slug}else{'cast-iron-steel-fittings'}
$updateCategory=if($null-ne$req.update_category){[bool]$req.update_category}else{$true}
$maxRelated=if($req.max_related){[int]$req.max_related}else{4}
if($maxRelated-lt2-or$maxRelated-gt6){Fail 'max_related must be 2..6'}

function Get-CategoryProducts([int]$CategoryId){
  $all=@()
  for($page=1;$page-le10;$page++){
    $response=Invoke-K20 'GET' "wp-json/wc/v3/products?category=$CategoryId&status=publish&orderby=id&order=asc&per_page=100&page=$page"
    $items=@();foreach($p in $response){$items+=$p}
    if($items.Count-eq0){break}
    foreach($p in $items){$all+=$p}
    if($items.Count-lt100){break}
  }
  return $all
}

$catResponse=Invoke-K20 'GET' ("wp-json/wc/v3/products/categories?slug="+[Uri]::EscapeDataString($slug)+"&per_page=100")
$cats=@();foreach($c in $catResponse){$cats+=$c}
if($cats.Count-ne1){Fail "Expected one category for slug $slug; got $($cats.Count)"}
$cat=$cats[0];$catId=[int]$cat.id
$products=@(Get-CategoryProducts $catId)
if($products.Count-eq0){Fail 'No published products found in target category.'}

function Get-Family([string]$Name){
  $n=Normalize-InchText $Name
  if($n-match 'سر\s*شلنگ'){return 'hose_tail'}
  if($n-match 'بست\s*تک\s*کپه'){return 'clamp_single_cap'}
  if($n-match 'بست\s*دو\s*کپه'){return 'clamp_double_cap'}
  if($n-match 'بست\s*هندلی'){return 'clamp_handle'}
  if($n-match 'بست\s*و\s*قلاب\s*اهرمی'){return 'clamp_lever_hook'}
  if($n-match 'سوپاپ'){
    if($n-match 'چدنی'){return 'valve_cast'}
    if($n-match 'آهنی'){return 'valve_iron'}
    return 'valve'
  }
  if($n-match 'فلنچ|فلنج'){
    if($n-match 'کور'){return 'blind_flange'}
    if($n-match 'چهار\s*راه'){return 'four_way_flanged'}
    if($n-match 'سه\s*راه'){return 'tee_flanged'}
    if($n-match 'تبدیل'){return 'reducer_flanged'}
    return 'threaded_flange'
  }
  if($n-match 'رابط.*پرسی.*ش[یي]لنگ'){return 'pressed_hose_adapter'}
  if($n-match 'رابط|اتصال'){return 'adapter'}
  return 'unknown'
}

function Get-InchSizes([string]$Name){
  $n=Normalize-InchText $Name
  $vals=@()
  $pair=[regex]::Match($n,'(?<!\d)(?<a>\d+(?:\.\d+)?)\s*(?:x|X|×|\*)\s*(?<b>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)',[Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if($pair.Success){$vals+=[double]$pair.Groups['a'].Value;$vals+=[double]$pair.Groups['b'].Value}
  foreach($m in [regex]::Matches($n,'(?<!\d)(?<i>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)',[Text.RegularExpressions.RegexOptions]::IgnoreCase)){$vals+=[double]$m.Groups['i'].Value}
  return @($vals|Sort-Object -Unique)
}

function Get-Material([string]$Name){
  $n=Normalize-Digits $Name
  if($n-match 'آلومینیوم|آلمینیوم'){return 'آلومینیومی'}
  if($n-match 'چدنی'){return 'چدنی'}
  if($n-match 'آهنی'){return 'آهنی'}
  if($n-match 'فلزی'){return 'فلزی'}
  return 'فلزی'
}

function Format-Inch([double]$Size){
  $s=$Size.ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
  return (Convert-ToPersianDigits $s)+' اینچ'
}
function Format-Sizes($Sizes){
  $a=@($Sizes)
  if($a.Count-eq0){return 'سایز درج‌شده در عنوان محصول'}
  if($a.Count-eq1){return (Format-Inch ([double]$a[0]))}
  return ((Format-Inch ([double]$a[0]))+' به '+(Format-Inch ([double]$a[1])))
}

function Family-Label([string]$Family){
  switch($Family){
    'hose_tail'{'سرشلنگی فلزی'}
    'clamp_single_cap'{'بست تک‌کپه'}
    'clamp_double_cap'{'بست دوکپه'}
    'clamp_handle'{'بست هندلی'}
    'clamp_lever_hook'{'بست و قلاب اهرمی'}
    'valve_cast'{'سوپاپ چدنی'}
    'valve_iron'{'سوپاپ آهنی'}
    'pressed_hose_adapter'{'رابط آهنی پرسی شیلنگ'}
    'reducer_flanged'{'تبدیل آهنی فلنجدار'}
    'four_way_flanged'{'چهارراه فلنجدار آهنی'}
    'tee_flanged'{'سه‌راه فلنجدار آهنی'}
    'blind_flange'{'فلنج کور آهنی'}
    'threaded_flange'{'فلنج دنده‌ای آهنی'}
    default{'اتصال فلزی'}
  }
}

function Get-UseText([string]$Family,[string]$SizeText){
  switch($Family){
    'hose_tail'{return "برای اتصال شیلنگ به بخش سازگار شبکه انتقال آب در سایز $SizeText استفاده می‌شود. بخش شیلنگ‌خور باید با قطر واقعی شیلنگ هماهنگ باشد و مهار مکانیکی آن با بست مناسب انجام شود."}
    'clamp_single_cap'{return "برای مهار و نگه‌داشتن اتصال شیلنگی هم‌سایز $SizeText به کار می‌رود. تطبیق قطر شیلنگ، قطعه داخل شیلنگ و نحوه قرارگیری کپه قبل از سفت‌کردن اهمیت دارد."}
    'clamp_double_cap'{return "برای مهار اتصال شیلنگی هم‌سایز $SizeText با ساختار دوکپه استفاده می‌شود. دو بخش بست باید یکنواخت و بدون کجی روی مجموعه قرار بگیرند تا فشار موضعی روی شیلنگ ایجاد نشود."}
    'clamp_handle'{return "برای قفل و مهار اتصال شیلنگی در سایز $SizeText استفاده می‌شود. عملکرد هندلی زمانی درست است که قطر شیلنگ و قطعه مقابل با سایز بست هماهنگ باشند و اهرم بدون فشار غیرعادی بسته شود."}
    'clamp_lever_hook'{return "برای مهار سریع اتصال شیلنگی هم‌سایز $SizeText به کمک مجموعه اهرم و قلاب استفاده می‌شود. سایز واقعی شیلنگ و قطعه مقابل باید دقیقاً با بست تطبیق داشته باشد."}
    'valve_iron'{return "سوپاپ آهنی $SizeText برای استفاده در مسیر آب و تجهیزات هم‌سایز انتخاب می‌شود. جهت نصب و وضعیت عملکرد قطعه باید مطابق ساختار و علامت‌های روی بدنه همان محصول انجام شود."}
    'valve_cast'{return "سوپاپ چدنی $SizeText برای استفاده در مسیر آب و تجهیزات هم‌سایز انتخاب می‌شود. هنگام نصب، جهت جریان، نوع اتصال و آب‌بندی قطعه مقابل باید با خود سوپاپ هماهنگ باشد."}
    'pressed_hose_adapter'{return "برای اتصال شیلنگ به رابط آهنی پرسی در سایز $SizeText استفاده می‌شود. قطر شیلنگ، قطعات پرس و تجهیز سمت مقابل باید یک مجموعه سازگار تشکیل دهند."}
    'reducer_flanged'{return "برای اتصال دو بخش فلنجی با سایزهای متفاوت $SizeText استفاده می‌شود. هر دو سمت تبدیل باید جداگانه با فلنج مقابل، الگوی پیچ و آب‌بندی همان سمت تطبیق داده شوند."}
    'four_way_flanged'{return "برای ایجاد چهار مسیر فلنجی هم‌سایز $SizeText در شبکه انتقال آب استفاده می‌شود. همه دهانه‌ها باید از نظر سایز، فلنج مقابل، واشر و الگوی پیچ با مسیر طراحی‌شده هماهنگ باشند."}
    'tee_flanged'{return "برای ایجاد یک انشعاب سه‌جهته فلنجی هم‌سایز $SizeText در شبکه انتقال آب استفاده می‌شود. مسیر اصلی و شاخه انشعاب باید پیش از نصب از نظر جهت و فضای مونتاژ مشخص باشند."}
    'blind_flange'{return "برای بستن انتهای یک مسیر فلنجی در سایز $SizeText استفاده می‌شود. آب‌بندی این نقطه به تطبیق سطح فلنج، واشر مناسب و سفت‌کردن یکنواخت پیچ‌ها وابسته است."}
    'threaded_flange'{return "برای ایجاد اتصال بین بخش رزوه‌ای و مجموعه فلنجی در سایز $SizeText استفاده می‌شود. رزوه و فلنج دو بخش مستقل‌اند و هر دو باید با قطعه مقابل سازگار باشند."}
    default{return "برای تکمیل شبکه انتقال آب در سایز $SizeText استفاده می‌شود و انتخاب آن باید بر اساس نوع اتصال و قطعه مقابل انجام شود."}
  }
}

function Get-BuyChecks([string]$Family){
  if($Family-match '^clamp_|^hose_tail$|pressed_hose_adapter'){
    return @('قطر واقعی شیلنگ را با سایز محصول تطبیق دهید.','نوع قطعه‌ای که داخل یا مقابل شیلنگ قرار می‌گیرد مشخص باشد.','بست یا روش مهار را متناسب با ساختار همان اتصال انتخاب کنید.','پس از نصب، اتصال را از نظر لغزش شیلنگ و نشتی کنترل کنید.')
  }
  if($Family-match '^valve_'){
    return @('سایز دهانه و نوع اتصال دو طرف را با مسیر تطبیق دهید.','جهت نصب را از روی ساختار یا علامت روی بدنه همان قطعه رعایت کنید.','روش آب‌بندی را متناسب با نوع اتصال همان محصول انتخاب کنید.','پس از آبگیری، عملکرد قطعه و نبود نشتی را کنترل کنید.')
  }
  if($Family-match 'flange|flanged'){
    return @('سایز اسمی هر فلنج را با قطعه مقابل تطبیق دهید.','الگوی سوراخ پیچ و سطح نشیمن دو فلنج باید سازگار باشد.','واشر مناسب بین سطوح فلنجی قرار گیرد.','پیچ‌ها را به‌صورت متقاطع و یکنواخت سفت کنید و از کشیدن لوله با پیچ‌ها خودداری کنید.')
  }
  return @('سایز و نوع اتصال را با قطعه مقابل تطبیق دهید.','مسیر نصب را بدون تنش و کجی آماده کنید.','آب‌بندی متناسب با نوع اتصال انجام شود.','بعد از راه‌اندازی محل اتصال را از نظر نشتی کنترل کنید.')
}

function Get-RelatedFamilies([string]$Family){
  switch($Family){
    'hose_tail'{return @('clamp_handle','clamp_single_cap','clamp_double_cap','clamp_lever_hook','pressed_hose_adapter')}
    'clamp_single_cap'{return @('hose_tail','clamp_handle','clamp_double_cap','clamp_lever_hook')}
    'clamp_double_cap'{return @('hose_tail','clamp_handle','clamp_single_cap','clamp_lever_hook')}
    'clamp_handle'{return @('hose_tail','clamp_single_cap','clamp_double_cap','clamp_lever_hook')}
    'clamp_lever_hook'{return @('hose_tail','clamp_handle','clamp_single_cap','clamp_double_cap')}
    'pressed_hose_adapter'{return @('hose_tail','clamp_handle','clamp_single_cap','clamp_double_cap')}
    'valve_iron'{return @('threaded_flange','blind_flange','tee_flanged','four_way_flanged')}
    'valve_cast'{return @('threaded_flange','blind_flange','tee_flanged','four_way_flanged')}
    'blind_flange'{return @('threaded_flange','tee_flanged','four_way_flanged','reducer_flanged')}
    'threaded_flange'{return @('blind_flange','tee_flanged','four_way_flanged','reducer_flanged')}
    'tee_flanged'{return @('blind_flange','threaded_flange','four_way_flanged','reducer_flanged')}
    'four_way_flanged'{return @('blind_flange','threaded_flange','tee_flanged','reducer_flanged')}
    'reducer_flanged'{return @('threaded_flange','blind_flange','tee_flanged','four_way_flanged')}
    default{return @()}
  }
}

function Get-IntegritySnapshot($P){
  $o=[ordered]@{
    name=[string]$P.name;slug=[string]$P.slug;status=[string]$P.status;sku=[string]$P.sku;
    price=[string]$P.price;regular_price=[string]$P.regular_price;sale_price=[string]$P.sale_price;
    stock_status=[string]$P.stock_status;stock_quantity=$P.stock_quantity;manage_stock=$P.manage_stock;
    categories=@($P.categories|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});
    tags=@($P.tags|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});
    images=@($P.images|ForEach-Object{[ordered]@{id=[int]$_.id;src=[string]$_.src}});
    attributes=@($P.attributes);upsell_ids=@($P.upsell_ids);cross_sell_ids=@($P.cross_sell_ids)
  }
  return ($o|ConvertTo-Json -Depth 30 -Compress)
}

$targets=@()
foreach($p in $products){
  $targets+=[pscustomobject][ordered]@{
    id=[int]$p.id;name=[string]$p.name;permalink=[string]$p.permalink;family=(Get-Family ([string]$p.name));
    material=(Get-Material ([string]$p.name));sizes_inch=@(Get-InchSizes ([string]$p.name));stock_status=[string]$p.stock_status
  }
}
$unknown=@($targets|Where-Object{$_.family-eq'unknown'})
$noSize=@($targets|Where-Object{@($_.sizes_inch).Count-eq0})

function Get-Related($Target){
  $families=@(Get-RelatedFamilies ([string]$Target.family))
  if($families.Count-eq0){return @()}
  $sizes=@($Target.sizes_inch);$rows=@()
  foreach($family in $families){
    foreach($candidate in $targets){
      if([int]$candidate.id-eq[int]$Target.id){continue}
      if([string]$candidate.family-ne$family){continue}
      if([string]$candidate.stock_status-ne'instock'){continue}
      $common=$false
      foreach($a in $sizes){
        foreach($b in @($candidate.sizes_inch)){if([double]$a-eq[double]$b){$common=$true;break}}
        if($common){break}
      }
      if(-not$common){continue}
      $rows+=$candidate;break
    }
    if($rows.Count-ge$maxRelated){break}
  }
  return @($rows|Select-Object -First $maxRelated)
}

function Build-Short($Target){
  $name=[Net.WebUtility]::HtmlEncode([string]$Target.name)
  $sizeText=Format-Sizes @($Target.sizes_inch)
  $use=Get-UseText ([string]$Target.family) $sizeText
  return '<div dir="rtl"><p><strong>'+$name+'</strong> — '+$use+' پیش از سفارش، سایز و نوع اتصال را با قطعه واقعی پروژه تطبیق دهید.</p></div>'
}

function Build-Description($Target){
  $name=[Net.WebUtility]::HtmlEncode([string]$Target.name)
  $family=[string]$Target.family;$label=Family-Label $family;$material=[string]$Target.material
  $sizeText=Format-Sizes @($Target.sizes_inch)
  $use=Get-UseText $family $sizeText
  $checks=@(Get-BuyChecks $family)
  $related=@(Get-Related $Target)
  $checkItems=($checks|ForEach-Object{'<li>'+[Net.WebUtility]::HtmlEncode([string]$_)+'</li>'})-join"`n"
  if($related.Count-gt0){
    $items=@()
    foreach($r in $related){
      $url=[Net.WebUtility]::HtmlEncode([string]$r.permalink);$rn=[Net.WebUtility]::HtmlEncode([string]$r.name)
      $items+='<li><a href="'+$url+'"><strong>'+$rn+'</strong></a> — هم‌سایز و از خانواده مکمل همین اتصال.</li>'
    }
    $relatedHtml='<h2>قطعات مکمل هم‌سایز</h2><p>پیشنهادهای زیر فقط از محصولات واقعی همین فروشگاه و با سایز مشترک انتخاب شده‌اند؛ محصول نامرتبط یا سایز نزدیک جایگزین نشده است.</p><ul>'+($items-join"`n")+'</ul>'
  }else{
    $relatedHtml='<h2>قطعات مکمل</h2><p>برای این سایز، مکمل دقیق و موجودی که معیار هم‌سایزی و خانواده سازگار را هم‌زمان داشته باشد پیدا نشد؛ به همین دلیل لینک نامرتبط یا سایز جایگزین نمایش داده نمی‌شود.</p>'
  }
  $specific=''
  if($family-match'flange|flanged'){$specific='<p><strong>نکته فلنجی:</strong> سایز اسمی به‌تنهایی برای مونتاژ کافی نیست؛ سطح فلنج، آرایش سوراخ‌ها، پیچ‌ها و واشر قطعه مقابل باید با این اتصال هماهنگ باشد. رده فشار یا استانداردی که در عنوان محصول ذکر نشده، در این صفحه حدس زده نشده است.</p>'}
  elseif($family-match'^clamp_|hose_tail|pressed_hose_adapter'){$specific='<p><strong>نکته شیلنگ و بست:</strong> انتخاب را از قطر واقعی شیلنگ و قطعه داخل شیلنگ شروع کنید. عدد اینچ روی عنوان زمانی مفید است که با شیلنگ و قطعه مقابل پروژه شما هم‌خوان باشد.</p>'}
  elseif($family-match'^valve_'){$specific='<p><strong>نکته سوپاپ:</strong> جهت نصب و جهت جریان را از روی شکل و علامت‌های خود قطعه رعایت کنید. مشخصات فشار یا نوع مکانیزم داخلی که در عنوان محصول درج نشده، در این توضیح به‌صورت فرضی اضافه نشده است.</p>'}

  return @"
<article dir="rtl" style="direction:rtl;text-align:right;line-height:2;color:#26352d">
<p><strong>$name</strong> از خانواده <strong>$label</strong> با جنس درج‌شده <strong>$material</strong> و سایز <strong>$sizeText</strong> است. $use</p>
<h2>کاربرد و انتخاب درست</h2>
<p>این قطعه را بر اساس محل نصب واقعی انتخاب کنید، نه صرفاً شباهت ظاهری. مهم‌ترین معیارها سایز اسمی، نوع اتصال، قطعه مقابل، روش آب‌بندی یا مهار و فضای مونتاژ هستند. فشار کاری، استاندارد رزوه یا رده فلنج فقط زمانی معتبر است که روی محصول یا مشخصات سازنده همان مدل درج شده باشد؛ بنابراین مقدار حدسی در این صفحه اضافه نشده است.</p>
$specific
<h2>چک‌لیست قبل از خرید</h2>
<ul>$checkItems</ul>
<h2>نکات نصب و راه‌اندازی</h2>
<p>پیش از بازکردن اتصال، فشار خط را قطع کنید. سطوح تماس و قطعات مقابل را تمیز و هم‌راستا کنید، مونتاژ را بدون اعمال نیروی جانبی انجام دهید و پس از راه‌اندازی، شبکه را مرحله‌ای آبگیری کنید. نشتی، حرکت غیرعادی، شل‌شدن بست یا تنش روی اتصال باید قبل از بهره‌برداری پیوسته برطرف شود.</p>
$relatedHtml
<h2>اشتباهات رایج</h2>
<ul><li>انتخاب محصول فقط بر اساس عدد اینچ بدون تطبیق قطعه مقابل.</li><li>استفاده از آب‌بندی یا بست نامتناسب با نوع اتصال.</li><li>تحمیل وزن، کشش یا کجی لوله و شیلنگ به محل اتصال.</li><li>جایگزین‌کردن سایز نزدیک به‌جای سایز دقیق.</li><li>فرض‌کردن فشار کاری یا استاندارد رزوه بدون مدرک همان محصول.</li></ul>
<h2>پرسش‌های پرتکرار درباره $name</h2>
<h3>مبنای اصلی انتخاب این محصول چیست؟</h3><p>سایز درج‌شده در عنوان، نوع اتصال و قطعه‌ای که مستقیماً به آن متصل می‌شود باید با هم تطبیق داشته باشند.</p>
<h3>آیا می‌توان از سایز نزدیک به‌جای این سایز استفاده کرد؟</h3><p>خیر؛ در اتصال شیلنگی، رزوه‌ای یا فلنجی، سایز نزدیک جایگزین مطمئنی برای سایز دقیق نیست.</p>
<h3>آیا فشار کاری این محصول از روی نام آن مشخص است؟</h3><p>خیر؛ در عنوان این محصول عددی برای فشار کاری ثبت نشده است، بنابراین فشار مجاز باید از مشخصات معتبر همان مدل گرفته شود.</p>
<h3>بعد از نصب چه چیزی کنترل شود؟</h3><p>آب‌بندی، هم‌راستایی اتصال، نبود تنش روی بدنه و ثابت‌بودن قطعات مهارکننده را در آبگیری اولیه کنترل کنید.</p>
<h3>چطور مکمل مناسب را انتخاب کنیم؟</h3><p>مکمل باید هم از نظر خانواده اتصال و هم از نظر سایز با همین محصول سازگار باشد؛ پیشنهادهای این صفحه فقط با همین دو شرط ساخته شده‌اند.</p>
</article>
"@
}

function Build-CategoryDescription(){
  return @"
<h2>خرید اتصالات چدنی و آهنی برای آبیاری و انتقال آب</h2>
<p>دسته <strong>اتصالات چدنی و آهنی</strong> کشاورز بیست شامل خانواده‌های واقعی موجود در همین کاتالوگ است: سرشلنگی فلزی، بست‌های تک‌کپه و دوکپه، بست هندلی، بست و قلاب اهرمی، سوپاپ آهنی و چدنی، رابط آهنی پرسی شیلنگ، تبدیل فلنجدار، سه‌راه و چهارراه فلنجدار، فلنج کور و فلنج دنده‌ای. انتخاب هرکدام باید بر اساس نوع اتصال و قطعه مقابل انجام شود، نه فقط نام یا ظاهر.</p>
<h2>از کدام خانواده استفاده کنیم؟</h2>
<ul>
<li><strong>سرشلنگی و بست‌ها:</strong> برای اتصال و مهار شیلنگ؛ قطر واقعی شیلنگ و نوع بست را هم‌زمان انتخاب کنید.</li>
<li><strong>رابط آهنی پرسی شیلنگ:</strong> برای مجموعه‌هایی که اتصال شیلنگ با روش پرس انجام می‌شود؛ شیلنگ و قطعات پرس باید سازگار باشند.</li>
<li><strong>سوپاپ آهنی و چدنی:</strong> برای مسیر آب در سایزهای مختلف؛ جهت نصب و نوع اتصال را از روی خود قطعه کنترل کنید.</li>
<li><strong>فلنج دنده‌ای و فلنج کور:</strong> برای اتصال رزوه به فلنج یا بستن انتهای مسیر فلنجی؛ واشر، پیچ و آرایش سوراخ‌ها اهمیت دارد.</li>
<li><strong>سه‌راه و چهارراه فلنجدار:</strong> برای ایجاد انشعاب‌های فلنجی هم‌سایز در شبکه.</li>
<li><strong>تبدیل فلنجدار:</strong> برای اتصال دو سایز فلنجی متفاوت؛ هر دو سمت باید مستقل تطبیق داده شوند.</li>
</ul>
<h2>راهنمای انتخاب سایز</h2>
<p>در این دسته سایزهای مختلف اینچی وجود دارد. برای محصولات شیلنگی، قطر واقعی شیلنگ و برای محصولات فلنجی، سایز فلنج مقابل ملاک است. در تبدیل‌های فلنجدار دو سایز جداگانه وجود دارد و نباید یکی از آن‌ها را به کل اتصال تعمیم داد. هیچ سایز نزدیک یا تبدیل میلی‌متر/اینچ نامطمئن به‌عنوان جایگزین پیشنهاد نمی‌شود.</p>
<h2>نکات نصب و آب‌بندی</h2>
<p>اتصالات فلنجی به سطح تماس سالم، واشر مناسب و سفت‌کردن یکنواخت پیچ‌ها نیاز دارند. اتصالات شیلنگی باید بدون کشش و کجی مهار شوند. در اتصالات رزوه‌ای نیز نوع رزوه و روش آب‌بندی باید با قطعه مقابل سازگار باشد. پس از نصب، خط را مرحله‌ای آبگیری و تمام نقاط اتصال را از نظر نشتی و حرکت غیرعادی کنترل کنید.</p>
<h2>سوالات رایج</h2>
<h3>آیا همه اتصالات این دسته فشار کاری یکسان دارند؟</h3><p>خیر. فشار کاری از نام خانواده یا سایز قابل تعمیم نیست و فقط مشخصات معتبر همان محصول ملاک است.</p>
<h3>برای فلنج فقط دانستن سایز اینچ کافی است؟</h3><p>خیر. علاوه بر سایز، آرایش سوراخ پیچ، سطح فلنج، واشر و قطعه مقابل نیز باید سازگار باشند.</p>
<h3>برای سرشلنگی چه بستی انتخاب کنیم؟</h3><p>بستی انتخاب کنید که هم با قطر واقعی شیلنگ و هم با سرشلنگی همان سایز سازگار باشد. محصولات هم‌سایز موجود در صفحات محصول به‌عنوان مکمل نمایش داده می‌شوند.</p>
"@
}

$familyCounts=@();foreach($g in ($targets|Group-Object family|Sort-Object Name)){$familyCounts+=[ordered]@{family=$g.Name;count=$g.Count}}
$changes=@();$categoryChange=$null

if($mode-eq'apply_content'){
  if($unknown.Count-gt0){Fail "Refusing apply: unknown product IDs $((@($unknown.id)-join','))"}
  if($noSize.Count-gt0){Fail "Refusing apply: missing parsed size for IDs $((@($noSize.id)-join','))"}

  $beforeById=@{}
  foreach($p in $products){$beforeById[[int]$p.id]=$p}
  $desiredById=@{}
  $updates=@()
  foreach($t in $targets){
    $id=[int]$t.id;$before=$beforeById[$id]
    $desiredShort=Build-Short $t;$desiredDescription=Build-Description $t
    $desiredById[$id]=[ordered]@{short=$desiredShort;description=$desiredDescription;integrity=(Get-IntegritySnapshot $before)}
    $already=(([string]$before.short_description)-ceq$desiredShort)-and(([string]$before.description)-ceq$desiredDescription)
    if(-not$already){$updates+=[ordered]@{id=$id;short_description=$desiredShort;description=$desiredDescription}}
  }
  if($updates.Count-gt0){$null=Invoke-K20 'POST' 'wp-json/wc/v3/products/batch' ([ordered]@{update=@($updates)})}

  $afterProducts=@(Get-CategoryProducts $catId)
  $afterById=@{};foreach($p in $afterProducts){$afterById[[int]$p.id]=$p}
  foreach($t in $targets){
    $id=[int]$t.id;$before=$beforeById[$id];$after=$afterById[$id];$desired=$desiredById[$id]
    if($null-eq$after){Fail "Readback product missing: $id"}
    $semantic=(([string]$after.short_description)-ceq[string]$desired.short)-and(([string]$after.description)-ceq[string]$desired.description)
    $integrity=((Get-IntegritySnapshot $after)-ceq[string]$desired.integrity)
    if(-not$semantic){Fail "Content readback failed for $id"}
    if(-not$integrity){Fail "Protected-field integrity mismatch for $id"}
    $changed= -not((([string]$before.short_description)-ceq[string]$desired.short)-and(([string]$before.description)-ceq[string]$desired.description))
    $changes+=[ordered]@{id=$id;name=[string]$t.name;family=[string]$t.family;changed=$changed;semantic_verified=$true;integrity_unchanged=$true;reason=if($changed){'written_and_verified'}else{'already_current'}}
  }

  if($updateCategory){
    $catBefore=Invoke-K20 'GET' "wp-json/wc/v3/products/categories/$catId"
    $catSnapshot=([ordered]@{id=[int]$catBefore.id;name=[string]$catBefore.name;slug=[string]$catBefore.slug;parent=[int]$catBefore.parent;count=[int]$catBefore.count}|ConvertTo-Json -Compress)
    $desiredCategory=Build-CategoryDescription
    $catAlready=([string]$catBefore.description)-ceq$desiredCategory
    if(-not$catAlready){$null=Invoke-K20 'PUT' "wp-json/wc/v3/products/categories/$catId" ([ordered]@{description=$desiredCategory})}
    $catAfter=Invoke-K20 'GET' "wp-json/wc/v3/products/categories/$catId"
    $catSemantic=([string]$catAfter.description)-ceq$desiredCategory
    $catIntegrity=(([ordered]@{id=[int]$catAfter.id;name=[string]$catAfter.name;slug=[string]$catAfter.slug;parent=[int]$catAfter.parent;count=[int]$catAfter.count}|ConvertTo-Json -Compress)-ceq$catSnapshot)
    if(-not$catSemantic){Fail 'Category description readback failed.'}
    if(-not$catIntegrity){Fail 'Category protected fields changed.'}
    $categoryChange=[ordered]@{id=$catId;changed=(-not$catAlready);semantic_verified=$true;integrity_unchanged=$true;reason=if($catAlready){'already_current'}else{'written_and_verified'}}
  }
}

$record=[ordered]@{
  ok=$true;mode=$mode;executed_at_utc=[DateTime]::UtcNow.ToString('o');
  category=[ordered]@{id=$catId;name=[string]$cat.name;slug=[string]$cat.slug;count=[int]$cat.count};
  product_count=$targets.Count;family_counts=@($familyCounts);unknown_count=$unknown.Count;no_size_count=$noSize.Count;
  unknown_products=@($unknown);no_size_products=@($noSize);targets=@($targets);category_change=$categoryChange;changes=@($changes);
  changed_count=@($changes|Where-Object{$_.changed}).Count;semantic_verified_count=@($changes|Where-Object{$_.semantic_verified}).Count;integrity_verified_count=@($changes|Where-Object{$_.integrity_unchanged}).Count
}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
$record|ConvertTo-Json -Depth 50|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "IRON_FITTINGS_OK mode=$mode products=$($targets.Count) unknown=$($unknown.Count) changed=$(@($changes|Where-Object{$_.changed}).Count)"
