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
if ([string]::IsNullOrWhiteSpace($base) -or [string]::IsNullOrWhiteSpace($user) -or [string]::IsNullOrWhiteSpace($pass)) { Fail 'Required WordPress secrets are missing.' }
$base = $base.TrimEnd('/')

$request = Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
$mode = if ($request.mode) { [string]$request.mode } else { 'audit' }
if ($mode -notin @('audit','apply_description')) { Fail "Unsupported mode: $mode" }

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
  return $all
}

function Normalize-Digits([string]$Text) {
  if ($null -eq $Text) { return '' }
  $s = $Text
  $from = @('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹','٠','١','٢','٣','٤','٥','٦','٧','٨','٩')
  $to   = @('0','1','2','3','4','5','6','7','8','9','0','1','2','3','4','5','6','7','8','9')
  for ($i=0; $i -lt $from.Count; $i++) { $s = $s.Replace($from[$i], $to[$i]) }
  return $s.Replace('٫','.').Replace('٬',',').Replace('‌',' ')
}

function Normalize-InchText([string]$Text) {
  $s = Normalize-Digits $Text
  $s = $s.Replace('½',' 1/2').Replace('¼',' 1/4').Replace('¾',' 3/4')
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*(?:و|\.|\s)\s*1\s*/\s*2(?!\d)', {
    param($m); $w=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture); (($w+0.5).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture))
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*(?:و|\.|\s)\s*1\s*/\s*4(?!\d)', {
    param($m); $w=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture); (($w+0.25).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture))
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*(?:و|\.|\s)\s*3\s*/\s*4(?!\d)', {
    param($m); $w=[double]::Parse($m.Groups['w'].Value,[Globalization.CultureInfo]::InvariantCulture); (($w+0.75).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture))
  })
  $s = [regex]::Replace($s, '(?<!\d)3\s*/\s*4(?!\d)', '0.75')
  $s = [regex]::Replace($s, '(?<!\d)1\s*/\s*2(?!\d)', '0.5')
  $s = [regex]::Replace($s, '(?<!\d)1\s*/\s*4(?!\d)', '0.25')
  return $s
}

function Format-Size([double]$Value) { return $Value.ToString('0.##',[Globalization.CultureInfo]::InvariantCulture) }
$mmToInch = @{ 20='0.5'; 25='0.75'; 32='1'; 40='1.25'; 50='1.5'; 63='2'; 75='2.5'; 90='3'; 110='4'; 125='4.5' }

function Get-ExplicitInchSize([string]$Name) {
  $s = Normalize-InchText $Name
  $m = [regex]::Match($s, '(?<!\d)(?<s>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)')
  if (-not $m.Success) { return $null }
  $v = [double]::Parse($m.Groups['s'].Value,[Globalization.CultureInfo]::InvariantCulture)
  if ($v -lt 0.25 -or $v -gt 6) { return $null }
  return (Format-Size $v)
}

function Get-ClampOutletSize([string]$Name) {
  $s = Normalize-InchText $Name
  $m = [regex]::Match($s, '(?<!\d)(?<a>\d+(?:\.\d+)?)\s*(?:x|X|×|\*)\s*(?<b>\d+(?:\.\d+)?)(?!\d)')
  if ($m.Success) {
    $a=[double]::Parse($m.Groups['a'].Value,[Globalization.CultureInfo]::InvariantCulture)
    $b=[double]::Parse($m.Groups['b'].Value,[Globalization.CultureInfo]::InvariantCulture)
    $small=[Math]::Min($a,$b)
    if ($small -le 6) { return (Format-Size $small) }
    $smallMm=[int][Math]::Round($small)
    if ($mmToInch.ContainsKey($smallMm)) { return [string]$mmToInch[$smallMm] }
  }
  return (Get-ExplicitInchSize $Name)
}

function Get-BallValveSize([string]$Name) { return (Get-ExplicitInchSize $Name) }
function Get-ProductSize([string]$Name) { return (Get-ExplicitInchSize $Name) }

