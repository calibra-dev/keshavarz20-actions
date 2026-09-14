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
function Get-Paged([string]$Route){
  $all=@();$sep=if($Route.Contains('?')){'&'}else{'?'}
  for($page=1;$page -le 20;$page++){
    $response=Invoke-K20 ("$Route${sep}per_page=100&page=$page")
    $items=@($response|ForEach-Object{$_})
    if($items.Count-eq0){break}
    foreach($item in $items){$all+=$item}
    if($items.Count-lt100){break}
  }
  return @($all|ForEach-Object{$_})
}
function Norm([string]$s){if($null-eq$s){return ''};$x=$s.Replace('ي','ی').Replace('ك','ک').Replace('‌',' ');return ([regex]::Replace($x,'\s+',' ').Trim())}
$needle=Norm $query
$encoded=[Uri]::EscapeDataString($query)
$categoryCandidates=@(Get-Paged "wp-json/wc/v3/products/categories?hide_empty=false&search=$encoded")
$matchedCats=@($categoryCandidates|Where-Object{(Norm([string]$_.name)).Contains($needle)-or(Norm([string]$_.slug)).Contains($needle)})
if($matchedCats.Count-eq0){
  $allCategories=@(Get-Paged 'wp-json/wc/v3/products/categories?hide_empty=false')
  $matchedCats=@($allCategories|Where-Object{(Norm([string]$_.name)).Contains($needle)-or(Norm([string]$_.slug)).Contains($needle)})
}
$productsById=@{}
foreach($c in $matchedCats){
  $rows=@(Get-Paged ("wp-json/wc/v3/products?status=publish&orderby=id&order=asc&category="+[int]$c.id))
  foreach($p in $rows){$productsById[[int]$p.id]=$p}
}
# Include published products matching the phrase in their title even if taxonomy assignment is imperfect.
$titleRows=@(Get-Paged "wp-json/wc/v3/products?status=publish&orderby=id&order=asc&search=$encoded")
foreach($p in $titleRows){if((Norm([string]$p.name)).Contains($needle)){$productsById[[int]$p.id]=$p}}
$matchedProducts=@()
foreach($p in @($productsById.Values|Sort-Object id)){
  $matchedProducts+=[pscustomobject][ordered]@{
    id=[int]$p.id;name=[string]$p.name;slug=[string]$p.slug;status=[string]$p.status;permalink=[string]$p.permalink;
    stock_status=[string]$p.stock_status;sku=[string]$p.sku;catalog_visibility=[string]$p.catalog_visibility;
    short_description=[string]$p.short_description;description=[string]$p.description;
    categories=@($p.categories|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});
    tags=@($p.tags|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});
    images=@($p.images|ForEach-Object{[ordered]@{id=[int]$_.id;src=[string]$_.src;alt=[string]$_.alt}})
  }
}
$catRows=@();foreach($c in $matchedCats){$catRows+=[ordered]@{id=[int]$c.id;name=[string]$c.name;slug=[string]$c.slug;parent=[int]$c.parent;count=[int]$c.count;description=[string]$c.description}}
$record=[ordered]@{ok=$true;query=$query;executed_at_utc=[DateTime]::UtcNow.ToString('o');category_count=$matchedCats.Count;product_count=$matchedProducts.Count;matching_categories=@($catRows);matching_products=@($matchedProducts)}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
$record|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "CATEGORY_INVENTORY_OK query=$query categories=$($matchedCats.Count) products=$($matchedProducts.Count)"
