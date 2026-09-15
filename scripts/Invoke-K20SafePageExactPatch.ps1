param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
if(-not(Test-Path -LiteralPath $RequestPath)){throw "Request file not found: $RequestPath"}
$req=Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
$id=[int]$req.id
if($id-lt1){throw 'Positive page id required.'}
$expectedSlug=[string]$req.expected_slug
$replacements=@($req.replacements)
if($replacements.Count-lt1-or$replacements.Count-gt10){throw 'replacements must contain 1..10 exact replacements.'}
$base=$env:WP_BASE_URL.TrimEnd('/');$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"));$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Get-Page(){Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}?context=edit" -Method GET -Headers $headers -TimeoutSec 180}
function Count-Exact([string]$Text,[string]$Needle){if([string]::IsNullOrEmpty($Needle)){throw 'Replacement old value cannot be empty.'};$count=0;$pos=0;while(($i=$Text.IndexOf($Needle,$pos,[StringComparison]::Ordinal))-ge0){$count++;$pos=$i+$Needle.Length};return $count}
function Sha256([string]$Text){$sha=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))).Replace('-','').ToLowerInvariant())}finally{$sha.Dispose()}}
$page=Get-Page
if($expectedSlug-and[string]$page.slug-ne$expectedSlug){throw "Slug guard failed. Expected '$expectedSlug', got '$($page.slug)'."}
if([string]$page.status-ne'publish'){throw "Status guard failed. Expected publish, got '$($page.status)'."}
$content=[string]$page.content.raw
$beforeHash=Sha256 $content;$beforeLength=$content.Length;$checks=@()
foreach($r in $replacements){$old=[string]$r.old;$new=[string]$r.new;$expected=[int]$r.expected_count;if($expected-lt1){$expected=1};$actual=Count-Exact $content $old;$checks+=,[pscustomobject][ordered]@{old=$old;new=$new;expected_count=$expected;actual_count=$actual};if($actual-ne$expected){throw "Exact replacement guard failed for '$old': expected $expected occurrence(s), found $actual."};$content=$content.Replace($old,$new)}
$afterHash=Sha256 $content;$afterLength=$content.Length
if($beforeHash-eq$afterHash){throw 'Patch produced no content change.'}
$tmpReq=Join-Path $env:RUNNER_TEMP 'k20-safe-page-update.json';$tmpOut=Join-Path $env:RUNNER_TEMP 'k20-safe-page-update.result.json'
[ordered]@{action='page.update';id=$id;payload=[ordered]@{content=$content}}|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $tmpReq -Encoding utf8
& ./scripts/Invoke-K20SiteGateway.ps1 -RequestPath $tmpReq -OutputPath $tmpOut
if(-not(Test-Path $tmpOut)){throw 'Guarded gateway did not produce a result.'}
$gatewayResult=Get-Content -Raw -LiteralPath $tmpOut|ConvertFrom-Json -Depth 100
if(-not$gatewayResult.ok){throw 'Guarded gateway result was not ok.'}
$verify=Get-Page;$verifyContent=[string]$verify.content.raw;$verifyHash=Sha256 $verifyContent
if($verifyHash-ne$afterHash){throw "Readback hash mismatch. Expected $afterHash, got $verifyHash."}
$postChecks=@();foreach($r in $replacements){$old=[string]$r.old;$new=[string]$r.new;$oldCount=Count-Exact $verifyContent $old;$newCount=Count-Exact $verifyContent $new;$postChecks+=,[pscustomobject][ordered]@{old=$old;old_count=$oldCount;new=$new;new_count=$newCount};if($oldCount-ne0){throw "Readback still contains old value: $old"}}
$record=[ordered]@{ok=$true;mode='guarded-exact-page-patch';executed_at_utc=[DateTime]::UtcNow.ToString('o');page=[ordered]@{id=[int]$verify.id;slug=[string]$verify.slug;status=[string]$verify.status;link=[string]$verify.link;title=[string]$verify.title.raw;modified_gmt=[string]$verify.modified_gmt};before=[ordered]@{content_length=$beforeLength;sha256=$beforeHash};after=[ordered]@{content_length=$afterLength;sha256=$afterHash};preflight_checks=$checks;readback_checks=$postChecks;gateway=[ordered]@{ok=[bool]$gatewayResult.ok;action=[string]$gatewayResult.action;method=[string]$gatewayResult.method;target=[string]$gatewayResult.target}}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Force -Path $dir|Out-Null};$record|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "SAFE_PAGE_PATCH_OK id=$id before=$beforeHash after=$afterHash"