function Is-ClampTarget($Product,[hashtable]$CategoryNames) {
  if ([string]$Product.name -match 'کمربند') { return $true }
  foreach ($c in @($Product.categories)) { $cid=[int]$c.id; if ($CategoryNames.ContainsKey($cid) -and $CategoryNames[$cid] -match 'کمربند') { return $true } }
  return $false
}
function Is-BallValveTarget($Product,[hashtable]$CategoryNames) {
  if ([string]$Product.name -match 'شیر\s*توپی') { return $true }
  foreach ($c in @($Product.categories)) { $cid=[int]$c.id; if ($CategoryNames.ContainsKey($cid) -and $CategoryNames[$cid] -match 'شیر\s*توپی') { return $true } }
  return $false
}
function Is-CompatibleAccessory([string]$Name) {
  $n=Normalize-Digits $Name
  if ($n -match 'کمربند' -or $n -match 'لوله\s*نخدار') { return $false }
  return ($n -match 'شیر|سر\s*(?:شیلنگ|شلنگ)|اتصال|رابط|مغزی|بوشن|زانویی|سه\s*راه|سه‌راه|تبدیل|فلنج|کوپل|درپوش|دنباله|سرپیچ|فیلتر|سوپاپ|واسطه')
}
function Is-ThreadedHose([string]$Name) { return ((Normalize-Digits $Name) -match 'لوله\s*نخدار') }

