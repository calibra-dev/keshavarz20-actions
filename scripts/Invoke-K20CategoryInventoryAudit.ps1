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
if($matchedCats.Count-eq0){$allCategories=@(Get-Paged 'wp-json/wc/v3/products/categories?hide_empty=false');$matchedCats=@($allCategories|Where-Object{(Norm([string]$_.name)).Contains($needle)-or(Norm([string]$_.slug)).Contains($needle)})}
$coreProbe=@()
if($req.wp_core_probe){
  foreach($c in $matchedCats){
    try{
      $o=Invoke-K20 ("wp-json/wp/v2/product_cat/"+[int]$c.id+"?context=edit")
      $raw=$null;$rendered=$null
      if($null-ne$o.description){if($o.description-is[string]){$raw=[string]$o.description;$rendered=[string]$o.description}else{$raw=[string]$o.description.raw;$rendered=[string]$o.description.rendered}}
      $coreProbe+=[ordered]@{id=[int]$c.id;ok=$true;name=[string]$o.name;slug=[string]$o.slug;parent=[int]$o.parent;description_raw=$raw;description_rendered=$rendered}
    }catch{$status=0;if($_.Exception.Response){try{$status=[int]$_.Exception.Response.StatusCode}catch{$status=0}};$coreProbe+=[ordered]@{id=[int]$c.id;ok=$false;http_status=$status;message=$_.Exception.Message}}
  }
}
$bridgeRoutes=@();$bridgeInfo=$null
if($req.bridge_probe){
  try{
    $root=Invoke-K20 'wp-json'
    foreach($prop in $root.routes.PSObject.Properties){
      if($prop.Name -notmatch 'keshavarz20-ops/v2'){continue}
      $endpoints=@()
      foreach($ep in @($prop.Value.endpoints)){$argNames=@();if($ep.args){$argNames=@($ep.args.PSObject.Properties|ForEach-Object{$_.Name}|Sort-Object -Unique)};$endpoints+=[ordered]@{methods=@($ep.methods);arg_names=@($argNames)}}
      $bridgeRoutes+=[ordered]@{route=$prop.Name;methods=@($prop.Value.methods);endpoints=@($endpoints)}
    }
    try{
      $info=Invoke-K20 'wp-json/keshavarz20-ops/v2'
      $bridgeInfo=[ordered]@{ok=$true;top_level_keys=@($info.PSObject.Properties|ForEach-Object{$_.Name}|Sort-Object);status=[string]$info.status;plugin=[string]$info.plugin;version=[string]$info.version;capabilities=@($info.capabilities);actions=@($info.actions)}
    }catch{$bridgeInfo=[ordered]@{ok=$false;message=$_.Exception.Message}}
  }catch{$bridgeRoutes+=[ordered]@{route='probe_error';methods=@();endpoints=@();message=$_.Exception.Message}}
}
$productsById=@{}
foreach($c in $matchedCats){$rows=@(Get-Paged ("wp-json/wc/v3/products?status=publish&orderby=id&order=asc&category="+[int]$c.id));foreach($p in $rows){$productsById[[int]$p.id]=$p}}
$titleRows=@(Get-Paged "wp-json/wc/v3/products?status=publish&orderby=id&order=asc&search=$encoded")
foreach($p in $titleRows){if((Norm([string]$p.name)).Contains($needle)){$productsById[[int]$p.id]=$p}}
$matchedProducts=@()
foreach($p in @($productsById.Values|Sort-Object id)){$matchedProducts+=[pscustomobject][ordered]@{id=[int]$p.id;name=[string]$p.name;slug=[string]$p.slug;status=[string]$p.status;permalink=[string]$p.permalink;stock_status=[string]$p.stock_status;sku=[string]$p.sku;catalog_visibility=[string]$p.catalog_visibility;short_description=[string]$p.short_description;description=[string]$p.description;categories=@($p.categories|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});tags=@($p.tags|ForEach-Object{[ordered]@{id=[int]$_.id;name=[string]$_.name;slug=[string]$_.slug}});images=@($p.images|ForEach-Object{[ordered]@{id=[int]$_.id;src=[string]$_.src;alt=[string]$_.alt}})}}
$catRows=@();foreach($c in $matchedCats){$catRows+=[ordered]@{id=[int]$c.id;name=[string]$c.name;slug=[string]$c.slug;parent=[int]$c.parent;count=[int]$c.count;description=[string]$c.description}}
$record=[ordered]@{ok=$true;query=$query;executed_at_utc=[DateTime]::UtcNow.ToString('o');category_count=$matchedCats.Count;product_count=$matchedProducts.Count;matching_categories=@($catRows);wp_core_probe=@($coreProbe);bridge_routes=@($bridgeRoutes);bridge_info=$bridgeInfo;matching_products=@($matchedProducts)}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
$record|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "CATEGORY_INVENTORY_OK query=$query categories=$($matchedCats.Count) products=$($matchedProducts.Count) core_probe=$($coreProbe.Count) bridge_routes=$($bridgeRoutes.Count)"
