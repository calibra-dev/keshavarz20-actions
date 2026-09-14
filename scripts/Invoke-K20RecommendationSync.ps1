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
  for ($i = 0; $i -lt $from.Count; $i++) { $s = $s.Replace($from[$i], $to[$i]) }
  $s = $s.Replace('٫','.').Replace('٬',',').Replace('‌',' ')
  $s = [regex]::Replace($s, '(?<!\d)4\s*[- ]?1\s*/\s*2(?!\d)', '4.5')
  $s = [regex]::Replace($s, '(?<!\d)3\s*[- ]?1\s*/\s*2(?!\d)', '3.5')
  $s = [regex]::Replace($s, '(?<!\d)2\s*[- ]?1\s*/\s*2(?!\d)', '2.5')
  $s = [regex]::Replace($s, '(?<!\d)1\s*[- ]?1\s*/\s*2(?!\d)', '1.5')
  $s = [regex]::Replace($s, '(?<!\d)3\s*/\s*4(?!\d)', '0.75')
  $s = [regex]::Replace($s, '(?<!\d)1\s*/\s*2(?!\d)', '0.5')
  return $s
}

function Format-Size([double]$Value) {
  return $Value.ToString('0.##', [Globalization.CultureInfo]::InvariantCulture)
}

function Get-ClampOutletSize([string]$Name) {
  $s = Normalize-Digits $Name
  $m = [regex]::Match($s, '(?<!\d)(?<a>\d+(?:\.\d+)?)\s*(?:x|X|×|\*)\s*(?<b>\d+(?:\.\d+)?)(?!\d)')
  if (-not $m.Success) { return $null }
  $a = [double]::Parse($m.Groups['a'].Value, [Globalization.CultureInfo]::InvariantCulture)
  $b = [double]::Parse($m.Groups['b'].Value, [Globalization.CultureInfo]::InvariantCulture)
  $small = [Math]::Min($a, $b)
  if ($small -lt 0.5 -or $small -gt 6) { return $null }
  return (Format-Size $small)
}

function Get-ExplicitInchSize([string]$Name) {
  $s = Normalize-Digits $Name
  $matches = [regex]::Matches($s, '(?<!\d)(?<s>0\.5|0\.75|1(?:\.5)?|2(?:\.5)?|3(?:\.5)?|4(?:\.5)?|5|6)\s*(?:اینچ|inch|in\b|"|″)')
  if ($matches.Count -gt 0) { return $matches[0].Groups['s'].Value }
  return $null
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
    if ($CategoryNames.ContainsKey([int]$c.id) -and $CategoryNames[[int]$c.id] -match 'کمربند') { return $true }
  }
  return $false
}

