param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw $Message }

$base = $env:WP_BASE_URL
$user = $env:WP_USERNAME
$pass = $env:WP_APP_PASSWORD
if ([string]::IsNullOrWhiteSpace($base) -or [string]::IsNullOrWhiteSpace($user) -or [string]::IsNullOrWhiteSpace($pass)) {
  Fail 'Required WordPress secrets are missing.'
}
$base = $base.TrimEnd('/')
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers = @{ Authorization = "Basic $auth"; Accept = 'application/json' }

function Invoke-K20([string]$Method,[string]$Path,$Body=$null) {
  $args = @{ Uri = $base + '/' + $Path.TrimStart('/'); Method = $Method; Headers = $headers; TimeoutSec = 180 }
  if ($null -ne $Body) {
    $args.ContentType = 'application/json; charset=utf-8'
    $args.Body = ($Body | ConvertTo-Json -Depth 100 -Compress)
  }
  return Invoke-RestMethod @args
}

function Get-Paged([string]$Route) {
  $all = @()
  $sep = if ($Route.Contains('?')) { '&' } else { '?' }
  for ($page=1; $page -le 20; $page++) {
    $response = Invoke-K20 'GET' ("$Route${sep}per_page=100&page=$page")
    $items = @($response | ForEach-Object { $_ })
    if ($items.Count -eq 0) { break }
    $all += $items
    if ($items.Count -lt 100) { break }
  }
  return @($all)
}

function Norm([string]$Text) {
  if ($null -eq $Text) { return '' }
  $x = $Text.Replace('ي','ی').Replace('ك','ک').Replace('‌',' ').Replace('ۀ','ه').Replace('ة','ه')
  return ([regex]::Replace($x,'\s+',' ').Trim())
}

function H([string]$Text) {
  if ($null -eq $Text) { return '' }
  return [System.Net.WebUtility]::HtmlEncode($Text)
}

function Test-CategoryId($Product,[int]$CategoryId) {
  foreach ($c in @($Product.categories)) { if ([int]$c.id -eq $CategoryId) { return $true } }
  return $false
}

function Get-Family([string]$Name) {
  $n = Norm $Name
  if ($n -match 'کپسول') { return 'root_capsule' }
  if ($n -match 'سه\s*راه.*(?:قطره\s*چکان|دریپر)|سه‌راه.*(?:قطره\s*چکان|دریپر)') { return 'emitter_tee' }
  if ($n -match 'بابلر') { return 'bubbler' }
  if ($n -match 'دریپر|قطره\s*چکان|قطره‌چکان') { return 'dripper' }
  if ($n -match 'واشر.*(?:16|۱۶)') { return 'starter_washer' }
  if ($n -match 'بست\s*ابتدایی') { return 'starter_fitting' }
  if ($n -match 'کور(?:کن)?|درپوش') {
    if ($n -match 'لی\s*فلت|لی‌فلت') { return 'layflat_endcap' }
    if ($n -match '16|۱۶') { return 'endcap_16' }
  }
  if ($n -match 'انشعاب.*(?:دو\s*شاخه|دوشاخه|سه\s*شاخه|سه‌شاخه)') { return 'multi_branch' }
  if ($n -match 'شیر') {
    if ($n -match 'تیپ|نوار') { return 'tape_valve' }
    if ($n -match '16\s*(?:به|×|x)\s*16|۱۶\s*(?:به|×|x)\s*۱۶') { return 'line_valve_16' }
    if ($n -match '16|۱۶' -and $n -match '1\s*/\s*2|۱\s*/\s*۲') { return 'transition_valve' }
    return 'irrigation_valve'
  }
  if ($n -match 'رابط') {
    if ($n -match 'تیپ|نوار') {
      if ($n -match 'لی\s*فلت|لی‌فلت') { return 'tape_layflat_adapter' }
      if ($n -match '(?:تیپ|نوار).*(?:تیپ|نوار)') { return 'tape_coupling' }
      if ($n -match '16|۱۶') { return 'tape_16_adapter' }
      return 'tape_adapter'
    }
    if ($n -match '16|۱۶') { return 'coupling_16' }
    return 'generic_fitting'
  }
  if ($n -match 'سه\s*راه|سه‌راه') {
    if ($n -match '16|۱۶') { return 'tee_16' }
    return 'generic_fitting'
  }
  if ($n -match 'زانو') {
    if ($n -match '16|۱۶') { return 'elbow_16' }
    return 'generic_fitting'
  }
  if ($n -match 'پانچ|گردبر|مته') { return 'installation_tool' }
  if ($n -match 'بست|انشعاب') { return 'generic_fitting' }
  return 'generic_accessory'
}

function Get-ProtectedSnapshot($Product) {
  $obj = [ordered]@{
    id = [int]$Product.id
    slug = [string]$Product.slug
    sku = [string]$Product.sku
    status = [string]$Product.status
    catalog_visibility = [string]$Product.catalog_visibility
    featured = [bool]$Product.featured
    price = [string]$Product.price
    regular_price = [string]$Product.regular_price
    sale_price = [string]$Product.sale_price
    stock_status = [string]$Product.stock_status
    manage_stock = [bool]$Product.manage_stock
    stock_quantity = $Product.stock_quantity
    categories = @($Product.categories | ForEach-Object { [int]$_.id } | Sort-Object)
    tags = @($Product.tags | ForEach-Object { [int]$_.id } | Sort-Object)
    images = @($Product.images | ForEach-Object { [int]$_.id })
    attributes = @($Product.attributes | ForEach-Object { [ordered]@{id=$_.id;name=$_.name;options=@($_.options)} })
  }
  return ($obj | ConvertTo-Json -Depth 20 -Compress)
}

