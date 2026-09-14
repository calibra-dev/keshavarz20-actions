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
if ($mode -notin @('audit','apply')) { Fail "Unsupported mode: $mode" }

$authText = "$user`:$pass"
$authValue = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($authText))
$headers = @{ Authorization = "Basic $authValue"; Accept = 'application/json' }

function Invoke-K20([string]$Method, [string]$Path, $Body = $null) {
  $uri = $base + '/' + $Path.TrimStart('/')
  $args = @{ Uri = $uri; Method = $Method; Headers = $headers; TimeoutSec = 180 }
  if ($null -ne $Body) {
    $args.ContentType = 'application/json; charset=utf-8'
    $args.Body = ($Body | ConvertTo-Json -Depth 100 -Compress)
  }
  return Invoke-RestMethod @args
}

function Get-AllProducts() {
  $all = @()
  for ($page = 1; $page -le 100; $page++) {
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
  for ($i = 0; $i -lt $from.Count; $i++) { $s = $s.Replace($from[$i], $to[$i]) }
  $s = $s.Replace('٫','.').Replace('٬',',').Replace('‌',' ')
  return $s
}

function Normalize-InchText([string]$Text) {
  $s = Normalize-Digits $Text
  $s = $s.Replace('½',' 1/2').Replace('¼',' 1/4').Replace('¾',' 3/4')

  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*[\. ]\s*1\s*/\s*2(?!\d)', {
    param($m)
    $w = [double]::Parse($m.Groups['w'].Value, [Globalization.CultureInfo]::InvariantCulture)
    return (($w + 0.5).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture))
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*[\. ]\s*1\s*/\s*4(?!\d)', {
    param($m)
    $w = [double]::Parse($m.Groups['w'].Value, [Globalization.CultureInfo]::InvariantCulture)
    return (($w + 0.25).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture))
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*[\. ]\s*3\s*/\s*4(?!\d)', {
    param($m)
    $w = [double]::Parse($m.Groups['w'].Value, [Globalization.CultureInfo]::InvariantCulture)
    return (($w + 0.75).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture))
  })

  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*و\s*1\s*/\s*2(?!\d)', {
    param($m)
    $w = [double]::Parse($m.Groups['w'].Value, [Globalization.CultureInfo]::InvariantCulture)
    return (($w + 0.5).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture))
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*و\s*1\s*/\s*4(?!\d)', {
    param($m)
    $w = [double]::Parse($m.Groups['w'].Value, [Globalization.CultureInfo]::InvariantCulture)
    return (($w + 0.25).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture))
  })
  $s = [regex]::Replace($s, '(?<!\d)(?<w>\d+)\s*و\s*3\s*/\s*4(?!\d)', {
    param($m)
    $w = [double]::Parse($m.Groups['w'].Value, [Globalization.CultureInfo]::InvariantCulture)
    return (($w + 0.75).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture))
  })

  $s = [regex]::Replace($s, '(?<!\d)3\s*/\s*4(?!\d)', '0.75')
  $s = [regex]::Replace($s, '(?<!\d)1\s*/\s*2(?!\d)', '0.5')
  $s = [regex]::Replace($s, '(?<!\d)1\s*/\s*4(?!\d)', '0.25')
  return $s
}

function Format-Size([double]$Value) {
  return $Value.ToString('0.##', [Globalization.CultureInfo]::InvariantCulture)
}

function Get-ExplicitInchSize([string]$Name) {
  $s = Normalize-InchText $Name
  $m = [regex]::Match($s, '(?<!\d)(?<s>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)')
  if (-not $m.Success) { return $null }
  $v = [double]::Parse($m.Groups['s'].Value, [Globalization.CultureInfo]::InvariantCulture)
  if ($v -lt 0.25 -or $v -gt 6) { return $null }
  return (Format-Size $v)
}

function Get-ClampOutletSize([string]$Name) {
  $s = Normalize-InchText $Name
  $m = [regex]::Match($s, '(?<!\d)(?<a>\d+(?:\.\d+)?)\s*(?:x|X|×|\*)\s*(?<b>\d+(?:\.\d+)?)(?!\d)')
  if ($m.Success) {
    $a = [double]::Parse($m.Groups['a'].Value, [Globalization.CultureInfo]::InvariantCulture)
    $b = [double]::Parse($m.Groups['b'].Value, [Globalization.CultureInfo]::InvariantCulture)
    $small = [Math]::Min($a, $b)
    if ($small -ge 0.25 -and $small -le 6) { return (Format-Size $small) }
  }
  return (Get-ExplicitInchSize $Name)
}

function Get-BallValveSize([string]$Name) {
  return (Get-ExplicitInchSize $Name)
}

function Get-ProductSize([string]$Name) {
  return (Get-ExplicitInchSize $Name)
}