function Is-BallValveTarget($Product, [hashtable]$CategoryNames) {
  $name = [string]$Product.name
  if ($name -match 'شیر\s*توپی') { return $true }
  foreach ($c in @($Product.categories)) {
    if ($CategoryNames.ContainsKey([int]$c.id) -and $CategoryNames[[int]$c.id] -match 'شیر\s*توپی') { return $true }
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

$products = @(Get-AllProducts)
if ($products.Count -eq 0) { Fail 'No published WooCommerce products were returned.' }

$categoryNames = @{}
foreach ($p in $products) {
  foreach ($c in @($p.categories)) {
    $categoryNames[[int]$c.id] = [string]$c.name
  }
}

$byId = @{}
foreach ($p in $products) { $byId[[int]$p.id] = $p }

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
    if ($byId.ContainsKey([int]$id)) { $currentUpsellNames += [string]$byId[[int]$id].name }
  }
  $currentCrossNames = @()
  foreach ($id in @($p.cross_sell_ids)) {
    if ($byId.ContainsKey([int]$id)) { $currentCrossNames += [string]$byId[[int]$id].name }
  }

  $proposed = @()
  $reasonRows = @()
  if ($size) {
    foreach ($candidate in $products) {
      if ([int]$candidate.id -eq [int]$p.id) { continue }
      if ([string]$candidate.catalog_visibility -eq 'hidden') { continue }
      if ([string]$candidate.stock_status -eq 'outofstock') { continue }
      $candidateSize = Get-ProductSize ([string]$candidate.name)
      if ($candidateSize -and $candidateSize -eq $size -and (Is-CompatibleAccessory ([string]$candidate.name))) {
        $proposed += [int]$candidate.id
        $reasonRows += [ordered]@{ id=[int]$candidate.id; name=[string]$candidate.name; reason="same_output_$size" }
      }
    }

    $hoseSize = Format-Size(([double]::Parse($size, [Globalization.CultureInfo]::InvariantCulture)) + 0.5)
    foreach ($candidate in $products) {
      if ([int]$candidate.id -eq [int]$p.id) { continue }
      if ([string]$candidate.catalog_visibility -eq 'hidden') { continue }
      if ([string]$candidate.stock_status -eq 'outofstock') { continue }
      if (-not (Is-ThreadedHose ([string]$candidate.name))) { continue }
      $candidateSize = Get-ProductSize ([string]$candidate.name)
      if ($candidateSize -and $candidateSize -eq $hoseSize) {
        $proposed += [int]$candidate.id
        $reasonRows += [ordered]@{ id=[int]$candidate.id; name=[string]$candidate.name; reason="threaded_hose_plus_0.5_$hoseSize" }
      }
    }
  }
  $proposed = @($proposed | Sort-Object -Unique)
  $reasonRows = @($reasonRows | Sort-Object id -Unique)

  $targets += [ordered]@{
    id = [int]$p.id
    name = [string]$p.name
    kind = $kind
    output_size_inch = $size
    categories = @($p.categories | ForEach-Object { [ordered]@{ id=[int]$_.id; name=[string]$_.name } })
    current_upsell_ids = @($p.upsell_ids | ForEach-Object { [int]$_ })
    current_upsell_names = @($currentUpsellNames)
    current_cross_sell_ids = @($p.cross_sell_ids | ForEach-Object { [int]$_ })
    current_cross_sell_names = @($currentCrossNames)
    proposed_upsell_ids = @($proposed)
    proposed_products = @($reasonRows)
  }
}

$unparsed = @($targets | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.output_size_inch) })
if ($mode -eq 'apply' -and $unparsed.Count -gt 0) {
  $ids = ($unparsed | ForEach-Object { $_.id }) -join ','
  Fail "Refusing apply because output size could not be parsed for target IDs: $ids"
}

$changes = @()
if ($mode -eq 'apply') {
  foreach ($t in $targets) {
    $id = [int]$t.id
    $desired = @($t.proposed_upsell_ids | ForEach-Object { [int]$_ })
    $before = @($t.current_upsell_ids | ForEach-Object { [int]$_ })
    $same = (($before -join ',') -eq ($desired -join ','))
    if ($same) {
      $changes += [ordered]@{ id=$id; name=$t.name; changed=$false; verified=$true; before=$before; after=$before }
      continue
    }

    $body = [ordered]@{ upsell_ids = $desired }
    $null = Invoke-K20 'PUT' "wp-json/wc/v3/products/$id" $body
    $readback = Invoke-K20 'GET' "wp-json/wc/v3/products/$id"
    $after = @($readback.upsell_ids | ForEach-Object { [int]$_ })
    $verified = (($after -join ',') -eq ($desired -join ','))
    if (-not $verified) { Fail "Upsell readback mismatch for product $id" }
    $changes += [ordered]@{ id=$id; name=$t.name; changed=$true; verified=$verified; before=$before; after=$after }
  }
}

$record = [ordered]@{
  ok = $true
  mode = $mode
  executed_at_utc = [DateTime]::UtcNow.ToString('o')
  published_product_count = $products.Count
  target_count = $targets.Count
  unparsed_target_count = $unparsed.Count
  target_rules = [ordered]@{
    clamp = 'smaller number in clamp size is treated as outlet inch size'
    ball_valve = 'explicit inch size in product name is treated as outlet size'
    same_size = 'published visible in-stock irrigation accessories with the same outlet size'
    threaded_hose = 'threaded hose is recommended at outlet size + 0.5 inch'
    write_field = 'upsell_ids only'
  }
  targets = @($targets)
  changes = @($changes)
}

$dir = Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$record | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "K20_RECOMMENDATION_SYNC_OK mode=$mode targets=$($targets.Count) unparsed=$($unparsed.Count) output=$OutputPath"
