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
  $n=Normalize-InchText $Name;$vals=@()
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
function Format-Inch([double]$Size){return (Convert-ToPersianDigits ($Size.ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)))+' اینچ'}
function Format-Sizes($Sizes){$a=@($Sizes);if($a.Count-eq0){return 'سایز درج‌شده در عنوان'};if($a.Count-eq1){return Format-Inch ([double]$a[0]};return (Format-Inch([double]$a[0]))+' به '+(Format-Inch([double]$a[1]))}