function Is-ClampTarget($Product, [hashtable]$CategoryNames) {
  $name = [string]$Product.name
  if ($name -match 'کمربند') { return $true }
  foreach ($c in @($Product.categories)) {
    $cid = [int]($c.id)
    if ($CategoryNames.ContainsKey($cid) -and $CategoryNames[$cid] -match 'کمربند') { return $true }
  }
  return $false
}

function Is-BallValveTarget($Product, [hashtable]$CategoryNames) {
  $name = [string]$Product.name
  if ($name -match 'شیر\s*توپی') { return $true }
  foreach ($c in @($Product.categories)) {
    $cid = [int]($c.id)
    if ($CategoryNames.ContainsKey($cid) -and $CategoryNames[$cid] -match 'شیر\s*توپی') { return $true }
  }
  return $false
}

function Is-CompatibleAccessory([string]$Name) {
  $n = Normalize-Digits $Name
  if ($n -match 'کمربند') { return $false }
  if ($n -match 'لوله\s*نخدار') { return $false }
  return ($n -match 'شیر|سر\s*(?:شیلنگ|شلنگ)|اتصال|رابط|مغزی|بوشن|زانویی|سه\s*راه|سه‌راه|تبدیل|فلنج|کوپل|درپوش|دنباله|سرپیچ|فیلتر|سوپاپ|واسطه')
}

function Is-ThreadedHose([string]$Name) {
  return ((Normalize-Digits $Name) -match 'لوله\s*نخدار')
}

function Get-RecommendationDescriptionInfo([string]$Html) {
  if ([string]::IsNullOrWhiteSpace($Html)) {
    return [pscustomobject][ordered]@{ found=$false; marker=$null; snippet=$null }
  }
  $markers = @(
    'محصولات پیشنهادی','محصولات مرتبط','محصولات مکمل','پیشنهادهای مرتبط','پیشنهاد خرید',
    'پیشنهاد می‌کنیم','پیشنهاد می کنیم','محصول مکمل','برای تکمیل خرید','همراه این محصول','خرید همزمان'
  )
  foreach ($marker in $markers) {
    $idx = $Html.IndexOf($marker, [StringComparison]::OrdinalIgnoreCase)
    if ($idx -ge 0) {
      $start = [Math]::Max(0, $idx - 400)
      $len = [Math]::Min(2600, $Html.Length - $start)
      return [pscustomobject][ordered]@{
        found = $true
        marker = $marker
        snippet = $Html.Substring($start, $len)
      }
    }
  }
  return [pscustomobject][ordered]@{ found=$false; marker=$null; snippet=$null }
}

$products = @(Get-AllProducts)
if ($products.Count -eq 0) { Fail 'No published WooCommerce products were returned.' }

$categoryNames = @{}
foreach ($p in $products) {
  foreach ($c in @($p.categories)) { $categoryNames[[int]($c.id)] = [string]($c.name) }
}

$byId = @{}
foreach ($p in $products) { $byId[[int]($p.id)] = $p }

