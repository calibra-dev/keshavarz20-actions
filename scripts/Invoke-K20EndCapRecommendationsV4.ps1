param(
  [Parameter(Mandatory = $true)][string]$RequestPath,
  [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$sourcePath = Join-Path $PSScriptRoot 'Invoke-K20EndCapRecommendationsV3.ps1'
if (-not (Test-Path -LiteralPath $sourcePath)) { throw "Source script missing: $sourcePath" }

$source = Get-Content -Raw -LiteralPath $sourcePath
$start = $source.IndexOf('function Get-AllProducts() {',[StringComparison]::Ordinal)
$end = $source.IndexOf('function Normalize-Digits',[StringComparison]::Ordinal)
if ($start -lt 0 -or $end -le $start) { throw 'Could not locate Get-AllProducts function boundaries.' }

$fixedFunction = @'
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

$patched = $source.Substring(0,$start) + $fixedFunction + $source.Substring($end)
$tempScript = Join-Path $env:RUNNER_TEMP 'Invoke-K20EndCapRecommendationsV4.runtime.ps1'
Set-Content -LiteralPath $tempScript -Value $patched -Encoding utf8
& $tempScript -RequestPath $RequestPath -OutputPath $OutputPath
