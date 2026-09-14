param(
  [Parameter(Mandatory = $true)][string]$RequestPath,
  [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
function Fail([string]$Message) { throw $Message }

if (-not (Test-Path -LiteralPath $RequestPath)) { Fail "Request file not found: $RequestPath" }

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
$categorySlug = if ($request.category_slug) { [string]$request.category_slug } else { 'polyethylene-end-cap' }
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
    $response = Invoke-K20 'GET' "wp-json/wc/v3/products?per_page=100&page=$page&status=publish&orderby=id&order=asc"
    $items = @($response | ForEach-Object { $_ })
    if ($items.Count -eq 0) { break }
    foreach ($item in $items) { $all += $item }
    if ($items.Count -lt 100) { break }
  }
  return @($all)
}

function Normalize-Digits([string]$Text) {
  if ($null -eq $Text) { return '' }
  $s = $Text
  $from = @('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹','٠','١','٢','٣','٤','٥','٦','٧','٨','٩')
  $to   = @('0','1','2','3','4','5','6','7','8','9','0','1','2','3','4','5','6','7','8','9')
  for ($i=0; $i -lt $from.Count; $i++) { $s = $s.Replace($from[$i], $to[$i]) }
  return $s.Replace('‌',' ').Replace('٫','.').Replace('٬',',')
}

function Normalize-InchText([string]$Text) {
  $s = Normalize-Digits $Text
  $s = $s.Replace('½',' 1/2').Replace('¼',' 1/4').Replace('¾',' 3/4')
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*1\s*/\s*2(?!\d)', {
    param($m); $w=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture); ($w+0.5).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*1\s*/\s*4(?!\d)', {
    param($m); $w=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture); ($w+0.25).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*3\s*/\s*4(?!\d)', {
    param($m); $w=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture); ($w+0.75).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
  })
  $s = [regex]::Replace($s, '(?<!\d)3\s*/\s*4(?!\d)', '0.75')
  $s = [regex]::Replace($s, '(?<!\d)1\s*/\s*2(?!\d)', '0.5')
  $s = [regex]::Replace($s, '(?<!\d)1\s*/\s*4(?!\d)', '0.25')
  return $s
}

function Convert-ToPersianDigits([string]$Text) {
  $s = [string]$Text
  $from = @('0','1','2','3','4','5','6','7','8','9')
  $to   = @('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹')
  for ($i=0; $i -lt 10; $i++) { $s = $s.Replace($from[$i],$to[$i]) }
  return $s
}

$knownMm = @(16,20,25,32,40,50,63,75,90,110,125,160,200)
$inchToMm = @{
  '0.5'=20; '0.75'=25; '1'=32; '1.25'=40; '1.5'=50;
  '2'=63; '2.5'=75; '3'=90; '4'=110; '6'=160
}