$targets = @()
foreach ($p in $products) {
  $kind = $null
  $size = $null
  if (Is-ClampTarget $p $categoryNames) {
    $kind = 'clamp'
    $size = Get-ClampOutletSize ([string]$p.name)
  } elseif (Is-BallValveTarget $p $categoryNames) {
    $kind = 'ball_valve'
    $size = Get-BallValveSize ([string]$p.name)
  }
  if (-not $kind) { continue }

  $currentUpsellNames = @()
  foreach ($id in @($p.upsell_ids)) {
    $iid = [int]$id
    if ($byId.ContainsKey($iid)) { $currentUpsellNames += [string]($byId[$iid].name) }
  }
  $currentCrossNames = @()
  foreach ($id in @($p.cross_sell_ids)) {
    $iid = [int]$id
    if ($byId.ContainsKey($iid)) { $currentCrossNames += [string]($byId[$iid].name) }
  }

  $proposed = @()
  $reasonRows = @()
  if ($size) {
    foreach ($candidate in $products) {
      if ([int]($candidate.id) -eq [int]($p.id)) { continue }
      if ([string]$candidate.catalog_visibility -eq 'hidden') { continue }
      if ([string]$candidate.stock_status -eq 'outofstock') { continue }
      $candidateSize = Get-ProductSize ([string]$candidate.name)
      if ($candidateSize -and $candidateSize -eq $size -and (Is-CompatibleAccessory ([string]$candidate.name))) {
        $cid = [int]($candidate.id)
        $proposed += $cid
        $reasonRows += [pscustomobject][ordered]@{ id=$cid; name=[string]$candidate.name; reason="same_output_$size" }
      }
    }

    $hoseSize = Format-Size(([double]::Parse($size, [Globalization.CultureInfo]::InvariantCulture)) + 0.5)
    foreach ($candidate in $products) {
      if ([int]($candidate.id) -eq [int]($p.id)) { continue }
      if ([string]$candidate.catalog_visibility -eq 'hidden') { continue }
      if ([string]$candidate.stock_status -eq 'outofstock') { continue }
      if (-not (Is-ThreadedHose ([string]$candidate.name))) { continue }
      $candidateSize = Get-ProductSize ([string]$candidate.name)
      if ($candidateSize -and $candidateSize -eq $hoseSize) {
        $cid = [int]($candidate.id)
        $proposed += $cid
        $reasonRows += [pscustomobject][ordered]@{ id=$cid; name=[string]$candidate.name; reason="threaded_hose_plus_0.5_$hoseSize" }
      }
    }
  }
  $proposed = @($proposed | Sort-Object -Unique)
  $reasonRows = @($reasonRows | Sort-Object -Property id -Unique)
  $descInfo = Get-RecommendationDescriptionInfo ([string]$p.description)

  $targets += [pscustomobject][ordered]@{
    id = [int]($p.id)
    name = [string]$p.name
    kind = $kind
    output_size_inch = $size
    categories = @($p.categories | ForEach-Object { [pscustomobject][ordered]@{ id=[int]($_.id); name=[string]$_.name } })
    current_upsell_ids = @($p.upsell_ids | ForEach-Object { [int]$_ })
    current_upsell_names = @($currentUpsellNames)
    current_cross_sell_ids = @($p.cross_sell_ids | ForEach-Object { [int]$_ })
    current_cross_sell_names = @($currentCrossNames)
    description_recommendation_found = [bool]$descInfo.found
    description_recommendation_marker = $descInfo.marker
    description_recommendation_snippet = $descInfo.snippet
    proposed_upsell_ids = @($proposed)
    proposed_products = @($reasonRows)
  }
}

$unparsed = @($targets | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.output_size_inch) })
$descriptionTargets = @($targets | Where-Object { $_.description_recommendation_found })

if ($mode -eq 'apply' -and $unparsed.Count -gt 0) {
  $ids = ($unparsed | ForEach-Object { $_.id }) -join ','
  Fail "Refusing apply because output size could not be parsed for target IDs: $ids"
}

$changes = @()
if ($mode -eq 'apply') {
  foreach ($t in $targets) {
    $id = [int]($t.id)
    $desired = @($t.proposed_upsell_ids | ForEach-Object { [int]$_ })
    $before = @($t.current_upsell_ids | ForEach-Object { [int]$_ })
    $same = (($before -join ',') -eq ($desired -join ','))
    if ($same) {
      $changes += [pscustomobject][ordered]@{ id=$id; name=$t.name; changed=$false; verified=$true; before=$before; after=$before }
      continue
    }

    $body = [ordered]@{ upsell_ids = $desired }
    $null = Invoke-K20 'PUT' "wp-json/wc/v3/products/$id" $body
    $readback = Invoke-K20 'GET' "wp-json/wc/v3/products/$id"
    $after = @($readback.upsell_ids | ForEach-Object { [int]$_ })
    $verified = (($after -join ',') -eq ($desired -join ','))
    if (-not $verified) { Fail "Upsell readback mismatch for product $id" }
    $changes += [pscustomobject][ordered]@{ id=$id; name=$t.name; changed=$true; verified=$verified; before=$before; after=$after }
  }
}

$record = [ordered]@{
  ok = $true
  mode = $mode
  executed_at_utc = [DateTime]::UtcNow.ToString('o')
  published_product_count = $products.Count
  target_count = $targets.Count
  unparsed_target_count = $unparsed.Count
  description_recommendation_target_count = $descriptionTargets.Count
  unparsed_targets = @($unparsed | ForEach-Object { [pscustomobject][ordered]@{ id=$_.id; name=$_.name; kind=$_.kind } })
  target_rules = [ordered]@{
    clamp = 'smaller number in clamp size is treated as outlet inch size; explicit inch size is fallback when no multiplication pair exists'
    ball_valve = 'normalized explicit inch size in product name is treated as outlet size, including mixed fractions'
    same_size = 'published visible in-stock irrigation accessories with the same outlet size'
    threaded_hose = 'threaded hose is recommended at outlet size + 0.5 inch'
    write_field = 'upsell_ids only in apply mode; descriptions are audited but not changed by this script version'
  }
  targets = @($targets)
  changes = @($changes)
}

$dir = Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$record | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "K20_RECOMMENDATION_SYNC_OK mode=$mode targets=$($targets.Count) unparsed=$($unparsed.Count) descriptionTargets=$($descriptionTargets.Count) output=$OutputPath"
