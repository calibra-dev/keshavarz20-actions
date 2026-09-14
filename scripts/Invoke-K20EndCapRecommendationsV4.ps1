param(
  [Parameter(Mandatory = $true)][string]$RequestPath,
  [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$sourcePath = Join-Path $PSScriptRoot 'Invoke-K20EndCapRecommendationsV3.ps1'
if (-not (Test-Path -LiteralPath $sourcePath)) { throw "Source script missing: $sourcePath" }

$source = Get-Content -Raw -LiteralPath $sourcePath

function Replace-FunctionBlock([string]$Text,[string]$StartMarker,[string]$EndMarker,[string]$Replacement) {
  $start = $Text.IndexOf($StartMarker,[StringComparison]::Ordinal)
  $end = $Text.IndexOf($EndMarker,[StringComparison]::Ordinal)
  if ($start -lt 0 -or $end -le $start) { throw "Could not locate patch boundaries: $StartMarker -> $EndMarker" }
  return $Text.Substring(0,$start) + $Replacement + $Text.Substring($end)
}

$fixedGetAllProducts = @'
function Get-AllProducts() {
  $all = @()
  for ($page=1; $page -le 100; $page++) {
    $response = Invoke-K20 'GET' "wp-json/wc/v3/products?per_page=100&page=$page&status=publish&orderby=id&order=asc"
    $items = @()
    foreach ($item in $response) { $items += $item }
    if ($items.Count -eq 0) { break }
    foreach ($item in $items) { $all += $item }
    if ($items.Count -lt 100) { break }
  }
  return $all
}

'@
$source = Replace-FunctionBlock $source 'function Get-AllProducts() {' 'function Normalize-Digits' $fixedGetAllProducts

$visibilityNeedle = "      if ([string]`$candidate.catalog_visibility -eq 'hidden') { continue }"
$visibilityReplacement = $visibilityNeedle + "`n      if ([string]`$candidate.permalink -match '__trashed') { continue }"
if (-not $source.Contains($visibilityNeedle)) { throw 'Could not locate candidate visibility guard.' }
$source = $source.Replace($visibilityNeedle,$visibilityReplacement)

$fixedBuildBlock = @'
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

  if ([int]$Target.same_size_pipe_count -gt 0) {
    $intro1="اگر این درپوش را برای بستن انتهای خط پلی‌اتیلن $sizeFa میلی‌متری انتخاب می‌کنید، لوله و قطعات کناری شبکه هم باید با همین سایز نامی هماهنگ باشند. پیشنهادهای زیر از محصولات واقعی فروشگاه و با تطبیق مستقیم سایز انتخاب شده‌اند تا هنگام تکمیل خط، قطعه نامرتبط یا تبدیل ناخواسته وارد انتخاب شما نشود."
    $intro2='لوله پلی‌اتیلن هم‌سایز در اولویت قرار گرفته است؛ بعد از آن فقط چند قطعه کاربردی هم‌سایز برای ادامه خط، تغییر مسیر، انشعاب یا کنترل جریان پیشنهاد شده‌اند.'
  } else {
    $intro1="این درپوش برای بستن انتهای خط پلی‌اتیلن $sizeFa میلی‌متری انتخاب می‌شود و برای هماهنگی شبکه، لوله اصلی نیز باید $sizeFa میلی‌متر باشد. در فهرست زیر فقط قطعات واقعی $sizeFa میلی‌متری موجود در کاتالوگ فروشگاه آمده‌اند؛ بنابراین گزینه‌ای با سایز متفاوت یا تبدیل به‌عنوان جایگزین پیشنهاد نشده است."
    $intro2="برای تکمیل همین خط، رابط، زانو، سه‌راه و شیر هم‌سایز را بر اساس نیاز مسیر انتخاب کنید. معیار اصلی در این بخش، هماهنگی واقعی سایز قطعات با خط $sizeFa میلی‌متری است."
  }

  return @"
<h2 style="font-size:24px;line-height:1.8;color:#176b3a;margin:34px 0 14px;border-right:5px solid #5d9a68;padding-right:12px">قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن $sizeFa میلی‌متر</h2>
<div style="background:#f7fbf8;border:1px solid #dbe8df;border-radius:16px;padding:17px;margin:15px 0">
<p>$intro1</p>
<p>$intro2</p>
<ul style="padding-right:22px;margin:10px 0">
$list
</ul>
<p style="margin:12px 0 0"><strong>قبل از خرید:</strong> عدد سایز روی لوله یا اتصال فعلی را با $sizeFa میلی‌متر تطبیق دهید. اگر سایز خط متفاوت است، درپوش و قطعات مکمل را بر اساس همان سایز انتخاب کنید.</p>
</div>
"@
}

'@
$source = Replace-FunctionBlock $source 'function Build-RecommendationBlock($Target) {' 'function Get-Hash' $fixedBuildBlock

$fixedVerifier = @'
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

  $pipeProducts=@($Target.proposed_products | Where-Object { [string]$_.family -eq 'pipe' })
  $sizeFa=Convert-ToPersianDigits ([string]$Target.size_mm)
  if ([int]$Target.same_size_pipe_count -gt 0) {
    if ($pipeProducts.Count -lt 1) { return [pscustomobject]@{ok=$false;reason='same_size_pipe_link_missing'} }
    if ($block -notmatch 'لوله\s*پلی.?اتیلن\s*هم.?سایز') { return [pscustomobject]@{ok=$false;reason='human_pipe_copy_missing'} }
  } else {
    if ($pipeProducts.Count -ne 0) { return [pscustomobject]@{ok=$false;reason='unexpected_pipe_link_in_fallback'} }
    if ($block.IndexOf("لوله اصلی نیز باید $sizeFa میلی",[StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return [pscustomobject]@{ok=$false;reason='fallback_pipe_size_copy_missing'}
    }
  }
  return [pscustomobject]@{ok=$true;reason='ok'}
}

'@
$source = Replace-FunctionBlock $source 'function Test-RecommendationReadback([string]$Html,$Target) {' '$targetCategories=' $fixedVerifier

$missingPipeGuard = @'
if ($mode -eq 'apply_description' -and $missingPipe.Count -gt 0) { Fail "Refusing apply: no same-size published PE pipe for IDs $((@($missingPipe.id)-join ','))" }
'@
if (-not $source.Contains($missingPipeGuard.TrimEnd("`r","`n"))) { throw 'Could not locate missing-pipe apply guard.' }
$source = $source.Replace($missingPipeGuard.TrimEnd("`r","`n"),'# Missing same-size pipe targets use an honest human-written fallback block without a fabricated pipe link.')

$tempScript = Join-Path $env:RUNNER_TEMP 'Invoke-K20EndCapRecommendationsV4.runtime.ps1'
Set-Content -LiteralPath $tempScript -Value $source -Encoding utf8
& $tempScript -RequestPath $RequestPath -OutputPath $OutputPath