function Get-RelatedFamilies([string]$Family) {
  switch ($Family) {
    'dripper' { return @('coupling_16','starter_fitting','endcap_16','line_valve_16','tee_16') }
    'bubbler' { return @('coupling_16','starter_fitting','line_valve_16','tee_16') }
    'root_capsule' { return @('dripper','coupling_16','line_valve_16','tee_16') }
    'emitter_tee' { return @('dripper','coupling_16','line_valve_16','endcap_16') }
    'tape_valve' { return @('tape_coupling','tape_16_adapter','tape_layflat_adapter','tape_adapter') }
    'tape_layflat_adapter' { return @('tape_coupling','tape_valve','layflat_endcap','tape_16_adapter') }
    'tape_16_adapter' { return @('tape_coupling','line_valve_16','coupling_16','tape_valve') }
    'tape_coupling' { return @('tape_valve','tape_16_adapter','tape_layflat_adapter','tape_adapter') }
    'tape_adapter' { return @('tape_coupling','tape_valve','tape_16_adapter','tape_layflat_adapter') }
    'coupling_16' { return @('tee_16','elbow_16','endcap_16','line_valve_16','starter_fitting') }
    'tee_16' { return @('coupling_16','elbow_16','endcap_16','line_valve_16') }
    'elbow_16' { return @('coupling_16','tee_16','endcap_16','line_valve_16') }
    'endcap_16' { return @('coupling_16','tee_16','elbow_16','line_valve_16') }
    'starter_fitting' { return @('starter_washer','coupling_16','endcap_16','line_valve_16') }
    'starter_washer' { return @('starter_fitting','coupling_16','endcap_16') }
    'line_valve_16' { return @('coupling_16','tee_16','elbow_16','endcap_16') }
    'transition_valve' { return @('coupling_16','tee_16','elbow_16','starter_fitting') }
    'layflat_endcap' { return @('tape_layflat_adapter','tape_valve','tape_coupling') }
    'multi_branch' { return @('coupling_16','line_valve_16','dripper','tee_16') }
    'installation_tool' { return @('starter_fitting','starter_washer','tape_layflat_adapter','tape_valve') }
    default { return @('coupling_16','tee_16','endcap_16','tape_coupling') }
  }
}

function Build-RelatedHtml($Target,$Targets) {
  $families = @(Get-RelatedFamilies ([string]$Target.family))
  $items = @()
  foreach ($f in $families) {
    foreach ($candidate in @($Targets | Where-Object { $_.family -eq $f -and $_.id -ne $Target.id -and $_.stock_status -eq 'instock' } | Sort-Object id)) {
      if ($items.Count -ge 4) { break }
      if (@($items | Where-Object { $_.id -eq $candidate.id }).Count -eq 0) { $items += $candidate }
    }
    if ($items.Count -ge 4) { break }
  }
  if ($items.Count -eq 0) { return '' }
  $lis = @()
  foreach ($r in $items) {
    $lis += '<li><a href="' + (H $r.permalink) + '">' + (H $r.name) + '</a></li>'
  }
  return '<h2>محصولات مکملی که ارزش بررسی دارند</h2><p>برای بستن یک مسیر آبیاری کامل، قطعه را جدا از بقیه شبکه انتخاب نکنید. بر اساس محصولات موجود همین دسته، این گزینه‌ها می‌توانند در کنار این کالا کاربرد داشته باشند:</p><ul>' + ($lis -join '') + '</ul>'
}