function Get-NominalMmSizes([string]$Name) {
  $s = Normalize-InchText $Name
  $values = @()
  foreach ($m in [regex]::Matches($s, '(?<!\d)(?<mm>\d{2,3})\s*(?:میلی\s*متر|میلیمتر|mm\b)', [Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
    $v = [int]$m.Groups['mm'].Value
    if ($knownMm -contains $v) { $values += $v }
  }
  if ($values.Count -eq 0) {
    foreach ($m in [regex]::Matches($s, '(?<!\d)(?<inch>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)', [Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
      $key = [double]::Parse($m.Groups['inch'].Value,[Globalization.CultureInfo]::InvariantCulture).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)
      if ($inchToMm.ContainsKey($key)) { $values += [int]$inchToMm[$key] }
    }
  }
  return @($values | Sort-Object -Unique)
}

function Get-SingleNominalMm([string]$Name) {
  $sizes = @(Get-NominalMmSizes $Name)
  if ($sizes.Count -ne 1) { return $null }
  return [int]$sizes[0]
}

function Is-PolyethylenePipe([string]$Name) {
  $n = Normalize-Digits $Name
  if ($n -notmatch 'لوله' -or $n -notmatch 'پلی\s*اتیلن') { return $false }
  if ($n -match 'نخدار|لی\s*فلت|مه\s*پاش|بارانی|نوار|تیپ|خرطومی|تاشو') { return $false }
  return $true
}

function Get-RelatedFamily([string]$Name) {
  $n = Normalize-Digits $Name
  if (Is-PolyethylenePipe $Name) { return 'pipe' }
  if ($n -match 'رابط|کوپل') { return 'coupling' }
  if ($n -match 'زانویی|زانو') { return 'elbow' }
  if ($n -match 'سه\s*راه|سه‌راه') { return 'tee' }
  if ($n -match 'شیر') { return 'valve' }
  if ($n -match 'کمربند') { return 'clamp' }
  if ($n -match 'مغزی|بوشن|اتصال') { return 'fitting' }
  return $null
}

function Get-RecommendationBounds([string]$Html) {
  if ([string]::IsNullOrWhiteSpace($Html)) { return $null }
  $markers = @(
    'قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن',
    'قطعات پیشنهادی برای تکمیل خط پلی اتیلن',
    'محصولات مرتبط', 'محصولات پیشنهادی', 'محصولات مکمل', 'پیشنهادهای مرتبط',
    'پیشنهاد خرید', 'برای تکمیل خرید', 'همراه این محصول', 'خرید همزمان'
  )
  $bestIdx=-1; $bestMarker=$null
  foreach ($marker in $markers) {
    $idx=$Html.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
    if ($idx -ge 0 -and ($bestIdx -lt 0 -or $idx -lt $bestIdx)) { $bestIdx=$idx; $bestMarker=$marker }
  }
  if ($bestIdx -lt 0) { return $null }
  $start=$Html.LastIndexOf('<h2',$bestIdx,[StringComparison]::OrdinalIgnoreCase)
  if ($start -lt 0) { return $null }
  $next=$Html.IndexOf('<h2',$bestIdx+$bestMarker.Length,[StringComparison]::OrdinalIgnoreCase)
  if ($next -lt 0) { $next=$Html.Length }
  return [pscustomobject][ordered]@{ start=$start; end=$next; marker=$bestMarker }
}

function Remove-RecommendationBlock([string]$Html) {
  if ($null -eq $Html) { return '' }
  $bounds=Get-RecommendationBounds $Html
  if ($null -eq $bounds) { return $Html }
  return $Html.Substring(0,[int]$bounds.start)+$Html.Substring([int]$bounds.end)
}

function Get-PlainText([string]$Html) {
  if ($null -eq $Html) { return '' }
  $s=[regex]::Replace($Html,'<[^>]+>',' ')
  $s=[System.Net.WebUtility]::HtmlDecode($s)
  return ([regex]::Replace($s,'\s+',' ')).Trim()
}

function Set-RecommendationBlock([string]$Html,[string]$Block) {
  if ($null -eq $Html) { $Html='' }
  $bounds=Get-RecommendationBounds $Html
  if ($null -ne $bounds) {
    return $Html.Substring(0,[int]$bounds.start)+$Block+$Html.Substring([int]$bounds.end)
  }
  foreach ($marker in @('پرسش‌های پرتکرار','پرسش های پرتکرار','سوالات متداول','سؤالات متداول')) {
    $idx=$Html.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
    if ($idx -ge 0) {
      $h2=$Html.LastIndexOf('<h2',$idx,[StringComparison]::OrdinalIgnoreCase)
      if ($h2 -ge 0) { return $Html.Insert($h2,$Block) }
    }
  }
  return ($Html.TrimEnd()+"`n"+$Block)
}

function Get-FamilyLabel([string]$Family) {
  switch ($Family) {
    'pipe' { return 'لوله پلی‌اتیلن هم‌سایز' }
    'coupling' { return 'رابط هم‌سایز' }
    'elbow' { return 'زانو هم‌سایز' }
    'tee' { return 'سه‌راه هم‌سایز' }
    'valve' { return 'شیر هم‌سایز' }
    'clamp' { return 'کمربند انشعاب' }
    default { return 'اتصال هم‌سایز' }
  }
}

function Get-FamilyNote([string]$Family,[string]$SizeFa) {
  switch ($Family) {
    'pipe' { return "برای اجرای همان خط $SizeFa میلی‌متری." }
    'coupling' { return 'برای وصل‌کردن دو بخش هم‌سایز خط.' }
    'elbow' { return 'برای تغییر مسیر خط بدون تغییر سایز نامی.' }
    'tee' { return 'برای گرفتن انشعاب هم‌سایز از مسیر.' }
    'valve' { return 'برای قطع و وصل مسیر در همین سایز نامی.' }
    'clamp' { return 'برای گرفتن انشعاب از خط اصلی؛ سایز خروجی آن را هم جداگانه کنترل کنید.' }
    default { return 'برای تکمیل اتصال در همین سایز نامی.' }
  }
}

function Build-RecommendationBlock($Target) {
  $sizeFa = Convert-ToPersianDigits ([string]$Target.size_mm)
  $lines=@()
  foreach ($r in @($Target.proposed_products)) {
    $name=[System.Net.WebUtility]::HtmlEncode([string]$r.name)
    $url=[System.Net.WebUtility]::HtmlEncode([string]$r.permalink)
    $label=[System.Net.WebUtility]::HtmlEncode((Get-FamilyLabel ([string]$r.family)))
    $note=[System.Net.WebUtility]::HtmlEncode((Get-FamilyNote ([string]$r.family) $sizeFa))
    $lines += ('<li style="margin:7px 0"><strong>{0}:</strong> <a style="color:#176b3a;font-weight:700" href="{1}">{2}</a> — {3}</li>' -f $label,$url,$name,$note)
  }
  $list=$lines -join "`n"
  return @"
<h2 style="font-size:24px;line-height:1.8;color:#176b3a;margin:34px 0 14px;border-right:5px solid #5d9a68;padding-right:12px">قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن $sizeFa میلی‌متر</h2>
<div style="background:#f7fbf8;border:1px solid #dbe8df;border-radius:16px;padding:17px;margin:15px 0">
<p>اگر این درپوش را برای بستن انتهای خط پلی‌اتیلن $sizeFa میلی‌متری انتخاب می‌کنید، بهتر است لوله و قطعات کناری شبکه هم بر اساس همین سایز نامی انتخاب شوند. پیشنهادهای زیر از محصولات واقعی فروشگاه و با تطبیق مستقیم سایز انتخاب شده‌اند تا موقع تکمیل خط، بین درپوش و قطعات اطراف آن مغایرت سایزی ایجاد نشود.</p>
<p>لوله پلی‌اتیلن هم‌سایز عمداً در اولویت قرار گرفته است؛ بعد از آن چند قطعه کاربردی هم‌سایز برای ادامه، تغییر مسیر یا کنترل خط آمده است.</p>
<ul style="padding-right:22px;margin:10px 0">
$list
</ul>
<p style="margin:12px 0 0"><strong>نکته انتخاب:</strong> قبل از ثبت سفارش، سایز درج‌شده روی لوله یا اتصال فعلی را با $sizeFa میلی‌متر تطبیق دهید. اگر قطر خط شما متفاوت است، همین خانواده محصول را در سایز همان خط انتخاب کنید.</p>
</div>
"@
}

function Get-Hash([string]$Text) {
  if ($null -eq $Text) { $Text='' }
  $sha=[Security.Cryptography.SHA256]::Create()
  try {
    $bytes=[Text.Encoding]::UTF8.GetBytes($Text)
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
  } finally { $sha.Dispose() }
}

function Get-IntegritySnapshot($p) {
  $o=[ordered]@{
    id=[int]$p.id; name=[string]$p.name; slug=[string]$p.slug; status=[string]$p.status; type=[string]$p.type; sku=[string]$p.sku;
    price=[string]$p.price; regular_price=[string]$p.regular_price; sale_price=[string]$p.sale_price;
    manage_stock=[bool]$p.manage_stock; stock_quantity=$p.stock_quantity; stock_status=[string]$p.stock_status; backorders=[string]$p.backorders;
    weight=[string]$p.weight; dimensions=$p.dimensions; shipping_class_id=$p.shipping_class_id;
    short_description_sha256=Get-Hash ([string]$p.short_description);
    categories=@($p.categories | ForEach-Object { [int]$_.id } | Sort-Object);
    tags=@($p.tags | ForEach-Object { [int]$_.id } | Sort-Object);
    images=@($p.images | ForEach-Object { [int]$_.id } | Sort-Object);
    upsell_ids=@($p.upsell_ids | ForEach-Object { [int]$_ } | Sort-Object);
    cross_sell_ids=@($p.cross_sell_ids | ForEach-Object { [int]$_ } | Sort-Object);
    variations=@($p.variations | ForEach-Object { [int]$_ } | Sort-Object);
    grouped_products=@($p.grouped_products | ForEach-Object { [int]$_ } | Sort-Object);
    attributes_json=@($p.attributes | ConvertTo-Json -Depth 30 -Compress)
  }
  return (Get-Hash ($o | ConvertTo-Json -Depth 50 -Compress))
}

function Test-RecommendationReadback([string]$Html,$Target) {
  $bounds=Get-RecommendationBounds $Html
  if ($null -eq $bounds) { return [pscustomobject]@{ ok=$false; link_count=0; reason='recommendation_block_missing' } }
  $block=$Html.Substring([int]$bounds.start,[int]$bounds.end-[int]$bounds.start)
  $links=@([regex]::Matches($block,'<a\b[^>]*href=["''][^"'']+["''][^>]*>',[Text.RegularExpressions.RegexOptions]::IgnoreCase))
  $expected=@($Target.proposed_products)
  foreach ($r in $expected) {
    $url=[string]$r.permalink
    if ($block.IndexOf($url,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return [pscustomobject]@{ ok=$false; link_count=$links.Count; reason="missing_expected_link_$([int]$r.id)" }
    }
  }
  if ($links.Count -ne $expected.Count) {
    return [pscustomobject]@{ ok=$false; link_count=$links.Count; reason="link_count_$($links.Count)_expected_$($expected.Count)" }
  }
  $sizeFa=Convert-ToPersianDigits ([string]$Target.size_mm)
  if ($block -notmatch [regex]::Escape("$sizeFa میلی")) {
    return [pscustomobject]@{ ok=$false; link_count=$links.Count; reason='size_text_missing' }
  }
  if ($block -notmatch 'لوله\s*پلی.?اتیلن\s*هم.?سایز') {
    return [pscustomobject]@{ ok=$false; link_count=$links.Count; reason='human_pipe_copy_missing' }
  }
  return [pscustomobject]@{ ok=$true; link_count=$links.Count; reason='ok' }
}

$categoryQuery=[Uri]::EscapeDataString($categorySlug)
$categoryMatches=@(Invoke-K20 'GET' "wp-json/wc/v3/products/categories?slug=$categoryQuery&per_page=100")
if ($categoryMatches.Count -ne 1) { Fail "Expected exactly one product category for slug '$categorySlug'; got $($categoryMatches.Count)." }
$category=$categoryMatches[0]
$categoryId=[int]$category.id

$products=@(Get-AllProducts)
if ($products.Count -eq 0) { Fail 'No published WooCommerce products were returned.' }
$byId=@{}; foreach ($p in $products) { $byId[[int]$p.id]=$p }

$targets=@()
foreach ($p in $products) {
  $inCategory=$false
  foreach ($c in @($p.categories)) { if ([int]$c.id -eq $categoryId) { $inCategory=$true; break } }
  if (-not $inCategory) { continue }

  $size=Get-SingleNominalMm ([string]$p.name)
  $pipeCandidates=@()
  $familyCandidates=@{}
  if ($null -ne $size) {
    foreach ($candidate in $products) {
      if ([int]$candidate.id -eq [int]$p.id) { continue }
      if ([string]$candidate.catalog_visibility -eq 'hidden') { continue }
      $isTargetCategory=$false
      foreach ($cc in @($candidate.categories)) { if ([int]$cc.id -eq $categoryId) { $isTargetCategory=$true; break } }
      if ($isTargetCategory) { continue }
      if ((Normalize-Digits ([string]$candidate.name)) -match 'درپوش') { continue }

      $candidateSize=Get-SingleNominalMm ([string]$candidate.name)
      if ($null -eq $candidateSize -or [int]$candidateSize -ne [int]$size) { continue }
      $family=Get-RelatedFamily ([string]$candidate.name)
      if (-not $family) { continue }
      $row=[pscustomobject][ordered]@{
        id=[int]$candidate.id; name=[string]$candidate.name; permalink=[string]$candidate.permalink;
        family=$family; stock_status=[string]$candidate.stock_status
      }
      if ($family -eq 'pipe') {
        $pipeCandidates += $row
      } else {
        if (-not $familyCandidates.ContainsKey($family)) { $familyCandidates[$family]=@() }
        $familyCandidates[$family] += $row
      }
    }
  }

  $pipeCandidates=@($pipeCandidates | Sort-Object @{Expression={ if ($_.stock_status -eq 'instock') {0} else {1} }},id)
  $selected=@($pipeCandidates | Select-Object -First 2)
  foreach ($family in @('coupling','elbow','tee','valve','clamp','fitting')) {
    if ($selected.Count -ge $maxRelated) { break }
    if (-not $familyCandidates.ContainsKey($family)) { continue }
    $best=@($familyCandidates[$family] | Sort-Object @{Expression={ if ($_.stock_status -eq 'instock') {0} else {1} }},id | Select-Object -First 1)
    if ($best.Count -gt 0) { $selected += $best[0] }
  }
  if ($selected.Count -gt $maxRelated) { $selected=@($selected | Select-Object -First $maxRelated) }

  $bounds=Get-RecommendationBounds ([string]$p.description)
  $targets += [pscustomobject][ordered]@{
    id=[int]$p.id; name=[string]$p.name; size_mm=$size;
    existing_recommendation_block=($null -ne $bounds);
    existing_marker=if ($bounds) { [string]$bounds.marker } else { $null };
    same_size_pipe_count=$pipeCandidates.Count;
    proposed_products=@($selected | ForEach-Object { [pscustomobject][ordered]@{ id=$_.id; name=$_.name; permalink=$_.permalink; family=$_.family; reason="same_size_$size`mm" } })
  }
}

if ($targets.Count -eq 0) { Fail "No published products found in category '$categorySlug' ($categoryId)." }
$unparsed=@($targets | Where-Object { $null -eq $_.size_mm })
$missingPipe=@($targets | Where-Object { [int]$_.same_size_pipe_count -lt 1 })
$tooFew=@($targets | Where-Object { @($_.proposed_products).Count -lt 1 })

if ($mode -eq 'apply_description' -and $unparsed.Count -gt 0) { Fail "Refusing apply: unparsed target IDs $((@($unparsed.id)-join ','))" }
if ($mode -eq 'apply_description' -and $missingPipe.Count -gt 0) { Fail "Refusing apply: no same-size polyethylene pipe for target IDs $((@($missingPipe.id)-join ','))" }
if ($mode -eq 'apply_description' -and $tooFew.Count -gt 0) { Fail "Refusing apply: no recommendations for target IDs $((@($tooFew.id)-join ','))" }

$changes=@()
if ($mode -eq 'apply_description') {
  foreach ($t in $targets) {
    $id=[int]$t.id
    $before=$byId[$id]
    $beforeIntegrity=Get-IntegritySnapshot $before
    $beforeDescription=[string]$before.description
    $beforeOutsideText=Get-PlainText (Remove-RecommendationBlock $beforeDescription)
    $desiredDescription=Set-RecommendationBlock $beforeDescription (Build-RecommendationBlock $t)

    $already=Test-RecommendationReadback $beforeDescription $t
    if ($already.ok) {
      $changes += [pscustomobject][ordered]@{
        id=$id; name=$t.name; changed=$false; semantic_verified=$true; integrity_unchanged=$true; outside_text_unchanged=$true;
        recommendation_count=@($t.proposed_products).Count; readback_reason='already_current'
      }
      continue
    }

    $null=Invoke-K20 'PUT' "wp-json/wc/v3/products/$id" ([ordered]@{ description=$desiredDescription })
    $after=Invoke-K20 'GET' "wp-json/wc/v3/products/$id"
    $readback=Test-RecommendationReadback ([string]$after.description) $t
    $integrityUnchanged=((Get-IntegritySnapshot $after) -eq $beforeIntegrity)
    $afterOutsideText=Get-PlainText (Remove-RecommendationBlock ([string]$after.description))
    $outsideTextUnchanged=($afterOutsideText -ceq $beforeOutsideText)

    if (-not $readback.ok) { Fail "Recommendation readback failed for product $id: $($readback.reason)" }
    if (-not $integrityUnchanged) { Fail "Non-description integrity mismatch for product $id" }
    if (-not $outsideTextUnchanged) { Fail "Non-recommendation text changed for product $id" }

    $changes += [pscustomobject][ordered]@{
      id=$id; name=$t.name; changed=$true; semantic_verified=$true; integrity_unchanged=$integrityUnchanged; outside_text_unchanged=$outsideTextUnchanged;
      recommendation_count=@($t.proposed_products).Count; readback_reason=$readback.reason
    }
  }
}

$changedCount=@($changes | Where-Object { $_.changed }).Count
$semanticVerifiedCount=@($changes | Where-Object { $_.semantic_verified }).Count
$integrityVerifiedCount=@($changes | Where-Object { $_.integrity_unchanged }).Count
$outsideVerifiedCount=@($changes | Where-Object { $_.outside_text_unchanged }).Count

$record=[ordered]@{
  ok=$true; mode=$mode; executed_at_utc=[DateTime]::UtcNow.ToString('o');
  category=[ordered]@{ id=$categoryId; name=[string]$category.name; slug=[string]$category.slug };
  published_product_count=$products.Count; target_count=$targets.Count;
  unparsed_target_count=$unparsed.Count; missing_same_size_pipe_count=$missingPipe.Count; empty_recommendation_count=$tooFew.Count;
  rules=[ordered]@{
    target='all published products in product category polyethylene-end-cap';
    size='single exact nominal size parsed from explicit millimetre value, with conservative inch fallback';
    pipe='at least one published visible polyethylene pipe of the exact same nominal size is mandatory';
    related='up to two same-size polyethylene pipes, then one same-size product per useful fitting family';
    copy='human-written Persian block tailored to the exact nominal line size';
    mutation='description field only';
    protected='price, regular_price, sale_price, stock, SKU, name, slug, short description, categories, tags, images, attributes, upsells and cross-sells are never sent and are readback-protected'
  };
  unparsed_targets=@($unparsed | Select-Object id,name);
  missing_pipe_targets=@($missingPipe | Select-Object id,name,size_mm);
  targets=@($targets);
  changes=@($changes);
  changed_count=$changedCount; semantic_verified_count=$semanticVerifiedCount; integrity_verified_count=$integrityVerifiedCount; outside_text_verified_count=$outsideVerifiedCount
}

$dir=Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$record | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "K20_END_CAP_RECOMMENDATIONS_OK mode=$mode category=$categoryId targets=$($targets.Count) unparsed=$($unparsed.Count) missingPipe=$($missingPipe.Count) changed=$changedCount output=$OutputPath"
