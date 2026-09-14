param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'

$v1 = Join-Path $PSScriptRoot 'Invoke-K20DripIrrigationContentV1.ps1'
if (-not (Test-Path -LiteralPath $v1)) { throw "V1 script not found: $v1" }
$src = Get-Content -Raw -LiteralPath $v1

$oldSame = '$same = (([string]$before.description -ceq [string]$desired.long) -and ([string]$before.short_description -ceq [string]$desired.short))'
$newSame = @'
    $beforeDescText = [regex]::Replace([System.Net.WebUtility]::HtmlDecode([regex]::Replace([string]$before.description,'<[^>]+>',' ')),'\s+',' ').Trim()
    $desiredDescText = [regex]::Replace([System.Net.WebUtility]::HtmlDecode([regex]::Replace([string]$desired.long,'<[^>]+>',' ')),'\s+',' ').Trim()
    $beforeShortText = [regex]::Replace([System.Net.WebUtility]::HtmlDecode([regex]::Replace([string]$before.short_description,'<[^>]+>',' ')),'\s+',' ').Trim()
    $desiredShortText = [regex]::Replace([System.Net.WebUtility]::HtmlDecode([regex]::Replace([string]$desired.short,'<[^>]+>',' ')),'\s+',' ').Trim()
    $same = (($beforeDescText -ceq $desiredDescText) -and ($beforeShortText -ceq $desiredShortText) -and ([string]$before.description).Contains("<!-- $marker -->"))
'@

$oldSemantic = '$semantic = (([string]$after.description -ceq [string]$desired.long) -and ([string]$after.short_description -ceq [string]$desired.short) -and ([string]$after.description).Contains("<!-- $marker -->"))'
$newSemantic = @'
    $afterDescText = [regex]::Replace([System.Net.WebUtility]::HtmlDecode([regex]::Replace([string]$after.description,'<[^>]+>',' ')),'\s+',' ').Trim()
    $afterShortText = [regex]::Replace([System.Net.WebUtility]::HtmlDecode([regex]::Replace([string]$after.short_description,'<[^>]+>',' ')),'\s+',' ').Trim()
    $semantic = (($afterDescText -ceq $desiredDescText) -and ($afterShortText -ceq $desiredShortText) -and ([string]$after.description).Contains("<!-- $marker -->"))
'@

if (-not $src.Contains($oldSame)) { throw 'V1 same-content verifier signature not found.' }
if (-not $src.Contains($oldSemantic)) { throw 'V1 semantic verifier signature not found.' }
$src = $src.Replace($oldSame,$newSame).Replace($oldSemantic,$newSemantic)

$temp = Join-Path $env:RUNNER_TEMP 'Invoke-K20DripIrrigationContentV2.runtime.ps1'
Set-Content -LiteralPath $temp -Value $src -Encoding utf8
& $temp -RequestPath $RequestPath -OutputPath $OutputPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