function Get-FamilyCopy([string]$Family,[string]$Name) {
  $safe = H $Name
  $purpose='این قطعه برای تکمیل بخشی از شبکه آبیاری قطره‌ای استفاده می‌شود.'
  $selection='نوع اتصال، سایز قطعه مقابل، فشار واقعی خط و روش نصب را با پروژه تطبیق دهید.'
  $install='محل اتصال را تمیز و بدون تنش آماده کنید و قطعه را هم‌راستا با اجزای مقابل ببندید.'
  $care='پس از راه‌اندازی، نشتی، لق‌شدن اتصال و عملکرد مسیر را کنترل کنید.'
  $q1='مهم‌ترین نکته قبل از خرید چیست؟'; $a1='تطبیق دقیق همین قطعه با سایز و نوع اتصال قطعه مقابل؛ شباهت ظاهری به‌تنهایی برای انتخاب کافی نیست.'
  $q2='آیا برای نصب به قطعه مکمل نیاز است؟'; $a2='در بیشتر اجراها بله. لوله، انشعاب، شیر، فیلتر، رابط یا قطعه انتهایی باید متناسب با آرایش واقعی شبکه انتخاب شوند.'

  switch ($Family) {
    'dripper' {
      $purpose='برای رساندن آب به‌صورت موضعی در نزدیکی ریشه و کنترل خروجی در شبکه آبیاری قطره‌ای به‌کار می‌رود.'
      $selection='دبی نامی درج‌شده در نام محصول، فشار کار خط، فاصله قطره‌چکان‌ها، نیاز آبی گیاه و کیفیت آب را کنار هم بررسی کنید. عدد آبدهی را بدون درنظرگرفتن فشار واقعی خط به‌عنوان خروجی قطعی فرض نکنید.'
      $install='محل نصب روی لوله را تمیز و دقیق آماده کنید. پس از نصب، چند خروجی ابتدایی، میانی و انتهایی خط را از نظر یکنواختی آبدهی کنترل کنید.'
      $care='فیلتراسیون مناسب و شست‌وشوی دوره‌ای خط برای حفظ عملکرد قطره‌چکان ضروری است. در مدل‌هایی که در نام آن‌ها «خودشوینده» آمده، این ویژگی جای فیلتر و سرویس شبکه را نمی‌گیرد.'
      $q1='آیا عدد آبدهی درج‌شده روی نام محصول در همه فشارها ثابت است؟'; $a1='خیر. آن عدد رده نامی محصول است و آبدهی واقعی می‌تواند تحت تأثیر فشار، وضعیت خط و شرایط نصب قرار بگیرد.'
      $q2='برای جلوگیری از گرفتگی چه کار کنیم؟'; $a2='فیلتر مناسب منبع آب، شست‌وشوی دوره‌ای خط و جلوگیری از ورود رسوب و ذرات معلق سه اقدام اصلی هستند.'
    }
    'bubbler' {
      $purpose='برای آبیاری موضعی پای درخت، نهال و نقاطی استفاده می‌شود که نسبت به قطره‌چکان معمولی به خروجی آب بیشتری نیاز دارند.'
      $selection='آبدهی نامی درج‌شده در نام محصول، فشار خط، بافت خاک، اندازه تشتک و نیاز آبی گیاه را بررسی کنید. مدل تنظیمی باید بعد از نصب روی دبی مناسب همان درخت تنظیم شود.'
      $install='بابلر را طوری جانمایی کنید که آب در محدوده ریشه پخش شود و باعث فرسایش خاک یا خروج آب از تشتک نشود.'
      $care='گرفتگی مسیر ورودی، رسوب و تغییر فشار می‌تواند الگوی خروجی را تغییر دهد؛ بازدید دوره‌ای و فیلتراسیون مناسب اهمیت دارد.'
      $q1='بابلر برای چه کاربردی مناسب‌تر است؟'; $a1='برای آبیاری موضعی درخت، نهال و فضای سبز که به خروجی بیشتری از یک قطره‌چکان معمولی نیاز دارند.'
      $q2='مدل تنظیمی چه مزیتی دارد؟'; $a2='امکان تنظیم خروجی متناسب با نیاز هر نقطه را می‌دهد؛ تنظیم نهایی باید بعد از راه‌اندازی و مشاهده رفتار واقعی آب انجام شود.'
    }
    'root_capsule' {
      $purpose='برای هدایت آب به ناحیه ریشه در اجرای آبیاری موضعی یا زیرسطحی استفاده می‌شود و می‌تواند تبخیر سطحی و پخش نامنظم آب را در بعضی پروژه‌ها کاهش دهد.'
      $selection='عمق ریشه، بافت خاک، محل کاشت، کیفیت آب و روش تغذیه کپسول را قبل از اجرا مشخص کنید. فاصله و عمق نصب باید با گونه گیاه و شرایط خاک هماهنگ باشد.'
      $install='کپسول را بدون آسیب به ریشه اصلی و در ناحیه مؤثر ریشه قرار دهید و مسیر ورودی را طوری اجرا کنید که سرویس و شست‌وشو ممکن باشد.'
      $care='مسیر ورودی را از نظر رسوب و گرفتگی بررسی کنید و در آب‌های دارای ذرات معلق، فیلتراسیون را جدی بگیرید.'
      $q1='آیا کپسول زیرسطحی جای محاسبه نیاز آبی را می‌گیرد؟'; $a1='خیر. این قطعه روش رساندن آب را تغییر می‌دهد؛ مقدار و برنامه آبیاری همچنان باید متناسب با گیاه و خاک تعیین شود.'
      $q2='مهم‌ترین ریسک نصب نادرست چیست؟'; $a2='قرارگیری در عمق یا فاصله نامناسب از ریشه و همچنین گرفتگی مسیر ورودی می‌تواند اثرگذاری سیستم را کم کند.'
    }
    'emitter_tee' {
      $purpose='یک قطعه ترکیبی برای تقسیم مسیر و ایجاد خروجی‌های قابل تنظیم در شبکه لوله ۱۶ است و برای آبیاری چند نقطه نزدیک به هم کاربرد دارد.'
      $selection='نوع اتصال به لوله ۱۶، آرایش خروجی‌ها، فشار خط و نیاز آبی نقاطی که قرار است تغذیه شوند را پیش از خرید بررسی کنید.'
      $install='سه‌راه را بدون پیچش روی لوله نصب کنید و بعد از راه‌اندازی، خروجی‌ها را یکی‌یکی تنظیم کنید تا توزیع آب با نیاز گیاهان هماهنگ شود.'
      $care='در صورت کاهش خروجی، ابتدا فیلتراسیون، فشار خط و تمیزی مسیرهای خروجی را بررسی کنید.'
      $q1='آیا این قطعه برای هر فاصله کاشتی مناسب است؟'; $a1='خیر. آرایش سه‌راهی باید با فاصله واقعی نقاط آبیاری و مسیر لوله هماهنگ باشد.'
      $q2='چرا تنظیم خروجی‌ها بعد از نصب مهم است؟'; $a2='زیرا فشار و طول مسیر می‌تواند روی خروجی هر نقطه اثر بگذارد و تنظیم در شرایط واقعی شبکه دقیق‌تر است.'
    }
    'tape_valve' {
      $purpose='برای گرفتن یا کنترل یک انشعاب نوار تیپ از خط تغذیه استفاده می‌شود و امکان قطع و وصل همان ردیف را بدون خواباندن کل شبکه فراهم می‌کند.'
      $selection='سمت ورودی شیر را دقیقاً با همان اتصال درج‌شده در نام محصول تطبیق دهید؛ ۱۶، ۲۰، رزوه ۱/۲ یا لی‌فلت را جای یکدیگر فرض نکنید. سمت خروجی نیز باید با نوار تیپ پروژه سازگار باشد.'
      $install='محل انشعاب را دقیق ایجاد کنید، آب‌بندی را کنترل کنید و مهره یا قسمت قفل‌کننده تیپ را یکنواخت ببندید؛ فشار بیش از حد به تیپ می‌تواند به نوار آسیب بزند.'
      $care='پیش از فصل و در طول کار، باز و بسته شدن شیر و نشتی اطراف انشعاب را کنترل کنید.'
      $q1='مزیت شیر انشعاب نسبت به رابط ساده چیست؟'; $a1='امکان قطع و وصل مستقل یک ردیف آبیاری برای مدیریت، تعمیر یا خارج‌کردن آن ردیف از مدار.'
      $q2='آیا همه شیرهای تیپ روی یک ورودی نصب می‌شوند؟'; $a2='خیر. نوع ورودی در نام هر مدل مشخص است و باید با خط تغذیه واقعی پروژه یکی باشد.'
    }
    'line_valve_16' {
      $purpose='برای قطع و وصل یا کنترل یک مسیر ۱۶ میلی‌متری در آبیاری قطره‌ای استفاده می‌شود.'
      $selection='هر دو سمت اتصال را با لوله ۱۶ واقعی پروژه تطبیق دهید و محل نصب را جایی انتخاب کنید که دسترسی برای باز و بسته کردن شیر آسان باشد.'
      $install='لوله را صاف برش دهید، دو سمت شیر را هم‌راستا نصب کنید و از واردکردن بار خمشی لوله به بدنه شیر جلوگیری کنید.'
      $care='نشتی دو سر اتصال و حرکت روان دسته شیر را به‌صورت دوره‌ای کنترل کنید.'
      $q1='این شیر برای چه کاری مفید است؟'; $a1='برای ایزوله‌کردن یک بخش از خط ۱۶ و مدیریت بهتر تعمیر یا نوبت‌بندی آبیاری.'
      $q2='آیا می‌توان از آن به‌جای تنظیم‌کننده فشار استفاده کرد؟'; $a2='خیر. شیر قطع‌و‌وصل با رگولاتور فشار یکی نیست و وظیفه اصلی آن مدیریت جریان در مسیر است.'
    }
    'transition_valve' {
      $purpose='برای ایجاد یک مسیر کنترل‌شونده بین لوله ۱۶ و اتصال ۱/۲ اینچ استفاده می‌شود.'
      $selection='مشخص کنید سمت ۱/۲ اینچ در پروژه با چه قطعه‌ای جفت می‌شود و نوع رزوه یا رابط مقابل را قبل از خرید تطبیق دهید.'
      $install='سمت لوله ۱۶ را بدون تنش نصب کنید و سمت رزوه‌ای را با روش آب‌بندی مناسب همان اتصال ببندید؛ از سفت‌کردن بیش از حد جلوگیری کنید.'
      $care='نشتی دو سمت و سلامت قسمت قطع‌و‌وصل را پس از راه‌اندازی و در سرویس‌های دوره‌ای بررسی کنید.'
      $q1='آیا ۱/۲ اینچ همان ۱۶ میلی‌متر است؟'; $a1='خیر. این‌ها دو نام‌گذاری برای دو سمت متفاوت اتصال هستند و نباید معادل یکدیگر در نظر گرفته شوند.'
      $q2='قبل از خرید چه چیزی را از قطعه مقابل بدانیم؟'; $a2='نوع اتصال، جهت رزوه و نحوه آب‌بندی قطعه مقابل باید با این شیر سازگار باشد.'
    }
    'tape_layflat_adapter' {
      $purpose='برای گرفتن انشعاب نوار تیپ از لوله لی‌فلت و انتقال آب از خط اصلی یا نیمه‌اصلی به ردیف کشت استفاده می‌شود.'
      $selection='نوع لی‌فلت، محل سوراخ‌کاری، وجود یا نبود واشر در همین مدل و نوع قفل نوار تیپ را با روش اجرای پروژه تطبیق دهید.'
      $install='سوراخ لی‌فلت باید تمیز و متناسب با قطعه ایجاد شود. واشر یا سطح آب‌بندی را درست در نشیمن قرار دهید و نوار تیپ را بدون چین‌خوردگی در قسمت قفل‌کننده ببندید.'
      $care='در زمان کار، اطراف انشعاب را از نظر نشتی و تیپ را از نظر بیرون‌کشیدگی یا پارگی کنترل کنید.'
      $q1='مدل واشردار و بدون واشر یکی هستند؟'; $a1='خیر. روش آب‌بندی و قطعات همراه می‌تواند متفاوت باشد؛ همان مدل درج‌شده در نام محصول را مطابق روش اجرای لی‌فلت انتخاب کنید.'
      $q2='مهم‌ترین علت نشتی در این اتصال چیست؟'; $a2='سوراخ‌کاری نامناسب، جاافتادن ناقص قطعه یا واشر و بستن ناصحیح نوار تیپ از عوامل رایج هستند.'
    }
    'tape_16_adapter' {
      $purpose='برای اتصال نوار تیپ به خط ۱۶ میلی‌متری و انتقال آب بین این دو بخش شبکه استفاده می‌شود.'
      $selection='سمت ۱۶ میلی‌متر، نوع قفل تیپ و روش اتصال این مدل را با لوله و نوار واقعی پروژه تطبیق دهید.'
      $install='اتصال را بدون کشش روی نوار ببندید و پس از راه‌اندازی، محل اتصال را از نظر نشتی و جداشدن نوار بررسی کنید.'
      $care='در پایان فصل یا هنگام جابه‌جایی تیپ، از آسیب‌دیدگی قسمت قفل‌کننده و سطح آب‌بندی جلوگیری کنید.'
      $q1='این رابط چه زمانی استفاده می‌شود؟'; $a1='وقتی ردیف نوار تیپ باید به خط ۱۶ میلی‌متری متصل شود یا بین این دو نوع خط انتقال برقرار شود.'
      $q2='آیا همه نوارهای تیپ با یک رابط یکسان نصب می‌شوند؟'; $a2='خیر. نحوه قفل و ابعاد نوار و رابط باید با یکدیگر سازگار باشند.'
    }
    'tape_coupling' {
      $purpose='برای اتصال دو قطعه نوار تیپ به یکدیگر، ادامه‌دادن مسیر یا ترمیم بخش آسیب‌دیده تیپ استفاده می‌شود.'
      $selection='نوع قفل رابط و وضعیت نوار تیپ را بررسی کنید؛ دو سر نوار باید سالم، تمیز و بدون پارگی طولی در محل اتصال باشند.'
      $install='دو سر تیپ را صاف برش دهید، بدون چین‌خوردگی داخل رابط قرار دهید و قفل را یکنواخت ببندید.'
      $care='بعد از راه‌اندازی، اتصال را از نظر نشتی و بیرون‌کشیده‌شدن نوار کنترل کنید؛ در صورت آسیب‌دیدگی خود تیپ، قسمت معیوب را تا محل سالم کوتاه کنید.'
      $q1='آیا این رابط برای ترمیم تیپ مناسب است؟'; $a1='بله، وقتی بخش آسیب‌دیده حذف شود و دو سر سالم نوار با رابط به هم متصل شوند.'
      $q2='چرا تیپ از رابط بیرون می‌آید؟'; $a2='بستن ناقص قفل، چین‌خوردگی نوار، آسیب لبه تیپ یا فشار نامناسب می‌تواند باعث جداشدن اتصال شود.'
    }
    'tape_adapter' {
      $purpose='برای اتصال نوار تیپ به بخش دیگری از شبکه آبیاری استفاده می‌شود و باید دقیقاً مطابق نوع قطعه مقابل انتخاب شود.'
      $selection='نام همین مدل، نوع مهره یا قفل، قطعه مقابل و روش آب‌بندی را قبل از سفارش با اجرای واقعی تطبیق دهید.'
      $install='نوار تیپ را صاف و بدون چین داخل قسمت قفل‌کننده قرار دهید و اتصال سمت مقابل را بدون تنش ببندید.'
      $care='نشتی و شل‌شدن مهره یا قفل را در طول فصل کنترل کنید.'
    }
    'coupling_16' {
      $purpose='برای اتصال مستقیم دو بخش لوله ۱۶ میلی‌متری و ادامه یا تعمیر مسیر آبیاری قطره‌ای استفاده می‌شود.'
      $selection='قطر واقعی لوله، سلامت دو سر لوله و نوع اتصال این رابط را با پروژه تطبیق دهید.'
      $install='دو سر لوله را صاف و عمود بر محور برش دهید، تا محل نشیمن وارد رابط کنید و از کشش یا خم شدید کنار اتصال جلوگیری کنید.'
      $care='پس از راه‌اندازی و بعد از تغییرات دمایی، نشتی و بیرون‌کشیدگی لوله از رابط را بررسی کنید.'
      $q1='این رابط برای چه تعمیراتی مناسب است؟'; $a1='برای ادامه‌دادن خط ۱۶ یا حذف یک قسمت آسیب‌دیده و اتصال دوباره دو سر سالم لوله.'
      $q2='آیا برای لوله با قطر متفاوت مناسب است؟'; $a2='خیر. این خانواده برای مسیر ۱۶ میلی‌متری است و قطر قطعه مقابل باید دقیقاً تطبیق داده شود.'
    }
    'starter_fitting' {
      $purpose='برای شروع یک انشعاب ۱۶ میلی‌متری از لوله تغذیه استفاده می‌شود و محل عبور آب از خط اصلی به لوله فرعی را تشکیل می‌دهد.'
      $selection='عددهای درج‌شده در نام مدل، قطر سوراخ یا محل نصب و سایز خروجی را با ابزار پانچ و واشر مناسب همان اجرا تطبیق دهید.'
      $install='محل انشعاب را دقیق علامت بزنید، سوراخ تمیز ایجاد کنید، واشر سازگار را در جای خود بنشانید و بست را بدون آسیب به لوله نصب کنید.'
      $care='نشتی اطراف واشر و لق‌شدن اتصال را پس از راه‌اندازی و در سرویس دوره‌ای بررسی کنید.'
      $q1='تفاوت مدل‌های ۱۶×۱۶ و ۱۸×۱۶ چیست؟'; $a1='عدد اول به بخش ورودی یا سوراخ/اتصال سمت خط مادر و عدد دوم به خروجی لوله ۱۶ مربوط است؛ ابزار و واشر باید با همان مدل هماهنگ باشند.'
      $q2='آیا پانچ نامناسب می‌تواند نشتی ایجاد کند؟'; $a2='بله. سوراخ نامتناسب یا لبه‌دار می‌تواند آب‌بندی واشر و بست ابتدایی را مختل کند.'
    }
    'starter_washer' {
      $purpose='برای آب‌بندی محل نصب بست ابتدایی و جلوگیری از نشت اطراف انشعاب لوله ۱۶ استفاده می‌شود.'
      $selection='واشر را با قطر سوراخ، بست ابتدایی و ضخامت لوله مادر هماهنگ کنید؛ واشر مشابه از نظر ظاهر لزوماً جایگزین دقیق نیست.'
      $install='واشر باید بدون پیچ‌خوردگی و کاملاً در نشیمن سوراخ قرار بگیرد و سپس بست ابتدایی از مرکز آن عبور کند.'
      $care='اگر اطراف انشعاب نشتی ایجاد شد، سلامت واشر، اندازه سوراخ و جاافتادن کامل بست را بررسی کنید.'
      $q1='آیا واشر به‌تنهایی یک اتصال کامل است؟'; $a1='خیر. واشر بخش آب‌بندی مجموعه بست ابتدایی است و همراه قطعه انشعاب استفاده می‌شود.'
      $q2='چه چیزی باعث نشتی دور واشر می‌شود؟'; $a2='سوراخ نامناسب، لبه آسیب‌دیده، واشر فرسوده یا نصب کج بست از عوامل رایج هستند.'
    }
    'tee_16' {
      $purpose='برای تقسیم یک مسیر لوله ۱۶ میلی‌متری به دو شاخه و ایجاد آرایش سه‌راهی در شبکه استفاده می‌شود.'
      $selection='هر سه سمت سه‌راه باید با لوله ۱۶ پروژه سازگار باشند و مسیر جدید از نظر دبی و افت فشار در طراحی شبکه در نظر گرفته شود.'
      $install='سه سر لوله را صاف آماده کنید، اتصال را بدون پیچش نصب کنید و اجازه ندهید وزن یا کشش لوله به بدنه سه‌راه منتقل شود.'
      $care='نشتی هر سه اتصال و تغییر شکل ناشی از کشش لوله را دوره‌ای بررسی کنید.'
      $q1='آیا اضافه‌کردن شاخه جدید روی فشار اثر می‌گذارد؟'; $a1='بله. افزایش مصرف و طول مسیر می‌تواند توزیع فشار را تغییر دهد و باید در طراحی خط بررسی شود.'
      $q2='برای بستن انتهای شاخه جدید چه قطعه‌ای لازم است؟'; $a2='بسته به طراحی، معمولاً کورکن ۱۶ یا قطعه انتهایی مناسب همان خط استفاده می‌شود.'
    }
    'elbow_16' {
      $purpose='برای تغییر جهت مسیر لوله ۱۶ میلی‌متری بدون تا کردن شدید خود لوله استفاده می‌شود.'
      $selection='محل تغییر مسیر و فضای نصب را بررسی کنید و مطمئن شوید هر دو سمت زانو با لوله ۱۶ پروژه سازگار است.'
      $install='دو سر لوله را صاف وارد زانو کنید و مسیر را طوری مهار کنید که کشش جانبی به اتصال وارد نشود.'
      $care='محل اتصال را از نظر نشتی و خم‌شدگی یا فشار مکانیکی ناشی از جابه‌جایی لوله کنترل کنید.'
      $q1='چرا به‌جای خم‌کردن لوله از زانو استفاده کنیم؟'; $a1='در تغییر جهت‌های تند، زانو می‌تواند از تاخوردگی لوله و محدودشدن مسیر عبور آب جلوگیری کند.'
      $q2='آیا زانو برای تبدیل سایز است؟'; $a2='خیر. این مدل برای تغییر جهت مسیر ۱۶ میلی‌متری است، نه تبدیل قطر.'
    }
    'endcap_16' {
      $purpose='برای بستن انتهای خط ۱۶ میلی‌متری و ایجاد پایان قابل بازدید یا سرویس در شبکه آبیاری قطره‌ای استفاده می‌شود.'
      $selection='قطر لوله و نوع کورکن را با انتهای واقعی خط تطبیق دهید و اگر شست‌وشوی دوره‌ای خط لازم است، دسترسی به این نقطه را حفظ کنید.'
      $install='انتهای لوله را صاف آماده کنید و کورکن را مطابق مکانیزم خودش تا محل نشیمن ببندید؛ انتهای خط را زیر خاک یا سازه‌ای که دسترسی را سخت کند پنهان نکنید.'
      $care='در سرویس خط، کورکن را باز کنید تا رسوبات و ذرات خارج شوند و سپس آب‌بندی آن را دوباره کنترل کنید.'
      $q1='چرا دسترسی به انتهای خط مهم است؟'; $a1='چون شست‌وشوی دوره‌ای خطوط قطره‌ای معمولاً از نقاط انتهایی انجام می‌شود.'
      $q2='آیا می‌توان انتهای لوله را فقط تا زد؟'; $a2='روش‌های موقت وجود دارند، اما استفاده از قطعه انتهایی مناسب، باز و بسته‌کردن و سرویس خط را منظم‌تر می‌کند.'
    }
    'layflat_endcap' {
      $purpose='برای بستن انتهای لوله لی‌فلت و جلوگیری از خروج آب از انتهای مسیر استفاده می‌شود.'
      $selection='سایز واقعی لی‌فلت، نوع کورکن و روش مهار مکانیکی را با خط پروژه تطبیق دهید؛ کورکن باید با قطر و ساختار همان لوله سازگار باشد.'
      $install='انتهای لی‌فلت را صاف و بدون تاخوردگی آماده کنید، کورکن را کامل جا بزنید و مهار یا بست موردنیاز را یکنواخت ببندید.'
      $care='در شروع فشاردهی خط، انتهای لی‌فلت را از نظر لغزش، نشتی و شل‌شدن مهار کنترل کنید.'
      $q1='کار کورکن لی‌فلت چیست؟'; $a1='بستن انتهای خط لی‌فلت؛ این قطعه رابط تبدیل به مسیر دیگر نیست.'
      $q2='مهم‌ترین نکته نصب چیست؟'; $a2='تطبیق سایز و مهار مکانیکی صحیح تا انتهای لوله زیر فشار از جای خود خارج نشود.'
    }
    'multi_branch' {
      $purpose='برای تقسیم یک ورودی به چند مسیر خروجی و توزیع آب بین چند شاخه نزدیک به هم استفاده می‌شود.'
      $selection='تعداد شاخه‌ها، سایزهای درج‌شده در نام محصول، قطعات مقابل و دبی موردنیاز مجموع خروجی‌ها را با پروژه تطبیق دهید.'
      $install='قطعه را در نقطه‌ای نصب کنید که شاخه‌ها بدون پیچش و کشش شدید از آن جدا شوند و هر خروجی به‌درستی مهار شود.'
      $care='نشتی همه خروجی‌ها و یکنواختی نسبی جریان در شاخه‌ها را پس از راه‌اندازی بررسی کنید.'
      $q1='آیا با اضافه‌شدن شاخه‌ها دبی هر مسیر تغییر می‌کند؟'; $a1='ممکن است. مجموع مصرف شاخه‌ها و فشار موجود در خط تعیین می‌کند هر مسیر چه عملکردی داشته باشد.'
      $q2='اعداد روی نام محصول چه اهمیتی دارند؟'; $a2='برای تطبیق اتصال‌های ورودی و خروجی هستند و باید با قطعات واقعی شبکه کنترل شوند.'
    }
    'installation_tool' {
      $purpose='برای آماده‌سازی محل نصب برخی انشعاب‌ها و اتصالات آبیاری استفاده می‌شود.'
      $selection='سایز ابزار را دقیقاً با اتصال و واشر مورد استفاده تطبیق دهید؛ سوراخ بزرگ یا کوچک می‌تواند باعث نشتی یا نصب نادرست شود.'
      $install='سطح لوله را در محل مناسب نگه دارید و سوراخ را تمیز، عمود و بدون پارگی اضافی ایجاد کنید.'
      $care='لبه برش ابزار را تمیز و سالم نگه دارید تا سوراخ یکنواخت ایجاد شود.'
      $q1='چرا سایز ابزار مهم است؟'; $a1='چون قطر سوراخ باید با واشر و اتصال انشعاب هماهنگ باشد.'
      $q2='آیا ایجاد سوراخ نامنظم مشکل‌ساز است؟'; $a2='بله. لبه‌های پاره یا قطر نامناسب می‌تواند آب‌بندی اتصال را ضعیف کند.'
    }
    'irrigation_valve' {
      $purpose='برای مدیریت قطع و وصل جریان در بخشی از شبکه آبیاری استفاده می‌شود.'
      $selection='نوع اتصال دو سمت، سایز واقعی و نقش شیر در مدار را با خط موجود تطبیق دهید.'
      $install='شیر را در مسیر هم‌راستا و قابل‌دسترسی نصب کنید و از واردکردن وزن یا پیچش لوله به بدنه آن جلوگیری کنید.'
      $care='حرکت روان دسته و نشتی محل اتصالات را در سرویس‌های دوره‌ای بررسی کنید.'
    }
    'generic_fitting' {
      $purpose='برای اتصال، انشعاب یا تکمیل بخشی از شبکه آبیاری استفاده می‌شود.'
      $selection='نوع قطعه مقابل، سایزهای درج‌شده در نام محصول و روش آب‌بندی را با تجهیز واقعی پروژه تطبیق دهید.'
      $install='قطعه را بدون تنش، کجی یا فشار اضافی روی اتصالات مجاور نصب کنید.'
      $care='پس از فشاردهی شبکه، نشتی و پایداری مکانیکی اتصال را کنترل کنید.'
    }
    'generic_accessory' {
      $purpose='یکی از اجزای کمکی شبکه آبیاری قطره‌ای است و باید متناسب با آرایش واقعی پروژه انتخاب شود.'
      $selection='اطلاعات قابل استناد روی همین نام محصول، قطعه مقابل و نحوه نصب را مبنای انتخاب قرار دهید و ویژگی ثبت‌نشده را از روی ظاهر حدس نزنید.'
      $install='مطابق نقش واقعی قطعه در شبکه نصب کنید و قبل از فشاردهی نهایی، سازگاری آن با اجزای مجاور را کنترل کنید.'
      $care='در بازدیدهای دوره‌ای، اتصال، نشتی، شکستگی و عملکرد این بخش را همراه با کل خط بررسی کنید.'
    }
  }
  return [ordered]@{purpose=$purpose;selection=$selection;install=$install;care=$care;q1=$q1;a1=$a1;q2=$q2;a2=$a2}
}