function Get-RecommendationBounds([string]$Html) {
  if ([string]::IsNullOrWhiteSpace($Html)) { return $null }
  $markers=@('محصولات مرتبط','محصولات پیشنهادی','محصولات مکمل','پیشنهادهای مرتبط','پیشنهاد خرید','برای تکمیل خرید','همراه این محصول','خرید همزمان')
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

function Build-RecommendationBlock($Target) {
  $size=[System.Net.WebUtility]::HtmlEncode([string]$Target.output_size_inch)
  $lines=@()
  foreach ($r in @($Target.proposed_products)) {
    $name=[System.Net.WebUtility]::HtmlEncode([string]$r.name)
    $url=[System.Net.WebUtility]::HtmlEncode([string]$r.permalink)
    $lines += ('<li><a style="color:#176b3a;font-weight:700" href="{0}">{1}</a></li>' -f $url,$name)
  }
  $list=$lines -join "`n"
  return @"
<h2 style="font-size:24px;line-height:1.8;color:#176b3a;margin:34px 0 14px;border-right:5px solid #5d9a68;padding-right:12px">محصولات مرتبط برای تکمیل انتخاب</h2>
<div style="background:#f7fbf8;border:1px solid #dbe8df;border-radius:16px;padding:17px;margin:15px 0">
<p>این پیشنهادها بر اساس سایز خروجی $size اینچ این محصول انتخاب شده‌اند؛ اتصالات و تجهیزات هم‌سایز هستند و لوله نخدار، در صورت وجود در فروشگاه، نیم‌سایز بزرگ‌تر پیشنهاد شده است.</p>
<ul style="padding-right:22px">
$list
</ul>
</div>
"@
}

function Set-RecommendationBlock([string]$Html,[string]$Block) {
  if ($null -eq $Html) { $Html='' }
  $bounds=Get-RecommendationBounds $Html
  if ($null -ne $bounds) { return $Html.Substring(0,[int]$bounds.start)+$Block+$Html.Substring([int]$bounds.end) }
  foreach ($marker in @('پرسش‌های پرتکرار','پرسش های پرتکرار','سوالات متداول','سؤالات متداول')) {
    $idx=$Html.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
    if ($idx -ge 0) { $h2=$Html.LastIndexOf('<h2',$idx,[StringComparison]::OrdinalIgnoreCase); if ($h2 -ge 0) { return $Html.Insert($h2,$Block) } }
  }
  return ($Html.TrimEnd()+"`n"+$Block)
}

function Get-Hash([string]$Text) {
  if ($null -eq $Text) { $Text='' }
  $sha=[Security.Cryptography.SHA256]::Create()
  try { $bytes=[Text.Encoding]::UTF8.GetBytes($Text); return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() }
  finally { $sha.Dispose() }
}

function Get-IntegritySnapshot($p) {
  $o=[ordered]@{
    id=[int]$p.id; name=[string]$p.name; slug=[string]$p.slug; status=[string]$p.status; sku=[string]$p.sku;
    price=[string]$p.price; regular_price=[string]$p.regular_price; sale_price=[string]$p.sale_price;
    manage_stock=[bool]$p.manage_stock; stock_quantity=$p.stock_quantity; stock_status=[string]$p.stock_status;
    categories=@($p.categories | ForEach-Object { [int]$_.id } | Sort-Object);
    tags=@($p.tags | ForEach-Object { [int]$_.id } | Sort-Object);
    images=@($p.images | ForEach-Object { [int]$_.id } | Sort-Object)
  }
  return (Get-Hash ($o | ConvertTo-Json -Depth 20 -Compress))
}

$products=@(Get-AllProducts)
if ($products.Count -eq 0) { Fail 'No published WooCommerce products were returned.' }
$categoryNames=@{}; foreach ($p in $products) { foreach ($c in @($p.categories)) { $categoryNames[[int]$c.id]=[string]$c.name } }
$byId=@{}; foreach ($p in $products) { $byId[[int]$p.id]=$p }

$targets=@()
foreach ($p in $products) {
  $kind=$null; $size=$null
  if (Is-ClampTarget $p $categoryNames) { $kind='clamp'; $size=Get-ClampOutletSize ([string]$p.name) }
  elseif (Is-BallValveTarget $p $categoryNames) { $kind='ball_valve'; $size=Get-BallValveSize ([string]$p.name) }
  if (-not $kind) { continue }

  $proposed=@()
  if ($size) {
    foreach ($candidate in $products) {
      if ([int]$candidate.id -eq [int]$p.id -or [string]$candidate.catalog_visibility -eq 'hidden') { continue }
      $candidateSize=Get-ProductSize ([string]$candidate.name)
      if ($candidateSize -and $candidateSize -eq $size -and (Is-CompatibleAccessory ([string]$candidate.name))) {
        $proposed += [pscustomobject][ordered]@{ id=[int]$candidate.id; name=[string]$candidate.name; permalink=[string]$candidate.permalink; reason="same_output_$size" }
      }
    }
    $hoseSize=Format-Size(([double]::Parse($size,[Globalization.CultureInfo]::InvariantCulture))+0.5)
    foreach ($candidate in $products) {
      if ([int]$candidate.id -eq [int]$p.id -or [string]$candidate.catalog_visibility -eq 'hidden') { continue }
      if (-not (Is-ThreadedHose ([string]$candidate.name))) { continue }
      $candidateSize=Get-ProductSize ([string]$candidate.name)
      if ($candidateSize -and $candidateSize -eq $hoseSize) {
        $proposed += [pscustomobject][ordered]@{ id=[int]$candidate.id; name=[string]$candidate.name; permalink=[string]$candidate.permalink; reason="threaded_hose_plus_0.5_$hoseSize" }
      }
    }
  }
  $proposed=@($proposed | Sort-Object id -Unique)
  $bounds=Get-RecommendationBounds ([string]$p.description)
  $marker=$null; if ($bounds) { $marker=[string]$bounds.marker }
  $targets += [pscustomobject][ordered]@{
    id=[int]$p.id; name=[string]$p.name; kind=$kind; output_size_inch=$size;
    existing_recommendation_block=($null -ne $bounds); existing_marker=$marker; proposed_products=@($proposed)
  }
}

$unparsed=@($targets | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.output_size_inch) })
$emptyCandidates=@($targets | Where-Object { @($_.proposed_products).Count -eq 0 })
if ($mode -eq 'apply_description' -and $unparsed.Count -gt 0) { Fail "Refusing apply: unparsed target IDs $((@($unparsed.id)-join ','))" }
if ($mode -eq 'apply_description' -and $emptyCandidates.Count -gt 0) { Fail "Refusing apply: no compatible recommendation candidates for target IDs $((@($emptyCandidates.id)-join ','))" }

