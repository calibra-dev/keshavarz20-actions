param(
  [Parameter(Mandatory = $true)][string]$RequestPath,
  [Parameter(Mandatory = $true)][string]$OutputPath
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

$request = Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
$mode = if ($request.mode) { [string]$request.mode } else { 'audit' }
if ($mode -notin @('audit','apply_description')) { Fail "Unsupported mode: $mode" }
$targetCategorySlug = if ($request.category_slug) { [string]$request.category_slug } else { 'polyethylene-end-cap' }
$pipeCategorySlug = if ($request.pipe_category_slug) { [string]$request.pipe_category_slug } else { 'polyethylene-pipe' }
$maxRelated = if ($request.max_related) { [int]$request.max_related } else { 6 }
if ($maxRelated -lt 3 -or $maxRelated -gt 8) { Fail 'max_related must be between 3 and 8.' }

$authText = "$user`:$pass"
$authValue = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($authText))
$headers = @{ Authorization = "Basic $authValue"; Accept = 'application/json' }

function Invoke-K20([string]$Method, [string]$Path, $Body = $null) {
  $uri = $base + '/' + $Path.TrimStart('/')
  $args = @{ Uri=$uri; Method=$Method; Headers=$headers; TimeoutSec=180 }
  if ($null -ne $Body) {
    $args.ContentType = 'application/json; charset=utf-8'
    $args.Body = ($Body | ConvertTo-Json -Depth 100 -Compress)
  }
  return Invoke-RestMethod @args
}

function Get-AllProducts() {
  $all = @()
  for ($page=1; $page -le 100; $page++) {
    $items = @(Invoke-K20 'GET' "wp-json/wc/v3/products?per_page=100&page=$page&status=publish&orderby=id&order=asc")
    if ($items.Count -eq 0) { break }
    $all += $items
    if ($items.Count -lt 100) { break }
  }
  return @($all)
}

function Normalize-Digits([string]$Text) {
  if ($null -eq $Text) { return '' }
  $s = $Text
  $from = @('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹','٠','١','٢','٣','٤','٥','٦','٧','٨','٩')
  $to   = @('0','1','2','3','4','5','6','7','8','9','0','1','2','3','4','5','6','7','8','9')
  for ($i=0; $i -lt $from.Count; $i++) { $s = $s.Replace($from[$i],$to[$i]) }
  return $s.Replace('‌',' ').Replace('٫','.').Replace('٬',',')
}

function Normalize-InchText([string]$Text) {
  $s = Normalize-Digits $Text
  $s = $s.Replace('½',' 1/2').Replace('¼',' 1/4').Replace('¾',' 3/4')
  $s = [regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*1\s*/\s*2(?!\d)',{
    param($m)
    $whole=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture)
    return ($whole+0.5).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
  })
  $s = [regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*1\s*/\s*4(?!\d)',{
    param($m)
    $whole=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture)
    return ($whole+0.25).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
  })
  $s = [regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*3\s*/\s*4(?!\d)',{
    param($m)
    $whole=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture)
    return ($whole+0.75).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
  })
  $s = [regex]::Replace($s,'(?<!\d)3\s*/\s*4(?!\d)','0.75')
  $s = [regex]::Replace($s,'(?<!\d)1\s*/\s*2(?!\d)','0.5')
  $s = [regex]::Replace($s,'(?<!\d)1\s*/\s*4(?!\d)','0.25')
  return $s
}

function Convert-ToPersianDigits([string]$Text) {
  $s = [string]$Text
  $to = @('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹')
  for ($i=0; $i -lt 10; $i++) { $s = $s.Replace([string]$i,$to[$i]) }
  return $s
}

$inchToMm = @{
  '0.5'=20; '0.75'=25; '1'=32; '1.25'=40; '1.5'=50;
  '2'=63; '2.5'=75; '3'=90; '4'=110; '6'=160
}

