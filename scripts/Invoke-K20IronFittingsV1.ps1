param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
if(-not(Test-Path -LiteralPath $RequestPath)){throw "Request file not found: $RequestPath"}
. (Join-Path $PSScriptRoot 'coupling/CommonApi.ps1')

$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 50
$mode=if($req.mode){[string]$req.mode}else{'audit'}
if($mode -ne 'audit'){Fail "Unsupported mode for V1: $mode"}
$slug=if($req.category_slug){[string]$req.category_slug}else{'cast-iron-steel-fittings'}

$cats=@(Invoke-K20 'GET' ("wp-json/wc/v3/products/categories?slug="+[Uri]::EscapeDataString($slug)+"&per_page=100"))
if($cats.Count-ne1){Fail "Expected one category for slug $slug; got $($cats.Count)"}
$cat=$cats[0];$catId=[int]$cat.id

$products=@()
for($page=1;$page-le10;$page++){
  $response=Invoke-K20 'GET' "wp-json/wc/v3/products?category=$catId&status=publish&orderby=id&order=asc&per_page=100&page=$page"
  $items=@();foreach($p in $response){$items+=$p}
  if($items.Count-eq0){break}
  foreach($p in $items){$products+=$p}
  if($items.Count-lt100){break}
}

function Get-Family([string]$Name){
  $n=Normalize-InchText $Name
  if($n-match 'سر\s*شلنگ'){return 'hose_tail'}
  if($n-match 'فلنچ|فلنج'){
    if($n-match 'کور'){return 'blind_flange'}
    if($n-match 'چهار\s*راه'){return 'four_way_flanged'}
    if($n-match 'سه\s*راه'){return 'tee_flanged'}
    if($n-match 'زانو'){return 'elbow_flanged'}
    if($n-match 'تبدیل'){return 'reducer_flanged'}
    return 'flange'
  }
  if($n-match 'چهار\s*راه'){return 'four_way'}
  if($n-match 'سه\s*راه'){return 'tee'}
  if($n-match 'زانو'){return 'elbow'}
  if($n-match 'مهره\s*ماسوره'){return 'union'}
  if($n-match 'بوشن'){return 'coupling'}
  if($n-match 'مغزی|نیپل'){return 'nipple'}
  if($n-match 'تبدیل'){return 'reducer'}
  if($n-match 'درپوش|کپ'){return 'cap'}
  if($n-match 'کمربند'){return 'saddle'}
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

$rows=@();$unknown=@()
foreach($p in $products){
  $family=Get-Family ([string]$p.name)
  $row=[pscustomobject][ordered]@{
    id=[int]$p.id;name=[string]$p.name;family=$family;sizes_inch=@(Get-InchSizes ([string]$p.name));
    stock_status=[string]$p.stock_status;short_description_length=([string]$p.short_description).Length;description_length=([string]$p.description).Length
  }
  $rows+=$row
  if($family-eq'unknown'){$unknown+=$row}
}
$familyCounts=@();foreach($g in ($rows|Group-Object family|Sort-Object Name)){$familyCounts+=[ordered]@{family=$g.Name;count=$g.Count}}
$record=[ordered]@{
  ok=$true;mode=$mode;executed_at_utc=[DateTime]::UtcNow.ToString('o');
  category=[ordered]@{id=$catId;name=[string]$cat.name;slug=[string]$cat.slug;count=[int]$cat.count;description=[string]$cat.description};
  product_count=$products.Count;family_counts=@($familyCounts);unknown_count=$unknown.Count;unknown_products=@($unknown);products=@($rows)
}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
$record|ConvertTo-Json -Depth 50|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "IRON_FITTINGS_AUDIT_OK products=$($products.Count) unknown=$($unknown.Count)"