function Build-Content($Target,$Targets,[string]$Marker) {
  $name = [string]$Target.name
  $safe = H $name
  $copy = Get-FamilyCopy ([string]$Target.family) $name
  $related = Build-RelatedHtml $Target $Targets
  $short = '<div dir="rtl"><p><strong>'+$safe+'</strong> '+$copy.purpose+' '+$copy.selection+'</p><p>برای خرید دقیق‌تر، قبل از ثبت سفارش قطعه مقابل، سایز خط و شرایط نصب را با همین مدل تطبیق دهید.</p></div>'
  $long = '<!-- '+$Marker+' --><article dir="rtl" style="direction:rtl;text-align:right;line-height:2;color:#26352d">' +
    '<h2>'+$safe+'</h2><p>'+$copy.purpose+' این صفحه بر انتخاب درست، نصب بدون خطا و استفاده واقعی در مزرعه، باغ یا گلخانه تمرکز دارد و ویژگی‌هایی که برای همین کالا قابل اثبات نیستند به‌صورت حدسی اضافه نشده‌اند.</p>' +
    '<h2>این محصول چه نقشی در سیستم دارد؟</h2><p>'+$copy.purpose+'</p>' +
    '<h2>قبل از خرید چه چیزهایی را کنترل کنیم؟</h2><p>'+$copy.selection+'</p><ul><li>سایز و نوع اتصال قطعه مقابل را با خود کالا تطبیق دهید.</li><li>فشار و دبی واقعی خط را در شرایط کار بررسی کنید.</li><li>اگر خروجی ریز یا نوار تیپ در پایین‌دست دارید، فیلتراسیون مناسب را جدی بگیرید.</li><li>تعداد قطعات و مسیرهای موردنیاز را قبل از اجرا مشخص کنید تا شبکه با اتصال‌های موقت و ناهمگون بسته نشود.</li></ul>' +
    '<h2>نکات نصب</h2><p>'+$copy.install+'</p><p>پس از نصب، شبکه را به‌تدریج تحت فشار قرار دهید و محل اتصال را قبل از تحویل نهایی از نظر نشتی و جابه‌جایی بررسی کنید.</p>' +
    '<h2>نگهداری و عیب‌یابی</h2><p>'+$copy.care+'</p><p>اگر افت دبی، نشتی یا عملکرد نامنظم مشاهده شد، علاوه بر خود قطعه، فشار ورودی، تمیزی فیلتر و وضعیت خط بالادست و پایین‌دست را هم بررسی کنید.</p>' +
    $related +
    '<h2>سوالات پرتکرار</h2><h3>'+(H $copy.q1)+'</h3><p>'+$copy.a1+'</p><h3>'+(H $copy.q2)+'</h3><p>'+$copy.a2+'</p>' +
    '<h3>آیا می‌توان مشخصات فنی ثبت‌نشده را از روی ظاهر محصول حدس زد؟</h3><p>خیر. فشار کاری، دبی دقیق، جنس یا جزئیات فنی‌ای که روی همین محصول یا منبع معتبر آن ثبت نشده‌اند نباید مبنای خرید قرار بگیرند. انتخاب را بر اساس مشخصات تأییدشده و تطبیق با قطعه واقعی پروژه انجام دهید.</p>' +
    '</article>'
  return [ordered]@{short=$short;long=$long}
}