function Get-NominalSizeMm([string]$Name) {
  $s = Normalize-InchText $Name

  # A reducer such as 32 x 50 is not an exact same-size product.
  $pair = [regex]::Match($s,'(?<!\d)(?<a>16|20|25|32|40|50|63|75|90|110|125|160|200)\s*(?:x|X|×|\*)\s*(?<b>16|20|25|32|40|50|63|75|90|110|125|160|200)(?!\d)')
  if ($pair.Success -and [int]$pair.Groups['a'].Value -ne [int]$pair.Groups['b'].Value) { return $null }

  $values = @()
  foreach ($m in [regex]::Matches($s,'(?<!\d)(?<mm>16|20|25|32|40|50|63|75|90|110|125|160|200)\s*(?:میلی\s*متر|میلیمتر|mm\b)',[Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
    $values += [int]$m.Groups['mm'].Value
  }
  $values = @($values | Sort-Object -Unique)
  if ($values.Count -eq 1) { return [int]$values[0] }
  if ($values.Count -gt 1) { return $null }

  $inch = [regex]::Match($s,'(?<!\d)(?<i>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)',[Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if ($inch.Success) {
    $key = ([double]$inch.Groups['i'].Value).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
    if ($inchToMm.ContainsKey($key)) { return [int]$inchToMm[$key] }
  }
  return $null
}

function Test-CategoryId($Product,[int]$CategoryId) {
  foreach ($c in @($Product.categories)) {
    if ([int]$c.id -eq $CategoryId) { return $true }
  }
  return $false
}

function Get-RelatedFamily($Product,[int]$PipeCategoryId) {
  if (Test-CategoryId $Product $PipeCategoryId) { return 'pipe' }
  $n = Normalize-Digits ([string]$Product.name)
  if ($n -match 'تبدیل') { return $null }
  if ($n -match '^\s*رابط\b|کوپل') { return 'coupling' }
  if ($n -match 'زانویی|زانو') { return 'elbow' }
  if ($n -match 'سه\s*راه|سه‌راه') { return 'tee' }
  if ($n -match 'شیر') { return 'valve' }
  if ($n -match 'مغزی|بوشن|اتصال') { return 'fitting' }
  return $null
}

function Get-RecommendationBounds([string]$Html) {
  if ([string]::IsNullOrWhiteSpace($Html)) { return $null }
  $markers=@(
    'قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن','قطعات پیشنهادی برای تکمیل خط پلی اتیلن',
    'محصولات مرتبط','محصولات پیشنهادی','محصولات مکمل','پیشنهادهای مرتبط',
    'پیشنهاد خرید','برای تکمیل خرید','همراه این محصول','خرید همزمان'
  )
  $bestIndex=-1; $bestMarker=$null
  foreach ($marker in $markers) {
    $index=$Html.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
    if ($index -ge 0 -and ($bestIndex -lt 0 -or $index -lt $bestIndex)) { $bestIndex=$index; $bestMarker=$marker }
  }
  if ($bestIndex -lt 0) { return $null }
  $start=$Html.LastIndexOf('<h2',$bestIndex,[StringComparison]::OrdinalIgnoreCase)
  if ($start -lt 0) { return $null }
  $end=$Html.IndexOf('<h2',$bestIndex+$bestMarker.Length,[StringComparison]::OrdinalIgnoreCase)
  if ($end -lt 0) { $end=$Html.Length }
  return [pscustomobject][ordered]@{ start=$start; end=$end; marker=$bestMarker }
}

function Remove-RecommendationBlock([string]$Html) {
  if ($null -eq $Html) { return '' }
  $bounds=Get-RecommendationBounds $Html
  if ($null -eq $bounds) { return $Html }
  return $Html.Substring(0,[int]$bounds.start)+$Html.Substring([int]$bounds.end)
}

function Get-PlainText([string]$Html) {
  if ($null -eq $Html) { return '' }
  $text=[regex]::Replace($Html,'<[^>]+>',' ')
  $text=[System.Net.WebUtility]::HtmlDecode($text)
  return ([regex]::Replace($text,'\s+',' ')).Trim()
}

function Set-RecommendationBlock([string]$Html,[string]$Block) {
  if ($null -eq $Html) { $Html='' }
  $bounds=Get-RecommendationBounds $Html
  if ($null -ne $bounds) {
    return $Html.Substring(0,[int]$bounds.start)+$Block+$Html.Substring([int]$bounds.end)
  }
  foreach ($marker in @('پرسش‌های پرتکرار','پرسش های پرتکرار','سوالات متداول','سؤالات متداول')) {
    $index=$Html.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
    if ($index -ge 0) {
      $heading=$Html.LastIndexOf('<h2',$index,[StringComparison]::OrdinalIgnoreCase)
      if ($heading -ge 0) { return $Html.Insert($heading,$Block) }
    }
  }
  return $Html.TrimEnd()+"`n"+$Block
}

function Get-FamilyLabel([string]$Family) {
  switch ($Family) {
    'pipe' { return 'لوله پلی‌اتیلن هم‌سایز' }
    'coupling' { return 'رابط هم‌سایز' }
    'elbow' { return 'زانو هم‌سایز' }
    'tee' { return 'سه‌راه هم‌سایز' }
    'valve' { return 'شیر هم‌سایز' }
    default { return 'اتصال هم‌سایز' }
  }
}

function Get-FamilyNote([string]$Family,[string]$SizeFa) {
  switch ($Family) {
    'pipe' { return "برای اجرای همان خط $SizeFa میلی‌متری." }
    'coupling' { return 'برای اتصال مستقیم دو بخش هم‌سایز خط.' }
    'elbow' { return 'برای تغییر مسیر خط بدون تغییر سایز نامی.' }
    'tee' { return 'برای گرفتن انشعاب هم‌سایز از مسیر.' }
    'valve' { return 'برای قطع و وصل جریان در همین سایز نامی.' }
    default { return 'برای تکمیل اتصال در همین سایز نامی.' }
  }
}

function Build-RecommendationBlock($Target) {
  $sizeFa=Convert-ToPersianDigits ([string]$Target.size_mm)
  $items=@()
  foreach ($r in @($Target.proposed_products)) {
    $name=[System.Net.WebUtility]::HtmlEncode([string]$r.name)
    $url=[System.Net.WebUtility]::HtmlEncode([string]$r.permalink)
    $label=[System.Net.WebUtility]::HtmlEncode((Get-FamilyLabel ([string]$r.family)))
    $note=[System.Net.WebUtility]::HtmlEncode((Get-FamilyNote ([string]$r.family) $sizeFa))
    $items += ('<li style="margin:7px 0"><strong>{0}:</strong> <a style="color:#176b3a;font-weight:700" href="{1}">{2}</a> — {3}</li>' -f $label,$url,$name,$note)
  }
  $list=$items -join "`n"
  return @"
<h2 style="font-size:24px;line-height:1.8;color:#176b3a;margin:34px 0 14px;border-right:5px solid #5d9a68;padding-right:12px">قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن $sizeFa میلی‌متر</h2>
<div style="background:#f7fbf8;border:1px solid #dbe8df;border-radius:16px;padding:17px;margin:15px 0">
<p>اگر این درپوش را برای بستن انتهای خط پلی‌اتیلن $sizeFa میلی‌متری انتخاب می‌کنید، لوله و قطعات کناری شبکه هم باید با همین سایز نامی هماهنگ باشند. پیشنهادهای زیر از محصولات واقعی فروشگاه و با تطبیق مستقیم سایز انتخاب شده‌اند تا هنگام تکمیل خط، قطعه نامرتبط یا تبدیل ناخواسته وارد انتخاب شما نشود.</p>
<p>اول لوله پلی‌اتیلن هم‌سایز آمده است؛ بعد از آن فقط چند قطعه کاربردی هم‌سایز برای ادامه خط، تغییر مسیر، انشعاب یا کنترل جریان پیشنهاد شده‌اند.</p>
<ul style="padding-right:22px;margin:10px 0">
$list
</ul>
<p style="margin:12px 0 0"><strong>قبل از خرید:</strong> عدد سایز روی لوله یا اتصال فعلی را با $sizeFa میلی‌متر تطبیق دهید. اگر سایز خط متفاوت است، درپوش و قطعات مکمل را بر اساس همان سایز انتخاب کنید.</p>
</div>
"@
}

function Get-Hash([string]$Text) {
  if ($null -eq $Text) { $Text='' }
  $sha=[Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-','').ToLowerInvariant()
  } finally { $sha.Dispose() }
}

function Get-IntegritySnapshot($Product) {
  $snapshot=[ordered]@{
    id=[int]$Product.id; name=[string]$Product.name; slug=[string]$Product.slug; status=[string]$Product.status; type=[string]$Product.type; sku=[string]$Product.sku;
    price=[string]$Product.price; regular_price=[string]$Product.regular_price; sale_price=[string]$Product.sale_price;
    manage_stock=[bool]$Product.manage_stock; stock_quantity=$Product.stock_quantity; stock_status=[string]$Product.stock_status; backorders=[string]$Product.backorders;
    short_description_sha256=Get-Hash ([string]$Product.short_description);
    categories=@($Product.categories | ForEach-Object { [int]$_.id } | Sort-Object);
    tags=@($Product.tags | ForEach-Object { [int]$_.id } | Sort-Object);
    images=@($Product.images | ForEach-Object { [int]$_.id } | Sort-Object);
    upsell_ids=@($Product.upsell_ids | ForEach-Object { [int]$_ } | Sort-Object);
    cross_sell_ids=@($Product.cross_sell_ids | ForEach-Object { [int]$_ } | Sort-Object);
    attributes_json=($Product.attributes | ConvertTo-Json -Depth 30 -Compress)
  }
  return Get-Hash ($snapshot | ConvertTo-Json -Depth 50 -Compress)
}

function Test-RecommendationReadback([string]$Html,$Target) {
  $bounds=Get-RecommendationBounds $Html
  if ($null -eq $bounds) { return [pscustomobject]@{ok=$false;reason='block_missing'} }
  $block=$Html.Substring([int]$bounds.start,[int]$bounds.end-[int]$bounds.start)
  foreach ($r in @($Target.proposed_products)) {
    if ($block.IndexOf([string]$r.permalink,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return [pscustomobject]@{ok=$false;reason="missing_link_$([int]$r.id)"}
    }
  }
  $links=@([regex]::Matches($block,'<a\b[^>]*href=["''][^"'']+["''][^>]*>',[Text.RegularExpressions.RegexOptions]::IgnoreCase))
  if ($links.Count -ne @($Target.proposed_products).Count) { return [pscustomobject]@{ok=$false;reason='link_count_mismatch'} }
  if ($block -notmatch 'لوله\s*پلی.?اتیلن\s*هم.?سایز') { return [pscustomobject]@{ok=$false;reason='human_pipe_copy_missing'} }
  return [pscustomobject]@{ok=$true;reason='ok'}
}

$targetCategories=@(Invoke-K20 'GET' ("wp-json/wc/v3/products/categories?slug="+[Uri]::EscapeDataString($targetCategorySlug)+"&per_page=100"))
$pipeCategories=@(Invoke-K20 'GET' ("wp-json/wc/v3/products/categories?slug="+[Uri]::EscapeDataString($pipeCategorySlug)+"&per_page=100"))
if ($targetCategories.Count -ne 1) { Fail "Expected one target category; got $($targetCategories.Count)" }
if ($pipeCategories.Count -ne 1) { Fail "Expected one pipe category; got $($pipeCategories.Count)" }
$targetCategory=$targetCategories[0]; $targetCategoryId=[int]$targetCategory.id
$pipeCategory=$pipeCategories[0]; $pipeCategoryId=[int]$pipeCategory.id

$products=@(Get-AllProducts)
if ($products.Count -eq 0) { Fail 'No published WooCommerce products returned.' }
$byId=@{}; foreach ($p in $products) { $byId[[int]$p.id]=$p }

$pipeCatalog=@()
foreach ($p in $products) {
  if (Test-CategoryId $p $pipeCategoryId) {
    $pipeCatalog += [pscustomobject][ordered]@{
      id=[int]$p.id; name=[string]$p.name; size_mm=Get-NominalSizeMm ([string]$p.name);
      permalink=[string]$p.permalink; stock_status=[string]$p.stock_status
    }
  }
}

$targets=@()
foreach ($p in $products) {
  if (-not (Test-CategoryId $p $targetCategoryId)) { continue }
  $size=Get-NominalSizeMm ([string]$p.name)
  $pipes=@(); $families=@{}

  if ($null -ne $size) {
    foreach ($candidate in $products) {
      if ([int]$candidate.id -eq [int]$p.id) { continue }
      if ([string]$candidate.catalog_visibility -eq 'hidden') { continue }
      if (Test-CategoryId $candidate $targetCategoryId) { continue }
      $normalized=Normalize-Digits ([string]$candidate.name)
      if ($normalized -match 'درپوش|تبدیل') { continue }
      $candidateSize=Get-NominalSizeMm ([string]$candidate.name)
      if ($null -eq $candidateSize -or [int]$candidateSize -ne [int]$size) { continue }
      $family=Get-RelatedFamily $candidate $pipeCategoryId
      if (-not $family) { continue }
      $row=[pscustomobject][ordered]@{
        id=[int]$candidate.id; name=[string]$candidate.name; permalink=[string]$candidate.permalink;
        family=$family; stock_status=[string]$candidate.stock_status
      }
      if ($family -eq 'pipe') { $pipes += $row }
      else {
        if (-not $families.ContainsKey($family)) { $families[$family]=@() }
        $families[$family] += $row
      }
    }
  }

  $pipes=@($pipes | Sort-Object @{Expression={if($_.stock_status -eq 'instock'){0}else{1}}},id)
  $selected=@($pipes | Select-Object -First 2)
  foreach ($family in @('coupling','elbow','tee','valve','fitting')) {
    if ($selected.Count -ge $maxRelated) { break }
    if (-not $families.ContainsKey($family)) { continue }
    $best=@($families[$family] | Sort-Object @{Expression={if($_.stock_status -eq 'instock'){0}else{1}}},id | Select-Object -First 1)
    if ($best.Count -gt 0) { $selected += $best[0] }
  }
  if ($selected.Count -gt $maxRelated) { $selected=@($selected | Select-Object -First $maxRelated) }

  $bounds=Get-RecommendationBounds ([string]$p.description)
  $targets += [pscustomobject][ordered]@{
    id=[int]$p.id; name=[string]$p.name; size_mm=$size;
    existing_recommendation_block=($null -ne $bounds);
    same_size_pipe_count=$pipes.Count;
    proposed_products=@($selected | ForEach-Object {
      [pscustomobject][ordered]@{id=$_.id;name=$_.name;permalink=$_.permalink;family=$_.family;reason="same_size_${size}mm"}
    })
  }
}

$unparsed=@($targets | Where-Object { $null -eq $_.size_mm })
$missingPipe=@($targets | Where-Object { [int]$_.same_size_pipe_count -lt 1 })
$empty=@($targets | Where-Object { @($_.proposed_products).Count -lt 1 })
if ($mode -eq 'apply_description' -and $unparsed.Count -gt 0) { Fail "Refusing apply: unparsed IDs $((@($unparsed.id)-join ','))" }
if ($mode -eq 'apply_description' -and $missingPipe.Count -gt 0) { Fail "Refusing apply: no same-size published PE pipe for IDs $((@($missingPipe.id)-join ','))" }
if ($mode -eq 'apply_description' -and $empty.Count -gt 0) { Fail "Refusing apply: empty recommendations for IDs $((@($empty.id)-join ','))" }

$changes=@()
if ($mode -eq 'apply_description') {
  foreach ($t in $targets) {
    $id=[int]$t.id; $before=$byId[$id]
    $beforeIntegrity=Get-IntegritySnapshot $before
    $beforeDescription=[string]$before.description
    $beforeOutsideText=Get-PlainText (Remove-RecommendationBlock $beforeDescription)
    $newBlock=Build-RecommendationBlock $t
    $desired=Set-RecommendationBlock $beforeDescription $newBlock

    $currentCheck=Test-RecommendationReadback $beforeDescription $t
    if ($currentCheck.ok) {
      $changes += [pscustomobject][ordered]@{id=$id;name=$t.name;changed=$false;semantic_verified=$true;integrity_unchanged=$true;outside_text_unchanged=$true;reason='already_current'}
      continue
    }

    $null=Invoke-K20 'PUT' "wp-json/wc/v3/products/$id" ([ordered]@{description=$desired})
    $after=Invoke-K20 'GET' "wp-json/wc/v3/products/$id"
    $readback=Test-RecommendationReadback ([string]$after.description) $t
    $integrityUnchanged=((Get-IntegritySnapshot $after) -eq $beforeIntegrity)
    $afterOutsideText=Get-PlainText (Remove-RecommendationBlock ([string]$after.description))
    $outsideTextUnchanged=($afterOutsideText -ceq $beforeOutsideText)

    if (-not $readback.ok) { Fail "Recommendation readback failed for product ${id}: $($readback.reason)" }
    if (-not $integrityUnchanged) { Fail "Protected-field integrity mismatch for product $id" }
    if (-not $outsideTextUnchanged) { Fail "Text outside recommendation block changed for product $id" }

    $changes += [pscustomobject][ordered]@{id=$id;name=$t.name;changed=$true;semantic_verified=$true;integrity_unchanged=$true;outside_text_unchanged=$true;reason='ok'}
  }
}

$record=[ordered]@{
  ok=$true; mode=$mode; executed_at_utc=[DateTime]::UtcNow.ToString('o');
  target_category=[ordered]@{id=$targetCategoryId;name=[string]$targetCategory.name;slug=[string]$targetCategory.slug};
  pipe_category=[ordered]@{id=$pipeCategoryId;name=[string]$pipeCategory.name;slug=[string]$pipeCategory.slug};
  published_product_count=$products.Count; target_count=$targets.Count;
  unparsed_target_count=$unparsed.Count; missing_same_size_pipe_count=$missingPipe.Count; empty_recommendation_count=$empty.Count;
  rules=[ordered]@{
    pipe='product must belong to live WooCommerce polyethylene-pipe category';
    mixed_sizes='reducers and mixed nominal sizes are excluded';
    related='up to two exact same-size PE pipes, then one exact same-size item per useful fitting family';
    copy='human-written Persian copy specific to the exact nominal size';
    mutation='description only';
    protected='price, regular/sale price, stock, SKU, identity, short description, taxonomy, images, attributes, upsells and cross-sells are readback-protected'
  };
  unparsed_targets=@($unparsed | Select-Object id,name);
  missing_pipe_targets=@($missingPipe | Select-Object id,name,size_mm);
  pipe_catalog=@($pipeCatalog | Sort-Object size_mm,id);
  targets=@($targets);
  changes=@($changes);
  changed_count=@($changes | Where-Object {$_.changed}).Count;
  semantic_verified_count=@($changes | Where-Object {$_.semantic_verified}).Count;
  integrity_verified_count=@($changes | Where-Object {$_.integrity_unchanged}).Count;
  outside_text_verified_count=@($changes | Where-Object {$_.outside_text_unchanged}).Count
}

$dir=Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$record | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "K20_END_CAP_V3_OK mode=$mode targets=$($targets.Count) missingPipe=$($missingPipe.Count) changed=$(@($changes|Where-Object {$_.changed}).Count)"
