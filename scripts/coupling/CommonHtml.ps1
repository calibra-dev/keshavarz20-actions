function Get-RecommendationBounds([string]$Html) {
  if ([string]::IsNullOrWhiteSpace($Html)) { return $null }
  $markers = @(
    'قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن','قطعات پیشنهادی برای تکمیل خط پلی اتیلن',
    'قطعات پیشنهادی برای زانو پلی‌اتیلن','قطعات پیشنهادی برای زانو پلی اتیلن',
    'لوازم پیشنهادی برای زانو پلی‌اتیلن','لوازم پیشنهادی برای زانو پلی اتیلن',
    'قطعات پیشنهادی برای سه‌راه مساوی پلی‌اتیلن','قطعات پیشنهادی برای سه راه مساوی پلی اتیلن',
    'قطعات پیشنهادی برای سه‌راه تبدیل پلی‌اتیلن','قطعات پیشنهادی برای سه راه تبدیل پلی اتیلن',
    'لوازم پیشنهادی برای سه‌راه ماده پلی‌اتیلن','لوازم پیشنهادی برای سه راه ماده پلی اتیلن',
    'لوازم پیشنهادی برای سه‌راه نر پلی‌اتیلن','لوازم پیشنهادی برای سه راه نر پلی اتیلن',
    'لوازم پیشنهادی برای اتصال نر پلی‌اتیلن','لوازم پیشنهادی برای اتصال نر پلی اتیلن',
    'لوازم پیشنهادی برای اتصال ماده پلی‌اتیلن','لوازم پیشنهادی برای اتصال ماده پلی اتیلن',
    'لوازم پیشنهادی برای اتصال فلنج‌دار پلی‌اتیلن','لوازم پیشنهادی برای اتصال فلنج دار پلی اتیلن',
    'لوازم پیشنهادی برای اتصال فلنچ‌دار پلی‌اتیلن','لوازم پیشنهادی برای اتصال فلنچ دار پلی اتیلن',
    'محصولات مرتبط','محصولات پیشنهادی','محصولات مکمل','پیشنهادهای مرتبط',
    'پیشنهاد خرید','برای تکمیل خرید','همراه این محصول','خرید همزمان'
  )
  $bestIndex = -1
  $bestMarker = $null
  foreach ($marker in $markers) {
    $index = $Html.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
    if ($index -ge 0 -and ($bestIndex -lt 0 -or $index -lt $bestIndex)) {
      $bestIndex = $index
      $bestMarker = $marker
    }
  }
  if ($bestIndex -lt 0) { return $null }
  $start = $Html.LastIndexOf('<h2',$bestIndex,[StringComparison]::OrdinalIgnoreCase)
  if ($start -lt 0) { return $null }
  $end = $Html.IndexOf('<h2',$bestIndex+$bestMarker.Length,[StringComparison]::OrdinalIgnoreCase)
  if ($end -lt 0) { $end = $Html.Length }
  return [pscustomobject]@{start=$start;end=$end;marker=$bestMarker}
}

function Remove-RecommendationBlock([string]$Html) {
  if ($null -eq $Html) { return '' }
  $bounds = Get-RecommendationBounds $Html
  if ($null -eq $bounds) { return $Html }
  return $Html.Substring(0,[int]$bounds.start) + $Html.Substring([int]$bounds.end)
}

function Get-PlainText([string]$Html) {
  if ($null -eq $Html) { return '' }
  $text = [regex]::Replace($Html,'<[^>]+>',' ')
  $text = [Net.WebUtility]::HtmlDecode($text)
  return ([regex]::Replace($text,'\s+',' ')).Trim()
}

function Set-RecommendationBlock([string]$Html,[string]$Block) {
  if ($null -eq $Html) { $Html = '' }
  $bounds = Get-RecommendationBounds $Html
  if ($null -ne $bounds) {
    return $Html.Substring(0,[int]$bounds.start) + $Block + $Html.Substring([int]$bounds.end)
  }
  foreach ($marker in @('پرسش‌های پرتکرار','پرسش های پرتکرار','سوالات متداول','سؤالات متداول')) {
    $index = $Html.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
    if ($index -ge 0) {
      $heading = $Html.LastIndexOf('<h2',$index,[StringComparison]::OrdinalIgnoreCase)
      if ($heading -ge 0) { return $Html.Insert($heading,$Block) }
    }
  }
  return $Html.TrimEnd() + "`n" + $Block
}

function Get-Hash([string]$Text) {
  if ($null -eq $Text) { $Text = '' }
  $sha = [Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-','').ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Get-IntegritySnapshot($Product) {
  $snapshot = [ordered]@{
    id = [int]$Product.id
    name = [string]$Product.name
    slug = [string]$Product.slug
    status = [string]$Product.status
    type = [string]$Product.type
    sku = [string]$Product.sku
    price = [string]$Product.price
    regular_price = [string]$Product.regular_price
    sale_price = [string]$Product.sale_price
    manage_stock = [bool]$Product.manage_stock
    stock_quantity = $Product.stock_quantity
    stock_status = [string]$Product.stock_status
    backorders = [string]$Product.backorders
    short_description_sha256 = Get-Hash ([string]$Product.short_description)
    categories = @($Product.categories | ForEach-Object {[int]$_.id} | Sort-Object)
    tags = @($Product.tags | ForEach-Object {[int]$_.id} | Sort-Object)
    images = @($Product.images | ForEach-Object {[int]$_.id} | Sort-Object)
    upsell_ids = @($Product.upsell_ids | ForEach-Object {[int]$_} | Sort-Object)
    cross_sell_ids = @($Product.cross_sell_ids | ForEach-Object {[int]$_} | Sort-Object)
    attributes_json = ($Product.attributes | ConvertTo-Json -Depth 30 -Compress)
  }
  return Get-Hash ($snapshot | ConvertTo-Json -Depth 50 -Compress)
}