$request = Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 50
$mode = if ($request.mode) { [string]$request.mode } else { 'audit' }
if ($mode -notin @('audit','apply')) { Fail "Unsupported mode: $mode" }
$categoryId = if ($request.category_id) { [int]$request.category_id } else { 756 }
$expectedCount = if ($request.expected_count) { [int]$request.expected_count } else { 40 }
$marker = if ($request.marker) { [string]$request.marker } else { 'k20-drip-content-v1' }
if ($categoryId -ne 756) { Fail 'This workflow is intentionally locked to drip irrigation category id 756.' }
if ($expectedCount -lt 1 -or $expectedCount -gt 100) { Fail 'expected_count must be 1..100' }
if ($marker -notmatch '^k20-drip-[a-z0-9-]+$') { Fail 'Invalid marker.' }

$category = Invoke-K20 'GET' "wp-json/wc/v3/products/categories/$categoryId"
if ([string]$category.slug -ne 'drip-irrigation') { Fail "Category 756 slug mismatch: $($category.slug)" }
$products = @(Get-Paged "wp-json/wc/v3/products?status=publish&orderby=id&order=asc&category=$categoryId")
if ($products.Count -ne $expectedCount) { Fail "Target count guard failed. Expected $expectedCount, got $($products.Count)." }
foreach ($p in $products) { if (-not (Test-CategoryId $p $categoryId)) { Fail "Product $($p.id) is not a member of category $categoryId." } }

