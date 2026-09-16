param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 20
$id=[int]$req.id;$rev=[int]$req.revision_id;$expected=[string]$req.expected_elementor_sha256
if($id-ne13-or$rev-ne144349-or$expected-ne'5045936e3ba36035b68ec5a12ac001aad32abfcc51876edb22fdbff7dd8f9396'){throw 'Recovery request does not match the hard-coded verified source.'}
$base=$env:WP_BASE_URL.TrimEnd('/');$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"));$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Hash([string]$t){$s=[Security.Cryptography.SHA256]::Create();try{return([BitConverter]::ToString($s.ComputeHash([Text.Encoding]::UTF8.GetBytes($t))).Replace('-','').ToLowerInvariant())}finally{$s.Dispose()}}
$revision=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}/revisions/${rev}?context=edit" -Headers $headers -Method GET -TimeoutSec 180
$raw=[string]$revision.meta._elementor_data
if([string]::IsNullOrWhiteSpace($raw)){throw 'Verified revision has no _elementor_data.'}
$sourceHash=Hash $raw
if($sourceHash-ne$expected){throw "Revision hash guard failed expected=$expected actual=$sourceHash"}
$body=@{meta=@{_elementor_data=$raw}}|ConvertTo-Json -Depth 10 -Compress
$null=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}" -Headers $headers -Method POST -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 180
$check=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}?context=edit" -Headers $headers -Method GET -TimeoutSec 180
$stored=[string]$check.meta._elementor_data;$storedHash=Hash $stored
if($storedHash-ne$expected){throw "Restore readback hash mismatch expected=$expected actual=$storedHash"}
$null=Invoke-RestMethod -Uri "$base/wp-json/elementor/v1/cache" -Headers $headers -Method DELETE -TimeoutSec 180
Start-Sleep -Seconds 3
$front=Invoke-WebRequest -Uri "$base/refund_returns/?k20recovery=$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())" -Headers @{'Cache-Control'='no-cache';Pragma='no-cache'} -TimeoutSec 180 -MaximumRedirection 5
$html=[string]$front.Content;$h1=[regex]::Matches($html,'(?is)<h1\b[^>]*>').Count
if([int]$front.StatusCode-ne200){throw "Recovery live status is $($front.StatusCode)"}
$result=[ordered]@{ok=$true;action='refund.elementor.restore';page_id=13;revision_id=$rev;source_elementor_sha256=$sourceHash;readback_elementor_sha256=$storedHash;cache_cleared=$true;live_http_status=[int]$front.StatusCode;live_h1_count=$h1;executed_at_utc=[DateTime]::UtcNow.ToString('o')}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath)|Out-Null
$result|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "REFUND_ELEMENTOR_RESTORE_OK revision=$rev live_status=$($front.StatusCode) h1=$h1"
