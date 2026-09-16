param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'

$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 20
$id=[int]$req.id
$phrase=[string]$req.phrase
if($id -ne 13){throw 'This guarded patch is hard-limited to page ID 13.'}
$expectedPhrase='شرایط مرجوعی، مغایرت کالا و پیگیری بار در کشاورز بیست'
if($phrase -ne $expectedPhrase){throw 'Unexpected target phrase.'}

$base=$env:WP_BASE_URL.TrimEnd('/')
$user=$env:WP_USERNAME
$pass=$env:WP_APP_PASSWORD
if([string]::IsNullOrWhiteSpace($base)-or[string]::IsNullOrWhiteSpace($user)-or[string]::IsNullOrWhiteSpace($pass)){throw 'Required WordPress secrets are missing.'}
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers=@{Authorization="Basic $auth";Accept='application/json'}

function Hash([string]$t){$s=[Security.Cryptography.SHA256]::Create();try{return([BitConverter]::ToString($s.ComputeHash([Text.Encoding]::UTF8.GetBytes($t))).Replace('-','').ToLowerInvariant())}finally{$s.Dispose()}}
function CountLiteral([string]$t,[string]$n){if([string]::IsNullOrEmpty($n)){return 0};$c=0;$o=0;while(($i=$t.IndexOf($n,$o,[StringComparison]::Ordinal))-ge0){$c++;$o=$i+$n.Length};return $c}

$page=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}?context=edit" -Headers $headers -Method GET -TimeoutSec 180
$meta=$page.meta
if(-not $meta -or -not $meta.PSObject.Properties['_elementor_data']){throw '_elementor_data is not exposed for this page.'}
$before=[string]$meta._elementor_data
if([string]::IsNullOrWhiteSpace($before)){throw '_elementor_data is empty.'}
$beforeHash=Hash $before
$root=$before|ConvertFrom-Json -Depth 100
if($root.Count -lt 1){throw 'Unexpected Elementor root.'}

$target=$null
try{$target=$root[0].elements[0].elements[0].settings.html}catch{throw 'Expected Elementor widget path was not found.'}
if($null -eq $target){throw 'Expected Elementor HTML widget is empty.'}
$html=[string]$target
$oldHeading="<h1>$phrase</h1>"
$newHeading="<h2>$phrase</h2>"
$oldHeadingCount=CountLiteral $html $oldHeading
$newHeadingCount=CountLiteral $html $newHeading
$oldSelectorCount=CountLiteral $html '.k20-hero h1'
$newSelectorCount=CountLiteral $html '.k20-hero h2'
if($oldHeadingCount -ne 1){throw "Guard failed: expected exactly 1 old heading, found $oldHeadingCount."}
if($newHeadingCount -ne 0){throw "Guard failed: new heading already present $newHeadingCount time(s)."}
if($oldSelectorCount -lt 1){throw 'Guard failed: no .k20-hero h1 selector found.'}
if($newSelectorCount -ne 0){throw "Guard failed: .k20-hero h2 already present $newSelectorCount time(s)."}

$newHtml=$html.Replace('.k20-hero h1','.k20-hero h2').Replace($oldHeading,$newHeading)
if((CountLiteral $newHtml $oldHeading)-ne 0){throw 'Post-patch guard failed: old heading remains in target widget.'}
if((CountLiteral $newHtml $newHeading)-ne 1){throw 'Post-patch guard failed: new heading count is not 1.'}
if((CountLiteral $newHtml '.k20-hero h1')-ne 0){throw 'Post-patch guard failed: old CSS selector remains in target widget.'}
$root[0].elements[0].elements[0].settings.html=$newHtml
$after=$root|ConvertTo-Json -Depth 100 -Compress
$afterHash=Hash $after
if($beforeHash -eq $afterHash){throw 'Patch produced no Elementor data change.'}

$body=@{meta=@{_elementor_data=$after}}|ConvertTo-Json -Depth 100 -Compress
$write=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}" -Headers $headers -Method POST -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 180
$check=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}?context=edit" -Headers $headers -Method GET -TimeoutSec 180
$stored=[string]$check.meta._elementor_data
$storedHash=Hash $stored
if($storedHash -ne $afterHash){throw "Readback hash mismatch. expected=$afterHash actual=$storedHash"}
$checkRoot=$stored|ConvertFrom-Json -Depth 100
$checkHtml=[string]$checkRoot[0].elements[0].elements[0].settings.html
$readOldHeading=CountLiteral $checkHtml $oldHeading
$readNewHeading=CountLiteral $checkHtml $newHeading
$readOldSelector=CountLiteral $checkHtml '.k20-hero h1'
$readNewSelector=CountLiteral $checkHtml '.k20-hero h2'
if($readOldHeading-ne0-or$readNewHeading-ne1-or$readOldSelector-ne0-or$readNewSelector-lt1){throw 'Elementor readback content guard failed.'}

Start-Sleep -Seconds 2
$front=Invoke-WebRequest -Uri "$base/refund_returns/?k20verify=$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())" -Headers @{'Cache-Control'='no-cache';Pragma='no-cache'} -TimeoutSec 180 -MaximumRedirection 5
$frontHtml=[string]$front.Content
$frontOld=[regex]::Matches($frontHtml,'(?is)<h1\b[^>]*>\s*'+[regex]::Escape($phrase)+'\s*</h1>').Count
$frontNew=[regex]::Matches($frontHtml,'(?is)<h2\b[^>]*>\s*'+[regex]::Escape($phrase)+'\s*</h2>').Count
$frontH1=[regex]::Matches($frontHtml,'(?is)<h1\b[^>]*>').Count
if($frontOld-ne0-or$frontNew-ne1){throw "Live verification failed: target_h1=$frontOld target_h2=$frontNew total_h1=$frontH1"}

$result=[ordered]@{
  ok=$true;action='refund.elementor_heading_patch';page_id=13;slug=[string]$check.slug;
  before=[ordered]@{elementor_sha256=$beforeHash;target_h1=$oldHeadingCount;target_h2=$newHeadingCount;css_h1=$oldSelectorCount;css_h2=$newSelectorCount};
  after=[ordered]@{elementor_sha256=$afterHash;target_h1=$readOldHeading;target_h2=$readNewHeading;css_h1=$readOldSelector;css_h2=$readNewSelector;modified_gmt=[string]$check.modified_gmt};
  live=[ordered]@{http_status=[int]$front.StatusCode;total_h1=$frontH1;target_h1=$frontOld;target_h2=$frontNew};
  executed_at_utc=[DateTime]::UtcNow.ToString('o')
}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath)|Out-Null
$result|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "REFUND_ELEMENTOR_PATCH_OK id=13 live_h1=$frontH1 target_h2=$frontNew"