$targets = @()
foreach ($p in $products) {
  $family = Get-Family ([string]$p.name)
  $targets += [pscustomobject][ordered]@{
    id=[int]$p.id
    name=[string]$p.name
    permalink=[string]$p.permalink
    stock_status=[string]$p.stock_status
    family=$family
    fallback=($family -in @('generic_fitting','generic_accessory'))
    marker_present=([string]$p.description).Contains("<!-- $marker -->")
  }
}

$changes = @()
if ($mode -eq 'apply') {
  foreach ($t in $targets) {
    $before = Invoke-K20 'GET' "wp-json/wc/v3/products/$($t.id)"
    if (-not (Test-CategoryId $before $categoryId)) { Fail "Membership changed before write for $($t.id)." }
    $protectedBefore = Get-ProtectedSnapshot $before
    $desired = Build-Content $t $targets $marker
    $same = (([string]$before.description -ceq [string]$desired.long) -and ([string]$before.short_description -ceq [string]$desired.short))
    if (-not $same) {
      $body = [ordered]@{description=[string]$desired.long;short_description=[string]$desired.short}
      $null = Invoke-K20 'PUT' "wp-json/wc/v3/products/$($t.id)" $body
    }
    $after = Invoke-K20 'GET' "wp-json/wc/v3/products/$($t.id)"
    $semantic = (([string]$after.description -ceq [string]$desired.long) -and ([string]$after.short_description -ceq [string]$desired.short) -and ([string]$after.description).Contains("<!-- $marker -->"))
    $integrity = ((Get-ProtectedSnapshot $after) -ceq $protectedBefore)
    if (-not $semantic) { Fail "Content readback failed for product $($t.id)." }
    if (-not $integrity) { Fail "Protected field integrity failed for product $($t.id)." }
    $changes += [pscustomobject][ordered]@{id=$t.id;name=$t.name;family=$t.family;changed=(-not $same);semantic_verified=$semantic;integrity_verified=$integrity}
  }
}

