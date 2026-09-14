param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
if(-not(Test-Path -LiteralPath $RequestPath)){throw "Request file not found: $RequestPath"}
$base=$env:WP_BASE_URL;$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
if([string]::IsNullOrWhiteSpace($base)-or[string]::IsNullOrWhiteSpace($user)-or[string]::IsNullOrWhiteSpace($pass)){throw 'Required WordPress secrets are missing.'}
$base=$base.TrimEnd('/')
$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 50
$query=[string]$req.query
if([string]::IsNullOrWhiteSpace($query)){throw 'query is required'}
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Invoke-K20([string]$Path){Invoke-RestMethod -Uri ($base+'/'+$Path.TrimStart('/')) -Method GET -Headers $headers -TimeoutSec 180}
function Get-All([string]$Route){
  $all=@()
  for($page=1;$page -le 100;$page++){
    $items=@(Invoke-K20 ("$Route"+(if($Route.Contains('?')){'&'}else{'?'})+"per_page=100&page=$page"))
    if($items.Count-eq0){break}
    $all+=$items
    if($items.Count-lt100){break}
  }
  return $all
}
function Norm([string]$s){
  if($null-eq$s){return ''}
  $x=$s.Replace('ي','ی').Replace('ك','ک').Replace('‌',' ')
  $x=[regex]::Replace($x,'\s+',' ').Trim()
  return $x
}
$needle=Norm $query
$categories=@(Get-All 'wp-json/wc/v3/products/categories?hide_empty=false')
$catById=@{};foreach($c in $categories){$catById[[int]$c.id]=$c}
$matchedCats=@($categories|Where-Object{(Norm([string]$_.name)).Contains($needle)-or(Norm([string]$_.slug)).Contains($needle)})
$products=@(Get-All 'wp-json/wc/v3/products?status=publish&orderby=id&order=asc')
$matchedProducts=@()
foreach($p in $products){
  $catNames=@($p.categories|ForEach-Object{[string]$_.name})
  $nameHit=(Norm([string]$p.name)).Contains($needle)
  $catHit=@($catNames|Where-Object{(Norm $_).Contains($needle)}).Count -gt 0
  $matchedIdHit=$false
  foreach($pc in @($p.categories)){if(@($matchedCats.id)-contains [int]$pc.id){$matchedIdHit=$true;break}}
  if(-not($nameHit-or$catHit-or$matchedIdHit)){continue}
  $matchedProducts+=[pscustomobject][ordered]@{
    id=[int]$p.id;name=[string]$p.name;slug=[string]$p.slug;status=[string]$p.status;permalink=[string]$p.permalink;
    stock_status=[string]$p.stock_status;sku=[string]$p.sku;catalog_visibility=[string]$p.catalog_visibility;
    short_description=[string]$p.short_description;description=[string]$p.description;
    categories=@($p.categories|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});
    tags=@($p.tags|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});
    images=@($p.images|ForEach-Object{[ordered]@{id=[int]$_.id;src=[string]$_.src;alt=[string]$_.alt}})
  }
}
$record=[ordered]@{
  ok=$true;query=$query;executed_at_utc=[DateTime]::UtcNow.ToString('o');
  category_count=$matchedCats.Count;product_count=$matchedProducts.Count;
  matching_categories=@($matchedCats|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug;parent=[int]$_.parent;count=[int]$_.count;description=[string]$_.description}});
  matching_products=@($matchedProducts)
}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
$record|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "CATEGORY_INVENTORY_OK query=$query categories=$($matchedCats.Count) products=$($matchedProducts.Count)"