$changes=@()
if ($mode -eq 'apply_description') {
  foreach ($t in $targets) {
    $id=[int]$t.id; $before=$byId[$id]
    $beforeIntegrity=Get-IntegritySnapshot $before
    $beforeDescription=[string]$before.description
    $desiredDescription=Set-RecommendationBlock $beforeDescription (Build-RecommendationBlock $t)
    $beforeHash=Get-Hash $beforeDescription; $desiredHash=Get-Hash $desiredDescription
    if ($beforeHash -eq $desiredHash) {
      $changes += [pscustomobject][ordered]@{ id=$id; name=$t.name; changed=$false; verified=$true; integrity_unchanged=$true; before_description_sha256=$beforeHash; after_description_sha256=$beforeHash; recommendation_count=@($t.proposed_products).Count }
      continue
    }
    $null=Invoke-K20 'PUT' "wp-json/wc/v3/products/$id" ([ordered]@{ description=$desiredDescription })
    $after=Invoke-K20 'GET' "wp-json/wc/v3/products/$id"
    $afterDescription=[string]$after.description; $afterHash=Get-Hash $afterDescription
    $verified=($afterDescription -ceq $desiredDescription)
    $integrityUnchanged=((Get-IntegritySnapshot $after) -eq $beforeIntegrity)
    if (-not $verified) { Fail "Description readback mismatch for product $id" }
    if (-not $integrityUnchanged) { Fail "Non-description integrity mismatch for product $id" }
    $changes += [pscustomobject][ordered]@{ id=$id; name=$t.name; changed=$true; verified=$verified; integrity_unchanged=$integrityUnchanged; before_description_sha256=$beforeHash; after_description_sha256=$afterHash; recommendation_count=@($t.proposed_products).Count }
  }
}

$sizeGroups=@()
foreach ($size in @($targets.output_size_inch | Where-Object { $_ } | Sort-Object -Unique)) {
  $sample=@($targets | Where-Object { $_.output_size_inch -eq $size } | Select-Object -First 1)
  if ($sample.Count -gt 0) { $sizeGroups += [pscustomobject][ordered]@{ output_size_inch=$size; candidate_count=@($sample[0].proposed_products).Count; candidates=@($sample[0].proposed_products) } }
}

$clampCount=@($targets | Where-Object { $_.kind -eq 'clamp' }).Count
$ballCount=@($targets | Where-Object { $_.kind -eq 'ball_valve' }).Count
$existingCount=@($targets | Where-Object { $_.existing_recommendation_block }).Count
$changedCount=@($changes | Where-Object { $_.changed }).Count
$verifiedCount=@($changes | Where-Object { $_.verified }).Count
$integrityCount=@($changes | Where-Object { $_.integrity_unchanged }).Count

$record=[ordered]@{
  ok=$true; mode=$mode; executed_at_utc=[DateTime]::UtcNow.ToString('o'); published_product_count=$products.Count; target_count=$targets.Count;
  clamp_count=$clampCount; ball_valve_count=$ballCount; unparsed_target_count=$unparsed.Count; empty_candidate_target_count=$emptyCandidates.Count; existing_recommendation_block_count=$existingCount;
  rules=[ordered]@{
    clamp='smaller stated clamp size is outlet; millimetre-only outlets use validated PE nominal mapping';
    ball_valve='explicit normalized inch size is outlet, including mixed fractions';
    same_size='published visible compatible accessories with exact outlet size';
    threaded_hose='published visible threaded hose at outlet + 0.5 inch';
    mutation='description field only';
    protected='price, regular_price, sale_price, stock, SKU, name, slug, categories, tags and images are readback-protected and never sent in the write payload'
  };
  unparsed_targets=@($unparsed | Select-Object id,name,kind); empty_candidate_targets=@($emptyCandidates | Select-Object id,name,kind,output_size_inch);
  size_groups=@($sizeGroups); targets=@($targets); changes=@($changes); changed_count=$changedCount; verified_count=$verifiedCount; integrity_verified_count=$integrityCount
}

$dir=Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$record | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "K20_RECOMMENDATION_SYNC_OK mode=$mode targets=$($targets.Count) unparsed=$($unparsed.Count) empty=$($emptyCandidates.Count) changed=$changedCount output=$OutputPath"