$familyCounts = @()
foreach ($g in @($targets | Group-Object family | Sort-Object Name)) { $familyCounts += [pscustomobject]@{family=$g.Name;count=$g.Count} }
$record = [ordered]@{
  ok=$true
  mode=$mode
  executed_at_utc=[DateTime]::UtcNow.ToString('o')
  category=[ordered]@{id=[int]$category.id;name=[string]$category.name;slug=[string]$category.slug;count=[int]$category.count}
  expected_count=$expectedCount
  target_count=$targets.Count
  fallback_count=@($targets | Where-Object {$_.fallback}).Count
  family_counts=@($familyCounts)
  mutation='description and short_description only; title, slug, price, stock, SKU, taxonomy, images and attributes are protected by readback'
  targets=@($targets)
  changes=@($changes)
  changed_count=@($changes | Where-Object {$_.changed}).Count
  semantic_verified_count=@($changes | Where-Object {$_.semantic_verified}).Count
  integrity_verified_count=@($changes | Where-Object {$_.integrity_verified}).Count
}
$dir = Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$record | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "DRIP_CONTENT_OK mode=$mode targets=$($targets.Count) fallback=$(@($targets | Where-Object {$_.fallback}).Count) changed=$(@($changes | Where-Object {$_.changed}).Count)"
