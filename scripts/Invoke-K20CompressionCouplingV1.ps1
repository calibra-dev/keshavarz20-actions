param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
if(-not(Test-Path -LiteralPath $RequestPath)){throw "Request file not found: $RequestPath"}
. (Join-Path $PSScriptRoot 'coupling/CommonApi.ps1')
. (Join-Path $PSScriptRoot 'coupling/CommonHtml.ps1')
. (Join-Path $PSScriptRoot 'coupling/BuildBlock.ps1')
. (Join-Path $PSScriptRoot 'coupling/Verifier.ps1')
$request=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 100
$mode=if($request.mode){[string]$request.mode}else{'audit'};if($mode-notin@('audit','apply_description')){Fail "Unsupported mode: $mode"}
$targetSlug=if($request.category_slug){[string]$request.category_slug}else{'polyethylene-compression-coupling'}
$pipeSlug=if($request.pipe_category_slug){[string]$request.pipe_category_slug}else{'polyethylene-pipe'}
$maxRelated=if($request.max_related){[int]$request.max_related}else{8};if($maxRelated-lt3-or$maxRelated-gt8){Fail 'max_related must be 3..8'}
$tc=@(Invoke-K20 'GET' ("wp-json/wc/v3/products/categories?slug="+[Uri]::EscapeDataString($targetSlug)+"&per_page=100"));if($tc.Count-ne1){Fail "Expected one target category; got $($tc.Count)"};$targetCategory=$tc[0];$targetCategoryId=[int]$targetCategory.id
$pc=@(Invoke-K20 'GET' ("wp-json/wc/v3/products/categories?slug="+[Uri]::EscapeDataString($pipeSlug)+"&per_page=100"));if($pc.Count-ne1){Fail "Expected one pipe category; got $($pc.Count)"};$pipeCategory=$pc[0];$pipeCategoryId=[int]$pipeCategory.id
$products=@(Get-AllProducts);if($products.Count-eq0){Fail 'No published WooCommerce products returned.'};$byId=@{};foreach($p in$products){$byId[[int]$p.id]=$p}
. (Join-Path $PSScriptRoot 'coupling/TargetBlock.ps1')
$changes=@()
if($mode-eq'apply_description'){
  foreach($t in$targets){
    $id=[int]$t.id;$before=$byId[$id];$beforeIntegrity=Get-IntegritySnapshot $before;$beforeDescription=[string]$before.description;$beforeOutside=Get-PlainText(Remove-RecommendationBlock $beforeDescription);$desired=Set-RecommendationBlock $beforeDescription (Build-RecommendationBlock $t)
    $current=Test-RecommendationReadback $beforeDescription $t
    if($current.ok){$changes+=[pscustomobject]@{id=$id;name=$t.name;changed=$false;semantic_verified=$true;integrity_unchanged=$true;outside_text_unchanged=$true;reason='already_current'};continue}
    $null=Invoke-K20 'PUT' "wp-json/wc/v3/products/$id" ([ordered]@{description=$desired});$after=Invoke-K20 'GET' "wp-json/wc/v3/products/$id";$check=Test-RecommendationReadback ([string]$after.description) $t;$integrity=((Get-IntegritySnapshot $after)-eq$beforeIntegrity);$outside=(Get-PlainText(Remove-RecommendationBlock([string]$after.description))-ceq$beforeOutside)
    if(-not$check.ok){Fail "Recommendation readback failed for ${id}: $($check.reason)"};if(-not$integrity){Fail "Protected-field integrity mismatch for $id"};if(-not$outside){Fail "Text outside recommendation block changed for $id"}
    $changes+=[pscustomobject]@{id=$id;name=$t.name;changed=$true;semantic_verified=$true;integrity_unchanged=$true;outside_text_unchanged=$true;reason='written_and_verified'}
  }
}
$record=[ordered]@{ok=$true;mode=$mode;executed_at_utc=[DateTime]::UtcNow.ToString('o');target_category=[ordered]@{id=$targetCategoryId;name=[string]$targetCategory.name;slug=[string]$targetCategory.slug;count=[int]$targetCategory.count;description=[string]$targetCategory.description};pipe_category=[ordered]@{id=$pipeCategoryId;name=[string]$pipeCategory.name;slug=[string]$pipeCategory.slug};published_product_count=$products.Count;target_count=$targets.Count;ambiguous_target_count=$unparsed.Count;missing_pipe_target_count=$missingPipe.Count;empty_recommendation_count=$empty.Count;rules=[ordered]@{equal='one nominal size: exact-size PE pipe plus useful same-size fittings';reducer='two nominal sizes: pipe for each side plus equal couplings and side-specific fittings';pipe='must belong to live polyethylene-pipe category';stale='hidden and __trashed products are excluded';mutation='description field only';protected='price, regular/sale price, stock, SKU, name, slug, short description, taxonomy, images, attributes, upsells and cross-sells are readback-protected'};ambiguous_targets=@($unparsed);missing_pipe_targets=@($missingPipe|Select-Object id,name,kind,sizes_mm,missing_pipe_sizes);pipe_catalog=@($pipeCatalog);targets=@($targets);changes=@($changes);changed_count=@($changes|Where-Object{$_.changed}).Count;semantic_verified_count=@($changes|Where-Object{$_.semantic_verified}).Count;integrity_verified_count=@($changes|Where-Object{$_.integrity_unchanged}).Count;outside_text_verified_count=@($changes|Where-Object{$_.outside_text_unchanged}).Count}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null};$record|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "COMPRESSION_COUPLING_OK mode=$mode targets=$($targets.Count) ambiguous=$($unparsed.Count) changed=$(@($changes|Where-Object{$_.changed}).Count)"
